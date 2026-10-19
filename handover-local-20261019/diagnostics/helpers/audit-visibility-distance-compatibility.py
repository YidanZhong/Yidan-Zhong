"""Static necessary-condition audit; no visibility or reachability conclusions."""
from pathlib import Path
import hashlib,json,sys
root=Path('/mnt/d/xprogram/RAVEN-AirGround-github');sys.path.insert(0,str(root/'benchmark'))
from airground_benchmark.scenes import is_paper_class
rows=[]
for path in sorted((root/'runs/scene_gt_adaptation_20261017').glob('*/targets.unreviewed.json')):
    manifest=json.loads(path.read_text());scene=manifest['scene_id'];affected=[]
    for target in manifest['instances']:
        if not is_paper_class(scene,target['semantic_class']):continue
        obb=target['obb']
        if any(abs(v)>1e-10 for v in obb['orientation_rpy_rad'][:2]):continue
        lower_bound=min(obb['size_xyz_m'][:2])/2+1.5
        if lower_bound>8.+1e-8:
            affected.append({'instance_id':target['instance_id'],'semantic_class':target['semantic_class'],
                             'size_xy_m':obb['size_xyz_m'][:2],'minimum_center_distance_for_surface_ge_1p5_m':lower_bound,
                             'current_center_visibility_max_m':8.,'formal_exclusion':False})
    rows.append({'scene':scene,'targets_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'affected_count':len(affected),'affected':affected})
result={'scope':'necessary-condition incompatibility under current unreviewed OBBs, not an exclusion or measured visibility result',
        'formal_accepted':False,'protocol_parameters_changed':False,'target_flags_changed':False,
        'reach_metric':'planar distance to OBB surface in [1.5,8]m',
        'current_visibility_code_metric':'hypot(target_center_xy - pose_xy) in [1.5,8]m',
        'derivation':'For an outside point with OBB surface distance >=1.5m, distance to rectangle center >= min(size_x,size_y)/2+1.5m. If this exceeds 8m, both constraints cannot hold.',
        'handover_note':'Page 1 explicitly defines OBB surface distance for reach; visibility states distance 1.5-8m without naming its reference. Page 4 forbids the old center-based formal arrival sampler, not explicitly the visibility checker.',
        'requires':'Confirm teacher visibility distance definition or provide the validated checker version; preserve all existing thresholds meanwhile.',
        'source_sha256':hashlib.sha256((root/'benchmark/airground_benchmark/ground_truth.py').read_bytes()).hexdigest(),
        'handover_sha256':hashlib.sha256((root.parent/'scene-gt-adaptation-handover.pdf').read_bytes()).hexdigest(),'rows':rows}
out=root/'runs/additional_scene_preflight_20261019/visibility-distance-compatibility.json';assert not out.exists();out.write_text(json.dumps(result,indent=2))
print(json.dumps([{'scene':r['scene'],'affected_count':r['affected_count']} for r in rows],indent=2))
