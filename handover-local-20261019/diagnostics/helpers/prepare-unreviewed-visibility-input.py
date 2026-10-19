"""Select bounded private poses from a complete unreviewed arrival diagnostic."""
from pathlib import Path
import argparse,hashlib,json,math
import numpy as np

parser=argparse.ArgumentParser();parser.add_argument('--candidates',type=Path,required=True);parser.add_argument('--postprocess',type=Path,required=True);parser.add_argument('--review-input',type=Path,required=True);parser.add_argument('--contract',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
if args.output.exists():raise FileExistsError(args.output)
if any((folder/'INVALIDATED.json').exists() for folder in (args.candidates,args.postprocess)):
    raise ValueError('Map or candidate contract invalidated; do not reuse for visibility preparation')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
index=json.loads((args.candidates/'index.unreviewed.json').read_text());post=json.loads((args.postprocess/'report.json').read_text());review=json.loads(args.review_input.read_text());contract=json.loads(args.contract.read_text())
if index['formal_gt_approved'] or post['formal_gt_approved'] or post['status']!='passed':raise ValueError('Expected complete unreviewed diagnostics')
if sha(args.postprocess/'report.json')!=index['input_report_sha256'] or post['contract_sha256']!=index['scene_contract_sha256']:raise ValueError('Map report identity changed')
if review['scene_sha256']!=contract['scene_sha256'] or review['source_sha256']['targets']!=index['input_targets_sha256']:raise ValueError('Scene/target identity differs')
archive=args.candidates/'geometric-candidates.unreviewed.npz'
if sha(archive)!=index['output_sha256']:raise ValueError('Candidate bytes changed')
height_file=args.postprocess/'terrain/height.npy'
if sha(height_file)!=post['files']['terrain/height.npy']['sha256']:raise ValueError('Terrain heights changed')
height=np.load(height_file,mmap_mode='r',allow_pickle=False)
meta=index['metadata'];nrows,ncols=meta['shape'];res=meta['resolution_m'];ox,oy=meta['origin']['x_m'],meta['origin']['y_m']
if height.shape!=(nrows,ncols) or res!=.05:raise ValueError('Wrong grid identity')
review_rows={r['target']['instance_id']:r for r in review['rows']};rows=[]
with np.load(archive,allow_pickle=False) as arrays:
    for entry in index['entries']:
        row=review_rows[entry['instance_id']];target=row['target'];poses=[];skip=None
        if target['verified'] or target['ground_reachable']!='unknown':raise ValueError('Review flags changed')
        if not target['usd_prim_path']:skip='unbound target; no geometry or semantic ownership invented'
        else:
            flat=arrays[entry['array_key']].astype(np.int64);rr,cc=np.divmod(flat,ncols)
            x=ox+(cc+.5)*res;y=oy+(rr+.5)*res;cx,cy=target['obb']['center_xyz_m'][:2]
            center=np.hypot(x-cx,y-cy);angle=np.arctan2(y-cy,x-cx);bins=np.floor((angle+math.pi)/(2*math.pi)*8).astype(int)%8
            allowed=(center>=1.5)&(center<=8.)
            for bucket in range(8):
                candidates=np.flatnonzero(allowed&(bins==bucket))
                if not len(candidates):continue
                picked=candidates[np.argmin(np.abs(center[candidates]-5.))]
                z=float(height[rr[picked],cc[picked]])
                if not math.isfinite(z):raise ValueError('Nonfinite candidate ground height')
                poses.append({'flat_cell':int(flat[picked]),'position_xyz_m':[float(x[picked]),float(y[picked]),z],
                              'yaw_rad':math.atan2(cy-y[picked],cx-x[picked]),'center_distance_m':float(center[picked]),'angular_bin':bucket})
            if not poses:skip='no cells also satisfy the unchanged center-distance visibility gate'
        rows.append({'target':target,'candidate':row['candidate'],'poses':poses,'skip_reason':skip,'source_arrival_cells':entry['cell_count']})
result={'scope':'unreviewed_candidate_visibility_diagnostic','formal_gt_approved':False,'scene_id':index['scene_id'],
        'scene_sha256':contract['scene_sha256'],'map_contract_sha256':index['scene_contract_sha256'],
        'colliders_sha256':contract['setup']['colliders_sha256'],'targets_sha256':index['input_targets_sha256'],
        'source_sha256':{'index':sha(args.candidates/'index.unreviewed.json'),'candidates':sha(archive),'postprocess':sha(args.postprocess/'report.json'),'height':sha(height_file),'review_input':sha(args.review_input)},
        'selection':'at most eight angular bins, nearest center distance to 5m within the original distance gates; not an exhaustive visibility search',
        'rows':rows}
args.output.write_text(json.dumps(result,indent=2));print(json.dumps({'instances':len(rows),'poses':sum(len(r['poses']) for r in rows),'skipped':[(r['target']['instance_id'],r['skip_reason']) for r in rows if r['skip_reason']]}))
