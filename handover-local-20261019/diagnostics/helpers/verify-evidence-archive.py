from pathlib import Path,PurePosixPath
import argparse,hashlib,json,zipfile
p=argparse.ArgumentParser();p.add_argument('archive',type=Path);p.add_argument('sha256');p.add_argument('destination',type=Path);a=p.parse_args()
assert hashlib.sha256(a.archive.read_bytes()).hexdigest()==a.sha256
a.destination.mkdir(exist_ok=True,parents=True)
with zipfile.ZipFile(a.archive) as z:
 assert z.testzip() is None
 manifest=json.loads(z.read('sha256.json'))
 assert len(z.namelist())==len(set(z.namelist()))
 for name,digest in manifest.items():
  rel=PurePosixPath(name);assert not rel.is_absolute() and '..' not in rel.parts and ':' not in name
  target=a.destination/name;assert target.resolve().is_relative_to(a.destination.resolve())
  data=z.read(name);assert hashlib.sha256(data).hexdigest()==digest
  target.parent.mkdir(parents=True,exist_ok=True)
  if target.exists():assert hashlib.sha256(target.read_bytes()).hexdigest()==digest
  else:
   with target.open('xb') as f:f.write(data)
print(json.dumps({'archive':str(a.archive),'sha256':a.sha256,'verified_files':len(manifest),'destination':str(a.destination)}))
