from pathlib import Path
import ast, hashlib, json, shutil
base = Path('D:/xprogram/.raven-setup-cache')
new = base / 'construction-clock-v1'
shutil.copytree(base / 'construction-instances-v2', new, ignore=shutil.ignore_patterns('__pycache__', 'source-sha256.json'))
shutil.copy2(base / 'probe_physx_clock_stride.py', new / 'probe_physx_clock_stride.py')
p = new / 'probe_tiled_terrain.py'
s = p.read_text(encoding='utf-8')
needle = '    return report\n'
assert s.count(needle) == 1
s = s.replace(needle, "    from probe_physx_clock_stride import probe_clock\n    report['clock_diagnostic'] = probe_clock(world, stage, output)\n    (output/'tile-validation.json').write_text(json.dumps(report,indent=2),encoding='utf-8')\n" + needle)
p.write_text(s, encoding='utf-8')
for p in (new/'launch-tiles.py', new/'construction-instances-a02.json'):
    p.write_text(p.read_text().replace('construction-instances-v2', new.name).replace('construction-instances-a02', 'construction-clock-a01'), encoding='utf-8')
(new/'construction-instances-a02.json').rename(new/'construction-clock-a01.json')
for p in new.rglob('*.py'): ast.parse(p.read_text(encoding='utf-8-sig'))
hashes = {p.relative_to(new).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in new.rglob('*') if p.is_file() and '__pycache__' not in p.parts}
(new/'source-sha256.json').write_text(json.dumps(hashes,indent=2))
s = (base/'start-construction-instances-a02.ps1').read_text(encoding='utf-8-sig').replace('construction-instances-v2',new.name).replace('construction-instances-a02','construction-clock-a01').replace('RAVEN-Construction-Instances-A02-20261019','RAVEN-Construction-Clock-20261019')
(base/'start-construction-clock.ps1').write_text(s,encoding='utf-8-sig')
p=base/'archive-scene-diagnostic.py'
p.write_text(p.read_text(encoding='utf-8').replace("'construction-instances-v2',", "'construction-instances-v2','construction-clock-v1',"),encoding='utf-8')
print(json.dumps({'prepared_not_started':str(new),'pinned_files':len(hashes),'does_not_use_invalidated_map':True}))
