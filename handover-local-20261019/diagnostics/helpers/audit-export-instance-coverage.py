from pathlib import Path
import collections,gc,hashlib,json,resource
resource.setrlimit(resource.RLIMIT_AS,(8*1024**3,8*1024**3))
from pxr import Usd,UsdGeom,UsdPhysics
root=Path('/mnt/d/xprogram/RAVEN-AirGround-github');rows=[]
for scene in ['RetroNeighborhood','ConstructionSite','FireAcademy','AbandonedFactory']:
 source=root/f'AirStack/scenes/{scene}/{scene}_Export.usd';stage=Usd.Stage.Open(str(source));counts=collections.Counter();examples=[]
 for prim in Usd.PrimRange.Stage(stage,Usd.TraverseInstanceProxies()):
  if not prim.IsA(UsdGeom.Mesh):continue
  counts['meshes']+=1;proxy=prim.IsInstanceProxy();collision=prim.HasAPI(UsdPhysics.CollisionAPI)
  if proxy:counts['proxy_meshes']+=1
  if collision:counts['collision_api_meshes']+=1
  if proxy and not collision and UsdGeom.Imageable(prim).ComputeVisibility()!=UsdGeom.Tokens.invisible:
   counts['visible_proxy_meshes_missing_collision_api']+=1
   if len(examples)<10:examples.append(str(prim.GetPath()))
 rows.append({'scene_id':scene,'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'counts':dict(counts),'examples':examples})
 del stage;gc.collect()
out=root/'runs/additional_scene_preflight_20261019/export-instance-coverage.json'
with out.open('x') as f:json.dump({'scope':'readonly source coverage and known GetChildren traversal risk; not new runtime confirmation','scenes':rows},f,indent=2)
print(json.dumps(rows))
