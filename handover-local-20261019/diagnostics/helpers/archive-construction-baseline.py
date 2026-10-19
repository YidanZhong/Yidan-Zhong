from pathlib import Path
import json,hashlib,zipfile
base=Path('D:/RAVEN-4060');logs=base/'logs';dataset=logs/'construction-full-map-20261019'
progress=json.loads((dataset/'progress.json').read_text());execution=json.loads((logs/'construction-map-a02/execution.json').read_text())
assert progress['state']=='operator_stop_file' and progress['completed_tiles']==36 and execution['exit_code']==0
assert (logs/'construction-batches-20261019/agent-stop-record.json').exists()
dirs=[dataset,logs/'construction-batches-20261019',logs/'construction-map-a02',logs/'construction-map-a02-frames',base/'setup/construction-tiles-v1']
files=[f for directory in dirs for f in directory.rglob('*') if f.is_file() and '__pycache__' not in f.parts]
files += [base/'setup/run-construction-batches.py',base/'setup/construction-batches.json',base/'setup/telemetry-v2/run_windows_probe.py',logs/'construction-map-a02-launch.log']
manifest={f.relative_to(base).as_posix():hashlib.sha256(f.read_bytes()).hexdigest() for f in files}
output=logs/'construction-baseline36-evidence.zip'
with zipfile.ZipFile(output,'x',zipfile.ZIP_DEFLATED,6) as z:
 for f in files:z.write(f,f.relative_to(base).as_posix())
 z.writestr('sha256.json',json.dumps(manifest,indent=2))
print(json.dumps({'bytes':output.stat().st_size,'sha256':hashlib.sha256(output.read_bytes()).hexdigest(),'files':len(files),'raw_tiles_included':True,'formal_accepted':False}))
