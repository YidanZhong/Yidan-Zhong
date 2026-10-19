"""Freeze deterministic YAML export separately from every existing source snapshot."""
from pathlib import Path, PurePosixPath
import ast, hashlib, json, shutil, zipfile
base=Path('D:/xprogram/.raven-setup-cache')
package_root=base/'tile-benchmark-lf-v1';package_root.mkdir(exist_ok=False)
with zipfile.ZipFile(base/'tile-benchmark.zip') as z:
    for name in z.namelist():
        rel=PurePosixPath(name)
        assert not rel.is_absolute() and '..' not in rel.parts and ':' not in name
        p=package_root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(z.read(name))
package=package_root/'airground_benchmark'
maproot=base/'construction-instance-map-v1'
config=json.loads((maproot/'stream-input.json').read_text())
for relative,digest in config['source_sha256'].items():
    if relative.startswith('benchmark/'):
        assert hashlib.sha256((package/relative[10:]).read_bytes()).hexdigest()==digest,relative
p=package/'traversability.py';s=p.read_text(encoding='utf-8')
old='yaml_path.write_text(yaml_text, encoding="utf-8")'
assert s.count(old)==1
p.write_text(s.replace(old,'yaml_path.write_bytes(yaml_text.encode("utf-8"))'),encoding='utf-8',newline='\n')
new_hash=hashlib.sha256(p.read_bytes()).hexdigest()
config['source_sha256']['benchmark/traversability.py']=new_hash
(maproot/'stream-input.json').write_text(json.dumps(config,indent=2),encoding='utf-8')
for p in maproot.glob('construction-instancemap-a*.json'):
    job=json.loads(p.read_text());at=job['args'].index('--benchmark-package')+1
    job['args'][at]='D:/RAVEN-4060/setup/tile-benchmark-lf-v1/airground_benchmark'
    p.write_text(json.dumps(job,indent=2),encoding='utf-8')
new=base/'construction-instance-post-v1';shutil.copytree(base/'construction-ground-post-v2',new)
p=new/'launch-post.py'
s=p.read_text().replace('construction-groundpost-a01','construction-instancepost-a01').replace('construction-ground-post-v2',new.name).replace('construction-ground-map-20261019','construction-instance-map-20261019').replace('construction-ground-a01-frames','construction-instancewindows-a01-frames').replace('setup/tile-benchmark/','setup/tile-benchmark-lf-v1/')
p.write_text(s,encoding='utf-8')
for folder in [maproot,new,package_root]:
    for p in folder.rglob('*.py'):ast.parse(p.read_text(encoding='utf-8-sig'))
    hashes={p.relative_to(folder).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in folder.rglob('*') if p.is_file() and p.name!='source-sha256.json' and '__pycache__' not in p.parts}
    (folder/'source-sha256.json').write_text(json.dumps(hashes,indent=2),encoding='utf-8')
print(json.dumps({'benchmark_traversability_sha256':new_hash,'new_dataset_source_updated_before_launch':True,'postprocess_prepared':str(new),'old_packages_unchanged':True}))
