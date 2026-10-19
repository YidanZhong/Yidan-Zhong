from pathlib import Path
import copy, hashlib, json, zipfile

root=Path(r'D:\xprogram\RAVEN-AirGround-github')
run=root/'runs/tiled_map_validation_20261018'
run.mkdir(exist_ok=True)
cache=Path(r'D:\xprogram\.raven-setup-cache')
def read(p): return json.loads(p.read_text(encoding='utf-8-sig'))
def write(p,v): p.write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
source=root/'runs/target_integration_20261018/targets.auto-bound.json'
original=read(source); corrected=copy.deepcopy(original)
proposal=read(root/'runs/paper31_review_20261018/red-car-root-proposal.json')
target=next(t for t in corrected['instances'] if t['instance_id']==proposal['instance_id'])
before=copy.deepcopy(target)
target['usd_prim_path']=proposal['source_candidate']['prim_path']
assert target['verified'] is False and target['ground_reachable']=='unknown'
write(run/'targets.binding-corrected.unreviewed.json',corrected)
changes=[t['instance_id'] for t,o in zip(corrected['instances'],original['instances']) if t!=o]
assert changes==[target['instance_id']]
write(run/'binding-change.json',{'status':'applied_to_separate_unreviewed_copy','before':before,'after':target,
    'annotation_obb_changed':False,'source_sha256':sha(source),'output_sha256':sha(run/'targets.binding-corrected.unreviewed.json'),
    'reason':proposal['reason'],'human_approval':False})
sourcefiles=['simulation/isaac-sim/utils/'+n for n in ['scene_prep.py','scene_physics_profile.py','scene_audit.py','ugv_traction_setup.py']]
hashes={'AirStack/'+p:sha(root/'AirStack'/p) for p in sourcefiles}
bench=root/'benchmark/airground_benchmark'
for p in bench.rglob('*.py'):
    hashes['benchmark/'+p.relative_to(bench).as_posix()]=sha(p)
config={'scene_sha256':read(root/'runs/paper31_review_20261018/review-input.json')['scene_sha256'],
    'corrected_target':target,'expected_bounds':proposal['source_candidate'],'source_sha256':hashes,
    'windows':[{'name':'bus_stop_0002','origin':[-34.,-22.],'rows':160,'cols':160,'resolution_m':.05,'tile_cells':64},
               {'name':'red_car_0000','origin':[87.,-34.],'rows':160,'cols':160,'resolution_m':.05,'tile_cells':64}]}
write(run/'tile-input.json',config)
job={'name':'tile-map-a01','timeout':840,'memory_gib':14,'ros2':False,'env':{},'args':[
    '--graphics-api','vulkan','--defer-stage','--cpu-threads','16','--shader-concurrency','1',
    '--disable-motion-bvh','--async-loads','--physics-only',
    '--scene',r'D:\RAVEN-4060\source\AirStack\scenes\RetroNeighborhood\RetroNeighborhood_Export.usd',
    '--tile-validation',r'D:\RAVEN-4060\setup\tile-input.json',
    '--air-stack-root',r'D:\RAVEN-4060\source\AirStack',
    '--benchmark-package',r'D:\RAVEN-4060\setup\tile-benchmark\airground_benchmark']}
write(cache/'tile-map-a01.json',job)
with zipfile.ZipFile(cache/'tile-benchmark.zip','w',zipfile.ZIP_DEFLATED) as z:
    for p in bench.rglob('*.py'):z.write(p,'airground_benchmark/'+p.relative_to(bench).as_posix())
print(json.dumps({'source_files':len(hashes),'changed_targets':changes,'windows':config['windows']},indent=2))
