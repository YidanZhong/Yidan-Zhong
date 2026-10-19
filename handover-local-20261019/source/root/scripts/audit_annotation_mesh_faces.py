"""Read-only face candidates for unbound annotations; never creates approved bindings."""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import math
from pathlib import Path
from typing import Any

import numpy as np


def face_candidates(points: np.ndarray, counts: np.ndarray, indices: np.ndarray,
                    obb: dict[str, Any]) -> dict[str, np.ndarray]:
    """OBB-space broad phase and vertex tests, not semantic ownership or exact clipping."""
    if (counts.ndim != 1 or not len(counts) or np.any(counts < 3)
            or int(counts.sum()) != len(indices) or np.any(indices < 0)
            or np.any(indices >= len(points))):
        raise ValueError('Invalid polygon topology')
    center=np.asarray(obb['center_xyz_m'],dtype=float)
    half=np.asarray(obb['size_xyz_m'],dtype=float)/2
    roll,pitch,yaw=obb['orientation_rpy_rad']
    cr,sr,cp,sp,cy,sy=math.cos(roll),math.sin(roll),math.cos(pitch),math.sin(pitch),math.cos(yaw),math.sin(yaw)
    rotation=np.asarray([[cy*cp,cy*sp*sr-sy*cr,cy*sp*cr+sy*sr],
                         [sy*cp,sy*sp*sr+cy*cr,sy*sp*cr-cy*sr],[-sp,cp*sr,cp*cr]])
    if not np.isfinite(points).all() or not np.isfinite(center).all() or not np.isfinite(rotation).all() or not np.isfinite(half).all() or np.any(half<=0):
        raise ValueError('Invalid point/OBB coordinates')
    local=(points-center)@rotation
    vertices=local[indices]
    offsets=np.r_[0,np.cumsum(counts[:-1])]
    lo=np.minimum.reduceat(vertices,offsets,axis=0)
    hi=np.maximum.reduceat(vertices,offsets,axis=0)
    centroid=np.add.reduceat(vertices,offsets,axis=0)/counts[:,None]
    return {
        'aabb_overlap_broad_phase':np.flatnonzero(np.all((hi>=-half)&(lo<=half),axis=1)),
        'vertex_mean_inside':np.flatnonzero(np.all(np.abs(centroid)<=half,axis=1)),
        'all_vertices_inside':np.flatnonzero(np.all((lo>=-half)&(hi<=half),axis=1)),
    }


def sha(path: Path) -> str:
    digest=hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda:stream.read(4*1024**2),b''):digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    from pxr import Usd,UsdGeom
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('scene','targets','output'):parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--root-prim',default='/World/stage',help='Scene geometry root; excludes unrelated default environment helpers')
    args=parser.parse_args()
    logging.basicConfig(level=logging.INFO,format='%(asctime)s %(message)s')
    targets=json.loads(args.targets.read_text(encoding='utf-8-sig'))
    if any(t['verified'] or t.get('usd_prim_path') or t['ground_reachable']!='unknown' for t in targets['instances']):
        raise ValueError('This audit is restricted to wholly unbound, unapproved annotations')
    if args.output.exists():raise FileExistsError('Existing evidence must remain unchanged')
    stage=Usd.Stage.Open(str(args.scene.resolve(strict=True)))
    if not stage or UsdGeom.GetStageMetersPerUnit(stage)!=1 or UsdGeom.GetStageUpAxis(stage)!='Z':
        raise ValueError('Expected a metre, Z-up stage')
    root_prim=stage.GetPrimAtPath(args.root_prim)
    if not root_prim:raise ValueError('Scene geometry root does not exist')
    args.output.mkdir(parents=True)
    transforms=UsdGeom.XformCache();records=[];files={}
    for mesh_index,prim in enumerate(p for p in Usd.PrimRange(root_prim,Usd.TraverseInstanceProxies()) if p.IsA(UsdGeom.Mesh)):
        mesh=UsdGeom.Mesh(prim)
        points=np.asarray(mesh.GetPointsAttr().Get(),dtype=np.float64)
        counts=np.asarray(mesh.GetFaceVertexCountsAttr().Get(),dtype=np.int64)
        indices=np.asarray(mesh.GetFaceVertexIndicesAttr().Get(),dtype=np.int64)
        if not len(counts):continue
        if len(counts)>5_000_000 or len(points)>10_000_000:raise RuntimeError('Bounded offline mesh audit budget exceeded')
        matrix=np.asarray(transforms.GetLocalToWorldTransform(prim),dtype=float)
        world=points@matrix[:3,:3]+matrix[3,:3]
        # Verify the vectorized row-vector transform against the USD API.
        for index in {0,len(points)//2,len(points)-1}:
            if not np.allclose(world[index],matrix_point(transforms,prim,points[index]),atol=1e-8,rtol=0):
                raise RuntimeError('World transform differs from USD')
        subsets=[]
        for child in prim.GetChildren():
            if child.IsA(UsdGeom.Subset):
                subset=UsdGeom.Subset(child)
                if str(subset.GetElementTypeAttr().Get())=='face':
                    subsets.append((str(child.GetPath()),np.asarray(subset.GetIndicesAttr().Get(),dtype=np.int64),
                                    [str(p) for p in child.GetRelationship('material:binding').GetTargets()]))
        entries=[];arrays={}
        for target_index,target in enumerate(targets['instances']):
            masks=face_candidates(world,counts,indices,target['obb'])
            for key,value in masks.items():arrays[f'target_{target_index:03d}_{key}']=value.astype(np.int64)
            materials=[{'subset':path,'material_bindings':bindings,
                        'candidate_vertex_mean_faces':int(np.intersect1d(faces,masks['vertex_mean_inside']).size)}
                       for path,faces,bindings in subsets]
            entries.append({'instance_id':target['instance_id'],'counts':{key:int(len(v)) for key,v in masks.items()},
                            'material_subsets':[m for m in materials if m['candidate_vertex_mean_faces']]})
        path=args.output/f'mesh-{mesh_index:02d}-candidate-face-ids.npz'
        np.savez_compressed(path,**arrays);files[path.name]={'sha256':sha(path),'bytes':path.stat().st_size}
        records.append({'prim':str(prim.GetPath()),'faces':int(len(counts)),'vertices':int(len(points)),
                        'face_ids_npz':path.name,'targets':entries})
        logging.info('Audited %s: %d faces, %d annotations',prim.GetPath(),len(counts),len(entries))
    report={'scene_id':targets['scene_id'],'status':'candidate_geometry_only_pending_human_ownership',
            'scene_sha256':sha(args.scene),'targets_sha256':sha(args.targets),'source_sha256':sha(Path(__file__)),
            'usd_version':Usd.GetVersion(),'geometry_root':args.root_prim,'meshes':records,'files':files,'formal_accepted':False,
            'limitations':['No USD, target binding, OBB or verified flag changed.',
                           'Broad-phase box overlap is not exact triangle-box intersection.',
                           'Vertex-mean inclusion is geometric, not semantic ownership; polygon centroid is a vertex mean.',
                           'Original annotation error, occlusion and merged topology require real RGB and human review.',
                           'Face numbering is pinned to this exact source USD hash.']}
    (args.output/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    return 0


def matrix_point(cache: Any, prim: Any, point: np.ndarray) -> tuple[float,...]:
    from pxr import Gf
    return tuple(cache.GetLocalToWorldTransform(prim).Transform(Gf.Vec3d(*point)))


if __name__=='__main__':raise SystemExit(main())
