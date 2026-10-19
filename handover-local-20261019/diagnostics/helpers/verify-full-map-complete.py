from pathlib import Path
import json,sys,time
sys.path.insert(0,r'D:\RAVEN-4060\setup\terrain-stream-v1')
from resumable_terrain_store import TileStore,dataset_lock,atomic_json
logs=Path(r'D:\RAVEN-4060\logs')
root=logs/'full-scene-map-20261018'
started=time.monotonic()
with dataset_lock(root):
    contract=json.loads((root/'contract.json').read_text(encoding='utf-8'))
    store=TileStore(root,contract)
    progress=json.loads((root/'progress.json').read_text(encoding='utf-8'))
    execution=json.loads((logs/'full-map-a02/execution.json').read_text(encoding='utf-8'))
    assert execution['exit_code']==0 and execution['status']=='completed'
    assert len(store.completed)==len(store.tiles)==527
    assert progress['sampling_complete'] and progress['completed_cells']==32235504
    assert store.contract_hash=='02b4ffca99f0513e8be51037c0456674ab81528691fe410613999a785574a428'
    cells=sum((r['tile']['core'][1]-r['tile']['core'][0])*(r['tile']['core'][3]-r['tile']['core'][2]) for r in store.completed.values())
    assert cells==32235504
    before=json.loads((logs/'full-map-a02-preflight.json').read_text(encoding='utf-8'))
    assert all(store.completed[k]==v for k,v in before['completed_records'].items())
    result={'status':'passed','completed_tiles':527,'completed_cells':cells,
        'contract_sha256':store.contract_hash,'completed_records':store.completed,
        'checks':['contract','complete tile layout','sha256 of all NPZ','8 fields','dtype','shape','finite values','133 pre-resume records unchanged'],
        'elapsed_s':time.monotonic()-started,'sampling_complete':True,
        'full_map_generated':False,'global_postprocess_complete':False,'formal_gt_approved':False}
    atomic_json(logs/'full-map-complete-integrity.json',result)
    print(json.dumps({k:v for k,v in result.items() if k!='completed_records'}))
