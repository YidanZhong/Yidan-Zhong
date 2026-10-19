from pathlib import Path
import json,shutil,hashlib
base=Path('D:/xprogram/.raven-setup-cache');root=Path('D:/xprogram/RAVEN-AirGround-github')
out=base/'construction-ground-v2';out.mkdir(exist_ok=False)
for name in ('probe_windows_scene_render.py','probe_tiled_terrain.py'):
 shutil.copy2(root/'scripts'/name,out/name)
config=json.loads((base/'construction-audit-v1/audit-input.json').read_text())
config['windows']=json.loads((base/'construction-tiles-v1/tile-input.json').read_text())['windows']
config['diagnostic_collision_change']='Only two exact ConstructionSite Land mesh identities now use ground meshSimplification; original USD and target transforms unchanged. New source hash requires fresh full map.'
for relative in list(config['source_sha256']):
 if relative.startswith('AirStack/'):
  source=root/relative;dest=out/'air-stack'/relative[9:];dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,dest)
  config['source_sha256'][relative]=hashlib.sha256(source.read_bytes()).hexdigest()
(out/'ground-input.json').write_text(json.dumps(config,indent=2),encoding='utf-8')
job=json.loads((base/'construction-audit-v1/construction-audit-a01.json').read_text());job['name']='construction-ground-a01'
job['args'][job['args'].index('--tile-validation')+1]='D:/RAVEN-4060/setup/construction-ground-v2/ground-input.json'
job['args'][job['args'].index('--air-stack-root')+1]='D:/RAVEN-4060/setup/construction-ground-v2/air-stack'
(out/'construction-ground-a01.json').write_text(json.dumps(job,indent=2),encoding='utf-8')
launcher=(base/'construction-audit-v1/launch-tiles.py').read_text().replace('construction-audit-v1','construction-ground-v2')
(out/'launch-tiles.py').write_text(launcher,encoding='utf-8')
start=(base/'start-construction-audit.ps1').read_text().replace('ConstructionAudit','ConstructionGround').replace('construction-audit-v1','construction-ground-v2')
(base/'start-construction-ground.ps1').write_text(start,encoding='utf-8')
manifest={p.relative_to(out).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in out.rglob('*') if p.is_file()}
(root/'runs/construction_adaptation_20261019/ground-candidate-source.json').write_text(json.dumps({'status':'prepared_not_run','files':manifest,'raw_assets_modified':False,'formal_accepted':False},indent=2),encoding='utf-8')
print('Prepared isolated',len(manifest),'files; no remote baseline sources modified')
