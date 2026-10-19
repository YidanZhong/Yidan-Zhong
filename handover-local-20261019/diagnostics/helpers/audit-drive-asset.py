from pathlib import Path
from pxr import Usd,UsdGeom,UsdPhysics
import json,hashlib
base=Path('D:/RAVEN-4060');asset=base/'source/AirStack/simulation/isaac-sim/assets/robots/jackal_airground.usda'
s=Usd.Stage.Open(str(asset));xforms=UsdGeom.XformCache();bbox=UsdGeom.BBoxCache(Usd.TimeCode.Default(),['default','render','proxy','guide'],False,True)
baseprim=s.GetPrimAtPath('/jackal/base_link');basepos=list(xforms.GetLocalToWorldTransform(baseprim).ExtractTranslation());items=[]
for prim in s.Traverse():
 if prim.HasAPI(UsdPhysics.CollisionAPI) or prim.HasAPI(UsdPhysics.RigidBodyAPI) or prim.IsA(UsdPhysics.RevoluteJoint):
  attrs={a.GetName():str(a.Get()) for a in prim.GetAttributes() if a.HasAuthoredValueOpinion()}
  bound=bbox.ComputeWorldBound(prim).ComputeAlignedRange()
  item={'path':str(prim.GetPath()),'type':prim.GetTypeName(),'collision':prim.HasAPI(UsdPhysics.CollisionAPI),'rigid':prim.HasAPI(UsdPhysics.RigidBodyAPI),'world_translation':list(xforms.GetLocalToWorldTransform(prim).ExtractTranslation()),'bbox_min':list(bound.GetMin()),'bbox_max':list(bound.GetMax()),'attributes':attrs}
  if prim.IsA(UsdGeom.Boundable):
   extent=UsdGeom.Boundable.ComputeExtentFromPlugins(UsdGeom.Boundable(prim),Usd.TimeCode.Default())
   item['computed_local_extent']=[list(v) for v in extent]
  if prim.IsA(UsdGeom.Cylinder):
   cyl=UsdGeom.Cylinder(prim)
   item['cylinder']={'axis':cyl.GetAxisAttr().Get(),'radius':cyl.GetRadiusAttr().Get(),'height':cyl.GetHeightAttr().Get()}
  items.append(item)
r={'asset':str(asset),'sha256':hashlib.sha256(asset.read_bytes()).hexdigest(),'usd_version':Usd.GetVersion(),'base_position':basepos,'prims':items}
(base/'logs/drive-asset-audit.json').write_text(json.dumps(r,indent=2))
for p in items:print(p['path'],p['bbox_min'],p['bbox_max'],{k:v for k,v in p['attributes'].items() if 'mass' in k.lower() or 'centerofmass' in k.lower()})

