from pathlib import Path
import shutil,json,hashlib,difflib
base=Path('D:/xprogram/.raven-setup-cache');root=Path('D:/xprogram/RAVEN-AirGround-github')
old=base/'full-nav-dwb-v1';new=base/'full-nav-strict-v1';new.mkdir(exist_ok=False)
for p in old.iterdir():
 if p.is_file() and p.suffix in ('.py','.json','.sh') and not p.name.startswith(('probe-full-nav','full-nav-')):
  shutil.copy2(p,new/p.name)
for name in ('launch-full-nav.py','run-peer.sh'):
 p=new/name;s=p.read_text().replace('full-nav-dwb-v1','full-nav-strict-v1').replace('full-nav-dwb-a[0-9][0-9]','full-nav-strict-a[0-9][0-9]')
 if name.endswith('.sh'):s=s.replace('--air-stack /mnt/d/RAVEN-4060/source/AirStack','--air-stack /mnt/d/RAVEN-4060/setup/full-nav-strict-v1/air-stack')
 p.write_text(s,newline='\n')
source=root/'AirStack/simulation/isaac-sim/tools/run_nav2_smoke.py'
before=source.read_text();after=before
oldcheck='plugin: "nav2_controller::SimpleGoalChecker"\n                  stateful: true'
assert after.count(oldcheck)==1;after=after.replace(oldcheck,oldcheck.replace('stateful: true','stateful: false'))
oldwindow='xy_goal_tolerance: 0.25\n                  trans_stopped_velocity: 0.25'
assert after.count(oldwindow)==1;after=after.replace(oldwindow,oldwindow.replace('xy_goal_tolerance: 0.25','xy_goal_tolerance: 0.10'))
destination=new/'air-stack/simulation/isaac-sim/tools/run_nav2_smoke.py';destination.parent.mkdir(parents=True);destination.write_text(after,newline='\n')
(new/'controller-candidate.diff').write_text(''.join(difflib.unified_diff(before.splitlines(True),after.splitlines(True),fromfile='original-run_nav2_smoke.py',tofile='strict-candidate-run_nav2_smoke.py')),encoding='utf-8')
job=json.loads((old/'full-nav-dwb-a01.json').read_text());job['name']='full-nav-strict-a01'
job['args']=[v.replace('full-nav-dwb-v1','full-nav-strict-v1').replace('full-nav-dwb-a01-20261019','full-nav-strict-a01-20261019') for v in job['args']]
(new/'full-nav-strict-a01.json').write_text(json.dumps(job,indent=2),encoding='utf-8')
helper=(base/'start-full-nav-dwb.ps1').read_text().replace('full-nav-dwb-v1','full-nav-strict-v1').replace('RAVEN-FullMap-DWB-20261019','RAVEN-FullMap-Strict-20261019')
(base/'start-full-nav-strict.ps1').write_text(helper,encoding='utf-8')
manifest={'status':'prepared_not_run','original_runner_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'candidate_runner_sha256':hashlib.sha256(destination.read_bytes()).hexdigest(),'acceptance_tolerances':[.25,.30],'goal_budget_s':120,'changes':{'goal_checker_stateful':False,'dwb_rotation_transition_distance_m':.10},'formal_accepted':False}
(new/'candidate.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8');print(manifest)
