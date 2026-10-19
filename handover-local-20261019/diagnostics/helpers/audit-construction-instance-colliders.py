from pathlib import Path
import collections,hashlib,json,resource,sys,time
resource.setrlimit(resource.RLIMIT_AS,(8*1024**3,8*1024**3))
from pxr import Usd,UsdGeom,UsdPhysics
root=Path('/mnt/d/xprogram/RAVEN-AirGround-github');source=root/'AirStack/scenes/ConstructionSite/ConstructionSite_Export.usd'
sha=hashlib.sha256(source.read_bytes()).hexdigest();assert sha=='d07b04097b7f1d75f99c6a411c86c66be5aa380757ad618e41c82e607065185c'
stage=Usd.Stage.Open(str(source));review=json.loads(Path('/mnt/d/xprogram/.raven-setup-cache/construction-review-v1/review-input.json').read_text())
instances=[];meshes=[]
for prim in Usd.PrimRange.Stage(stage,Usd.TraverseInstanceProxies()):
 if prim.IsInstance():instances.append(str(prim.GetPath()))
 if not prim.IsA(UsdGeom.Mesh):continue
 ancestors=[];parent=prim.GetParent()
 while parent and str(parent.GetPath())!='/':
  if parent.IsInstance():ancestors.append(str(parent.GetPath()))
  parent=parent.GetParent()
 meshes.append({'path':str(prim.GetPath()),'instance_proxy':prim.IsInstanceProxy(),'instance_ancestors':ancestors,
  'collision_api':prim.HasAPI(UsdPhysics.CollisionAPI),'collision_enabled':UsdPhysics.CollisionAPI(prim).GetCollisionEnabledAttr().Get() if prim.HasAPI(UsdPhysics.CollisionAPI) else None,
  'visible':UsdGeom.Imageable(prim).ComputeVisibility()!=UsdGeom.Tokens.invisible})
runtime=json.loads((root/'runs/construction_adaptation_20261019/visibility-a01-evidence/logs/construction-visibility-a01-frames/colliders.json').read_text())
enabled={r['path'] for r in runtime if r['enabled']};rows=[]
for entry in review['rows']:
 target=entry['target'];prefix=target['usd_prim_path']
 if not prefix:continue
 subset=[m for m in meshes if m['path']==prefix or m['path'].startswith(prefix+'/')]
 rows.append({'instance_id':target['instance_id'],'prim_path':prefix,'target_is_instance':bool(stage.GetPrimAtPath(prefix).IsInstance()),
  'mesh_count':len(subset),'proxy_meshes':sum(m['instance_proxy'] for m in subset),'visible_meshes':sum(m['visible'] for m in subset),
  'runtime_colliders':sum(m['path'] in enabled for m in subset),'meshes':subset})
result={'scope':'read-only complete mesh and instance collider coverage, not human GT approval','scene_sha256':sha,
 'mesh_count':len(meshes),'instance_roots':instances,'instance_proxy_meshes':sum(m['instance_proxy'] for m in meshes),
 'visible_meshes_missing_runtime_colliders':sum(m['visible'] and m['path'] not in enabled for m in meshes),'runtime_collider_count':len(enabled),
 'target_rows':rows,'mesh_rows':meshes,'source_unchanged':hashlib.sha256(source.read_bytes()).hexdigest()==sha}
out=root/'runs/construction_adaptation_20261019/instance-collider-audit.json'
with out.open('x') as f:json.dump(result,f,indent=2)
print(json.dumps({k:result[k] for k in ['mesh_count','instance_proxy_meshes','visible_meshes_missing_runtime_colliders','runtime_collider_count']}))
print(json.dumps([{k:r[k] for k in ['instance_id','target_is_instance','mesh_count','proxy_meshes','runtime_colliders']} for r in rows]))
