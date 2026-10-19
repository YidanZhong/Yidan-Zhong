from pathlib import Path,PurePosixPath
import argparse,hashlib,json,math,zipfile
import numpy as np
import yaml
from PIL import Image
p=argparse.ArgumentParser();p.add_argument('job');p.add_argument('sha256');a=p.parse_args()
root=Path('D:/xprogram/RAVEN-AirGround-github');run=root/'runs/nav2_dwb_stability_20261019'
archive=run/(a.job+'-evidence.zip');assert hashlib.sha256(archive.read_bytes()).hexdigest()==a.sha256
dest=run/a.job;dest.mkdir(exist_ok=True)
with zipfile.ZipFile(archive) as z:
 assert z.testzip() is None
 manifest=json.loads(z.read('sha256.json'))
 for name,digest in manifest.items():
  rel=PurePosixPath(name)
  assert not rel.is_absolute() and '..' not in rel.parts and ':' not in name
  data=z.read(name);assert hashlib.sha256(data).hexdigest()==digest,name
  target=dest/str(rel);assert target.resolve().is_relative_to(dest.resolve())
  target.parent.mkdir(parents=True,exist_ok=True)
  if target.exists():assert hashlib.sha256(target.read_bytes()).hexdigest()==digest,name
  else:
   with target.open('xb') as f:f.write(data)
read=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
base=dest/'logs';frames=base/(a.job+'-frames');rosdir=base/(a.job+'-wsl')
native=read(frames/'jackal-nav2.json');ros=read(rosdir/'ros-evidence.json');execution=read(base/a.job/'execution.json');render=read(frames/'report.json')
assert native['passed'] and ros['passed'] and execution['exit_code']==0 and render['status']=='passed'
assert native['goals_xy']==[[-35.5,-26.],[-35.5,-20.5],[-30.,-21.5]]
command=read(rosdir/'command.json');assert command[command.index('--tour-goal-timeout-s')+1]=='120.0' or command[command.index('--tour-goal-timeout-s')+1]=='120'
assert command[command.index('--local-planner')+1]=='dwb'
params=yaml.safe_load((rosdir/'nav2-runtime/airground_nav2_params.yaml').read_text())
controller=next(value['ros__parameters'] for key,value in params.items() if key.rstrip('/').endswith('controller_server'))
checker=controller[controller['goal_checker_plugins'][0]]
assert checker['xy_goal_tolerance']==.25 and checker['yaw_goal_tolerance']==.30
clouds={round(x['sim_time_s']*1e9):x for x in native['clouds']}
assert all(x['sha256']==clouds[round(x['sim_time_s']*1e9)]['sha256'] for x in ros['clouds'])
samples={round(x['sim_time_s']*1e9):x for x in native['samples']}
assert all(math.dist([o['x'],o['y'],o['z']],samples[round(o['sim_time_s']*1e9)]['position'])<1e-6 for o in ros['odom'])
assert ros['clock_backwards']==0 and ros['max_clock_publishers']==1
assert len(ros['terminal_actions'])==3 and ros['tour']['reached_count']==3
actions=[]
for goal,event,tour in zip(native['goals_xy'],ros['terminal_actions'],ros['tour']['goals']):
 assert event['status']==tour['result_status']==4 and tour['sim_time_s']<=120
 odom=event['odom'];sample=min(native['samples'],key=lambda s:abs(s['sim_time_s']-odom['sim_time_s']))
 x,y,z,w=sample['quaternion_xyzw'];yaw=math.atan2(2*(w*z+x*y),1-2*(y*y+z*z))
 error=math.dist(goal,sample['position'][:2])
 actions.append({'goal':goal,'action_status':4,'goal_duration_sim_s':tour['sim_time_s'],
  'sample_time_offset_s':sample['sim_time_s']-odom['sim_time_s'],'observed_xy_error_m':error,'observed_yaw_error_rad':abs(yaw),
  'observed_within_original_tolerances':error<=.25 and abs(yaw)<=.30})
assert ros['costmaps']['map']['matches_full_source_map']
with np.load(rosdir/'map-latest.npz') as snapshot:
 source=np.asarray(Image.open(frames/'local-map.pgm'))[::-1]
 assert np.array_equal(snapshot['data'],np.where(source==254,0,100).astype(np.int8))
images=[]
for entry in native['images']:
 image=frames/entry['file']
 with Image.open(image) as im:assert im.size==(960,600);im.verify()
 images.append({**entry,'path':image.relative_to(run).as_posix(),'sha256':hashlib.sha256(image.read_bytes()).hexdigest(),'original_rgb':True})
strict_pose_passed=all(item['observed_within_original_tolerances'] for item in actions)
report={'job':a.job,'scope':'same-route diagnostic repetition, not whole-scene acceptance',
 'status':'passed_cross_checks_and_observed_pose' if strict_pose_passed else 'failed_strict_observed_arrival_pose',
 'evidence_cross_checks_passed':True,'strict_observed_arrival_pose_passed':strict_pose_passed,
 'source_archive_sha256':a.sha256,'archive_files_verified':len(manifest),'metrics':native['metrics'],'actions':actions,
 'cloud_hash_matches':len(ros['clouds']),'odom_matches_physx':len(ros['odom']),'planned_paths':len(ros['plans']),
 'map_cells_equal':int(source.size),'goal_checker':checker,'execution':execution,'images':images,
 'limitations':['One repeated route is not general navigation stability or formal K=M.','Unreviewed map, PhysX odometry and CPU raycast point cloud remain diagnostic.','All goal orientations remain zero; no goal tolerance/budget relaxation.','Native log contains em import warning; real bridge messages and action outputs cross-checked.']}
(run/(a.job+'-summary.json')).write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in report.items() if k in ('job','metrics','actions','cloud_hash_matches','odom_matches_physx','map_cells_equal','archive_files_verified')},ensure_ascii=False))
