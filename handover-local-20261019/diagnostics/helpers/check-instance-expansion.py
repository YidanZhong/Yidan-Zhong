from pathlib import Path
import hashlib,json,resource,time,sys
resource.setrlimit(resource.RLIMIT_AS,(8*1024**3,8*1024**3))
import numpy as np
from pxr import Usd,UsdGeom
from expand_static_scene_instances import expand_instances
root=Path('/mnt/d/xprogram/RAVEN-AirGround-github');source=root/'AirStack/scenes/ConstructionSite/ConstructionSite_Export.usd'
initial=hashlib.sha256(source.read_bytes()).hexdigest();stage=Usd.Stage.Open(str(source));started=time.monotonic()
def snapshot():
    xforms=UsdGeom.XformCache();rows={}
    for prim in Usd.PrimRange.Stage(stage,Usd.TraverseInstanceProxies()):
        if not prim.IsA(UsdGeom.Mesh):continue
        mesh=UsdGeom.Mesh(prim);h=hashlib.sha256()
        for attr in [mesh.GetPointsAttr(),mesh.GetFaceVertexCountsAttr(),mesh.GetFaceVertexIndicesAttr()]:
            value=attr.Get();h.update(np.asarray(value).tobytes() if value is not None else b'null')
        h.update(np.asarray(xforms.GetLocalToWorldTransform(prim),dtype=np.float64).tobytes())
        h.update(str(UsdGeom.Imageable(prim).ComputeVisibility()).encode())
        rows[str(prim.GetPath())]=h.hexdigest()
    return rows
before=snapshot();summary=expand_instances(stage,'/World/stage');after=snapshot();assert before==after
remaining=sum(p.IsInstanceProxy() for p in Usd.PrimRange.Stage(stage,Usd.TraverseInstanceProxies()))
assert remaining==0 and hashlib.sha256(source.read_bytes()).hexdigest()==initial
result={'scope':'offline instance-expansion geometry preservation, not actual PhysX collision verification','passed':True,
        'scene_sha256':initial,'mesh_geometry_and_transform_count':len(before),'all_mesh_bytes_transforms_visibility_unchanged':True,
        'remaining_instance_proxies':remaining,'expansion':summary,'source_unchanged':True,
        'elapsed_s':time.monotonic()-started,'peak_rss_mib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024}
out=root/'runs/construction_adaptation_20261019/instance-expansion-check.json'
with out.open('x') as f:json.dump(result,f,indent=2)
print(json.dumps({k:v for k,v in result.items() if k!='expansion'}));print('expanded_roots',len(summary['changed_roots']))
