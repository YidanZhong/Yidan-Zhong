from pathlib import Path
import json,shutil
base=Path('D:/xprogram/.raven-setup-cache');old=base/'construction-post-v1';new=base/'construction-ground-post-v2';new.mkdir(exist_ok=False)
for name in ('postprocess_terrain_tiles.py','resumable_terrain_store.py','targets.unreviewed.json'):
 shutil.copy2(old/name,new/name)
text=(old/'launch-post.py').read_text().replace('construction-post-a01','construction-groundpost-a01').replace('construction-post-v1','construction-ground-post-v2').replace('construction-full-map-20261019','construction-ground-map-20261019').replace('construction-tiles-a01-frames','construction-ground-a01-frames')
(new/'launch-post.py').write_text(text,encoding='utf-8')
helper=(base/'start-construction-post.ps1').read_text().replace('ConstructionPost','ConstructionGroundPost').replace('construction-post-v1','construction-ground-post-v2').replace('construction-post-a01','construction-groundpost-a01')
(base/'start-construction-ground-post.ps1').write_text(helper,encoding='utf-8')
text=(base/'run-construction-batches.py').read_text().replace('construction-batches-20261019','construction-ground-batches-20261019').replace('construction-full-map-20261019','construction-ground-map-20261019').replace('construction-map-a','construction-groundmap-a').replace('construction-tiles-v1','construction-ground-map-v2').replace('construction-post-a01','construction-groundpost-a01').replace('construction-post-v1','construction-ground-post-v2')
# Stop at job boundaries on a diagnostic checkpoint; no automatic second attempt.
needle="    for job in config['map_jobs']:\n        before=read_progress()"
assert needle in text
text=text.replace(needle,"    for job in config['map_jobs']:\n        if (output/'STOP').exists() or (dataset/'STOP').exists():\n            state.update(status='agent_stop_checkpoint_saved', current_job=None);save();sys.exit(0)\n        for filename,digest in config['source_sha256'].items():\n            if hashlib.sha256(Path(filename).read_bytes()).hexdigest()!=digest:\n                raise RuntimeError('Prepared source changed before next batch: '+filename)\n        before=read_progress()")
# SystemExit(0) must retain the intentional stop record, not look like a failure.
text=text.replace('except BaseException as error:', 'except Exception as error:')
(base/'run-construction-ground-batches.py').write_text(text,encoding='utf-8')
helper=(base/'start-construction-batches.ps1').read_text().replace('ConstructionBatches','ConstructionGroundBatches').replace('run-construction-batches.py','run-construction-ground-batches.py').replace('construction-batches.json','construction-ground-batches.json').replace('construction-batches-20261019','construction-ground-batches-20261019')
(base/'start-construction-ground-batches.ps1').write_text(helper,encoding='utf-8')
print('Prepared postprocessor and finite corrected-map queue; not started')
