"""Archive only a fully finished, validated new instance-collision map."""
from pathlib import Path
import hashlib
import json
import zipfile

base = Path('D:/RAVEN-4060')
logs = base/'logs'
dataset = logs/'construction-instance-map-20261019'
queue = logs/'construction-instance-batches-20261019'
state = json.loads((queue/'progress.json').read_text())
if state['status'] != 'diagnostic_map_completed_pending_review' or state.get('current_job'):
    raise RuntimeError('Finite sampling/postprocessing queue not completed; no archive created')
progress = json.loads((dataset/'progress.json').read_text())
expected = 'dc30bf4ac8d061ceb549233a18a7a8206b29380bac5d97acebcc205c909e0366'
if progress['completed_tiles'] != 70 or progress['contract_sha256'] != expected or not progress['sampling_complete']:
    raise RuntimeError('New map not complete or contract differs')
post = logs/'construction-instancepost-a01-frames'
report = json.loads((post/'report.json').read_text())
if report['status'] != 'passed' or not report['reference_comparison_passed'] or report['formal_gt_approved']:
    raise RuntimeError('Expected independently compared, unreviewed full map')
directories = [dataset, queue, post, base/'setup/construction-instance-map-v1', base/'setup/construction-instance-post-v1', base/'setup/tile-benchmark-lf-v1', base/'setup/telemetry-v2']
for job in [f'construction-instancemap-a{i:02}' for i in range(1,6)]+['construction-instancepost-a01']:
    directory = logs/job
    if not directory.exists():
        continue
    execution = json.loads((directory/'execution.json').read_text())
    if execution.get('status') != 'completed' or execution.get('exit_code') != 0 or execution.get('diagnostic_status') != 'passed':
        raise RuntimeError('Guarded stage did not pass '+job)
    directories.extend([directory, logs/(job+'-frames')])
files = {p for d in directories for p in d.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.name != 'writer.lock' and not p.name.endswith('.tmp')}
for name in ['run-construction-instance-batches.py','construction-instance-batches.json','wait-initial-instance-map.py','archive-instance-complete70.py']:
    files.add(base/'setup'/name)
files.update(logs.glob('construction-instancemap-*-launch.log'))
files.update(logs.glob('construction-instancepost-*-command.json'))
files.update(logs.glob('construction-instancepost-*-launch.log'))
manifest = {}
output = logs/'construction-instance-map-complete70-evidence.zip'
with zipfile.ZipFile(output, 'x', zipfile.ZIP_DEFLATED, 6) as archive:
    for path in sorted(files):
        data = path.read_bytes()
        name = path.relative_to(base).as_posix()
        manifest[name] = hashlib.sha256(data).hexdigest()
        archive.writestr(name, data)
    archive.writestr('sha256.json', json.dumps(manifest, indent=2))
print(json.dumps({'archive':str(output),'files':len(manifest),'bytes':output.stat().st_size,'sha256':hashlib.sha256(output.read_bytes()).hexdigest()}))
