from pathlib import Path
import json,shutil
c=Path('D:/xprogram/.raven-setup-cache');root=Path('D:/xprogram/RAVEN-AirGround-github')
old=c/'construction-review-v1';new=c/'factory-review-v1';new.mkdir(exist_ok=False)
for p in old.glob('*.py'):
 if not p.name.startswith('probe-construction'):shutil.copy2(p,new/p.name)
p=new/'launch-review.py';p.write_text(p.read_text().replace('construction-review-v1','factory-review-v1'),newline='\n')
shutil.copy2(root/'runs/factory_adaptation_20261019/review-input.json',new/'review-input.json')
j=json.loads((old/'construction-review-a01.json').read_text());j['name']='factory-review-a01'
j['args']=[v.replace('construction-review-v1','factory-review-v1').replace('ConstructionSite','AbandonedFactory') for v in j['args']]
(new/'factory-review-a01.json').write_text(json.dumps(j,indent=2))
s=(c/'start-construction-review.ps1').read_text().replace('construction-review-v1','factory-review-v1').replace('RAVEN-ConstructionReview-20261019','RAVEN-AbandonedFactoryReview-20261019')
(c/'start-factory-review.ps1').write_text(s)
print('Prepared 11 contexts / 22 actual camera requests; no GPU job started.')

