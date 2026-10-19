"""Read-only validation of immutable committed tiles while the sampler runs."""
from pathlib import Path
import json
import sys
import numpy as np
sys.path.insert(0,r'D:\RAVEN-4060\setup\terrain-stream-v1')
from resumable_terrain_store import TileStore, digest, atomic_json

logs=Path(r'D:\RAVEN-4060\logs')
root=logs/'full-scene-map-20261018'
before=json.loads((logs/'full-map-a02-preflight.json').read_text(encoding='utf-8'))
progress=json.loads((root/'progress.json').read_text(encoding='utf-8'))
assert progress['session']=='full-map-a02-frames'
assert progress['skipped_existing_tiles']==133
assert progress['new_tiles_this_session']>0
for name,record in before['completed_records'].items():
    assert json.loads((root/'tiles'/f'{name}.json').read_text(encoding='utf-8'))==record
    assert digest(root/'tiles'/f'{name}.npz')==record['npz_sha256']
new=[]
for path in sorted((root/'tiles').glob('*.json')):
    if path.stem in before['completed_records']:
        continue
    record=json.loads(path.read_text(encoding='utf-8'))
    assert record['provenance']['session']=='full-map-a02-frames'
    assert record['contract_sha256']==before['contract_sha256']
    assert digest(path.with_suffix('.npz'))==record['npz_sha256']
    with np.load(path.with_suffix('.npz'),allow_pickle=False) as arrays:
        TileStore.validate_arrays(record['tile'],dict(arrays))
    new.append(record)
assert new
result={'status':'passed','preserved_tiles':133,'preserved_records_and_npz_hashes_unchanged':True,
    'new_commits_verified':new,'progress':progress,
    'guard_sha256':digest(Path(r'D:\RAVEN-4060\setup\telemetry-v2\run_windows_probe.py')),
    'generator_sha256':{p.name:digest(p) for p in (Path(r'D:\RAVEN-4060\setup\terrain-stream-v1')/n for n in
        ['probe_resumable_terrain.py','resumable_terrain_store.py','probe_tiled_terrain.py','probe_windows_scene_render.py'])}}
atomic_json(logs/'full-map-a02-recovery-verified.json',result)
print(json.dumps({'status':'passed','preserved_tiles':133,'new_tiles_verified':len(new),
    'completed_tiles':progress['completed_tiles']}))
