from pathlib import Path
import shutil,hashlib,json
base=Path('D:/xprogram/.raven-setup-cache');new=base/'fireacademy-windows-v1'
shutil.copytree(base/'fireacademy-triangle-v2',new,ignore=shutil.ignore_patterns('__pycache__','source-sha256.json'))
p=new/'geometry-input.json';d=json.loads(p.read_text());origins=[[-33.65,-8.0],[-43.65,7.0],[-3.15,-3.15]]
for row,origin in zip(d['windows'],origins):row.update(origin=origin,rows=128,cols=128,tile_cells=64)
p.write_text(json.dumps(d,indent=2))
for p in [new/'launch-tiles.py',new/'fireacademy-triangle-a02.json']:
 p.write_text(p.read_text().replace('fireacademy-triangle-v2','fireacademy-windows-v1').replace('fireacademy-triangle-a02','fireacademy-windows-a01'))
(new/'fireacademy-triangle-a02.json').rename(new/'fireacademy-windows-a01.json')
hashes={p.relative_to(new).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in new.rglob('*') if p.is_file()}
(new/'source-sha256.json').write_text(json.dumps(hashes,indent=2))
s=(base/'start-fireacademy-triangle-a02.ps1').read_text(encoding='utf-8-sig').replace('fireacademy-triangle-v2','fireacademy-windows-v1').replace('fireacademy-triangle-a02','fireacademy-windows-a01').replace('RAVEN-FireAcademy-Triangle-A02-20261019','RAVEN-FireAcademy-Windows-20261019')
(base/'start-fireacademy-windows.ps1').write_text(s,encoding='utf-8-sig')
p=base/'archive-scene-diagnostic.py';s=p.read_text().replace("'fireacademy-triangle-v2',", "'fireacademy-triangle-v2','fireacademy-windows-v1',");p.write_text(s)
