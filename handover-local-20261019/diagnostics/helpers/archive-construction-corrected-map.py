"""Archive a quiescent corrected Construction map checkpoint with all raw tiles."""
from pathlib import Path
import argparse,hashlib,json,re,zipfile
p=argparse.ArgumentParser();p.add_argument('label',choices=['checkpoint20','complete70']);a=p.parse_args()
base=Path('D:/RAVEN-4060');logs=base/'logs';dataset=logs/'construction-ground-map-20261019'
progress=json.loads((dataset/'progress.json').read_text())
expected=20 if a.label=='checkpoint20' else 70
if progress['completed_tiles']!=expected or progress['contract_sha256']!='659129eb5189aeeaab7e7525956ce76c409a5215aae2f3359be5785069a749cd':
    raise RuntimeError('Unexpected corrected-map checkpoint')
if progress['state']=='sampling':raise RuntimeError('Refusing active sample checkpoint')
directories=[dataset,base/'setup/construction-ground-map-v2',base/'setup/construction-ground-post-v2']
for name in [f'construction-groundmap-a{i:02}' for i in range(1,6)]+['construction-groundpost-a01']:
    job=logs/name
    if not job.exists():continue
    execution=job/'execution.json'
    if not execution.exists():raise RuntimeError('Unfinished guarded job '+name)
    if json.loads(execution.read_text()).get('status')!='completed':raise RuntimeError('Job not complete '+name)
    directories.extend([job,logs/(name+'-frames')])
queue=logs/'construction-ground-batches-20261019'
if queue.exists():
    state=json.loads((queue/'progress.json').read_text())
    if state['status'] in ('running','starting'):raise RuntimeError('Queue still active')
    directories.append(queue)
files={f for d in directories if d.exists() for f in d.rglob('*') if f.is_file() and '__pycache__' not in f.parts}
for filename in ['run-construction-ground-batches.py','construction-ground-batches.json']:
    f=base/'setup'/filename
    if f.exists():files.add(f)
files.update(logs.glob('construction-ground*-launch.log'))
manifest={f.relative_to(base).as_posix():hashlib.sha256(f.read_bytes()).hexdigest() for f in sorted(files)}
output=logs/f'construction-ground-map-{a.label}-evidence.zip'
with zipfile.ZipFile(output,'x',zipfile.ZIP_DEFLATED,6) as z:
    for f in sorted(files):z.write(f,f.relative_to(base).as_posix())
    z.writestr('sha256.json',json.dumps(manifest,indent=2))
print(json.dumps({'archive':str(output),'bytes':output.stat().st_size,'files':len(files),'sha256':hashlib.sha256(output.read_bytes()).hexdigest()}))
