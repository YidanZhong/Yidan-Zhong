"""Read-only USD and candidate-coordinate audit; requires pxr, not SimulationApp."""
from pathlib import Path
import argparse
import hashlib
import json
import math


def main():
    from pxr import Usd, UsdGeom, UsdUtils, Sdf
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scene',type=Path,required=True)
    parser.add_argument('--targets',type=Path,required=True)
    parser.add_argument('--candidates',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if args.output.exists():raise RuntimeError('Refusing to replace an existing preflight')
    sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    targets=json.loads(args.targets.read_text(encoding='utf-8-sig'))
    candidates=json.loads(args.candidates.read_text(encoding='utf-8-sig'))
    if targets['scene_id']!=candidates['scene_id']:raise ValueError('Cross-scene input')
    stage=Usd.Stage.Open(str(args.scene.resolve(strict=True)))
    if not stage:raise RuntimeError('USD stage did not open')
    bounds=UsdGeom.BBoxCache(Usd.TimeCode.Default(),['default','render'])
    by_path={c['prim_path']:c for c in candidates['candidates']}
    layers,assets,unresolved=UsdUtils.ComputeAllDependencies(str(args.scene))
    unresolved_attrs=[]
    for prim in stage.Traverse():
        for attr in prim.GetAttributes():
            if attr.GetTypeName() not in (Sdf.ValueTypeNames.Asset,Sdf.ValueTypeNames.AssetArray):continue
            value=attr.Get()
            values=[value] if isinstance(value,Sdf.AssetPath) else value or []
            for asset in values:
                if asset.path and not asset.resolvedPath:
                    unresolved_attrs.append({'prim':str(prim.GetPath()),'attribute':attr.GetName(),'asset':asset.path})
    rows=[]
    for target in targets['instances']:
        path=target.get('usd_prim_path');row={'instance_id':target['instance_id'],'prim_path':path,
            'human_verified':target['verified'],'status':'unbound'}
        if path:
            prim=stage.GetPrimAtPath(path)
            if not prim:row['status']='missing_prim'
            else:
                box=bounds.ComputeWorldBound(prim).ComputeAlignedRange()
                center=list(box.GetMidpoint());size=list(box.GetSize())
                if box.IsEmpty() or not all(math.isfinite(v) for v in center+size):row['status']='invalid_bounds'
                else:
                    candidate=by_path.get(path)
                    errors=[abs(a-b) for a,b in zip(center+size,candidate['center_xyz_m']+candidate['size_xyz_m'])] if candidate else None
                    row.update(center_xyz_m=center,size_xyz_m=size,candidate_max_error_m=max(errors) if errors else None,
                        status='matches_export' if errors is not None and max(errors)<=.02 else 'candidate_mismatch')
        rows.append(row)
    roots=[];cache=UsdGeom.XformCache()
    for path in ['/World','/World/stage']:
        prim=stage.GetPrimAtPath(path)
        if prim:
            roots.append({'path':path,'local_to_world':[[float(v) for v in row] for row in cache.GetLocalToWorldTransform(prim)]})
    result={'scene_id':targets['scene_id'],'scope':'offline USD dependency/coordinate diagnostic, not PhysX or human approval',
        'usd_version':Usd.GetVersion(),'scene':str(args.scene),'scene_sha256':sha(args.scene),
        'targets_sha256':sha(args.targets),'candidates_sha256':sha(args.candidates),
        'meters_per_unit':UsdGeom.GetStageMetersPerUnit(stage),'up_axis':UsdGeom.GetStageUpAxis(stage),
        'root_transforms':roots,'prim_count':sum(1 for _ in stage.Traverse()),
        'layer_count':len(layers),'asset_count':len(assets),'unresolved':list(unresolved),'targets':rows,
        'unresolved_asset_attributes':unresolved_attrs,
        'formal_accepted':False}
    result['passed']=bool(result['meters_per_unit']==1 and result['up_axis']=='Z' and not unresolved
        and all(r['status'] in ('matches_export','unbound') for r in rows))
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k not in ('targets','root_transforms','unresolved','unresolved_asset_attributes')},indent=2))
    return 0 if result['passed'] else 2


if __name__=='__main__':raise SystemExit(main())
