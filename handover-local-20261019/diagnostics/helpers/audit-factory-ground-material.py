from pathlib import Path
import json,hashlib
from pxr import Usd,UsdGeom,UsdShade,UsdPhysics
root=Path('/mnt/d/xprogram/RAVEN-AirGround-github');source=root/'AirStack/scenes/AbandonedFactory/AbandonedFactory_Export.usd';stage=Usd.Stage.Open(str(source))
material='/World/Environment/Looks/Ground';references=[];bindings=[]
cache=UsdGeom.BBoxCache(Usd.TimeCode.Default(),['default','render','proxy'])
for prim in stage.Traverse():
 for relationship in prim.GetRelationships():
  targets=[str(p) for p in relationship.GetTargets()]
  if any(t==material or t.startswith(material+'/') for t in targets):
   references.append({'prim':str(prim.GetPath()),'relationship':relationship.GetName(),'targets':targets})
 if prim.IsA(UsdGeom.Gprim):
  bound=UsdShade.MaterialBindingAPI(prim).ComputeBoundMaterial()[0]
  if bound and str(bound.GetPath())==material:
   box=cache.ComputeWorldBound(prim).ComputeAlignedBox()
   bindings.append({'prim':str(prim.GetPath()),'type':prim.GetTypeName(),'visibility':str(UsdGeom.Imageable(prim).ComputeVisibility()),'purpose':str(UsdGeom.Imageable(prim).ComputePurpose()),'collision':prim.HasAPI(UsdPhysics.CollisionAPI),'world_min':list(box.GetMin()),'world_max':list(box.GetMax())})
result={'scope':'offline missing-MDL usage audit, not rendering acceptance','scene_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'material':material,'relationships':references,'effective_geometry_bindings':bindings,'material_exists':bool(stage.GetPrimAtPath(material)),'formal_accepted':False}
out=root/'runs/additional_scene_preflight_20261019/AbandonedFactory-ground-material-usage.json';assert not out.exists();out.write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
