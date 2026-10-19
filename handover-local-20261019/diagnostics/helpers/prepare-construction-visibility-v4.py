from pathlib import Path
import shutil,hashlib,json
base=Path('D:/xprogram/.raven-setup-cache');new=base/'construction-visibility-v4'
shutil.copytree(base/'construction-visibility-v3',new,ignore=shutil.ignore_patterns('__pycache__','source-sha256.json'))
p=new/'probe_unreviewed_visibility.py';s=p.read_text()
start=s.index("    timing={'physics_dt_before_s'");end=s.index('    config=RaycastConfirmationVisibilityConfig',start)
s=s[:start]+'''    from pxr import PhysxSchema
    from isaacsim.core.simulation_manager import SimulationManager
    import omni.kit.app
    timing={'requested_physics_dt_s':1/250,'stride_steps':25,'snapshots':[]}
    def timing_snapshot(label):
        snapshot={'label':label,'physics_dt_s':float(world.get_physics_dt()),'sim_time_s':float(world.current_time),
                  'context_path':str(world.get_physics_context().prim_path),'active_scenes':[],'manager_scenes':[]}
        from pxr import UsdPhysics
        for prim in stage.Traverse():
            if prim.IsA(UsdPhysics.Scene):
                snapshot['active_scenes'].append({'path':str(prim.GetPath()),'hz':PhysxSchema.PhysxSceneAPI(prim).GetTimeStepsPerSecondAttr().Get()})
        # Read-only diagnostic of the SDK's scene registry, not a mutation.
        for path,api in SimulationManager._physics_scene_apis.items():
            snapshot['manager_scenes'].append({'path':str(path),'active':bool(api.GetPrim().IsActive()),'hz':api.GetTimeStepsPerSecondAttr().Get()})
        timing['snapshots'].append(snapshot)
        (output/'visibility-timing.json').write_text(json.dumps(timing,indent=2))
    timing_snapshot('before_event_flush')
    for _ in range(3):omni.kit.app.get_app().update()
    timing_snapshot('after_three_app_updates')
    world.set_simulation_dt(physics_dt=1/250,rendering_dt=1/250)
    timing_snapshot('after_reapply')
    if abs(float(world.get_physics_dt())-1/250)>1e-7:raise RuntimeError('Actual step rate differs from requested 250 Hz after bounded event flush')
''' +s[end:]
p.write_text(s)
for p in [new/'launch-tiles.py',new/'construction-visibility-a03.json']:
 p.write_text(p.read_text().replace('construction-visibility-v3','construction-visibility-v4').replace('construction-visibility-a03','construction-visibility-a04'))
(new/'construction-visibility-a03.json').rename(new/'construction-visibility-a04.json')
hashes={p.relative_to(new).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in new.rglob('*') if p.is_file()}
(new/'source-sha256.json').write_text(json.dumps(hashes,indent=2))
s=(base/'start-construction-visibility-a03.ps1').read_text(encoding='utf-8-sig').replace('construction-visibility-v3','construction-visibility-v4').replace('construction-visibility-a03','construction-visibility-a04').replace('Visibility-A03','Visibility-A04')
(base/'start-construction-visibility-a04.ps1').write_text(s,encoding='utf-8-sig')
p=base/'archive-scene-diagnostic.py';s=p.read_text().replace("'construction-visibility-v3',", "'construction-visibility-v3','construction-visibility-v4',");p.write_text(s)
