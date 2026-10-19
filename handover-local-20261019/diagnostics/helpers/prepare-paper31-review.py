from pathlib import Path
import sys,types,json,hashlib,math,csv
root=Path(r'D:\xprogram\RAVEN-AirGround-github');cache=Path(r'D:\xprogram\.raven-setup-cache')
source=root/'runs/target_integration_20261018';run=root/'runs/paper31_review_20261018';run.mkdir(exist_ok=True)
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
sys.path.insert(0,str(cache/'target-tools'))
p=types.ModuleType('airground_benchmark');p.__path__=[str(root/'benchmark/airground_benchmark')];sys.modules[p.__name__]=p
from airground_benchmark.ground_truth import load_target_annotations
from airground_benchmark.roi_analysis import annotation_roi
from airground_benchmark.task_catalog import upstream_tasks
m=load_target_annotations(source/'targets.auto-bound.json')
classes={c for t in upstream_tasks('RetroNeighborhood') for c in t.query_classes}
bindings={r['instance_id']:r for r in read(source/'binding-report.json')['bindings']}
candidates=read(root/'runs/local_scene1_preparation_20261017/target_candidates.json')['candidates']
by_path={c['prim_path']:c for c in candidates}
rows=[]
for instance in m.instances:
 if instance.semantic_class not in classes:continue
 target=instance.model_dump(mode='json');center=target['obb']['center_xyz_m'];size=target['obb']['size_xyz_m']
 diag=max(1.,math.sqrt(sum(v*v for v in size)));radius=max(8.,diag*2.2);elevation=max(4.,diag*.75)
 views=[{'eye':[center[0]+radius*math.cos(math.radians(a)),center[1]+radius*math.sin(math.radians(a)),center[2]+elevation],'look_at':center,'azimuth_deg':a} for a in (45.,225.)]
 chosen=by_path[target['usd_prim_path']]
 alternatives=[c for c in candidates if c['prim_path']!=chosen['prim_path'] and math.dist(c['center_xyz_m'],chosen['center_xyz_m'])<.25]
 alternatives.sort(key=lambda c:(math.dist(c['size_xyz_m'],chosen['size_xyz_m']),len(c['prim_path'])))
 rows.append({'target':target,'binding':bindings[instance.instance_id],'candidate':chosen,
              'near_center_alternatives':alternatives[:8],'views':views})
assert len(rows)==31 and all(not r['target']['verified'] for r in rows)
scene=root/'AirStack/scenes/RetroNeighborhood/RetroNeighborhood_Export.usd'
manifest={'scope':'static target review material, not human approval or navigation','scene_sha256':sha(scene),
 'camera_method':'same radius/elevation formula and opposite azimuths as official render_target_review_scene_packet.py',
 'source_sha256':{str(p.relative_to(root)):sha(p) for p in [source/'targets.auto-bound.json',source/'binding-report.json',root/'AirStack/simulation/isaac-sim/tools/render_target_review_scene_packet.py']},
 'target_count':31,'view_count':62,'rows':rows}
(run/'review-input.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
roi=annotation_roi(m,margin_m=2.,resolution_m=.05)
cells=math.prod(roi['shape'])
assessment={'roi':roi,'cell_count':cells,'targets_reviewed':False,
 'formal_map_created':False,'existing_runner':'scripts/run_roi_analysis.py:host_sample',
 'existing_available_ram_requirement_gib':64,'remote_installed_ram_gib':32,
 'entry_compatible':False,'guard_changed':False,
 'future_native_tiled_generator':'requires real PhysX validation and matching support-plane/collider policy before acceptance',
 'raw_array_estimate_bytes':cells*(4+3*4+4+1+4),
 'estimate_scope':'height float32, normal float32x3, cost float32, mask bool, component int32 only; NOT peak memory or a performance test'}
(run/'mapping-readiness.json').write_text(json.dumps(assessment,indent=2),encoding='utf-8')
job=read(cache/'jackal-target-a01.json');job['name']='paper31-review-a01';job['ros2']=False;job['env']={}
args=job['args'];args=args[:args.index('--ros2-seconds')]
args+=['--review-manifest',r'D:\RAVEN-4060\setup\paper31-review-input.json']
job['args']=args
(cache/'paper31-review-a01.json').write_text(json.dumps(job,indent=2),encoding='utf-8')
print(json.dumps({'targets':len(rows),'views':62,'ambiguous':sum('ambiguous_candidates' in r['binding']['issues'] for r in rows),'mapping':assessment},indent=2))
