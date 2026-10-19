#!/usr/bin/env python3
"""Compare GPU navigation safety, reach components and all paper targets."""
from __future__ import annotations

import argparse
from dataclasses import replace
import logging
from pathlib import Path
import sys

import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'benchmark'))
from airground_benchmark.ground_truth import GroundTruthError, load_target_annotations, load_traversability_metadata
from airground_benchmark.navigation_map_validation import compare_navigation_maps
from airground_benchmark.roi_analysis import sha256, write_json
from airground_benchmark.traversability import FootprintSweepConfig, raycast_terrain_grid_from_arrays, sweep_ugv_footprint_over_terrain


def main(argv: list[str] | None=None) -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-dir',type=Path,required=True)
    parser.add_argument('--reference-run',type=Path)
    parser.add_argument('--same-live-scene',action='store_true')
    parser.add_argument('--targets',type=Path,required=True)
    args=parser.parse_args(argv)
    if bool(args.reference_run)==args.same_live_scene:
        parser.error('choose --reference-run or --same-live-scene')
    metadata=load_traversability_metadata(args.run_dir/'raycast_metadata.json')
    gpu_npz=args.run_dir/'raycast_seed.npz'
    if metadata.npz_sha256!=sha256(gpu_npz): raise GroundTruthError('candidate checksum mismatch')
    if args.same_live_scene:
        reference=args.run_dir/'physx_reference.npz'
        ref_metadata=load_traversability_metadata(args.run_dir/'physx_reference.metadata.json')
    else:
        reference=args.reference_run/'raycast_seed.npz'
        ref_metadata=load_traversability_metadata(args.reference_run/'raycast_metadata.json')
    if (metadata.scene_id,metadata.shape,metadata.resolution_m,metadata.origin)!=(ref_metadata.scene_id,ref_metadata.shape,ref_metadata.resolution_m,ref_metadata.origin):
        raise GroundTruthError('reference and candidate grids differ')
    if ref_metadata.npz_sha256!=sha256(reference): raise GroundTruthError('reference checksum mismatch')
    config=FootprintSweepConfig(max_step_height_m=.05)
    masks=[]; terrains=[]
    for path in (reference,gpu_npz):
        with np.load(path,allow_pickle=False) as data:
            terrain=raycast_terrain_grid_from_arrays(metadata,{k:data[k] for k in data.files})
        masks.append(sweep_ugv_footprint_over_terrain(terrain,config).traversable_mask)
        terrains.append(terrain)
    # Independent physical attribution for edge differences. Only replace the
    # diagnostic slope derivative with the live PhysX hit normal; retain the
    # same obstacle, support, step, headroom and complete footprint checks.
    reference_terrain=terrains[0]
    normal=reference_terrain.normal
    normal_length=np.linalg.norm(normal,axis=2)
    surface_slope=np.arccos(np.clip(normal[:,:,2]/np.maximum(normal_length,1e-12),-1,1)).astype(np.float32)
    physical_terrain=replace(reference_terrain,slope_rad=surface_slope)
    physical_footprint=sweep_ugv_footprint_over_terrain(physical_terrain,config).traversable_mask
    report=compare_navigation_maps(*masks,metadata,load_target_annotations(args.targets),reference_physical_footprint=physical_footprint)
    report['inputs_sha256']={'candidate_npz':sha256(gpu_npz),'reference_npz':sha256(reference),'targets':sha256(args.targets)}
    report['footprint_config']=config.__dict__
    report['boundary_sampling_evidence']='same reference PhysX terrain: full footprint obstacle/support/step/headroom and actual hit-normal slope; at most one grid cell from reference free region; reach partition unchanged'
    # Keep actual terrain evidence around false-free footprint cells, so a
    # failed gate can distinguish geometry, headroom and derivative limits.
    diagnostics=[]
    for row,col in report['safety']['first_candidate_free_reference_blocked_cell_indices']:
        window=(slice(max(0,row-7),min(metadata.shape[0],row+8)),slice(max(0,col-7),min(metadata.shape[1],col+8)))
        samples={}
        for name,terrain in zip(('reference','candidate'),terrains):
            samples[name]={key:np.asarray(getattr(terrain,key)[window]).tolist() for key in ('height','normal','obstacle_mask','slope_rad','step_height_m','overhead_clearance_m')}
        diagnostics.append({'cell_indices':[row,col],'world_xy_m':[metadata.origin.x_m+(col+.5)*metadata.resolution_m,metadata.origin.y_m+(row+.5)*metadata.resolution_m],
                            'window_start_indices':[window[0].start,window[1].start],'terrain':samples})
    report['different_free_cell_terrain_diagnostics']=diagnostics
    write_json(args.run_dir/'gpu_navigation_comparison.json',report)
    logging.info('Navigation comparison: %s; unsafe cells=%s; accepted boundary sampling cells=%s; changed targets=%s',report['status'],report['safety']['unsafe_navigation_cells'],report['safety']['accepted_boundary_sampling_cells'],report['changed_target_ids'])
    return 0


if __name__=='__main__':
    logging.basicConfig(level=logging.INFO)
    raise SystemExit(main())
