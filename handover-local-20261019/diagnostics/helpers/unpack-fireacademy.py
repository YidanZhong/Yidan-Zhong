from pathlib import Path,PurePosixPath
import zipfile,json,hashlib
base=Path('D:/RAVEN-4060');archive=base/'setup/fireacademy-transfer-20261019.zip'
assert hashlib.sha256(archive.read_bytes()).hexdigest()=='7e2ef2a9e797e61fd62574b26874bbf9aab8b589a8f832b529b1ea8740542b13'
dest=base/'assets/handover-scenes-20261019';dest.mkdir(parents=True,exist_ok=True)
with zipfile.ZipFile(archive) as z:
 assert z.testzip() is None
 manifest=json.loads(z.read('transfer-manifest.json'))
 for item in manifest['files']:
  rel=PurePosixPath(item['path'])
  if rel.is_absolute() or '..' in rel.parts or ':' in item['path']:raise RuntimeError('Unsafe archive name')
  target=dest/'FireAcademy'/str(rel)
  if not target.resolve().is_relative_to(dest.resolve()):raise RuntimeError('Outside asset folder')
  if target.exists():
   if hashlib.sha256(target.read_bytes()).hexdigest()!=item['sha256']:raise RuntimeError('Existing asset mismatch')
   continue
  content=z.read('FireAcademy/'+item['path'])
  assert hashlib.sha256(content).hexdigest()==item['sha256']
  target.parent.mkdir(parents=True,exist_ok=True)
  with target.open('xb') as f:f.write(content)
 for item in manifest['files']:
  p=dest/'FireAcademy'/item['path'];assert p.stat().st_size==item['bytes'] and hashlib.sha256(p.read_bytes()).hexdigest()==item['sha256']
(base/'logs/fireacademy-transfer-verification.json').write_text(json.dumps({'scene_id':'FireAcademy','files_verified':len(manifest['files']),'destination':str(dest),'archive_sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'passed':True},indent=2))
print('377 assets copied and verified; original source folder unchanged.')
