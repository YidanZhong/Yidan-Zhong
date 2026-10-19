from pathlib import Path
import hashlib
import json

root=Path(r'D:\xprogram\RAVEN-AirGround-github')
cache=Path(r'D:\xprogram\.raven-setup-cache')
run=root/'runs/resumable_map_20261018'
recovery=run/'recovery-20261019'
recovery.mkdir(exist_ok=True)
job=json.loads((run/'source/full-map-a01.json').read_text(encoding='utf-8-sig'))
job['name']='full-map-a02'
job.pop('cleanup_task',None)
# Preserve the exact sampler input and frozen generation code.
(recovery/'full-map-a02.json').write_text(json.dumps(job,indent=2),encoding='utf-8')
launcher=(cache/'launch-raven-stream.py').read_text(encoding='utf-8')
launcher=launcher.replace("base/'setup/run_windows_probe.py'", "base/'setup/telemetry-v2/run_windows_probe.py'")
(recovery/'launch-raven-stream-v2.py').write_text(launcher,encoding='utf-8')
starter=(cache/'start-raven-stream.ps1').read_text(encoding='utf-8-sig')
starter=starter.replace('full-map-a01','full-map-a02').replace('launch-raven-stream.py','launch-raven-stream-v2.py')
(cache/'start-raven-stream-v2.ps1').write_text(starter,encoding='utf-8-sig')
for name,source in [('run_windows_probe.py',root/'scripts/run_windows_probe.py'),
                    ('test_windows_probe_telemetry.py',root/'tests/test_windows_probe_telemetry.py')]:
    (recovery/name).write_bytes(source.read_bytes())
(recovery/'check-existing-tiles.py').write_text('''from pathlib import Path
import json,sys,time
sys.path.insert(0,r'D:\\RAVEN-4060\\setup\\terrain-stream-v1')
from resumable_terrain_store import TileStore,dataset_lock,atomic_json
root=Path(r'D:\\RAVEN-4060\\logs\\full-scene-map-20261018')
start=time.monotonic()
with dataset_lock(root):
    contract=json.loads((root/'contract.json').read_text(encoding='utf-8'))
    store=TileStore(root,contract)
    result={'status':'passed','completed_tiles':len(store.completed),'total_tiles':len(store.tiles),
        'contract_sha256':store.contract_hash,'completed_records':store.completed,
        'checks':['contract','geometry','sha256','8 fields','dtype','shape','finite values'],
        'elapsed_s':time.monotonic()-start}
    assert len(store.completed)==133
    assert store.contract_hash=='02b4ffca99f0513e8be51037c0456674ab81528691fe410613999a785574a428'
    atomic_json(Path(r'D:\\RAVEN-4060\\logs\\full-map-a02-preflight.json'),result)
    print(json.dumps({k:v for k,v in result.items() if k!='completed_records'}))
''',encoding='utf-8')
print(recovery)
