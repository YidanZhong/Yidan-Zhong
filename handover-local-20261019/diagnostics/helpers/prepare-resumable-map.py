from pathlib import Path
import copy,hashlib,json,zipfile
root=Path(r'D:\xprogram\RAVEN-AirGround-github');cache=Path(r'D:\xprogram\.raven-setup-cache')
run=root/'runs/resumable_map_20261018';run.mkdir(exist_ok=True)
source=run/'source';source.mkdir(exist_ok=True)
files=['probe_resumable_terrain.py','resumable_terrain_store.py','probe_tiled_terrain.py','probe_windows_scene_render.py']
hashes={name:hashlib.sha256((root/'scripts'/name).read_bytes()).hexdigest() for name in files}
with zipfile.ZipFile(cache/'terrain-stream-v1.zip','w',zipfile.ZIP_DEFLATED) as z:
    for name in files:
        data=(root/'scripts'/name).read_bytes();(source/name).write_bytes(data);z.writestr(name,data)
def write(p,v):p.write_text(json.dumps(v,indent=2),encoding='utf-8')
base=json.loads((root/'runs/tiled_map_validation_20261018/tile-input.json').read_text())
base.pop('windows');base['mode']='resumable_sampling'
fullroi=json.loads((root/'runs/paper31_review_20261018/mapping-readiness.json').read_text())['roi']
for name,dataset,grid,limit,budget,timeout in [
    ('resume-test-a01','resume-proof-20261018',{'origin_xy_m':[87.,-34.],'shape':[160,160],'resolution_m':.05,'tile_cells':64},2,240,840),
    ('resume-test-a02','resume-proof-20261018',{'origin_xy_m':[87.,-34.],'shape':[160,160],'resolution_m':.05,'tile_cells':64},99,240,840),
    ('full-map-a01','full-scene-map-20261018',{'origin_xy_m':fullroi['origin_xy_m'],'shape':fullroi['shape'],'resolution_m':.05,'tile_cells':256},10000,27000,28800)]:
    config=copy.deepcopy(base);config['stream']={'dataset':dataset,'grid':grid,'max_new_tiles':limit,'budget_seconds':budget,'generator_sha256':hashes}
    write(run/f'{name}-input.json',config)
    job={'name':name,'timeout':timeout,'args':['--graphics-api','vulkan','--defer-stage','--cpu-threads','16','--shader-concurrency','1','--disable-motion-bvh','--async-loads','--physics-only',
        '--scene',r'D:\RAVEN-4060\source\AirStack\scenes\RetroNeighborhood\RetroNeighborhood_Export.usd',
        '--tile-validation',f'D:\\RAVEN-4060\\setup\\{name}-input.json',
        '--air-stack-root',r'D:\RAVEN-4060\source\AirStack',
        '--benchmark-package',r'D:\RAVEN-4060\setup\tile-benchmark\airground_benchmark']}
    if name=='full-map-a01':job['cleanup_task']='RAVEN-Scene1-FullMap-20261018'
    write(cache/f'{name}.json',job);write(source/f'{name}.json',job)
print('Prepared two restart-proof jobs and a bounded full-scene job.')
