from pathlib import Path
import shutil,hashlib,json
base=Path('D:/xprogram/.raven-setup-cache');new=base/'fireacademy-triangle-v2'
shutil.copytree(base/'fireacademy-triangle-v1',new,ignore=shutil.ignore_patterns('__pycache__','source-sha256.json'))
p=new/'probe_tiled_terrain.py';s=p.read_text();needle='query.raycast_all(origin, direction, float(distance), collect)'
assert s.count(needle)==1;s=s.replace(needle,'query.raycast_all(origin, direction, float(distance), collect, bothSides=True)')
s=s.replace("'scope':'isolated static triangle collision A/B, original USD unchanged'", "'scope':'isolated static triangle collision A/B, original USD unchanged','query_both_sides':True")
p.write_text(s)
for p in [new/'launch-tiles.py',new/'fireacademy-triangle-a01.json']:
 p.write_text(p.read_text().replace('fireacademy-triangle-v1','fireacademy-triangle-v2').replace('fireacademy-triangle-a01','fireacademy-triangle-a02'))
(new/'fireacademy-triangle-a01.json').rename(new/'fireacademy-triangle-a02.json')
hashes={p.relative_to(new).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in new.rglob('*') if p.is_file()}
(new/'source-sha256.json').write_text(json.dumps(hashes,indent=2))
s=(base/'start-fireacademy-triangle.ps1').read_text(encoding='utf-8-sig').replace('fireacademy-triangle-v1','fireacademy-triangle-v2').replace('fireacademy-triangle-a01','fireacademy-triangle-a02').replace('RAVEN-FireAcademy-Triangle-20261019','RAVEN-FireAcademy-Triangle-A02-20261019')
(base/'start-fireacademy-triangle-a02.ps1').write_text(s,encoding='utf-8-sig')
p=base/'archive-scene-diagnostic.py';s=p.read_text().replace("'fireacademy-triangle-v1',", "'fireacademy-triangle-v1','fireacademy-triangle-v2',");p.write_text(s)
