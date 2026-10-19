from pathlib import Path,PurePosixPath
import json,hashlib,zipfile,datetime
root=Path('D:/xprogram/RAVEN-AirGround-github');run=root/'runs/construction_adaptation_20261019'
archive=run/'construction-audit-a01-evidence.zip';digest=hashlib.sha256(archive.read_bytes()).hexdigest()
assert digest=='feb1067b6df6efa4388f0b769ba4529d8f0925065c76e9bbbcc9becf56b64224'
dest=run/'raw-ray-audit-evidence';dest.mkdir(exist_ok=True)
with zipfile.ZipFile(archive) as z:
 assert z.testzip() is None
 manifest=json.loads(z.read('sha256.json'))
 for name,sha in manifest.items():
  rel=PurePosixPath(name);assert not rel.is_absolute() and '..' not in rel.parts and ':' not in name
  content=z.read(name);assert hashlib.sha256(content).hexdigest()==sha
  path=dest/name;path.parent.mkdir(exist_ok=True,parents=True)
  if path.exists():assert hashlib.sha256(path.read_bytes()).hexdigest()==sha
  else:path.write_bytes(content)
raw=json.loads((dest/'logs/construction-audit-a01-frames/raw-ray-audit.json').read_text())
execution=json.loads((dest/'logs/construction-audit-a01/execution.json').read_text())
assert execution['exit_code']==0 and execution['diagnostic_status']=='passed'
report={'checked_at':datetime.datetime.now().astimezone().isoformat(),'source_archive_sha256':digest,'files_verified':len(manifest),'execution':execution,'raw':raw,'formal_accepted':False,'finding':'At two blocked-context points, downward hit Landscape2 at 1.210654 m and absolute obstacle ray starts inside at z=.05. Offline visual triangles at identical XY are z=-.3. Existing static_obstacle convexDecomposition produces filled concavity, not a visual terrain rise. Candidate exact ground classification needs independent real validation and a new map contract.'}
(root/'docs/development/ugv-ogn/construction-ground-diagnostic-20261019.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print('Verified',len(manifest),'files and actual ray evidence')
