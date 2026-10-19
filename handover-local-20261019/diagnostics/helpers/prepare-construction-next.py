from pathlib import Path
import shutil,json,py_compile
c=Path('D:/xprogram/.raven-setup-cache');root=Path('D:/xprogram/RAVEN-AirGround-github')
tiles=c/'construction-tiles-v1'
job=json.loads((tiles/'construction-map-a01.json').read_text())
for index in range(2,7):
 job['name']=f'construction-map-a{index:02}'
 p=tiles/(job['name']+'.json')
 if p.exists():raise FileExistsError(p)
 p.write_text(json.dumps(job,indent=2))
review=c/'construction-review-v1'
j=json.loads((review/'construction-review-a01.json').read_text());j['name']='construction-review-a02'
with (review/'construction-review-a02.json').open('x') as f:json.dump(j,f,indent=2)
post=c/'construction-post-v1';post.mkdir(exist_ok=False)
for name in ['postprocess_terrain_tiles.py','resumable_terrain_store.py']:
 shutil.copy2(root/'scripts'/name,post/name)
shutil.copy2(root/'runs/scene_gt_adaptation_20261017/ConstructionSite/targets.unreviewed.json',post/'targets.unreviewed.json')
source=(c/'launch-full-post.py').read_text().replace('full-post-a01','construction-post-a01').replace('full-post-v1','construction-post-v1').replace("'3600'","'600'").replace('full-scene-map-20261018','construction-full-map-20261019').replace('targets.binding-corrected.unreviewed.json','targets.unreviewed.json').replace('tile-map-a01-frames','construction-tiles-a01-frames')
(post/'launch-post.py').write_text(source,newline='\n')
py_compile.compile(str(post/'launch-post.py'),doraise=True)
ps=(c/'start-construction-map.ps1').read_text().replace('RAVEN-ConstructionMap-20261019','RAVEN-ConstructionPost-20261019').replace('construction-tiles-v1\\launch-tiles.py D:\\RAVEN-4060\\setup\\construction-tiles-v1\\JOBNAME.json','construction-post-v1\\launch-post.py').replace('-Minutes 22','-Minutes 12')
(c/'start-construction-post.ps1').write_text(ps)
print('Prepared map batches a02-a06, one unchanged-budget warm-cache review retry, and 600s guarded postprocess. None started.')
