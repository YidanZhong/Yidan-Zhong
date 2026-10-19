from pathlib import Path
import zipfile,re
base=Path(r'D:\RAVEN-4060');out=base/'logs/paper31-review-20261018.zip'
with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
 for p in sorted((base/'logs').glob('paper31-review-a*')):
  for item in sorted(p.rglob('*')) if p.is_dir() else [p]:
   if item.is_file():z.write(item,item.relative_to(base/'logs'))
  if (p/'stdout.log').exists():
   for match in re.findall(r'Logging to file: ([^\r\n]+)',(p/'stdout.log').read_text(errors='replace')):
    native=Path(match.strip())
    if native.is_file() and native.resolve().is_relative_to((base/'isaac45').resolve()):z.write(native,'native-logs/'+native.name)
 for name in ['probe_windows_scene_render.py','run_windows_probe.py','launch-raven-probe.py','paper31-review-a01.json','paper31-review-input.json']:
  z.write(base/'setup'/name,'source/'+name)
 z.write(base/'logs/paper31-review-cleanup-20261018.json','paper31-review-cleanup-20261018.json')
print(str(out),out.stat().st_size)
