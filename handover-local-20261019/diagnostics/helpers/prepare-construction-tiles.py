from pathlib import Path
import json,hashlib,shutil
repo=Path('D:/xprogram/RAVEN-AirGround-github');cache=Path('D:/xprogram/.raven-setup-cache');run=repo/'runs/construction_adaptation_20261019'
out=cache/'construction-tiles-v1';out.mkdir(exist_ok=False)
read=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
review=read(run/'review-input.json');anchor=review['rows'][0]
config=read(repo/'runs/tiled_map_validation_20261018/tile-input.json')
config.update(scene_id='ConstructionSite',scene_sha256=review['scene_sha256'],
 targets_sha256=sha(repo/'runs/scene_gt_adaptation_20261017/ConstructionSite/targets.unreviewed.json'),
 corrected_target=anchor['target'],expected_bounds=anchor['candidate'],
 windows=[{'name':'asphalt_roller_context','origin':[-52.,-2.],'rows':160,'cols':160,'resolution_m':.05,'tile_cells':64},
          {'name':'biotoilet_context','origin':[-36.,-18.],'rows':160,'cols':160,'resolution_m':.05,'tile_cells':64}])
(out/'tile-input.json').write_text(json.dumps(config,indent=2))
shutil.copy2(out/'tile-input.json',run/'tile-input.json')
for name in ['probe_windows_scene_render.py','probe_tiled_terrain.py','probe_resumable_terrain.py','resumable_terrain_store.py','postprocess_terrain_tiles.py']:
 shutil.copy2(repo/'scripts'/name,out/name)
launcher=(cache/'drive-audit-v1/launch-drive-audit.py').read_text().replace('drive-audit-v1','construction-tiles-v1')
(out/'launch-tiles.py').write_text(launcher)
job=read(cache/'tile-map-a01.json');job['name']='construction-tiles-a01'
args=job['args'];args[args.index('--scene')+1]='D:/RAVEN-4060/assets/handover-scenes-20261019/ConstructionSite/ConstructionSite_Export.usd'
args[args.index('--tile-validation')+1]='D:/RAVEN-4060/setup/construction-tiles-v1/tile-input.json'
(out/'construction-tiles-a01.json').write_text(json.dumps(job,indent=2))
ps=(cache/'start-drive-audit.ps1').read_text().replace('RAVEN-DriveAudit-20261019','RAVEN-ConstructionTiles-20261019').replace('drive-audit-v1','construction-tiles-v1').replace('launch-drive-audit.py','launch-tiles.py').replace('-Minutes 7','-Minutes 16')
(cache/'start-construction-tiles.ps1').write_text(ps)
print('Prepared; DO NOT launch while review GPU task is running.')
