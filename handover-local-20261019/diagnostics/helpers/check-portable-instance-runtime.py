from pathlib import Path
import ast,hashlib,json,resource,sys,time
resource.setrlimit(resource.RLIMIT_AS,(8*1024**3,8*1024**3))
from pxr import Usd,UsdGeom,UsdPhysics
root=Path('/mnt/d/xprogram/RAVEN-AirGround-github');utils=root/'AirStack/simulation/isaac-sim/utils'
sys.path.insert(0,str(utils))
from scene_instance_colliders import prepare_static_instance_colliders
from scene_audit import classify_scene_mesh,collision_approximation_for_profile
from scene_physics_profile import configure_airground_physics_profile
asset=root/'AirStack/scenes/ConstructionSite/ConstructionSite_Export.usd'
run=root/'runs/construction_adaptation_20261019'
original_sha=hashlib.sha256(asset.read_bytes()).hexdigest()
donors=json.loads((run/'instance-collision-geometry-matches.json').read_text())
manifest={'schema':'static-instance-collision-manifest-v1','asset_sha256':original_sha,
          'asset_default_prim':'/World','scene_root':'/World/stage','human_gt_approved':False,
          'unmatched_count':donors['unmatched_count'],'ambiguous_count':donors['ambiguous_count'],
          'matches':[{'path':r['path'],'donor':r['donor'],'geometry_sha256':r['geometry_sha256'],'profile':r['donor_profile']} for r in donors['matched']]}
manifest_path=run/'static-instance-collision-manifest.unreviewed.json'
with manifest_path.open('x') as f:json.dump(manifest,f,indent=2)
tree=ast.parse((utils/'scene_prep.py').read_text())
node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='add_profiled_colliders')
namespace={'UsdGeom':UsdGeom,'UsdPhysics':UsdPhysics,'classify_scene_mesh':classify_scene_mesh,'collision_approximation_for_profile':collision_approximation_for_profile}
exec(compile(ast.Module(body=[node],type_ignores=[]),'actual_scene_prep_function','exec'),namespace)
expected=json.loads((run/'instances-a02-evidence/logs/construction-instances-a02-frames/colliders.json').read_text())
expected={r['path']:{k:v for k,v in r.items() if k!='path'} for r in expected if r['path'].startswith('/World/stage/')}
results=[]
for mount in [None,'/World/stage']:
    started=time.monotonic()
    if mount is None:
        stage=Usd.Stage.Open(str(asset));scene_root='/World/stage'
    else:
        stage=Usd.Stage.CreateInMemory();stage.DefinePrim(mount,'Xform').GetReferences().AddReference(str(asset));scene_root=mount+'/stage'
    prepared=prepare_static_instance_colliders(stage,manifest_path=manifest_path,asset_path=asset,reference_root=mount)
    summary=namespace['add_profiled_colliders'](stage.GetPrimAtPath(scene_root),profile_overrides=prepared['profile_overrides'])
    physics=configure_airground_physics_profile(stage,root_prim_path=scene_root,profile_overrides=prepared['profile_overrides'])
    actual={};missing=[]
    for prim in Usd.PrimRange(stage.GetPrimAtPath(scene_root),Usd.TraverseInstanceProxies()):
        if prim.IsA(UsdGeom.Mesh):
            if prim.HasAPI(UsdPhysics.CollisionAPI):
                path=str(prim.GetPath());canonical='/World'+path[len(mount):] if mount else path
                actual[canonical]={'enabled':bool(UsdPhysics.CollisionAPI(prim).GetCollisionEnabledAttr().Get()),
                    'approximation':str(UsdPhysics.MeshCollisionAPI(prim).GetApproximationAttr().Get()) if prim.HasAPI(UsdPhysics.MeshCollisionAPI) else prim.GetTypeName()}
            if UsdGeom.Imageable(prim).ComputeVisibility()!='invisible' and (not prim.HasAPI(UsdPhysics.CollisionAPI) or not UsdPhysics.CollisionAPI(prim).GetCollisionEnabledAttr().Get()):missing.append(str(prim.GetPath()))
    assert not missing and actual==expected
    assert prepared['seeded_meshes']==5075 and len(actual)==5757
    results.append({'reference_root':mount,'runtime_root':scene_root,'elapsed_s':time.monotonic()-started,
                    'prepared':{k:v for k,v in prepared.items() if k!='profile_overrides'},'collider_count':len(actual),
                    'matches_actual_PhysX_a02_collider_manifest':True,'summary':summary,'cpu_physics_profile':physics})
    del stage
assert hashlib.sha256(asset.read_bytes()).hexdigest()==original_sha
report={'scope':'actual USD CPU runtime helper checks; not new PhysX cooking or patrol',
        'asset_source_unchanged':True,'manifest_sha256':hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        'helper_sha256':hashlib.sha256((utils/'scene_instance_colliders.py').read_bytes()).hexdigest(),
        'results':results,'peak_rss_mib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,'passed':True}
with (run/'portable-instance-runtime-cpu.json').open('x') as f:json.dump(report,f,indent=2)
print(json.dumps(report))
