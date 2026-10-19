from pathlib import Path
import shutil,hashlib,json
base=Path('D:/xprogram/.raven-setup-cache');new=base/'construction-visibility-v5'
shutil.copytree(base/'construction-visibility-v4',new,ignore=shutil.ignore_patterns('__pycache__','source-sha256.json'))
p=new/'probe_unreviewed_visibility.py';s=p.read_text()
start=s.index("    timing_snapshot('before_event_flush')");end=s.index('    config=RaycastConfirmationVisibilityConfig',start)
s=s[:start]+'''    world.set_simulation_dt(physics_dt=1/250,rendering_dt=1/250)
    timing_snapshot('configured_for_public_render_step')
    timing['step_entry']='World.step(render=True), actual PhysX clock checked after each 25 steps'
    timing['sdk_getter_limitation']='Empty manager registry returns 60 Hz; pure step uses this default. Public app-update stepping follows the authored 250 Hz scene.'
    scene_hz=PhysxSchema.PhysxSceneAPI(stage.GetPrimAtPath('/World/PhysicsScene')).GetTimeStepsPerSecondAttr().Get()
    if scene_hz!=250 or abs(float(world.get_rendering_dt())-1/250)>1e-7:raise RuntimeError('Authored physics/render rate differs from 250 Hz')
    (output/'visibility-timing.json').write_text(json.dumps(timing,indent=2))
''' +s[end:]
s=s.replace('for _ in range(25):world.step(render=False)', '''before_time=float(world.current_time)
                before_step=int(world.current_time_step_index)
                for _ in range(25):world.step(render=True)
                after_time=float(world.current_time)
                after_step=int(world.current_time_step_index)
                timing.setdefault('step_batches',[]).append({'before_s':before_time,'after_s':after_time,'before_step':before_step,'after_step':after_step})
                (output/'visibility-timing.json').write_text(json.dumps(timing,indent=2))
                if abs((after_time-before_time)-.1)>1e-5 or after_step-before_step!=25:
                    raise RuntimeError('Twenty-five actual PhysX steps did not advance by 0.1 s')''')
s=s.replace('No real RGB or ROS camera stream generated; five real PhysX times match official raycast trace method.', 'No RGB sensor frames or ROS camera stream saved. Public render stepping advances five real PhysX sample times; registry-default pure stepping was rejected.')
p.write_text(s)
for p in [new/'launch-tiles.py',new/'construction-visibility-a04.json']:
 p.write_text(p.read_text().replace('construction-visibility-v4','construction-visibility-v5').replace('construction-visibility-a04','construction-visibility-a05'))
(new/'construction-visibility-a04.json').rename(new/'construction-visibility-a05.json')
hashes={p.relative_to(new).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in new.rglob('*') if p.is_file()}
(new/'source-sha256.json').write_text(json.dumps(hashes,indent=2))
s=(base/'start-construction-visibility-a04.ps1').read_text(encoding='utf-8-sig').replace('construction-visibility-v4','construction-visibility-v5').replace('construction-visibility-a04','construction-visibility-a05').replace('Visibility-A04','Visibility-A05')
(base/'start-construction-visibility-a05.ps1').write_text(s,encoding='utf-8-sig')
p=base/'archive-scene-diagnostic.py';s=p.read_text().replace("'construction-visibility-v4',", "'construction-visibility-v4','construction-visibility-v5',");p.write_text(s)
