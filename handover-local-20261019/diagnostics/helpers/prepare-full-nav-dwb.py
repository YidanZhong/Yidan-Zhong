from pathlib import Path
import shutil,json
c=Path('D:/xprogram/.raven-setup-cache');root=Path('D:/xprogram/RAVEN-AirGround-github');old=c/'full-nav-v2';new=c/'full-nav-dwb-v1'
new.mkdir(exist_ok=False)
for p in old.iterdir():
 if p.is_file() and p.suffix in ('.py','.json','.sh') and not p.name.startswith('probe-full-nav'):
  shutil.copy2(p,new/p.name)
shutil.copy2(root/'scripts/probe_nav2_wsl_peer.py',new/'probe_nav2_wsl_peer.py')
for name in ['launch-full-nav.py','run-peer.sh']:
 p=new/name;s=p.read_text().replace('full-nav-v2','full-nav-dwb-v1')
 if name.endswith('.sh'):s=s.replace('full-nav-a[0-9][0-9]','full-nav-dwb-a[0-9][0-9]').replace('--tour-goal-timeout-s 180','--tour-goal-timeout-s 120 --local-planner dwb')
 p.write_text(s,newline='\n')
job=json.loads((old/'full-nav-a02.json').read_text());job['name']='full-nav-dwb-a01'
job['args']=[v.replace('full-nav-v2','full-nav-dwb-v1').replace('full-nav-a02-20261019','full-nav-dwb-a01-20261019') for v in job['args']]
(new/'full-nav-dwb-a01.json').write_text(json.dumps(job,indent=2))
ps=(c/'start-full-nav-v2.ps1').read_text().replace('full-nav-v2','full-nav-dwb-v1').replace('RAVEN-FullMap-Nav2-20261019','RAVEN-FullMap-DWB-20261019')
(c/'start-full-nav-dwb.ps1').write_text(ps)
print('Prepared DWB profile probe; 120 s/goal; not started; GPU execution remains sequential.')
