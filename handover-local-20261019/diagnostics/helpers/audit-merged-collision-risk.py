from pathlib import Path
import sys,json,hashlib
import numpy as np
from pxr import Usd,UsdGeom,UsdPhysics
root=Path('/mnt/d/xprogram/RAVEN-AirGround-github');sys.path.insert(0,str(root/'AirStack/simulation/isaac-sim/utils'))
from scene_audit import classify_scene_mesh,collision_approximation_for_profile
results=[]
for scene in ('FireAcademy','AbandonedFactory'):
 source=root/f'AirStack/scenes/{scene}/{scene}_Export.usd';stage=Usd.Stage.Open(str(source));xforms=UsdGeom.XformCache();meshes=[]
 for prim in Usd.PrimRange(stage.GetPrimAtPath('/World/stage'),Usd.TraverseInstanceProxies()):
  if not prim.IsA(UsdGeom.Mesh) or '/Prototypes/' in str(prim.GetPath()):continue
  mesh=UsdGeom.Mesh(prim);points=np.asarray(mesh.GetPointsAttr().Get(),dtype=np.float64)
  if not len(points):continue
  matrix=np.asarray(xforms.GetLocalToWorldTransform(prim));world=points@matrix[:3,:3]+matrix[3,:3]
  low,high=world.min(axis=0),world.max(axis=0);size=high-low;faces=len(mesh.GetFaceVertexCountsAttr().Get());path=str(prim.GetPath())
  profile=classify_scene_mesh(path,has_collision=prim.HasAPI(UsdPhysics.CollisionAPI),has_rigid_body=prim.HasAPI(UsdPhysics.RigidBodyAPI))
  meshes.append({'prim':path,'faces':faces,'world_min':low.tolist(),'world_max':high.tolist(),'size_xyz_m':size.tolist(),'profile':profile,'expected_runtime_approximation':collision_approximation_for_profile(profile),'visible':str(UsdGeom.Imageable(prim).ComputeVisibility()),'wide_complex_convex_candidate':profile=='static_obstacle' and faces>50000 and max(size[:2])>20,'thin_wide_surface_candidate':max(size[:2])>10 and size[2]<.2})
 result={'scene':scene,'scope':'offline collider-risk candidates; not proof of actual cooked collision error','scene_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'mesh_count_excluding_prototypes':len(meshes),'meshes':sorted(meshes,key=lambda m:m['faces'],reverse=True),'formal_accepted':False}
 for entry in meshes:
  for key in ('wide_complex_convex_candidate','thin_wide_surface_candidate'):entry[key]=bool(entry[key])
 out=root/f'runs/additional_scene_preflight_20261019/{scene}-collision-risk.json';assert not out.exists();out.write_text(json.dumps(result,indent=2));results.append({'scene':scene,'mesh_count':len(meshes),'wide_complex_convex_candidates':[m for m in result['meshes'] if m['wide_complex_convex_candidate']]})
print(json.dumps(results,indent=2))
