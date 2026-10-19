"""Prepare an unreviewed FireAcademy map using the proven local collision setup."""
from pathlib import Path
import ast, hashlib, json, shutil
base=Path('D:/xprogram/.raven-setup-cache');root=Path('D:/xprogram/RAVEN-AirGround-github')
new=base/'fireacademy-map-v1';shutil.copytree(base/'fireacademy-windows-v1',new,ignore=shutil.ignore_patterns('__pycache__','source-sha256.json'))
for name in ('probe_resumable_terrain.py','resumable_terrain_store.py'):
    shutil.copy2(base/'construction-ground-map-v2'/name,new/name)
p=new/'probe_tiled_terrain.py';s=p.read_text(encoding='utf-8')
s=s.replace("    if config.get('formal_gt_approved') is not False or config.get('mode') == 'resumable_sampling':", "    if config.get('formal_gt_approved') is not False:")
s=s.replace("raise ValueError('Only unapproved bounded geometry diagnostics are allowed')", "raise ValueError('Only unapproved bounded geometry diagnostics are allowed')\n    if streaming and (len(config.get('targets_sha256',''))!=64 or config['stream']['max_new_tiles']>20 or config['stream']['budget_seconds']>900):\n        raise ValueError('Streaming diagnostic needs pinned annotations and original batch bounds')")
p.write_text(s,encoding='utf-8')
d=json.loads((new/'geometry-input.json').read_text());request=json.loads((root/'runs/scene_gt_adaptation_20261017/FireAcademy/raycast.request.json').read_text())
targets=root/'runs/scene_gt_adaptation_20261017/FireAcademy/targets.unreviewed.json'
d.update(windows=[],mode='resumable_sampling',targets_sha256=hashlib.sha256(targets.read_bytes()).hexdigest())
d.pop('ray_audit_points_xy_m')
d['source_sha256']['benchmark/traversability.py']=hashlib.sha256((base/'tile-benchmark-lf-v1/airground_benchmark/traversability.py').read_bytes()).hexdigest()
d['stream']={'dataset':'fireacademy-triangle-map-20261019','budget_seconds':900,'max_new_tiles':20,
    'grid':{k:request['roi'][k] for k in ['origin_xy_m','shape','resolution_m']}}
d['stream']['grid']['tile_cells']=256
d['stream']['generator_sha256']={name:hashlib.sha256((new/name).read_bytes()).hexdigest() for name in ('probe_resumable_terrain.py','resumable_terrain_store.py','probe_tiled_terrain.py','probe_windows_scene_render.py')}
(new/'stream-input.json').write_text(json.dumps(d,indent=2),encoding='utf-8')
p=new/'launch-tiles.py';p.write_text(p.read_text().replace('fireacademy-windows-v1',new.name),encoding='utf-8')
job=json.loads((new/'fireacademy-windows-a01.json').read_text());job.update(timeout=1200,memory_gib=14)
job['args']=[s.replace('fireacademy-windows-v1',new.name).replace('geometry-input.json','stream-input.json').replace('setup/tile-benchmark/','setup/tile-benchmark-lf-v1/') for s in job['args']]
for i in range(1,6):
    job['name']=f'fireacademy-map-a{i:02}';(new/(job['name']+'.json')).write_text(json.dumps(job,indent=2),encoding='utf-8')
post=base/'fireacademy-post-v1';shutil.copytree(base/'construction-instance-post-v1',post)
shutil.copy2(targets,post/'targets.unreviewed.json')
p=post/'launch-post.py';p.write_text(p.read_text().replace('construction-instancepost-a01','fireacademy-post-a01').replace('construction-instance-post-v1',post.name).replace('construction-instance-map-20261019',d['stream']['dataset']).replace('construction-instancewindows-a01-frames','fireacademy-windows-a01-frames'),encoding='utf-8')
for folder in [new,post]:
    for p in folder.rglob('*.py'):ast.parse(p.read_text(encoding='utf-8-sig'))
    hashes={p.relative_to(folder).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in folder.rglob('*') if p.is_file() and p.name!='source-sha256.json' and '__pycache__' not in p.parts}
    (folder/'source-sha256.json').write_text(json.dumps(hashes,indent=2),encoding='utf-8')
s=(base/'start-fireacademy-windows.ps1').read_text(encoding='utf-8-sig').replace('fireacademy-windows-v1',new.name).replace('fireacademy-windows-a01','fireacademy-map-a01').replace('RAVEN-FireAcademy-Windows-20261019','RAVEN-FireAcademy-Map-20261019').replace('New-TimeSpan -Minutes 16','New-TimeSpan -Minutes 22')
gate="""$ravenPassed=Get-Content 'D:\\RAVEN-4060\\logs\\fireacademy-windows-a01\\execution.json' -Raw | ConvertFrom-Json
if($ravenPassed.exit_code -ne 0 -or $ravenPassed.diagnostic_status -ne 'passed'){throw 'FireAcademy larger windows have not passed'}
"""
s=s.replace('$ravenFolder=',gate+'$ravenFolder=',1)
(base/'start-fireacademy-map.ps1').write_text(s,encoding='utf-8-sig')
print(json.dumps({'prepared_not_started':str(new),'grid':d['stream']['grid'],'cells':request['roi']['shape'][0]*request['roi']['shape'][1],'all_13_targets_remain_unreviewed_unbound':True}))
