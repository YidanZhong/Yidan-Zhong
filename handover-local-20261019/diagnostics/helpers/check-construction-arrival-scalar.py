from pathlib import Path
import json,math,hashlib
import numpy as np
root=Path('D:/xprogram/RAVEN-AirGround-github')
folder=root/'runs/arrival_candidates_20261019/ConstructionSite-a01'
index=json.loads((folder/'index.unreviewed.json').read_text())
post=root/'runs/construction_adaptation_20261019/corrected-map70-evidence'
targets_path=post/'setup/construction-ground-post-v2/targets.unreviewed.json'
payload=json.loads(targets_path.read_text());targets={x['instance_id']:x for x in payload['instances']}
assert hashlib.sha256(targets_path.read_bytes()).hexdigest()==index['input_targets_sha256']
meta=index['metadata'];ncols=meta['shape'][1];origin=meta['origin'];res=meta['resolution_m'];checks=[]
with np.load(folder/'geometric-candidates.unreviewed.npz',allow_pickle=False) as arrays:
 for row in index['entries']:
  values=arrays[row['array_key']];selected=values[np.linspace(0,len(values)-1,min(1000,len(values)),dtype=int)]
  box=targets[row['instance_id']]['obb'];yaw=box['orientation_rpy_rad'][2];cx,cy=box['center_xyz_m'][:2];sx,sy=box['size_xyz_m'][:2]
  distances=[]
  for flat in selected:
   rr,cc=divmod(int(flat),ncols);x=origin['x_m']+(cc+.5)*res-cx;y=origin['y_m']+(rr+.5)*res-cy
   localx=math.cos(yaw)*x+math.sin(yaw)*y;localy=-math.sin(yaw)*x+math.cos(yaw)*y
   distance=math.hypot(max(abs(localx)-sx/2,0),max(abs(localy)-sy/2,0))
   assert 1.5<=distance<=8, (row['instance_id'],flat,distance)
   distances.append(distance)
  checks.append({'instance_id':row['instance_id'],'samples':len(distances),'minimum_m':min(distances),'maximum_m':max(distances)})
result={'scope':'independent scalar OBB-distance check only; not visibility or formal GT','passed':True,'samples':sum(c['samples'] for c in checks),'checks':checks,'index_sha256':hashlib.sha256((folder/'index.unreviewed.json').read_bytes()).hexdigest()}
with (folder/'independent-check.json').open('x') as f:json.dump(result,f,indent=2)
print(json.dumps({'passed':True,'samples':result['samples']}))
