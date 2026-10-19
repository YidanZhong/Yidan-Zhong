"""Freeze the committed runtime helper for a separate real PhysX check."""
from pathlib import Path
import ast
import hashlib
import json
import shutil

cache = Path('D:/xprogram/.raven-setup-cache')
repo = Path('D:/xprogram/RAVEN-AirGround-github')
source = cache/'construction-portable-v1'
shutil.copytree(cache/'construction-instances-v2', source,
    ignore=shutil.ignore_patterns('__pycache__', 'source-sha256.json', 'expand_static_scene_instances.py', 'seed_instance_colliders.py', 'instance-collision-geometry-matches.json', 'construction-ground-a01.json'))
manifest = repo/'runs/construction_adaptation_20261019/static-instance-collision-manifest.unreviewed.json'
shutil.copy2(manifest, source/manifest.name)
utils = source/'air-stack/simulation/isaac-sim/utils'
for name in ['scene_prep.py', 'scene_physics_profile.py', 'scene_instance_colliders.py']:
    shutil.copy2(repo/'AirStack/simulation/isaac-sim/utils'/name, utils/name)
probe = source/'probe_tiled_terrain.py'
text = probe.read_text(encoding='utf-8')
start = text.index('    from expand_static_scene_instances import expand_instances')
end = text.index("    setup['physics_profile']", start)
text = text[:start]+'''    from scene_instance_colliders import prepare_static_instance_colliders
    inherited = prepare_static_instance_colliders(stage,
        manifest_path=config_path.with_name('static-instance-collision-manifest.unreviewed.json'),
        asset_path=Path(config['asset_path']))
    overrides = inherited['profile_overrides']
    (output/'instance-collision-inheritance.json').write_text(json.dumps(inherited, indent=2))
    setup = {'colliders': scene_prep.add_profiled_colliders(scene_root, profile_overrides=overrides)}
    setup['portable_instance_preparation'] = {k:v for k,v in inherited.items() if k != 'profile_overrides'}
'''+text[end:]
old = '''        ref_reach = build_reach_region(reference.support_mask & ~reference.obstacle_mask, resolution_m=.05)
        tile_reach = build_reach_region(merged.support_mask & ~merged.obstacle_mask, resolution_m=.05)
'''
root_probe = (repo/'scripts/probe_tiled_terrain.py').read_text(encoding='utf-8')
new = root_probe[root_probe.index('        ref_reach ='):root_probe.index('        for name, left, right in')]
assert old in text
text = text.replace(old, new)
needle = "    setup['colliders_sha256'] = sha(output/'colliders.json')"
text = text.replace(needle, needle+'''
    expected_rows = json.loads(config_path.with_name('expected-colliders.json').read_text())
    key = lambda row: row['path']
    if sorted(collider_rows, key=key) != sorted(expected_rows, key=key):
        raise RuntimeError('Portable helper changed the previously measured collider manifest')
    setup['matches_prior_actual_PhysX_collider_manifest'] = True''')
probe.write_text(text, encoding='utf-8')
prior = repo/'runs/construction_adaptation_20261019/instances-a02-evidence/logs/construction-instances-a02-frames/colliders.json'
shutil.copy2(prior, source/'expected-colliders.json')
cfg_path = source/'ground-input.json'
cfg = json.loads(cfg_path.read_text(encoding='utf-8'))
cfg['asset_path'] = 'D:/RAVEN-4060/assets/handover-scenes-20261019/ConstructionSite/ConstructionSite_Export.usd'
cfg['scope'] = 'Committed c01d33b1 helper native-stage real PhysX equivalence probe; no full launch, navigation or human GT approval'
cfg['source_commit'] = 'c01d33b1'
for file in utils.glob('*.py'):
    cfg['source_sha256']['AirStack/simulation/isaac-sim/utils/'+file.name] = hashlib.sha256(file.read_bytes()).hexdigest()
cfg_path.write_text(json.dumps(cfg, indent=2), encoding='utf-8')
for file in [source/'launch-tiles.py', source/'construction-instances-a02.json']:
    text = file.read_text(encoding='utf-8').replace('construction-instances-v2', source.name).replace('construction-instances-a02', 'construction-portable-a01')
    file.write_text(text, encoding='utf-8')
(source/'construction-instances-a02.json').rename(source/'construction-portable-a01.json')
for file in source.rglob('*.py'):
    ast.parse(file.read_text(encoding='utf-8-sig'))
hashes = {p.relative_to(source).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in source.rglob('*') if p.is_file()}
(source/'source-sha256.json').write_text(json.dumps(hashes, indent=2), encoding='utf-8')
starter = (cache/'start-construction-clock.ps1').read_text(encoding='utf-8-sig')
starter = starter.replace('construction-clock-v1', source.name).replace('construction-clock-a01', 'construction-portable-a01').replace('RAVEN-Construction-Clock-20261019', 'RAVEN-Construction-Portable-20261019')
(cache/'start-construction-portable.ps1').write_text(starter, encoding='utf-8-sig')
print(json.dumps({'source':str(source), 'files':len(hashes), 'status':'prepared_not_run', 'scope':cfg['scope']}))
