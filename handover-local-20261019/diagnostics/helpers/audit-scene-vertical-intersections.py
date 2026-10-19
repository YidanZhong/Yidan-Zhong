"""Offline source triangle baseline, with no semantic ownership or collider claim."""
from pathlib import Path
import hashlib,json,logging,time
import numpy as np
from pxr import Usd,UsdGeom

root=Path('/mnt/d/xprogram/RAVEN-AirGround-github')
logging.basicConfig(level=logging.INFO)
scene_points={'FireAcademy':[[-30.475,-4.825],[-40.475,10.175],[0.025,0.025]],
              'AbandonedFactory':[[30.025,-82.025],[20.025,-67.025],[0.025,0.025]]}

def intersections(tri:np.ndarray,xy:np.ndarray)->np.ndarray:
    a,b,c=tri[:,0],tri[:,1],tri[:,2]
    denom=(b[:,1]-c[:,1])*(a[:,0]-c[:,0])+(c[:,0]-b[:,0])*(a[:,1]-c[:,1])
    valid=np.abs(denom)>1e-12
    u=np.zeros(len(tri));v=u.copy();x,y=xy
    u[valid]=((b[valid,1]-c[valid,1])*(x-c[valid,0])+(c[valid,0]-b[valid,0])*(y-c[valid,1]))/denom[valid]
    v[valid]=((c[valid,1]-a[valid,1])*(x-c[valid,0])+(a[valid,0]-c[valid,0])*(y-c[valid,1]))/denom[valid]
    w=1-u-v;hit=valid&(u>=-1e-8)&(v>=-1e-8)&(w>=-1e-8)
    return u[hit]*a[hit,2]+v[hit]*b[hit,2]+w[hit]*c[hit,2]

# Analytic sloping plane and vertical/degenerate projections.
tri=np.array([[[0.,0.,1.],[1.,0.,2.],[0.,1.,3.]],[[0.,0.,0.],[0.,0.,1.],[0.,1.,1.]]])
assert np.allclose(intersections(tri,np.array([.2,.3])),[1.8])
assert len(intersections(tri,np.array([2.,2.])))==0

for scene,points in scene_points.items():
    started=time.monotonic();source=root/f'AirStack/scenes/{scene}/{scene}_Export.usd'
    out=root/f'runs/additional_scene_preflight_20261019/{scene}-source-ray-baseline.json'
    if out.exists():raise FileExistsError(out)
    stage=Usd.Stage.Open(str(source));cache=UsdGeom.XformCache();bbox=UsdGeom.BBoxCache(Usd.TimeCode.Default(),['default','render'])
    result={'scope':'offline triangle intersections, not actual PhysX or reviewed GT','scene_id':scene,
            'scene_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
            'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'units_m':UsdGeom.GetStageMetersPerUnit(stage),'up_axis':str(UsdGeom.GetStageUpAxis(stage)),
            'formal_gt_approved':False,'points':[{'xy_m':p,'source_hits':[]} for p in points],
            'excluded_prototypes':'Prototype meshes do not establish instance placement; no full-scene equality claim',
            'triangulation':'fan triangulation of authored polygons; non-triangle counts recorded','meshes':[]}
    for prim in Usd.PrimRange(stage.GetPrimAtPath('/World/stage'),Usd.TraverseInstanceProxies()):
        if not prim.IsA(UsdGeom.Mesh) or '/Prototypes/' in str(prim.GetPath()):continue
        mesh=UsdGeom.Mesh(prim);pts=np.asarray(mesh.GetPointsAttr().Get(),dtype=float)
        if not len(pts):continue
        mat=np.asarray(cache.GetLocalToWorldTransform(prim));world=pts@mat[:3,:3]+mat[3,:3]
        low,high=world.min(axis=0),world.max(axis=0)
        active=[i for i,p in enumerate(points) if np.all(np.array(p)>=low[:2]) and np.all(np.array(p)<=high[:2])]
        if not active:continue
        counts=np.asarray(mesh.GetFaceVertexCountsAttr().Get());indices=np.asarray(mesh.GetFaceVertexIndicesAttr().Get())
        row={'path':str(prim.GetPath()),'faces':len(counts),'nontriangle_faces':int((counts!=3).sum()),'world_vertex_min':low.tolist(),'world_vertex_max':high.tolist()}
        result['meshes'].append(row)
        if np.all(counts==3):tri_indices=indices.reshape(-1,3)
        else:
            faces=[];offset=0
            for count in counts:
                face=indices[offset:offset+count];offset+=count
                faces.extend((int(face[0]),int(face[k]),int(face[k+1])) for k in range(1,count-1))
            tri_indices=np.asarray(faces,dtype=int)
        hits={i:[] for i in active}
        for offset in range(0,len(tri_indices),65536):
            tri=world[tri_indices[offset:offset+65536]]
            for i in active:
                z=intersections(tri,np.array(points[i]))
                if len(z):hits[i].extend(z.tolist())
        for i,values in hits.items():
            if values:result['points'][i]['source_hits'].append({'prim':str(prim.GetPath()),'z_m':np.unique(np.round(values,7)).tolist(),'triangle_intersection_count':len(values)})
        del tri_indices,world,pts
    largest=max(result['meshes'],key=lambda r:r['faces']);anchor=stage.GetPrimAtPath(largest['path']);box=bbox.ComputeWorldBound(anchor).ComputeAlignedRange()
    result['geometry_anchor']={'prim_path':largest['path'],'center_xyz_m':list(box.GetMidpoint()),'size_xyz_m':list(box.GetSize()),'semantic_binding':False}
    result['elapsed_s']=time.monotonic()-started
    out.write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps({'scene':scene,'elapsed_s':result['elapsed_s'],'points':result['points'],'anchor':result['geometry_anchor']}),flush=True)
