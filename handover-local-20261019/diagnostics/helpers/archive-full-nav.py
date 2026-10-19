from pathlib import Path
import zipfile,re
base=Path(r'D:\RAVEN-4060');target=base/'logs/full-nav-20261019.zip'
with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED) as z:
 for path in sorted((base/'logs').glob('full-nav-a*')):
  for item in sorted(path.rglob('*')) if path.is_dir() else [path]:
   if item.is_file():z.write(item,item.relative_to(base/'logs'))
  stdout=path/'stdout.log'
  if stdout.is_file():
   for match in re.findall(r'Logging to file: ([^\r\n]+)',stdout.read_text(errors='replace')):
    native=Path(match.strip())
    if native.is_file() and native.resolve().is_relative_to((base/'isaac45').resolve()):z.write(native,'native-logs/'+native.name)
 for version in ['full-nav-v1','full-nav-v2']:
  for item in (base/'setup'/version).glob('*'):
   if item.is_file():z.write(item,('source/' if version=='full-nav-v2' else 'source-a01/')+item.name)
 z.write(base/'source/AirStack/simulation/isaac-sim/tools/run_nav2_smoke.py','source/run_nav2_smoke.py')
 for item in [base/'setup/telemetry-v2/run_windows_probe.py',base/'setup/fastdds-windows.xml',base/'setup/fastdds-wsl.xml']:
  z.write(item,'source/'+item.name)
 for name in ['ros-bridge-network-20261018.json','full-nav-cleanup-20261019.json']:
  item=base/'logs'/name
  if item.is_file():z.write(item,name)
print(target,target.stat().st_size)
