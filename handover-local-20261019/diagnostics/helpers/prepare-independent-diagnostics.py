from pathlib import Path
import ast
import hashlib
import json

cache=Path('D:/xprogram/.raven-setup-cache')
remote=Path('D:/RAVEN-4060/setup')
rows=[('construction-portable-v1','construction-portable-a01','launch-tiles.py'),('construction-clock-v1','construction-clock-a01','launch-tiles.py'),('factory-triangle-v1','factory-triangle-a01','launch-tiles.py'),('construction-review-v3','construction-review-a04','launch-review.py')]
config={'scope':'exactly four independent finite diagnostic jobs, one GPU at a time after map release','wait_limit_s':3600,'jobs':[],'source_sha256':{}}
for folder,name,launcher in rows:
    hashes=json.loads((cache/folder/'source-sha256.json').read_text(encoding='utf-8'))
    for file,digest in hashes.items():
        assert hashlib.sha256((cache/folder/file).read_bytes()).hexdigest()==digest
        config['source_sha256'][(remote/folder/file).as_posix()]=digest
    config['jobs'].append({'name':name,'launcher':(remote/folder/launcher).as_posix(),'config':(remote/folder/(name+'.json')).as_posix()})
for file in ['run-independent-diagnostics.py']:
    ast.parse((cache/file).read_text(encoding='utf-8-sig'))
    config['source_sha256'][(remote/file).as_posix()]=hashlib.sha256((cache/file).read_bytes()).hexdigest()
existing=json.loads((cache/'construction-instance-batches.json').read_text(encoding='utf-8'))
guard=(remote/'telemetry-v2/run_windows_probe.py').as_posix()
config['source_sha256'][guard]=existing['source_sha256'][guard]
path=cache/'independent-diagnostics.json'
with path.open('x',encoding='utf-8') as stream:
    json.dump(config,stream,indent=2)
print(json.dumps({'config':str(path),'source_files':len(config['source_sha256']),'jobs':[r[1] for r in rows]}))
