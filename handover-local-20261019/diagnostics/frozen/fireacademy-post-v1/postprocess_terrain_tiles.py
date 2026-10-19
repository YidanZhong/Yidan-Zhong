"""Private diagnostic postprocessing of checksum-pinned real PhysX tiles."""
from __future__ import annotations

import argparse
from dataclasses import asdict
import gc
import json
import logging
from pathlib import Path
import shutil
import sys
import time
import types
from typing import Any

import numpy as np
from resumable_terrain_store import FIELDS, TileStore, atomic_json, dataset_lock, digest


def stitch(store: TileStore, output: Path) -> tuple[dict[str, np.ndarray], dict[str, Any]]:
    """Require complete committed coverage and verify every written core cell."""
    if len(store.completed) != len(store.tiles):
        raise ValueError('Incomplete dataset cannot produce a full map')
    shape = tuple(store.contract['grid']['shape'])
    output.mkdir(exist_ok=False)
    arrays = {key: np.lib.format.open_memmap(output/f'{key}.npy', mode='w+', dtype=dtype,
              shape=(*shape, 3) if key == 'normal' else shape) for key, dtype in FIELDS.items()}
    coverage = np.zeros(shape, dtype=np.uint8)
    for tile in store.tiles:
        r0,r1,c0,c1 = tile['core']
        core = (slice(r0,r1),slice(c0,c1))
        with np.load(store.root/'tiles'/f'{tile["id"]}.npz', allow_pickle=False) as data:
            for key in FIELDS:
                arrays[key][core] = data[key]
        coverage[core] += 1
    if not np.all(coverage == 1):
        raise ValueError('Missing or overlapping core cells')
    del coverage
    for value in arrays.values():
        value.flush()
    # Reopen disk files; compare independently of the in-memory write view.
    arrays = {key:np.load(output/f'{key}.npy', mmap_mode='r') for key in FIELDS}
    for tile in store.tiles:
        r0,r1,c0,c1=tile['core']
        with np.load(store.root/'tiles'/f'{tile["id"]}.npz', allow_pickle=False) as data:
            for key in FIELDS:
                if not np.array_equal(arrays[key][r0:r1,c0:c1],data[key]):
                    raise ValueError(f'Disk stitch differs: {tile["id"]}/{key}')
    return arrays, {'tiles':len(store.tiles),'cells':int(np.prod(shape)),
                    'coverage_exactly_once':True,'all_8_fields_disk_readback_equal':True}


