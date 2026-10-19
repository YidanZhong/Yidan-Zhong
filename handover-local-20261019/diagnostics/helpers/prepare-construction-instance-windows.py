"""Freeze a larger real-PhysX verification without changing the tested geometry."""
from pathlib import Path
import ast
import hashlib
import json
import shutil

base = Path('D:/xprogram/.raven-setup-cache')
old = base / 'construction-instances-v2'
new = base / 'construction-instancewindows-v1'
shutil.copytree(old, new, ignore=shutil.ignore_patterns('__pycache__', 'source-sha256.json'))
for p in (new / 'launch-tiles.py', new / 'construction-instances-a02.json'):
    s = p.read_text(encoding='utf-8').replace('construction-instances-v2', new.name).replace('construction-instances-a02', 'construction-instancewindows-a01')
    p.write_text(s, encoding='utf-8')
(new / 'construction-instances-a02.json').rename(new / 'construction-instancewindows-a01.json')
p = new / 'ground-input.json'
d = json.loads(p.read_text(encoding='utf-8'))
d['windows'] = json.loads((base / 'construction-ground-v2/ground-input.json').read_text(encoding='utf-8'))['windows']
d['diagnostic_collision_change'] = 'Runtime-only expansion of 5075 static instances and collision inheritance from exact geometry-matched existing colliders; two previously validated terrain profiles retained. No original asset or GT approval changes.'
d['scope'] = 'Unreviewed 51200-cell collision coverage and tiled equivalence diagnostic. Old full map remains INVALIDATED.'
p.write_text(json.dumps(d, indent=2), encoding='utf-8')
for p in new.rglob('*.py'):
    ast.parse(p.read_text(encoding='utf-8-sig'))
hashes = {p.relative_to(new).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in new.rglob('*') if p.is_file() and '__pycache__' not in p.parts}
(new / 'source-sha256.json').write_text(json.dumps(hashes, indent=2), encoding='utf-8')
s = (base / 'start-construction-instances-a02.ps1').read_text(encoding='utf-8-sig').replace('construction-instances-v2', new.name).replace('construction-instances-a02', 'construction-instancewindows-a01').replace('RAVEN-Construction-Instances-A02-20261019', 'RAVEN-Construction-InstanceWindows-20261019')
(base / 'start-construction-instancewindows.ps1').write_text(s, encoding='utf-8-sig')
p = base / 'archive-scene-diagnostic.py'
s = p.read_text(encoding='utf-8-sig').replace("'construction-instances-v2',", "'construction-instances-v2','construction-instancewindows-v1',")
p.write_text(s, encoding='utf-8')
print(json.dumps({'source': str(new), 'files': len(hashes), 'reference_cells': sum(w['rows']*w['cols'] for w in d['windows'])}))
