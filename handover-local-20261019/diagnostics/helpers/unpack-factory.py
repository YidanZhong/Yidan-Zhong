from pathlib import Path,PurePosixPath
import zipfile,json,hashlib
base=Path('D:/RAVEN-4060');archive=base/'setup/factory-transfer-20261019.zip'
assert hashlib.sha256(archive.read_bytes()).hexdigest()=='3b1ebbc0c744e215397029b649a93cdb2d1f6000757760b694935417cd0f0da4'
dest=base/'assets/handover-scenes-20261019';dest.mkdir(parents=True,exist_ok=True)
with zipfile.ZipFile(archive) as z:
 assert z.testzip() is None
 manifest=json.loads(z.read('transfer-manifest.json'))
 for item in manifest['files']:
  rel=PurePosixPath(item['path'])
  if rel.is_absolute() or '..' in rel.parts or ':' in item['path']:raise RuntimeError('Unsafe archive name')
  target=dest/'AbandonedFactory'/str(rel)
  if not target.resolve().is_relative_to(dest.resolve()):raise RuntimeError('Outside asset folder')
  if target.exists():
   if hashlib.sha256(target.read_bytes()).hexdigest()!=item['sha256']:raise RuntimeError('Existing asset mismatch')
   continue
  content=z.read('AbandonedFactory/'+item['path'])
  assert hashlib.sha256(content).hexdigest()==item['sha256']
  target.parent.mkdir(parents=True,exist_ok=True)
  with target.open('xb') as f:f.write(content)
 for item in manifest['files']:
  p=dest/'AbandonedFactory'/item['path'];assert p.stat().st_size==item['bytes'] and hashlib.sha256(p.read_bytes()).hexdigest()==item['sha256']
(base/'logs/factory-transfer-verification.json').write_text(json.dumps({'scene_id':'AbandonedFactory','files_verified':len(manifest['files']),'destination':str(dest),'archive_sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'passed':True},indent=2))
print('199 assets copied and verified; original source folder unchanged.')

