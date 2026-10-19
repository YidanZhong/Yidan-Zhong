"""Prepare a new dataset; launch remains gated on the larger-window real result."""
from pathlib import Path
import ast
import hashlib
import json
import shutil

base = Path('D:/xprogram/.raven-setup-cache')
new = base / 'construction-instance-map-v1'
shutil.copytree(base / 'construction-instancewindows-v1', new, ignore=shutil.ignore_patterns('__pycache__', 'source-sha256.json'))
for name in ('probe_resumable_terrain.py', 'resumable_terrain_store.py'):
    shutil.copy2(base / 'construction-ground-map-v2' / name, new / name)
# A resumption contract must pin the added runtime helpers and the donor table.
p = new / 'probe_resumable_terrain.py'
s = p.read_text(encoding='utf-8').replace("'probe_tiled_terrain.py','probe_windows_scene_render.py')", "'probe_tiled_terrain.py','probe_windows_scene_render.py',\n         'expand_static_scene_instances.py','seed_instance_colliders.py','instance-collision-geometry-matches.json')")
assert 'instance-collision-geometry-matches.json' in s
p.write_text(s, encoding='utf-8')
d = json.loads((new / 'ground-input.json').read_text(encoding='utf-8'))
old = json.loads((base / 'construction-ground-map-v2/stream-input.json').read_text())
d['windows'] = []
d.pop('ray_audit_points_xy_m')
d['mode'] = 'resumable_sampling'
d['stream'] = old['stream']
d['stream']['dataset'] = 'construction-instance-map-20261019'
names = list(d['stream']['generator_sha256']) + ['expand_static_scene_instances.py', 'seed_instance_colliders.py', 'instance-collision-geometry-matches.json']
d['stream']['generator_sha256'] = {name: hashlib.sha256((new / name).read_bytes()).hexdigest() for name in names}
d['scope'] = 'Unreviewed fresh diagnostic map with complete instance collider coverage; no old tiles reused'
(new / 'stream-input.json').write_text(json.dumps(d, indent=2), encoding='utf-8')
p = new / 'launch-tiles.py'
p.write_text(p.read_text().replace('construction-instancewindows-v1', new.name), encoding='utf-8')
job = json.loads((base / 'construction-ground-map-v2/construction-groundmap-a01.json').read_text())
job['args'] = [s.replace('construction-ground-map-v2', new.name) for s in job['args']]
for i in range(1, 6):
    job['name'] = f'construction-instancemap-a{i:02}'
    (new / (job['name'] + '.json')).write_text(json.dumps(job, indent=2), encoding='utf-8')
for p in new.rglob('*.py'):
    ast.parse(p.read_text(encoding='utf-8-sig'))
hashes = {p.relative_to(new).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in new.rglob('*') if p.is_file() and '__pycache__' not in p.parts}
(new / 'source-sha256.json').write_text(json.dumps(hashes, indent=2), encoding='utf-8')
s = (base / 'start-construction-instancewindows.ps1').read_text(encoding='utf-8-sig').replace('construction-instancewindows-v1', new.name).replace('construction-instancewindows-a01', 'construction-instancemap-a01').replace('RAVEN-Construction-InstanceWindows-20261019', 'RAVEN-Construction-InstanceMap-20261019')
gate = """$ravenWindowExecution=Get-Content 'D:\\RAVEN-4060\\logs\\construction-instancewindows-a01\\execution.json' -Raw | ConvertFrom-Json
if($ravenWindowExecution.exit_code -ne 0 -or $ravenWindowExecution.diagnostic_status -ne 'passed'){throw 'Larger real-PhysX windows have not passed'}
$ravenWindowReport=Get-Content 'D:\\RAVEN-4060\\logs\\construction-instancewindows-a01-frames\\tile-validation.json' -Raw | ConvertFrom-Json
if(-not $ravenWindowReport.passed -or $ravenWindowReport.formal_gt_approved){throw 'Window result is invalid'}
"""
s = s.replace("$ravenFolder=", gate + "$ravenFolder=", 1).replace('New-TimeSpan -Minutes 16', 'New-TimeSpan -Minutes 22')
(base / 'start-construction-instancemap.ps1').write_text(s, encoding='utf-8-sig')
print(json.dumps({'prepared_not_started': str(new), 'dataset': d['stream']['dataset'], 'files': len(hashes), 'guards': {'sampling_seconds': d['stream']['budget_seconds'], 'max_new_tiles': d['stream']['max_new_tiles'], 'job_seconds': job['timeout'], 'memory_gib': job['memory_gib']}}))
