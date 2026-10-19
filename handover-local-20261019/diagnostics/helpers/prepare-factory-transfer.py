from pathlib import Path
import json,hashlib,zipfile,time
repo=Path('D:/xprogram/RAVEN-AirGround-github');scene=repo/'AirStack/scenes/AbandonedFactory'
out=Path('D:/xprogram/.raven-setup-cache/factory-transfer-20261019.zip')
run=repo/'runs/factory_adaptation_20261019';run.mkdir(exist_ok=True)
if out.exists():raise RuntimeError('Existing transfer archive: inspect instead of overwrite')
files=[p for p in scene.rglob('*') if p.is_file() and p.name not in ('.gitignore','.gitkeep')]
manifest={'scene_id':'AbandonedFactory','source':str(scene),'files':[],'formal_accepted':False}
with zipfile.ZipFile(out,'x',zipfile.ZIP_DEFLATED,compresslevel=1) as z:
 for p in files:
  relative=p.relative_to(scene).as_posix();data=p.read_bytes()
  manifest['files'].append({'path':relative,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()})
  z.writestr('AbandonedFactory/'+relative,data)
 z.writestr('transfer-manifest.json',json.dumps(manifest,indent=2))
manifest['archive']={'file':str(out),'bytes':out.stat().st_size,'sha256':hashlib.sha256(out.read_bytes()).hexdigest()}
(run/'transfer-manifest.json').write_text(json.dumps(manifest,indent=2))
print(json.dumps({'file_count':len(files),'archive':manifest['archive']}),flush=True)

