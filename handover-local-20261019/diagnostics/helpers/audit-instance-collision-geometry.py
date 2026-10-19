from pathlib import Path
import collections,hashlib,json,resource,sys
resource.setrlimit(resource.RLIMIT_AS,(8*1024**3,8*1024**3))
import numpy as np
from pxr import Usd,UsdGeom,UsdPhysics
root=Path('/mnt/d/xprogram/RAVEN-AirGround-github');scene=root/'AirStack/scenes/ConstructionSite/ConstructionSite_Export.usd'
stage=Usd.Stage.Open(str(scene));known=collections.defaultdict(list);pending=[]
sys.path.insert(0,'/mnt/d/xprogram/.raven-setup-cache/construction-instances-v1/air-stack/simulation/isaac-sim/utils')
from scene_audit import classify_scene_mesh
for prim in Usd.PrimRange.Stage(stage,Usd.TraverseInstanceProxies()):
 if not prim.IsA(UsdGeom.Mesh) or not str(prim.GetPath()).startswith('/World/stage/'):continue
 mesh=UsdGeom.Mesh(prim);stack=mesh.GetPointsAttr().GetPropertyStack();source=stack[-1] if stack else None
 h=hashlib.sha256()
 for attr in [mesh.GetPointsAttr(),mesh.GetFaceVertexCountsAttr(),mesh.GetFaceVertexIndicesAttr()]:
  value=attr.Get();h.update(np.asarray(value).tobytes() if value is not None else b'null')
 key=(source.layer.identifier if source else '',str(source.path) if source else '',h.hexdigest())
 row={'path':str(prim.GetPath()),'source_layer':key[0],'source_property':key[1],'geometry_sha256':key[2],
      'profile':classify_scene_mesh(str(prim.GetPath()),has_collision=prim.HasAPI(UsdPhysics.CollisionAPI),has_rigid_body=prim.HasAPI(UsdPhysics.RigidBodyAPI))}
 if prim.HasAPI(UsdPhysics.CollisionAPI) and UsdPhysics.CollisionAPI(prim).GetCollisionEnabledAttr().Get():known[key[2]].append(row)
 elif prim.IsInstanceProxy():pending.append((key[2],row))
matched=[];unmatched=[];ambiguous=[]
for key,row in pending:
 choices=known.get(key,[]);profiles={r['profile'] for r in choices}
 if not choices:unmatched.append(row)
 elif len(profiles)!=1:ambiguous.append(dict(row,choices=choices))
 else:matched.append(dict(row,donor=choices[0]['path'],donor_profile=choices[0]['profile']))
result={'scope':'read-only exact mesh byte identity matching only; source properties differ after USD flattening; not automatic human GT review',
        'matched':matched,'unmatched':unmatched,'ambiguous':ambiguous,'matched_count':len(matched),'unmatched_count':len(unmatched),'ambiguous_count':len(ambiguous)}
out=root/'runs/construction_adaptation_20261019/instance-collision-geometry-matches.json'
with out.open('x') as f:json.dump(result,f,indent=2)
print(json.dumps({k:result[k] for k in ['matched_count','unmatched_count','ambiguous_count']}))
print('unmatched examples',json.dumps(unmatched[:3]));print('ambiguous examples',json.dumps(ambiguous[:1]))

