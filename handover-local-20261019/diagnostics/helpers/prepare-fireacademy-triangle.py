from pathlib import Path
import shutil,hashlib,json
base=Path('D:/xprogram/.raven-setup-cache');new=base/'fireacademy-triangle-v1'
shutil.copytree(base/'fireacademy-geometry-v1',new,ignore=shutil.ignore_patterns('__pycache__','source-sha256.json'))
p=new/'probe_tiled_terrain.py';s=p.read_text();needle='    collider_rows = []'
insert='''    mesh_path='/World/stage/Ds/Ds_001'
    merged=stage.GetPrimAtPath(mesh_path)
    if not merged or not merged.IsA(UsdGeom.Mesh):raise RuntimeError('Expected exact FireAcademy merged mesh')
    if merged.HasAPI(UsdPhysics.RigidBodyAPI) and UsdPhysics.RigidBodyAPI(merged).GetRigidBodyEnabledAttr().Get():
        raise RuntimeError('Triangle collision candidate must be static')
    api=UsdPhysics.MeshCollisionAPI(merged)
    previous=str(api.GetApproximationAttr().Get())
    if previous!='convexDecomposition':raise RuntimeError('Unexpected baseline collision approximation')
    api.GetApproximationAttr().Set('none')
    if str(api.GetApproximationAttr().Get())!='none':raise RuntimeError('Triangle collision override not effective')
    setup['private_collision_override']={'prim_path':mesh_path,'before':previous,'after':'none',
        'scope':'isolated static triangle collision A/B, original USD unchanged'}
'''
assert s.count(needle)==1;s=s.replace(needle,insert+needle);p.write_text(s)
for p in [new/'launch-tiles.py',new/'fireacademy-geometry-a01.json']:
 p.write_text(p.read_text().replace('fireacademy-geometry-v1','fireacademy-triangle-v1').replace('fireacademy-geometry-a01','fireacademy-triangle-a01'))
(new/'fireacademy-geometry-a01.json').rename(new/'fireacademy-triangle-a01.json')
hashes={p.relative_to(new).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in new.rglob('*') if p.is_file()}
(new/'source-sha256.json').write_text(json.dumps(hashes,indent=2))
s=(base/'start-construction-visibility.ps1').read_text(encoding='utf-8-sig').replace('construction-visibility-v1','fireacademy-triangle-v1').replace('construction-visibility-a01','fireacademy-triangle-a01').replace('RAVEN-Construction-Visibility-20261019','RAVEN-FireAcademy-Triangle-20261019')
(base/'start-fireacademy-triangle.ps1').write_text(s,encoding='utf-8-sig')
p=base/'archive-scene-diagnostic.py';s=p.read_text().replace("'fireacademy-geometry-v1',", "'fireacademy-geometry-v1','fireacademy-triangle-v1',");p.write_text(s)
