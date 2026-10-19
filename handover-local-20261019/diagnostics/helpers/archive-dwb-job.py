from pathlib import Path
import argparse,hashlib,json,re,zipfile
p=argparse.ArgumentParser();p.add_argument('job');a=p.parse_args()
if not re.fullmatch(r'full-nav-dwb-a[0-9]{2}',a.job):raise ValueError('Unexpected diagnostic job')
base=Path('D:/RAVEN-4060');logs=base/'logs';out=logs/(a.job+'-evidence.zip')
if not (logs/a.job/'execution.json').exists():raise RuntimeError('Native guard has not finished')
if not (logs/(a.job+'-wsl')/'done.json').exists():raise RuntimeError('WSL peer has not finished')
files=[]
for folder in [logs/a.job,logs/(a.job+'-frames'),logs/(a.job+'-wsl'),base/'setup/full-nav-dwb-v1']:
 files += [f for f in folder.rglob('*') if f.is_file() and '__pycache__' not in f.parts]
for name in [a.job+'-launch.log',a.job+'-wsl.log','ros-bridge-network-20261018.json']:
 if (logs/name).exists():files.append(logs/name)
files += [base/'source/AirStack/simulation/isaac-sim/tools/run_nav2_smoke.py',base/'setup/telemetry-v2/run_windows_probe.py',base/'setup/fastdds-windows.xml',base/'setup/fastdds-wsl.xml']
manifest={f.relative_to(base).as_posix():hashlib.sha256(f.read_bytes()).hexdigest() for f in files}
with zipfile.ZipFile(out,'x',zipfile.ZIP_DEFLATED,6) as z:
 for f in files:z.write(f,f.relative_to(base).as_posix())
 z.writestr('sha256.json',json.dumps(manifest,indent=2))
print(json.dumps({'job':a.job,'bytes':out.stat().st_size,'sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'files':len(files)}))
