"""Re-derive reach from saved actual terrain; preserve all original archives."""
from pathlib import Path
import ast,hashlib,json,sys,types
import numpy as np
root=Path('D:/xprogram/RAVEN-AirGround-github')
package=types.ModuleType('airground_benchmark');package.__path__=['D:/xprogram/.raven-setup-cache/tile-benchmark-lf-v1/airground_benchmark'];sys.modules['airground_benchmark']=package
from airground_benchmark.ground_truth import TraversabilityMetadata
from airground_benchmark.traversability import RaycastTerrainGrid,FootprintSweepConfig,sweep_ugv_footprint_over_terrain,build_reach_region
out=root/'runs/window_reach_correction_20261019';out.mkdir(exist_ok=False)
fields=('height','normal','support_mask','obstacle_mask','ceiling_height','slope_rad','step_height_m','overhead_clearance_m')
rows=[]
for scene,frames,count in [
    ('ConstructionSite',root/'runs/construction_adaptation_20261019/instancewindows-a01-evidence/logs/construction-instancewindows-a01-frames',2),
    ('FireAcademy',root/'runs/additional_scene_preflight_20261019/fireacademy-windows-a01-evidence/logs/fireacademy-windows-a01-frames',3)]:
    for i in range(count):
        masks=[];row={'scene':scene,'window':i,'source_npz_sha256':{}}
        for mode in ['reference','tiled']:
            p=frames/f'window-{i}-{mode}.npz';data=np.load(p,allow_pickle=False)
            row['source_npz_sha256'][mode]=hashlib.sha256(p.read_bytes()).hexdigest()
            meta=TraversabilityMetadata.model_validate_json((frames/f'window-{i}-metadata.json').read_text())
            terrain=RaycastTerrainGrid(metadata=meta,**{k:data[k] for k in fields},obstacle_band_m=(.05,1.))
            sweep=sweep_ugv_footprint_over_terrain(terrain,FootprintSweepConfig(max_step_height_m=.05))
            assert np.array_equal(sweep.traversable_mask,data['footprint_mask'])
            reach=build_reach_region(sweep.traversable_mask,resolution_m=.05,clearance_margin_m=.1075,footprint_width_m=.430,connectivity=8)
            assert not np.any(reach.reach_mask.astype(bool)&~sweep.traversable_mask)
            masks.append(reach.reach_component)
            if mode=='reference':
                row.update(footprint_cells=int(sweep.traversable_mask.sum()),corrected_reach_cells=int(reach.reach_mask.sum()),old_diagnostic_seed_reach_cells=int(np.count_nonzero(data['reach_component']>=0)))
                target=out/f'{scene}-window-{i}-reach.npz'
                np.savez_compressed(target,reach_mask=reach.reach_mask,reach_component=reach.reach_component)
                row['corrected_npz_sha256']=hashlib.sha256(target.read_bytes()).hexdigest()
        assert np.array_equal(*masks)
        row['whole_tiled_corrected_reach_equal']=True;rows.append(row)
source=root/'scripts/probe_tiled_terrain.py';ast.parse(source.read_text(encoding='utf-8'))
report={'scope':'CPU derivative correction from actual PhysX window samples; not new raycast or formal GT','issue':'Historical window reach_component used support minus obstacle seed, bypassing swept footprint. Terrain/footprint arrays and whole/tiled equality are unchanged.','corrected_source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'rows':rows,'original_archives_unchanged':True,'active_map_effect':'None: streaming returns before window derivatives; pinned full-map postprocessor already builds reach from swept footprint and recomputes independent windows that way. Frozen active sources not changed.','formal_accepted':False}
(out/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps(rows,indent=2))
