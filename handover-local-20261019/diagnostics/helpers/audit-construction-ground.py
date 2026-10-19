"""Read-only geometric check of terrain hit paths; never modifies USD or profiles."""
from pathlib import Path
import hashlib,json,sys
import numpy as np
from pxr import Usd,UsdGeom,UsdPhysics,Gf
root=Path('/mnt/d/xprogram/RAVEN-AirGround-github')
sys.path.insert(0,str(root/'AirStack/simulation/isaac-sim/utils'))
from scene_audit import classify_scene_mesh,collision_approximation_for_profile
source=root/'AirStack/scenes/ConstructionSite/ConstructionSite_Export.usd'
stage=Usd.Stage.Open(str(source));cache=UsdGeom.XformCache();bbox=UsdGeom.BBoxCache(Usd.TimeCode.Default(),['default','render','proxy'])
result={'scope':'offline source geometry diagnostic, not PhysX/GT approval','scene_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'stage_units':UsdGeom.GetStageMetersPerUnit(stage),'up_axis':str(UsdGeom.GetStageUpAxis(stage)),'meshes':[],'ground_profile_parent_groups':{},'formal_gt_approved':False}
for prim in stage.Traverse():
 if not prim.IsA(UsdGeom.Mesh):continue
 path=str(prim.GetPath());profile=classify_scene_mesh(path,has_collision=prim.HasAPI(UsdPhysics.CollisionAPI),has_rigid_body=prim.HasAPI(UsdPhysics.RigidBodyAPI))
 if profile=='ground':
  group='/'.join(path.split('/')[:5]);result['ground_profile_parent_groups'][group]=result['ground_profile_parent_groups'].get(group,0)+1
 if '/Land/' not in path:continue
 mesh=UsdGeom.Mesh(prim);points=np.array(mesh.GetPointsAttr().Get(),dtype=np.float64);matrix=np.array(cache.GetLocalToWorldTransform(prim));world=(np.c_[points,np.ones(len(points))]@matrix)[:,:3]
 counts=np.array(mesh.GetFaceVertexCountsAttr().Get());indices=np.array(mesh.GetFaceVertexIndicesAttr().Get());box=bbox.ComputeWorldBound(prim).ComputeAlignedBox()
 row={'path':path,'profile':profile,'runtime_approximation':collision_approximation_for_profile(profile),'authored_approximation':str(UsdPhysics.MeshCollisionAPI(prim).GetApproximationAttr().Get()),'points':len(points),'faces':len(counts),'world_vertex_min':world.min(axis=0).tolist(),'world_vertex_max':world.max(axis=0).tolist(),'authored_bbox_min':list(box.GetMin()),'authored_bbox_max':list(box.GetMax()),'vertical_triangle_intersections':[]}
 triangles=[];offset=0
 for count in counts:
  face=indices[offset:offset+count];offset+=count
  for k in range(1,count-1):triangles.append([face[0],face[k],face[k+1]])
 tri=world[np.asarray(triangles,dtype=int)];a=tri[:,0];b=tri[:,1];c=tri[:,2]
 denom=(b[:,1]-c[:,1])*(a[:,0]-c[:,0])+(c[:,0]-b[:,0])*(a[:,1]-c[:,1]);valid=abs(denom)>1e-12
 for x,y in [(-32.025,-14.025),(-34.025,-16.025),(-49.975,-.025)]:
  u=np.zeros(len(tri));v=u.copy();u[valid]=((b[valid,1]-c[valid,1])*(x-c[valid,0])+(c[valid,0]-b[valid,0])*(y-c[valid,1]))/denom[valid];v[valid]=((c[valid,1]-a[valid,1])*(x-c[valid,0])+(a[valid,0]-c[valid,0])*(y-c[valid,1]))/denom[valid];w=1-u-v
  hit=valid&(u>=-1e-8)&(v>=-1e-8)&(w>=-1e-8);z=u[hit]*a[hit,2]+v[hit]*b[hit,2]+w[hit]*c[hit,2]
  row['vertical_triangle_intersections'].append({'xy_m':[x,y],'triangle_count':int(hit.sum()),'z_m':np.unique(np.round(z,6)).tolist()})
 result['meshes'].append(row)
out=root/'runs/construction_adaptation_20261019/ground-mesh-source-audit.json'
if out.exists():raise RuntimeError('Refusing existing evidence')
out.write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps(result,indent=2))
