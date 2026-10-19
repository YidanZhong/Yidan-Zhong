from pathlib import Path
import zipfile
base=Path(r'D:\RAVEN-4060');out=base/'logs/resume-proof-20261018.zip'
with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
    for p in sorted((base/'logs').glob('resume-test-a*'))+[base/'logs/resume-proof-20261018']:
        for f in sorted(p.rglob('*')) if p.is_dir() else [p]:
            if f.is_file():z.write(f,f.relative_to(base/'logs'))
    for p in (base/'setup/terrain-stream-v1').glob('*.py'):z.write(p,'source/'+p.name)
    for n in ['resume-test-a01-input.json','resume-test-a02-input.json','full-map-a01-input.json',
              'resume-test-a01.json','resume-test-a02.json','full-map-a01.json','launch-raven-stream.py','run_windows_probe.py']:
        z.write(base/'setup'/n,'source/'+n)
print(str(out),out.stat().st_size)
