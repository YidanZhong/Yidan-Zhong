from pathlib import Path
import hashlib,json,py_compile
base=Path('D:/xprogram/.raven-setup-cache');remote='D:/RAVEN-4060/setup/'
config={'contract_sha256':'659129eb5189aeeaab7e7525956ce76c409a5215aae2f3359be5785069a749cd','map_jobs':[f'construction-groundmap-a{i:02}' for i in range(2,6)],'source_sha256':{}}
for folder in ('construction-ground-map-v2','construction-ground-post-v2'):
 for path in (base/folder).rglob('*'):
  if path.is_file() and '__pycache__' not in path.parts:
   config['source_sha256'][remote+path.relative_to(base).as_posix()]=hashlib.sha256(path.read_bytes()).hexdigest()
previous=json.loads((base/'construction-batches.json').read_text())
guard=remote+'telemetry-v2/run_windows_probe.py';config['source_sha256'][guard]=previous['source_sha256'][guard]
worker=base/'run-construction-ground-batches.py';config['source_sha256'][remote+worker.name]=hashlib.sha256(worker.read_bytes()).hexdigest()
(base/'construction-ground-batches.json').write_text(json.dumps(config,indent=2),encoding='utf-8')
py_compile.compile(str(worker),doraise=True)
print('Prepared finite queue with',len(config['source_sha256']),'pinned files; four bounded batches then guarded postprocess')