def run(args: argparse.Namespace) -> dict[str, Any]:
    started=time.monotonic()
    output=args.output
    output.mkdir(parents=True,exist_ok=False)
    def stage(name: str) -> None:
        logging.info('POSTPROCESS_STAGE: %s',name)
        atomic_json(output/'progress.json',{'stage':name,'elapsed_s':time.monotonic()-started})
    stage('validate_sources_and_tiles')
    contract=json.loads((args.dataset/'contract.json').read_text(encoding='utf-8'))
    for relative, expected in contract['source_sha256'].items():
        if relative.startswith('benchmark/'):
            if digest(args.benchmark_package/relative[10:]) != expected:
                raise ValueError(f'Benchmark source changed: {relative}')
    if digest(Path(__file__).with_name('resumable_terrain_store.py')) != contract['generator_sha256']['resumable_terrain_store.py']:
        raise ValueError('Tile reader differs from pinned version')
    if shutil.disk_usage(output).free < 8*1024**3:
        raise RuntimeError('Insufficient disk reserve')
    package=types.ModuleType('airground_benchmark')
    package.__path__=[str(args.benchmark_package)]
    sys.modules.setdefault('airground_benchmark',package)
    from airground_benchmark.config.schema import SCHEMA_VERSION
    from airground_benchmark.ground_truth import (GridOrigin, TraversabilityMetadata, TraversabilityGrid,
        load_target_annotations, validate_traversability_npz)
    from airground_benchmark.traversability import (RaycastTerrainGrid, FootprintSweepConfig,
        sweep_ugv_footprint_over_terrain, build_reach_region, write_nav2_occupancy_grid,
        _slope_from_height, _max_neighbor_height_delta)
    from airground_benchmark.roi_analysis import component_report, annotation_roi
    targets=load_target_annotations(args.targets)
    if targets.scene_id!=contract['scene_id'] or digest(args.targets)!=contract['targets_sha256']:
        raise ValueError('Target scene/hash differs from the sampled contract')
    if any(t.verified for t in targets.instances):raise ValueError('Expected explicit unreviewed targets')
    with dataset_lock(args.dataset):
        store=TileStore(args.dataset,contract)
        stage('stitch_and_readback')
        arrays,stitch_evidence=stitch(store,output/'terrain')
        contract_hash=store.contract_hash
    grid=contract['grid'];shape=tuple(grid['shape']);res=grid['resolution_m']
    metadata=TraversabilityMetadata(schema_version=SCHEMA_VERSION,scene_id=contract['scene_id'],frame='map',
        origin=GridOrigin(x_m=grid['origin_xy_m'][0],y_m=grid['origin_xy_m'][1],z_m=0),
        resolution_m=res,shape=shape,generator='private-physx-full-map-diagnostic',generator_version='v1')
    atomic_json(output/'terrain-metadata.json',metadata.model_dump(mode='json'))
    stage('global_derivative_and_seam_check')
    seam=np.zeros(shape,dtype=bool)
    for r in range(grid['tile_cells'],shape[0],grid['tile_cells']):seam[r-1:r+1,:]=True
    for c in range(grid['tile_cells'],shape[1],grid['tile_cells']):seam[:,c-1:c+1]=True
    derivatives={}
    for name,compute in [('slope_rad',lambda:_slope_from_height(arrays['height'],res)),
                         ('step_height_m',lambda:_max_neighbor_height_delta(arrays['height']))]:
        expected=compute().astype(np.float32)
        delta=np.abs(expected-arrays[name]);bad=delta>1e-5
        derivatives[name]={'max_abs_error':float(delta.max()),'outside_tolerance':int(bad.sum()),
                           'seam_outside_tolerance':int(bad[seam].sum()),'tolerance':1e-5}
        if bad.any():raise ValueError(f'Global derivative mismatch: {name}')
        del expected,delta,bad
    del seam
    terrain=RaycastTerrainGrid(metadata=metadata,**arrays,obstacle_band_m=(.05,1.))
    config=FootprintSweepConfig(max_step_height_m=.05)
    stage('global_footprint_sweep')
    sweep=sweep_ugv_footprint_over_terrain(terrain,config)
    stage('global_reach_clearance_and_components')
    reach=build_reach_region(sweep.traversable_mask,resolution_m=res,clearance_margin_m=.1075,
                             footprint_width_m=.430,connectivity=8)
    if np.any(reach.reach_mask.astype(bool)&~sweep.traversable_mask):
        raise ValueError('Reach escaped footprint mask')
    stage('independent_real_window_comparison')
    references=[]
    for index in (0,1):
        ref_path=args.reference_dir/f'window-{index}-reference.npz'
        ref_meta=TraversabilityMetadata.model_validate_json((args.reference_dir/f'window-{index}-metadata.json').read_text())
        if ref_meta.scene_id!=metadata.scene_id or ref_meta.resolution_m!=res:
            raise ValueError('Reference window scene/resolution mismatch')
        row=round((ref_meta.origin.y_m-metadata.origin.y_m)/res)
        col=round((ref_meta.origin.x_m-metadata.origin.x_m)/res)
        rows,cols=ref_meta.shape
        with np.load(ref_path,allow_pickle=False) as data:
            ref_arrays={key:data[key].astype(FIELDS[key]) for key in FIELDS}
        comparisons={}
        for key,left in ref_arrays.items():
            right=arrays[key][row:row+rows,col:col+cols]
            margin=1 if key in ('slope_rad','step_height_m') else 0
            inner=(slice(margin,-margin or None),slice(margin,-margin or None))
            delta=np.abs(left[inner].astype(float)-right[inner].astype(float))
            comparisons[key]={'outside_tolerance':int((delta>1e-5).sum()),'max_abs_error':float(delta.max()),'excluded_border_cells':margin}
        ref_terrain=RaycastTerrainGrid(metadata=ref_meta,**ref_arrays,obstacle_band_m=(.05,1.))
        ref_sweep=sweep_ugv_footprint_over_terrain(ref_terrain,config)
        ref_reach=build_reach_region(ref_sweep.traversable_mask,resolution_m=res,clearance_margin_m=.1075,connectivity=8)
        # Local image boundaries are blocked by the footprint sweep: omit a 12-cell boundary band.
        for key,left,right in [('footprint',ref_sweep.traversable_mask,sweep.traversable_mask),
                               ('reach',ref_reach.reach_mask,reach.reach_mask)]:
            actual=right[row:row+rows,col:col+cols]
            comparisons[key]={'outside_tolerance':int(np.count_nonzero(left[12:-12,12:-12]!=actual[12:-12,12:-12])),
                              'excluded_border_cells':12}
        references.append({'reference_npz_sha256':digest(ref_path),'window':index,'comparisons':comparisons})
    reference_pass=all(item['outside_tolerance']==0 for ref in references for item in ref['comparisons'].values())
    stage('target_geometric_coverage')
    roi=annotation_roi(targets,resolution_m=res)
    if roi['shape']!=list(shape) or not np.allclose(roi['origin_xy_m'],grid['origin_xy_m'],atol=1e-9,rtol=0):
        raise ValueError('Annotation ROI differs from sampled grid')
    # component_report retains the 31-instance gate for Retro only; new scenes
    # use their own Table A.3 classes and the hash-pinned annotation manifest.
    coverage=component_report(targets,metadata,sweep.traversable_mask,reach.reach_component)
    coverage['purpose']='unreviewed_full_fine_geometric_candidate_only'
    coverage['roi']=roi
    coverage['resolution_note']='0.05 m full ROI; 0.1075 m clearance on footprint mask, 8-connected reach labels'
    for target in coverage['targets']:
        target['geometric_candidate_in_selected_component']=target.pop('eligible_in_selected_component')
        target['eligible_in_selected_component']=False
        target['requires_binding_review']=True
        target['formal_gt_approved']=False
    selected=coverage['selected_component']
    atomic_json(output/'component-report.unreviewed.json',coverage)
    stage('export_diagnostic_maps')
    exports={}
    for name,mask,component in [('footprint',sweep.traversable_mask,sweep.component),
                               ('reach',reach.reach_mask,reach.reach_component)]:
        destination=output/name;destination.mkdir()
        data={'height':arrays['height'],'normal':arrays['normal'],'mask':mask.astype(np.uint8),
              'component':component.astype(np.int32),'cost':sweep.cost}
        npz=destination/f'{name}.npz'
        np.savez_compressed(npz,**data)
        export_meta=metadata.model_copy(update={'npz_sha256':digest(npz)})
        # JSON is valid YAML and keeps all canonical metadata fields.
        atomic_json(destination/f'{name}.metadata.yaml',export_meta.model_dump(mode='json'))
        validation=validate_traversability_npz(npz,export_meta)
        occupancy=write_nav2_occupancy_grid(TraversabilityGrid(metadata=export_meta,height=arrays['height'],
                    mask=data['mask'],component=data['component'],cost=sweep.cost),destination,stem=f'{name}.unreviewed')
        exports[name]={'validation':validation,'nav2':occupancy.summary(),'npz_sha256':digest(npz)}
        del data
    # The selected candidate map is explicitly labelled unreviewed; all component IDs stay local to this map.
    selected_mask=(reach.reach_component==selected).astype(np.uint8)
    nav_selected=write_nav2_occupancy_grid(TraversabilityGrid(metadata=metadata,height=arrays['height'],mask=selected_mask,
        component=np.where(selected_mask,0,-1).astype(np.int32),cost=sweep.cost),output/'selected',stem='selected.unreviewed')
    np.savez_compressed(output/'preview.npz',height=arrays['height'][::4,::4],
        obstacle=arrays['obstacle_mask'][::4,::4],support=arrays['support_mask'][::4,::4],
        footprint=sweep.traversable_mask[::4,::4],reach=reach.reach_mask[::4,::4],
        component=reach.reach_component[::4,::4],selected=selected_mask[::4,::4])
    stage('final_manifest')
    files={str(p.relative_to(output)).replace('\\','/'): {'sha256':digest(p),'bytes':p.stat().st_size}
           for p in output.rglob('*') if p.is_file() and p.name!='progress.json'}
    selected_info=next(c for c in coverage['components'] if c['component_id']==selected)
    report={'status':'passed' if reference_pass else 'failed','scope':'private_diagnostic_full_map_not_formal_gt',
        'input_dataset':str(args.dataset),'contract_sha256':contract_hash,'scene_sha256':contract['scene_sha256'],
        'source_sha256':{'postprocess_terrain_tiles.py':digest(Path(__file__)),
                         'traversability.py':digest(args.benchmark_package/'traversability.py')},
        'targets_sha256':digest(args.targets),'stitch':stitch_evidence,'derivatives':derivatives,
        'independent_real_window_comparison':references,'reference_comparison_passed':reference_pass,
        'grid':grid,'footprint_config':asdict(config),'terrain_summary':terrain.summary(),
        'footprint_summary':sweep.summary(),'reach_summary':reach.summary(),'selected_component':selected_info,
        'exports':exports,'selected_nav2':nav_selected.summary(),'files':files,
        'elapsed_s':time.monotonic()-started,'full_diagnostic_map_generated':True,
        'formal_gt_approved':False,'formal_episode_count':0,
        'limitations':['Uses actual PhysX data but postprocessing itself does not run robot dynamics.',
          'No teacher map comparison or human target review; geometry candidates are not scoring eligible.',
          'Reach labels use existing 8-connectivity; live navigation and corner-clearance validation remain pending.',
          'Reference-window comparisons exclude local boundary influence; no full monolithic raycast reference.',
          'z=0 support plane and existing collider approximations retained from sampled scene.']}
    atomic_json(output/'report.json',report)
    stage('complete' if reference_pass else 'reference_comparison_failed')
    gc.collect()
    return report


def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('dataset','output','benchmark-package','targets','reference-dir'):
        parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists():
        parser.error('Refusing an existing output directory; previous results must remain unchanged')
    logging.basicConfig(level=logging.INFO,format='%(asctime)s %(message)s')
    try:
        report=run(args)
        return 0 if report['status']=='passed' else 1
    except Exception as error:
        logging.exception('Postprocessing failed')
        if args.output.exists():
            atomic_json(args.output/'report.json',{'status':'failed','error':str(error),'formal_gt_approved':False})
        return 1


if __name__=='__main__':
    raise SystemExit(main())
