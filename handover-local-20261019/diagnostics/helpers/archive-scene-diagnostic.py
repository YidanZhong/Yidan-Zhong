from pathlib import Path
import argparse,hashlib,json,re,zipfile
p=argparse.ArgumentParser();p.add_argument('job');p.add_argument('source');a=p.parse_args()
if not re.fullmatch(r'(construction|fireacademy|factory)-[a-z]+-a[0-9]+',a.job):raise ValueError('Unexpected job')
if a.source not in ('construction-review-v1','construction-review-v2','construction-review-v3','construction-tiles-v1','construction-audit-v1','construction-ground-v2','construction-instances-v1','construction-instances-v2','construction-clock-v1','construction-instancewindows-v1','construction-visibility-v1','construction-visibility-v2','construction-visibility-v3','construction-visibility-v4','construction-visibility-v5','fireacademy-geometry-v1','fireacademy-triangle-v1','fireacademy-triangle-v2','fireacademy-windows-v1','factory-geometry-v1','factory-triangle-v1'):raise ValueError('Unexpected source snapshot')
base=Path('D:/RAVEN-4060');logs=base/'logs';output=logs/(a.job+'-evidence.zip')
if not (logs/a.job/'execution.json').exists() and not (a.job=='fireacademy-triangle-a02' and (logs/a.job/'operator-stop.json').exists() and (logs/a.job/'operator-stop-observation.json').exists()):raise RuntimeError('Guarded process not completed or explicitly recorded as stopped')
files=[]
for directory in [logs/a.job,logs/(a.job+'-frames'),base/'setup'/a.source]:
 if directory.exists():files.extend(f for f in directory.rglob('*') if f.is_file() and '__pycache__' not in f.parts)
for name in [a.job+'-launch.log','construction-transfer-verification.json','construction-static-preflight-a02.json','construction-static-preflight-a02.log','construction-binding-proposals-with-proxies.json']:
 if (logs/name).exists():files.append(logs/name)
manifest={f.relative_to(base).as_posix():hashlib.sha256(f.read_bytes()).hexdigest() for f in files}
with zipfile.ZipFile(output,'x',zipfile.ZIP_DEFLATED,6) as z:
 for f in files:z.write(f,f.relative_to(base).as_posix())
 z.writestr('sha256.json',json.dumps(manifest,indent=2))
print(json.dumps({'archive':str(output),'bytes':output.stat().st_size,'sha256':hashlib.sha256(output.read_bytes()).hexdigest()}))



