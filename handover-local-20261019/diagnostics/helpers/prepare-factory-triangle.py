from pathlib import Path
import shutil,hashlib,json
base=Path('D:/xprogram/.raven-setup-cache');new=base/'factory-triangle-v1'
shutil.copytree(base/'factory-geometry-v1',new,ignore=shutil.ignore_patterns('__pycache__','source-sha256.json'))
p=new/'probe_tiled_terrain.py';s=p.read_text();donor=(base/'fireacademy-triangle-v2/probe_tiled_terrain.py').read_text()
begin=donor.index("    mesh_path='/World/stage/Ds/Ds_001'");end=donor.index('    collider_rows = []',begin)
insert=donor[begin:end].replace('/World/stage/Ds/Ds_001','/World/stage/AbandonedFactory/MergedMeshes/merged_38').replace('FireAcademy merged mesh','Factory merged_38')
assert s.count('    collider_rows = []')==1;s=s.replace('    collider_rows = []',insert+'    collider_rows = []')
s=s.replace('query.raycast_all(origin, direction, float(distance), collect)','query.raycast_all(origin, direction, float(distance), collect, bothSides=True)')
p.write_text(s)
for p in [new/'launch-tiles.py',new/'factory-geometry-a01.json']:
 p.write_text(p.read_text().replace('factory-geometry-v1','factory-triangle-v1').replace('factory-geometry-a01','factory-triangle-a01'))
(new/'factory-geometry-a01.json').rename(new/'factory-triangle-a01.json')
hashes={p.relative_to(new).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in new.rglob('*') if p.is_file() and '__pycache__' not in p.parts}
(new/'source-sha256.json').write_text(json.dumps(hashes,indent=2))
s=(base/'start-fireacademy-triangle.ps1').read_text(encoding='utf-8-sig').replace('fireacademy-triangle','factory-triangle').replace('RAVEN-FireAcademy-Triangle','RAVEN-Factory-Triangle')
(base/'start-factory-triangle.ps1').write_text(s,encoding='utf-8-sig')
p=base/'archive-scene-diagnostic.py';s=p.read_text(encoding='utf-8-sig').replace("'factory-geometry-v1')", "'factory-geometry-v1','factory-triangle-v1')");p.write_text(s)
