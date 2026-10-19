from pathlib import Path
import sys,types,json,hashlib,zipfile
root=Path(r'D:\xprogram\RAVEN-AirGround-github')
cache=Path(r'D:\xprogram\.raven-setup-cache')
sys.path.insert(0,str(cache/'target-tools'))
p=types.ModuleType('airground_benchmark');p.__path__=[str(root/'benchmark/airground_benchmark')];sys.modules[p.__name__]=p
from airground_benchmark.ground_truth import load_target_annotations,load_usd_prim_candidate_manifest,bind_target_annotations_to_usd_prims
from airground_benchmark.task_catalog import build_task_catalog,upstream_tasks
run=root/'runs/target_integration_20261018';run.mkdir(exist_ok=True)
target_path=root/'benchmark/airground_benchmark/gt/targets/retro_neighborhood.targets.json'
candidates_path=root/'runs/local_scene1_preparation_20261017/target_candidates.json'
m=load_target_annotations(target_path);c=load_usd_prim_candidate_manifest(candidates_path)
b,r=bind_target_annotations_to_usd_prims(m,c)
for name,data in [('targets.auto-bound.json',b),('binding-report.json',r),('task_catalog.blocked.json',build_task_catalog(b))]:
 (run/name).write_text(data.model_dump_json(indent=2),encoding='utf-8')
target=next(i for i in m.instances if i.instance_id=='RetroNeighborhood.bus_stop.0002').model_dump(mode='json')
path='/World/stage/Neighborhood/BP_BusStop3/Bus_Stop'
candidate=next(i for i in c.candidates if i.prim_path==path).model_dump(mode='json')
target['usd_prim_path']=path
config={'scope':'unreviewed single-instance integration diagnostic',
 'task_id':'retro-type-i-bus-stop','target':target,'candidate':candidate,
 'selection_reason':'Whole shelter Xform matching annotation bounds; alternatives include benches, floor tiles and duplicate child mesh bounds. Human review pending.',
 'same_class_instances':[i.instance_id for i in m.instances if i.semantic_class=='bus stop'],
 'source_sha256':{str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [target_path,candidates_path]},
 'spawn_xy_m':[-30,-24],'goal_xy_m':[-30,-18],
 'formal_episode':False,'human_review_performed':False}
(run/'target-input.json').write_text(json.dumps(config,indent=2),encoding='utf-8')
job=json.loads((cache/'jackal-route-a02.json').read_text())
job['name']='jackal-target-a01'
args=job['args'];begin=args.index('--nav2-goal');args=args[:begin]
args[args.index('--jackal-spawn')+2]='-24'
args+=['--nav2-goal','-30','-18','--target-confirmation',r'D:\RAVEN-4060\setup\target-input.json',
 '--benchmark-package',r'D:\RAVEN-4060\setup\target-benchmark\airground_benchmark']
args[args.index('--ros2-run-id')+1]='jackal-target-a01-20261018'
job['args']=args
(cache/'jackal-target-a01.json').write_text(json.dumps(job,indent=2),encoding='utf-8')
(cache/'run-target-wsl-peer.sh').write_text((cache/'run-route-wsl-peer.sh').read_text().replace('jackal-route-a','jackal-target-a'),encoding='utf-8',newline='\n')
with zipfile.ZipFile(cache/'target-benchmark.zip','w',zipfile.ZIP_DEFLATED) as z:
 for path in sorted((root/'benchmark/airground_benchmark').rglob('*.py')):
  z.write(path,path.relative_to(root/'benchmark'))
print('Binding report:',{k:v for k,v in r.model_dump().items() if k!='bindings'})
print('Selected:',target['instance_id'],path)
print('Tasks:',len(upstream_tasks('RetroNeighborhood')),'bus-stop instances:',len(config['same_class_instances']))
