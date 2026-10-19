from pathlib import Path
import hashlib,json,sys
import numpy as np
root=Path(r'D:\xprogram\RAVEN-AirGround-github');run=root/'runs/resumable_map_20261018'
sys.path.insert(0,str(root/'scripts'))
from resumable_terrain_store import TileStore,FIELDS,digest
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
a,b=[read(run/f'resume-test-a0{i}-frames/stream-report.json') for i in [1,2]]
assert a['completed_tiles']==a['new_tiles_this_session']==2 and not a['sampling_complete']
assert b['completed_tiles']==9 and b['new_tiles_this_session']==7 and b['skipped_existing_tiles']==2 and b['sampling_complete']
for i in [1,2]:
    e=read(run/f'resume-test-a0{i}/execution.json');assert e['exit_code']==0 and e['diagnostic_status']=='passed'
dataset=run/'resume-proof-20261018'
store=TileStore(dataset,read(dataset/'contract.json'))
stitched={key:np.empty((160,160,3) if key=='normal' else (160,160),dtype=dtype) for key,dtype in FIELDS.items()}
first=[]
for record in store.completed.values():
    tile=record['tile'];r0,r1,c0,c1=tile['core']
    if record['provenance']['session']=='resume-test-a01-frames':first.append(record['npz_sha256'])
    else:assert record['provenance']['session']=='resume-test-a02-frames'
    with np.load(dataset/'tiles'/(tile['id']+'.npz')) as z:
        for key in FIELDS:stitched[key][r0:r1,c0:c1]=z[key]
assert len(first)==2
captured=read(run/'resume-test-a01-frames/first-committed-records.json')
assert sorted(first)==sorted(r['npz_sha256'] for r in captured)
for record in captured:assert store.completed[record['tile']['id']]==record
ref=root/'runs/tiled_map_validation_20261018/tile-map-a01-frames/window-1-reference.npz'
diff={}
with np.load(ref) as z:
    for key in FIELDS:
        np.testing.assert_array_equal(stitched[key],z[key])
        diff[key]=int(np.count_nonzero(stitched[key]!=z[key]))
np.savez_compressed(run/'resumed-red-car.npz',**stitched)
evidence={'passed':True,'first_session_tiles':2,'second_session_skipped':2,'second_session_new':7,
    'completed_tiles':9,'reference_cells':25600,'exact_difference_values':diff,
    'reference_sha256':digest(ref),'resumed_npz_sha256':digest(run/'resumed-red-car.npz'),
    'first_session_tile_hashes_preserved':first,'source_pins':read(dataset/'contract.json')['generator_sha256'],
    'scope':'two separate real Isaac processes; graceful bounded stop and restart; corruption/partial-write checks are separate unit tests'}
(run/'resume-verification.json').write_text(json.dumps(evidence,indent=2),encoding='utf-8')
print(json.dumps(evidence,indent=2))
