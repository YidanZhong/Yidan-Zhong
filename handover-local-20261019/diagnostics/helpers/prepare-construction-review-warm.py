from pathlib import Path
import shutil,hashlib,json
base=Path('D:/xprogram/.raven-setup-cache');old=base/'construction-review-v1';new=base/'construction-review-v2';new.mkdir()
for name in ['probe_windows_scene_render.py','launch-review.py','review-input.json']:shutil.copy2(old/name,new/name)
p=new/'launch-review.py';p.write_text(p.read_text().replace('construction-review-v1','construction-review-v2'))
job=json.loads((old/'construction-review-a02.json').read_text());job['name']='construction-review-a03';job['args']=[v.replace('construction-review-v1','construction-review-v2') for v in job['args']]
job['retry_basis']='Previous camera attempts compiled shaders; subsequent visibility render diagnostics completed further shader work. Same 480s first-frame/840s outer/14GiB/960x600/60-settle budgets; no weaker image acceptance.'
(new/'construction-review-a03.json').write_text(json.dumps(job,indent=2))
hashes={p.relative_to(new).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in new.rglob('*') if p.is_file()}
(new/'source-sha256.json').write_text(json.dumps(hashes,indent=2))
s=(base/'start-construction-visibility.ps1').read_text(encoding='utf-8-sig').replace('construction-visibility-v1','construction-review-v2').replace('construction-visibility-a01','construction-review-a03').replace('launch-tiles.py','launch-review.py').replace('RAVEN-Construction-Visibility-20261019','RAVEN-Construction-Review-A03-20261019')
(base/'start-construction-review-a03.ps1').write_text(s,encoding='utf-8-sig')
p=base/'archive-scene-diagnostic.py';s=p.read_text(encoding='utf-8-sig').replace("'construction-review-v1',", "'construction-review-v1','construction-review-v2',");p.write_text(s)
