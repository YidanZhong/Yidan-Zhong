"""Actual USD CPU session-layer profile inspection; never claims PhysX success."""
from pathlib import Path
import argparse
import ast
import collections
import contextlib
import hashlib
import json
import resource
import sys
import time

resource.setrlimit(resource.RLIMIT_AS,(8*1024**3,8*1024**3))
from pxr import Usd, UsdGeom, UsdPhysics

p=argparse.ArgumentParser();p.add_argument('--scene',required=True);args=p.parse_args()
started=time.monotonic()
root=Path('/mnt/d/xprogram/RAVEN-AirGround-github')
previous=root/'runs/partial_scene_geometry_20261019'/f'{args.scene}.json'
prior=json.loads(previous.read_text())
source=Path(prior['source']);expected=prior['scene_sha256']
output=root/'runs/partial_scene_collisions_20261019'/f'{args.scene}.json'
if output.exists():raise FileExistsError(output)
output.parent.mkdir(exist_ok=True)

def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):h.update(block)
    return h.hexdigest()

if sha(source)!=expected:raise ValueError('Root USD differs from geometry audit')
utils=root/'AirStack/simulation/isaac-sim/utils'
sys.path.insert(0,str(utils))
from scene_audit import classify_scene_mesh, collision_approximation_for_profile
tree=ast.parse((utils/'scene_prep.py').read_text())
node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='add_profiled_colliders')
namespace={'UsdGeom':UsdGeom,'UsdPhysics':UsdPhysics,'classify_scene_mesh':classify_scene_mesh,'collision_approximation_for_profile':collision_approximation_for_profile}
exec(compile(ast.Module(body=[node],type_ignores=[]),'committed_scene_prep_function','exec'),namespace)
stage=Usd.Stage.Open(str(source))
if not stage or not stage.GetDefaultPrim():raise ValueError('Source has no valid default prim')
scene_root=stage.GetDefaultPrim()
stage.SetEditTarget(stage.GetSessionLayer())
prior_meshes={r['path']:r for r in prior['meshes']}

def inspect():
    counts=collections.Counter();rows={};large=[];missing=[]
    for prim in Usd.PrimRange(scene_root,Usd.TraverseInstanceProxies()):
        if not prim.IsA(UsdGeom.Mesh):continue
        path=str(prim.GetPath());has_collision=prim.HasAPI(UsdPhysics.CollisionAPI)
        enabled=bool(UsdPhysics.CollisionAPI(prim).GetCollisionEnabledAttr().Get()) if has_collision else False
        role=classify_scene_mesh(path,has_collision=has_collision,has_rigid_body=prim.HasAPI(UsdPhysics.RigidBodyAPI))
        visible=UsdGeom.Imageable(prim).ComputeVisibility()!=UsdGeom.Tokens.invisible
        approximation=str(UsdPhysics.MeshCollisionAPI(prim).GetApproximationAttr().Get()) if prim.HasAPI(UsdPhysics.MeshCollisionAPI) else None
        row={'path':path,'instance_proxy':prim.IsInstanceProxy(),'visible':visible,'has_collision_api':has_collision,'collision_enabled':enabled,'profile':role,'approximation':approximation,'faces_from_prior_audit':prior_meshes.get(path,{}).get('faces')}
        rows[path]=row;counts['meshes']+=1;counts['profile_'+role]+=1
        if row['instance_proxy']:counts['instance_proxy_meshes']+=1
        if enabled:counts['enabled_collision_meshes']+=1
        if not visible and enabled:counts['invisible_enabled_collision_meshes']+=1
        if visible and not enabled:
            counts['visible_missing_collision_'+role]+=1;missing.append(row)
            if row['instance_proxy']:counts['visible_proxy_missing_collision']+=1
        if enabled and approximation in ('convexDecomposition','convexHull') and (row['faces_from_prior_audit'] or 0)>50000:
            large.append(row)
    return {'counts':dict(counts),'visible_without_enabled_collision':missing,'large_convex_candidates':large},rows

before,before_rows=inspect()
with (output.with_suffix('.profile.log')).open('x') as log,contextlib.redirect_stdout(log):
    preparation=namespace['add_profiled_colliders'](scene_root)
after,after_rows=inspect()
if before_rows.keys()!=after_rows.keys():raise RuntimeError('Mesh identities changed')
changes=[{'path':path,'before':before_rows[path],'after':after_rows[path]} for path in before_rows if before_rows[path]!=after_rows[path]]
if sha(source)!=expected:raise RuntimeError('Source file changed')
result={'scene_id':args.scene,'scope':'CPU USD profile application in session layer only; no material restoration, PhysX cooking or GT acceptance',
 'root':str(scene_root.GetPath()),'usd_version':Usd.GetVersion(),'scene_sha256':expected,'source_unchanged':True,'source_saved':False,
 'source_commit':'c01d33b1','source_sha256':{name:sha(utils/name) for name in ['scene_prep.py','scene_audit.py']},
 'prior_geometry_sha256':sha(previous),'geometry_read_errors_from_prior':len(prior['mesh_errors']),
 'before':before,'profile_preparation':preparation,'after':after,'changed_mesh_count':len(changes),'changes':changes,
 'composition_errors':[str(e) for e in stage.GetCompositionErrors()],
 'formal_accepted':False,'elapsed_s':time.monotonic()-started,'peak_rss_mib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,
 'limits':{'virtual_memory_gib':8,'parent_wall_s':180},
 'interpretation':['Visible non-colliding sky/light helpers can be intentional; visibility alone does not justify adding a collider.', 'Name-based ground/static classification is a diagnostic assumption and does not establish physical correctness.', 'Large convex candidates require source triangle versus PhysX comparison before claiming a geometry error.', 'Incomplete material dependencies remain unresolved and block full RGB review.']}
with output.open('x') as stream:json.dump(result,stream,indent=2)
print(json.dumps({'scene_id':args.scene,'before':before['counts'],'after':after['counts'],'large_convex_candidates':len(after['large_convex_candidates']),'changed_mesh_count':len(changes),'peak_rss_mib':result['peak_rss_mib'],'elapsed_s':result['elapsed_s']}))
