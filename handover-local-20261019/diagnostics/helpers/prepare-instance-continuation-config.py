from pathlib import Path
import hashlib,json
base=Path('D:/xprogram/.raven-setup-cache');remote='D:/RAVEN-4060/setup/'
config={'contract_sha256':'dc30bf4ac8d061ceb549233a18a7a8206b29380bac5d97acebcc205c909e0366',
        'map_jobs':[f'construction-instancemap-a{i:02}' for i in range(2,6)],'source_sha256':{}}
for folder in ['construction-instance-map-v1','construction-instance-post-v1','tile-benchmark-lf-v1']:
    for p in (base/folder).rglob('*'):
        if p.is_file() and '__pycache__' not in p.parts:
            config['source_sha256'][remote+p.relative_to(base).as_posix()]=hashlib.sha256(p.read_bytes()).hexdigest()
old=json.loads((base/'construction-ground-batches.json').read_text())
guard=remote+'telemetry-v2/run_windows_probe.py';config['source_sha256'][guard]=old['source_sha256'][guard]
worker=base/'run-construction-instance-batches.py';config['source_sha256'][remote+worker.name]=hashlib.sha256(worker.read_bytes()).hexdigest()
(base/'construction-instance-batches.json').write_text(json.dumps(config,indent=2),encoding='utf-8')
print(json.dumps({'pinned_files':len(config['source_sha256']),'measured_contract':config['contract_sha256'],'maximum_remaining_batches':4}))
