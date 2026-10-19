from pathlib import Path
import sys,json,hashlib
import numpy as np
root=Path('/mnt/d/xprogram/RAVEN-AirGround-github');sys.path.insert(0,str(root/'benchmark'))
from airground_benchmark.ground_truth import load_target_annotations,_obb_surface_distance_2d
out=root/'runs/arrival_candidates_20261019/RetroNeighborhood-a02'
index=json.loads((out/'index.unreviewed.json').read_text());targets=load_target_annotations(root/'runs/full_map_postprocess_20261019/source/targets.binding-corrected.unreviewed.json');instances={i.instance_id:i for i in targets.instances}
post=root/'runs/full_map_postprocess_20261019/full-post-a01-frames';report=json.loads((post/'report.json').read_text())
for name in ('reach/reach.metadata.yaml','component-report.unreviewed.json'):
 assert hashlib.sha256((post/name).read_bytes()).hexdigest()==report['files'][name]['sha256']
meta=index['metadata'];rows,cols=meta['shape'];res=meta['resolution_m'];ox,oy=meta['origin']['x_m'],meta['origin']['y_m'];checked=0
with np.load(out/'geometric-candidates.unreviewed.npz',allow_pickle=False) as data:
 for e in index['entries']:
  values=data[e['array_key']];assert len(values)==e['cell_count']
  chosen=values[np.linspace(0,len(values)-1,min(1000,len(values)),dtype=int)]
  for cell in chosen:
   row,col=divmod(int(cell),cols);d=_obb_surface_distance_2d(ox+(col+.5)*res,oy+(row+.5)*res,instances[e['instance_id']].obb)
   assert 1.5<=d<=8.,(e['instance_id'],d);checked+=1
result={'scope':'independent scalar-distance verification of actual exported geometry','sampled_cells':checked,'instances':len(index['entries']),'metadata_and_component_report_hashes_verified':True,'all_samples_within_original_window':True,'formal_accepted':False}
(out/'independent-check.json').write_text(json.dumps(result,indent=2));print(result)
