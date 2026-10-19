from pathlib import Path
import ast,hashlib,json,resource,sys
resource.setrlimit(resource.RLIMIT_AS,(8*1024**3,8*1024**3))
from pxr import Usd,UsdGeom,UsdPhysics
root=Path('/mnt/d/xprogram/RAVEN-AirGround-github');folder=Path('/mnt/d/xprogram/.raven-setup-cache/construction-instances-v2')
sys.path.insert(0,str(folder));sys.path.insert(0,str(folder/'air-stack/simulation/isaac-sim/utils'))
from expand_static_scene_instances import expand_instances
from seed_instance_colliders import seed_colliders
from scene_audit import classify_scene_mesh,collision_approximation_for_profile
from scene_physics_profile import configure_airground_physics_profile
source=root/'AirStack/scenes/ConstructionSite/ConstructionSite_Export.usd';sha=hashlib.sha256(source.read_bytes()).hexdigest()
stage=Usd.Stage.Open(str(source));expansion=expand_instances(stage,'/World/stage');inheritance=seed_colliders(stage,folder/'instance-collision-geometry-matches.json')
# Execute the exact pure-USD function from the frozen candidate, without loading its optional Omni UI imports.
tree=ast.parse((folder/'air-stack/simulation/isaac-sim/utils/scene_prep.py').read_text())
node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='add_profiled_colliders')
namespace={'UsdGeom':UsdGeom,'UsdPhysics':UsdPhysics,'classify_scene_mesh':classify_scene_mesh,'collision_approximation_for_profile':collision_approximation_for_profile}
exec(compile(ast.Module(body=[node],type_ignores=[]),'frozen_scene_prep_function','exec'),namespace)
summary=namespace['add_profiled_colliders'](stage.GetPrimAtPath('/World/stage'),profile_overrides=inheritance['profile_overrides'])
physics=configure_airground_physics_profile(stage,profile_overrides=inheritance['profile_overrides'])
missing=[]
for prim in Usd.PrimRange(stage.GetPrimAtPath('/World/stage'),Usd.TraverseInstanceProxies()):
 if prim.IsA(UsdGeom.Mesh) and UsdGeom.Imageable(prim).ComputeVisibility()!=UsdGeom.Tokens.invisible:
  if not prim.HasAPI(UsdPhysics.CollisionAPI) or not UsdPhysics.CollisionAPI(prim).GetCollisionEnabledAttr().Get():missing.append(str(prim.GetPath()))
assert not missing and hashlib.sha256(source.read_bytes()).hexdigest()==sha
result={'scope':'actual USD CPU coverage check of frozen candidate; not real PhysX cooking/raycast','passed':True,'source_unchanged':True,
        'seeded_count':inheritance['seeded_count'],'profile_summary':summary,'physics_profile_summary':physics,'missing_visible':missing,
        'peak_rss_mib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024}
with (root/'runs/construction_adaptation_20261019/instance-seeding-check.json').open('x') as f:json.dump(result,f,indent=2)
print(json.dumps(result))
