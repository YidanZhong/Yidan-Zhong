from pathlib import Path
import shutil,hashlib,json
base=Path('D:/xprogram/.raven-setup-cache');new=base/'construction-visibility-v3'
shutil.copytree(base/'construction-visibility-v2',new,ignore=shutil.ignore_patterns('__pycache__','source-sha256.json'))
p=new/'probe_windows_scene_render.py';s=p.read_text();needle='        dt = 1/250 if args.tile_validation else 1/120 if args.jackal_usd else 1/60'
insert='''        if args.tile_validation:
            from pxr import UsdPhysics
            disabled_physics_scenes=[]
            for physics_prim in list(stage.Traverse()):
                if physics_prim.IsA(UsdPhysics.Scene) and str(physics_prim.GetPath())!='/World/PhysicsScene':
                    disabled_physics_scenes.append(str(physics_prim.GetPath()))
                    physics_prim.SetActive(False)
            report['physics_scenes_disabled_before_world']=disabled_physics_scenes
'''
assert s.count(needle)==1;s=s.replace(needle,insert+needle);p.write_text(s)
p=new/'probe_unreviewed_visibility.py';s=p.read_text()
s=s.replace("    if abs(timing['physics_dt_after_s']-1/250)>1e-7:raise RuntimeError('Actual step rate differs from requested 250 Hz')\n    (output/'visibility-timing.json').write_text(json.dumps(timing,indent=2))", "    timing['physics_context_prim_path']=str(world.get_physics_context().prim_path)\n    (output/'visibility-timing.json').write_text(json.dumps(timing,indent=2))\n    if abs(timing['physics_dt_after_s']-1/250)>1e-7:raise RuntimeError('Actual step rate differs from requested 250 Hz')")
s=s.replace('# World construction requested 250 Hz, but the opened stage reset restores 60 Hz.', '# Confirm that pre-World scene isolation restored the requested 250 Hz rate.')
p.write_text(s)
for p in [new/'launch-tiles.py',new/'construction-visibility-a02.json']:
 p.write_text(p.read_text().replace('construction-visibility-v2','construction-visibility-v3').replace('construction-visibility-a02','construction-visibility-a03'))
(new/'construction-visibility-a02.json').rename(new/'construction-visibility-a03.json')
hashes={p.relative_to(new).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in new.rglob('*') if p.is_file()}
(new/'source-sha256.json').write_text(json.dumps(hashes,indent=2))
s=(base/'start-construction-visibility-a02.ps1').read_text(encoding='utf-8-sig').replace('construction-visibility-v2','construction-visibility-v3').replace('construction-visibility-a02','construction-visibility-a03').replace('Visibility-A02','Visibility-A03')
(base/'start-construction-visibility-a03.ps1').write_text(s,encoding='utf-8-sig')
p=base/'archive-scene-diagnostic.py';s=p.read_text().replace("'construction-visibility-v2',", "'construction-visibility-v2','construction-visibility-v3',");p.write_text(s)
