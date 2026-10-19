from pathlib import Path
import json,hashlib
c=Path('D:/xprogram/.raven-setup-cache');root=Path('D:/xprogram/RAVEN-AirGround-github');out=c/'construction-tiles-v1'
read=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
config=read(out/'tile-input.json');roi=read(root/'runs/scene_gt_adaptation_20261017/ConstructionSite/raycast.request.json')['roi']
config['mode']='resumable_sampling';config['windows']=[]
config['stream']={'dataset':'construction-full-map-20261019','budget_seconds':900,'max_new_tiles':20,
 'grid':{'origin_xy_m':roi['origin_xy_m'],'shape':roi['shape'],'resolution_m':.05,'tile_cells':256},
 'generator_sha256':{n:hashlib.sha256((out/n).read_bytes()).hexdigest() for n in ('probe_resumable_terrain.py','resumable_terrain_store.py','probe_tiled_terrain.py','probe_windows_scene_render.py')}}
(out/'stream-input.json').write_text(json.dumps(config,indent=2))
job=read(out/'construction-tiles-a01.json');job.update(name='construction-map-a01',timeout=1200)
job['args'][job['args'].index('--tile-validation')+1]='D:/RAVEN-4060/setup/construction-tiles-v1/stream-input.json'
(out/'construction-map-a01.json').write_text(json.dumps(job,indent=2))
ps=(c/'start-construction-tiles.ps1').read_text().replace('RAVEN-ConstructionTiles-20261019','RAVEN-ConstructionMap-20261019').replace('-Minutes 16','-Minutes 22')
(c/'start-construction-map.ps1').write_text(ps)
print(json.dumps({'prepared_only':True,'cells':roi['shape'][0]*roi['shape'][1],'maximum_new_tiles_per_batch':20,'sampling_budget_s':900,'outer_guard_s':1200}))
