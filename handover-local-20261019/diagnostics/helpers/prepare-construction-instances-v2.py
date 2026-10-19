from pathlib import Path
import shutil,hashlib,json
base=Path('D:/xprogram/.raven-setup-cache');new=base/'construction-instances-v2'
shutil.copytree(base/'construction-instances-v1',new,ignore=shutil.ignore_patterns('__pycache__','source-sha256.json'))
shutil.copy2(base/'seed_instance_colliders.py',new/'seed_instance_colliders.py')
shutil.copy2(Path('D:/xprogram/RAVEN-AirGround-github/runs/construction_adaptation_20261019/instance-collision-geometry-matches.json'),new/'instance-collision-geometry-matches.json')
utils=new/'air-stack/simulation/isaac-sim/utils'
p=utils/'scene_prep.py';s=p.read_text().replace('def add_profiled_colliders(prim, enabled_profiles=None, disable_other_colliders: bool = False):','def add_profiled_colliders(prim, enabled_profiles=None, disable_other_colliders: bool = False, profile_overrides=None):')
s=s.replace('            summary[profile] += 1',"            profile = (profile_overrides or {}).get(str(current.GetPath()), profile)\n            summary[profile] += 1")
p.write_text(s)
p=utils/'scene_physics_profile.py';s=p.read_text().replace('    profile: PhysicsProfile = DEFAULT_AIRGROUND_PHYSICS_PROFILE,\n','    profile: PhysicsProfile = DEFAULT_AIRGROUND_PHYSICS_PROFILE,\n    profile_overrides: dict[str, str] | None = None,\n')
s=s.replace('        if profile_name == "ground":','        profile_name = (profile_overrides or {}).get(str(prim.GetPath()), profile_name)\n        if profile_name == "ground":')
p.write_text(s)
p=new/'probe_tiled_terrain.py';s=p.read_text().replace("    setup = {'colliders': scene_prep.add_profiled_colliders(scene_root)}", "    from seed_instance_colliders import seed_colliders\n    inherited=seed_colliders(stage,config_path.with_name('instance-collision-geometry-matches.json'))\n    overrides=inherited['profile_overrides']\n    (output/'instance-collision-inheritance.json').write_text(json.dumps(inherited,indent=2))\n    setup = {'colliders': scene_prep.add_profiled_colliders(scene_root,profile_overrides=overrides)}")
s=s.replace("profile=DEFAULT_AIRGROUND_PHYSICS_PROFILE)","profile=DEFAULT_AIRGROUND_PHYSICS_PROFILE,profile_overrides=overrides)")
s=s.replace("    if missing:raise RuntimeError('Visible scene meshes still lack collision: '+str(len(missing)))", "    (output/'collision-coverage.json').write_text(json.dumps({'missing_visible':missing,'collider_count':len(collider_rows)},indent=2))\n    if missing:raise RuntimeError('Visible scene meshes still lack collision: '+str(len(missing)))")
p.write_text(s)
for p in [new/'launch-tiles.py',new/'construction-instances-a01.json']:
 p.write_text(p.read_text().replace('construction-instances-v1','construction-instances-v2').replace('construction-instances-a01','construction-instances-a02'))
(new/'construction-instances-a01.json').rename(new/'construction-instances-a02.json')
p=new/'ground-input.json';d=json.loads(p.read_text())
for relative in d['source_sha256']:
 if relative.startswith('AirStack/'):
  d['source_sha256'][relative]=hashlib.sha256((new/'air-stack'/relative[9:]).read_bytes()).hexdigest()
p.write_text(json.dumps(d,indent=2))
hashes={p.relative_to(new).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in new.rglob('*') if p.is_file()}
(new/'source-sha256.json').write_text(json.dumps(hashes,indent=2))
s=(base/'start-construction-instances.ps1').read_text(encoding='utf-8-sig').replace('construction-instances-v1','construction-instances-v2').replace('construction-instances-a01','construction-instances-a02').replace('RAVEN-Construction-Instances-20261019','RAVEN-Construction-Instances-A02-20261019')
(base/'start-construction-instances-a02.ps1').write_text(s,encoding='utf-8-sig')
p=base/'archive-scene-diagnostic.py';s=p.read_text(encoding='utf-8-sig').replace("'construction-instances-v1',", "'construction-instances-v1','construction-instances-v2',");p.write_text(s)
