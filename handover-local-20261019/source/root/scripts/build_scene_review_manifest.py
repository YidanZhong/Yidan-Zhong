"""Prepare unapproved scene review views without inventing missing prim bindings."""
from pathlib import Path
import argparse
import hashlib
import json
import math


def build(targets, candidates, bindings, scene_hash):
    scene=targets['scene_id']
    if any(x['scene_id']!=scene for x in (candidates,bindings)):raise ValueError('Cross-scene review input')
    by_path={c['prim_path']:c for c in candidates['candidates']}
    by_id={b['instance_id']:b for b in bindings['bindings']}
    rows=[]
    for target in targets['instances']:
        if target['verified'] or target['ground_reachable']!='unknown':raise ValueError('Expected unreviewed targets')
        if not target['instance_id'].startswith(scene+'.'):raise ValueError('Cross-scene target ID')
        path=target.get('usd_prim_path')
        candidate=by_path[path] if path else None
        center=target['obb']['center_xyz_m'];size=target['obb']['size_xyz_m']
        diag=max(1.,math.sqrt(sum(v*v for v in size)));radius=max(8.,diag*2.2);elevation=max(4.,diag*.75)
        views=[{'eye':[center[0]+radius*math.cos(math.radians(a)),center[1]+radius*math.sin(math.radians(a)),center[2]+elevation],
            'look_at':center,'azimuth_deg':a} for a in (45.,225.)]
        alternatives=[]
        if candidate:
            alternatives=[c for c in candidates['candidates'] if c['prim_path']!=path and math.dist(c['center_xyz_m'],candidate['center_xyz_m'])<.25]
            alternatives.sort(key=lambda c:(math.dist(c['size_xyz_m'],candidate['size_xyz_m']),len(c['prim_path'])))
        rows.append({'target':target,'candidate':candidate,'binding':by_id[target['instance_id']],
            'near_center_alternatives':alternatives[:8],'views':views})
    return {'scene_id':scene,'scene_sha256':scene_hash,'scope':'unapproved static review material; no GT acceptance',
        'target_count':len(rows),'view_count':len(rows)*2,'unbound_count':sum(r['candidate'] is None for r in rows),
        'camera_method':'opposite oblique views around original annotation OBB; unbound targets retain null prim',
        'rows':rows}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('scene','targets','candidates','bindings','output'):parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists():raise RuntimeError('Refusing to overwrite review input')
    read=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
    result=build(read(args.targets),read(args.candidates),read(args.bindings),hashlib.sha256(args.scene.read_bytes()).hexdigest())
    result['source_sha256']={name:hashlib.sha256(getattr(args,name).read_bytes()).hexdigest() for name in ('targets','candidates','bindings')}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='rows'}))


if __name__=='__main__':main()
