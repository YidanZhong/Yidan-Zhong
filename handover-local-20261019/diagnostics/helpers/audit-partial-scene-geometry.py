"""Bounded, read-only geometry coverage for downloaded incomplete scene roots."""
import resource
resource.setrlimit(resource.RLIMIT_AS,(8*1024**3,8*1024**3))
from pathlib import Path
import argparse,hashlib,json,time,math
import numpy as np
from pxr import Usd,UsdGeom

p=argparse.ArgumentParser();p.add_argument('--scene',required=True);p.add_argument('--source',type=Path,required=True);p.add_argument('--sha256',required=True);p.add_argument('--output',type=Path,required=True);args=p.parse_args()
started=time.monotonic();root=Path('/mnt/d/xprogram/RAVEN-AirGround-github')
if args.output.exists():raise FileExistsError(args.output)
def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):h.update(block)
    return h.hexdigest()
if digest(args.source)!=args.sha256:raise ValueError('Downloaded scene root changed')
targets_path=root/f'runs/scene_gt_adaptation_20261017/{args.scene}/targets.unreviewed.json'
targets=json.loads(targets_path.read_text());assert targets['scene_id']==args.scene and all(not i['verified'] for i in targets['instances'])
stage=Usd.Stage.Open(str(args.source));assert stage
mpu=UsdGeom.GetStageMetersPerUnit(stage);axis=str(UsdGeom.GetStageUpAxis(stage))
if mpu!=1. or axis!='Z':raise ValueError('Unexpected units/up axis; requires explicit transform analysis')
cache=UsdGeom.XformCache();rows=[];errors=[];root_rows=[]
for prim in stage.GetPseudoRoot().GetChildren():
    root_rows.append({'path':str(prim.GetPath()),'world_transform':np.asarray(cache.GetLocalToWorldTransform(prim)).tolist()})
for prim in Usd.PrimRange.Stage(stage,Usd.TraverseInstanceProxies()):
    if not prim.IsA(UsdGeom.Mesh):continue
    name=str(prim.GetPath())
    try:
        mesh=UsdGeom.Mesh(prim);points=np.asarray(mesh.GetPointsAttr().Get(),dtype=np.float64)
        counts=np.asarray(mesh.GetFaceVertexCountsAttr().Get(),dtype=np.int64);indices=np.asarray(mesh.GetFaceVertexIndicesAttr().Get(),dtype=np.int64)
        if points.ndim!=2 or points.shape[1]!=3 or not len(points):raise ValueError('Missing/invalid point array')
        if not np.isfinite(points).all():raise ValueError('Nonfinite points')
        if counts.ndim!=1 or indices.ndim!=1 or int(counts.sum())!=len(indices) or np.any(counts<3):raise ValueError('Invalid face counts/indices length')
        if len(indices) and (indices.min()<0 or indices.max()>=len(points)):raise ValueError('Point index out of bounds')
        matrix=np.asarray(cache.GetLocalToWorldTransform(prim));world=points@matrix[:3,:3]+matrix[3,:3]
        if not np.isfinite(world).all():raise ValueError('Nonfinite world geometry')
        rows.append({'path':name,'vertices':len(points),'faces':len(counts),'world_min':world.min(axis=0).tolist(),'world_max':world.max(axis=0).tolist(),
                     'visibility':str(UsdGeom.Imageable(prim).ComputeVisibility()),'is_instance_proxy':prim.IsInstanceProxy(),
                     'prototype_library_path':'/Prototypes/' in name or '/__Prototype_' in name})
    except Exception as exc:errors.append({'path':name,'error':str(exc)})
    if (len(rows)+len(errors))%2000==0:print(json.dumps({'scene':args.scene,'meshes_read':len(rows),'errors':len(errors),'elapsed_s':time.monotonic()-started}),flush=True)
use=[r for r in rows if r['visibility']!='invisible' and not r['prototype_library_path']]
lows=np.asarray([r['world_min'] for r in use]);highs=np.asarray([r['world_max'] for r in use]);candidates=[]
for instance in targets['instances']:
    box=instance['obb'];center=np.asarray(box['center_xyz_m']);half=np.asarray(box['size_xyz_m'])/2;yaw=box['orientation_rpy_rad'][2]
    if any(abs(v)>1e-12 for v in box['orientation_rpy_rad'][:2]):raise ValueError('Nonplanar annotation requires explicit OBB handling')
    ext=np.array([abs(math.cos(yaw))*half[0]+abs(math.sin(yaw))*half[1],abs(math.sin(yaw))*half[0]+abs(math.cos(yaw))*half[1],half[2]])
    overlap=np.all(highs>=center-ext,axis=1)&np.all(lows<=center+ext,axis=1) if use else np.zeros(0,dtype=bool)
    selected=np.flatnonzero(overlap)
    candidates.append({'instance_id':instance['instance_id'],'rough_world_aabb_overlap_count':len(selected),'candidate_paths':[use[i]['path'] for i in selected],
                       'semantic_binding':False,'verified':False})
composition=[str(e) for e in stage.GetCompositionErrors()]
result={'scene_id':args.scene,'scope':'offline geometry only for an incomplete asset package','formal_accepted':False,
        'source':str(args.source),'scene_sha256':args.sha256,'targets_sha256':digest(targets_path),'script_sha256':digest(Path(__file__)),
        'usd_version':Usd.GetVersion(),'meters_per_unit':mpu,'up_axis':axis,'root_transforms':root_rows,
        'mesh_count_read':len(rows),'mesh_errors':errors,'composition_errors':composition,
        'vertex_count':sum(r['vertices'] for r in rows),'face_count':sum(r['faces'] for r in rows),
        'visible_nonlibrary_meshes':len(use),'meshes':rows,'target_aabb_candidates':candidates,
        'status':'geometry_read_completed' if not errors and not composition else 'geometry_errors_require_diagnosis',
        'elapsed_s':time.monotonic()-started,'peak_rss_mib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,
        'limits':{'virtual_memory_gib':8,'parent_wall_timeout_s':180},
        'limitations':['No materials/textures repaired or renderer/PhysX executed.','No coordinate remount or annotation correction applied; raw source-world frame only.','AABB overlap is a coarse geometric cue, not semantic ownership or exact triangle intersection.','Embedded geometry readability does not establish complete scene dependencies or target identity.']}
if digest(args.source)!=args.sha256:raise ValueError('Source changed during audit')
args.output.write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in result.items() if k not in ('meshes','target_aabb_candidates','root_transforms')},indent=2))
raise SystemExit(0 if result['status']=='geometry_read_completed' else 2)
