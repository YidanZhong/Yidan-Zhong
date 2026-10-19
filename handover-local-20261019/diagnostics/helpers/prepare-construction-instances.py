from pathlib import Path
import shutil,hashlib,json
base=Path('D:/xprogram/.raven-setup-cache');new=base/'construction-instances-v1'
shutil.copytree(base/'construction-ground-v2',new,ignore=shutil.ignore_patterns('__pycache__','source-sha256.json'))
shutil.copy2(base/'expand_static_scene_instances.py',new/'expand_static_scene_instances.py')
p=new/'probe_tiled_terrain.py';s=p.read_text();needle="    setup = {'colliders': scene_prep.add_profiled_colliders(scene_root)}"
assert needle in s;s=s.replace(needle,"    from expand_static_scene_instances import expand_instances\n    expansion=expand_instances(stage,'/World/stage')\n"+needle+"\n    setup['instance_expansion']=expansion")
needle="    (output/'colliders.json').write_text"
insert="""    missing=[]
    for mesh_prim in Usd.PrimRange(scene_root,Usd.TraverseInstanceProxies()):
        if mesh_prim.IsA(UsdGeom.Mesh) and UsdGeom.Imageable(mesh_prim).ComputeVisibility()!=UsdGeom.Tokens.invisible:
            if not mesh_prim.HasAPI(UsdPhysics.CollisionAPI) or not UsdPhysics.CollisionAPI(mesh_prim).GetCollisionEnabledAttr().Get():
                missing.append(str(mesh_prim.GetPath()))
    setup['visible_scene_meshes_missing_collision']=missing
    if missing:raise RuntimeError('Visible scene meshes still lack collision: '+str(len(missing)))
"""
s=s.replace(needle,insert+needle);p.write_text(s)
p=new/'launch-tiles.py';p.write_text(p.read_text().replace('construction-ground-v2','construction-instances-v1'))
job_path=next(new.glob('construction-ground-a01.json'));job=json.loads(job_path.read_text());job['name']='construction-instances-a01'
job['args']=[v.replace('construction-ground-v2','construction-instances-v1') for v in job['args']]
new_job=new/'construction-instances-a01.json';new_job.write_text(json.dumps(job,indent=2))
config_path=new/Path(job['args'][job['args'].index('--tile-validation')+1]).name
cfg=json.loads(config_path.read_text());cfg['windows']=[dict(w,rows=2,cols=2,tile_cells=16) for w in cfg['windows']]
cfg['ray_audit_points_xy_m']=[[-32.025,-14.025],[-34.025,-16.025],[-49.975,-.025],[-32.314312,-13.342946],[-30.283248,22.29813]]
cfg['scope']='unreviewed instance collider coverage diagnostic; previous map is invalid for acceptance'
config_path.write_text(json.dumps(cfg,indent=2))
hashes={p.relative_to(new).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in new.rglob('*') if p.is_file()}
(new/'source-sha256.json').write_text(json.dumps(hashes,indent=2))
s=(base/'start-construction-visibility.ps1').read_text(encoding='utf-8-sig').replace('construction-visibility-v1','construction-instances-v1').replace('construction-visibility-a01','construction-instances-a01').replace('RAVEN-Construction-Visibility-20261019','RAVEN-Construction-Instances-20261019')
(base/'start-construction-instances.ps1').write_text(s,encoding='utf-8-sig')
p=base/'archive-scene-diagnostic.py';s=p.read_text(encoding='utf-8-sig').replace("'construction-ground-v2',", "'construction-ground-v2','construction-instances-v1',");p.write_text(s)
print(config_path.name,len(hashes))
