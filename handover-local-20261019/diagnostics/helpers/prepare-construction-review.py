from pathlib import Path
import json,shutil
cache=Path('D:/xprogram/.raven-setup-cache');repo=Path('D:/xprogram/RAVEN-AirGround-github');out=cache/'construction-review-v1';out.mkdir(exist_ok=False)
shutil.copy2(repo/'scripts/probe_windows_scene_render.py',out/'probe_windows_scene_render.py')
shutil.copy2(repo/'runs/construction_adaptation_20261019/review-input.json',out/'review-input.json')
launcher=(cache/'drive-audit-v1/launch-drive-audit.py').read_text().replace('drive-audit-v1','construction-review-v1')
(out/'launch-review.py').write_text(launcher)
job=json.loads((cache/'paper31-review-a01.json').read_text());job['name']='construction-review-a01'
args=job['args'];args[args.index('--scene')+1]='D:/RAVEN-4060/assets/handover-scenes-20261019/ConstructionSite/ConstructionSite_Export.usd'
args[args.index('--review-manifest')+1]='D:/RAVEN-4060/setup/construction-review-v1/review-input.json'
(out/'construction-review-a01.json').write_text(json.dumps(job,indent=2))
ps=(cache/'start-drive-audit.ps1').read_text().replace('RAVEN-DriveAudit-20261019','RAVEN-ConstructionReview-20261019').replace('drive-audit-v1','construction-review-v1').replace('launch-drive-audit.py','launch-review.py').replace('-Minutes 7','-Minutes 16')
(cache/'start-construction-review.ps1').write_text(ps)
print('Prepared isolated 28-target / 56-view review job; 14 GiB and 840 s limits.')
