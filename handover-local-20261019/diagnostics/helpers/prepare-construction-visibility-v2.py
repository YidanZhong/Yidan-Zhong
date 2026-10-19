from pathlib import Path
import json,hashlib,shutil
base=Path('D:/xprogram/.raven-setup-cache');old=base/'construction-visibility-v1';new=base/'construction-visibility-v2'
shutil.copytree(old,new,ignore=shutil.ignore_patterns('__pycache__','source-sha256.json'))
probe=new/'probe_unreviewed_visibility.py';s=probe.read_text()
s=s.replace("    config=RaycastConfirmationVisibilityConfig",'''    timing={'physics_dt_before_s':float(world.get_physics_dt()),'rendering_dt_before_s':float(world.get_rendering_dt()),
            'requested_physics_dt_s':1/250,'requested_rendering_dt_s':1/250,'stride_steps':25}
    # World construction requested 250 Hz, but the opened stage reset restores 60 Hz.
    # Reapply the originally requested rate after reset, before collecting evidence.
    world.set_simulation_dt(physics_dt=1/250,rendering_dt=1/250)
    timing['physics_dt_after_s']=float(world.get_physics_dt())
    timing['rendering_dt_after_s']=float(world.get_rendering_dt())
    if abs(timing['physics_dt_after_s']-1/250)>1e-7:raise RuntimeError('Actual step rate differs from requested 250 Hz')
    (output/'visibility-timing.json').write_text(json.dumps(timing,indent=2))
    config=RaycastConfirmationVisibilityConfig''')
s=s.replace("'five_frame_times_s':times", "'timing':timing,'five_frame_times_s':times")
probe.write_text(s)
for p in [new/'launch-tiles.py',new/'construction-visibility-a01.json']:
 s=p.read_text().replace('construction-visibility-v1','construction-visibility-v2').replace('construction-visibility-a01','construction-visibility-a02');p.write_text(s)
(new/'construction-visibility-a01.json').rename(new/'construction-visibility-a02.json')
hashes={p.relative_to(new).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in new.rglob('*') if p.is_file()}
(new/'source-sha256.json').write_text(json.dumps(hashes,indent=2))
s=(base/'start-construction-visibility.ps1').read_text(encoding='utf-8-sig').replace('construction-visibility-v1','construction-visibility-v2').replace('construction-visibility-a01','construction-visibility-a02').replace('RAVEN-Construction-Visibility-20261019','RAVEN-Construction-Visibility-A02-20261019')
(base/'start-construction-visibility-a02.ps1').write_text(s,encoding='utf-8-sig')
# General finite diagnostic archive: preserves failures as well as completed results.
s=(base/'archive-construction-ground.py').read_text().replace("if not re.fullmatch(r'construction-[a-z]+-a[0-9]+',a.job):", "if not re.fullmatch(r'(construction|fireacademy|factory)-[a-z]+-a[0-9]+',a.job):")
s=s.replace("'construction-ground-v2')", "'construction-ground-v2','construction-visibility-v1','construction-visibility-v2','fireacademy-geometry-v1','factory-geometry-v1')")
(base/'archive-scene-diagnostic.py').write_text(s)
print(len(hashes))
