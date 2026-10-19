from pathlib import Path
import json,shutil,hashlib
base=Path('D:/xprogram/.raven-setup-cache');root=Path('D:/xprogram/RAVEN-AirGround-github')
out=base/'construction-ground-map-v2';out.mkdir(exist_ok=False)
for name in ('probe_windows_scene_render.py','probe_tiled_terrain.py','probe_resumable_terrain.py','resumable_terrain_store.py'):
 shutil.copy2(root/'scripts'/name,out/name)
shutil.copytree(base/'construction-ground-v2/air-stack',out/'air-stack')
config=json.loads((base/'construction-tiles-v1/stream-input.json').read_text())
ground=json.loads((base/'construction-ground-v2/ground-input.json').read_text())
config['source_sha256']=ground['source_sha256'];config['stream']['dataset']='construction-ground-map-20261019'
config['stream']['generator_sha256']={name:hashlib.sha256((out/name).read_bytes()).hexdigest() for name in config['stream']['generator_sha256']}
(out/'stream-input.json').write_text(json.dumps(config,indent=2),encoding='utf-8')
launcher=(base/'construction-tiles-v1/launch-tiles.py').read_text().replace('construction-tiles-v1','construction-ground-map-v2')
(out/'launch-tiles.py').write_text(launcher,encoding='utf-8')
job=json.loads((base/'construction-tiles-v1/construction-map-a02.json').read_text())
job['args']=[s.replace('construction-tiles-v1','construction-ground-map-v2') for s in job['args']]
job['args'][job['args'].index('--air-stack-root')+1]='D:/RAVEN-4060/setup/construction-ground-map-v2/air-stack'
for index in range(1,6):
 job['name']=f'construction-groundmap-a{index:02}'
 (out/(job['name']+'.json')).write_text(json.dumps(job,indent=2),encoding='utf-8')
start=(base/'start-construction-map.ps1').read_text().replace('ConstructionMap','ConstructionGroundMap').replace('construction-tiles-v1','construction-ground-map-v2')
(base/'start-construction-ground-map.ps1').write_text(start,encoding='utf-8')
manifest={'status':'prepared_pending_real_ground_A_B','original_baseline_preserved':True,'new_dataset':config['stream']['dataset'],'files':{p.relative_to(out).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in out.rglob('*') if p.is_file()},'formal_accepted':False}
(root/'runs/construction_adaptation_20261019/ground-map-source.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
print('Prepared fresh map dataset; not started and no old tiles reused')
