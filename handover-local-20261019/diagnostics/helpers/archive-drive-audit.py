from pathlib import Path
import json,hashlib,zipfile
base=Path('D:/RAVEN-4060');out=base/'logs/drive-audit-evidence-20261019.zip'
if out.exists():raise RuntimeError('Refusing overwrite')
files=[]
for name in ['drive-audit-a01','drive-audit-a02','drive-audit-a03']:
 for folder in [base/'logs'/name,base/'logs'/(name+'-frames')]:
  if folder.exists():files.extend(p for p in folder.rglob('*') if p.is_file())
 p=base/'logs'/(name+'-launch.log')
 if p.exists():files.append(p)
files.extend(p for p in (base/'setup/drive-audit-v1').rglob('*') if p.is_file() and '__pycache__' not in str(p))
files.extend([base/'logs/drive-asset-audit.json',base/'setup/audit-drive-asset.py'])
files.extend([base/'isaac45/exts/isaacsim.core.prims/isaacsim/core/prims/impl/single_articulation.py',base/'isaac45/exts/isaacsim.core.prims/isaacsim/core/prims/impl/articulation.py'])
manifest={str(p.relative_to(base)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
with zipfile.ZipFile(out,'x',zipfile.ZIP_DEFLATED,6) as z:
 for p in files:z.write(p,str(p.relative_to(base)))
 z.writestr('sha256.json',json.dumps(manifest,indent=2))
print(json.dumps({'archive':str(out),'bytes':out.stat().st_size,'files':len(files),'sha256':hashlib.sha256(out.read_bytes()).hexdigest()}))
