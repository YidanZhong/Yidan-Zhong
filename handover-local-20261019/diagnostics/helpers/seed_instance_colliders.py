"""Private candidate: transfer only from byte-identical existing collidable meshes."""
from pathlib import Path
from typing import Any
import hashlib,json

def seed_colliders(stage: Any, matches_file: Path) -> dict:
    import numpy as np
    from pxr import UsdGeom,UsdPhysics
    from scene_audit import classify_scene_mesh
    data=json.loads(matches_file.read_text())
    if data['unmatched_count'] or data['ambiguous_count']:raise ValueError('Unresolved collision donors')
    cache={};overrides={};rows=[]
    def geometry(path):
        if path in cache:return cache[path]
        prim=stage.GetPrimAtPath(path)
        if not prim or not prim.IsA(UsdGeom.Mesh) or prim.IsInstanceProxy():raise ValueError('Expected expanded mesh: '+path)
        mesh=UsdGeom.Mesh(prim);digest=hashlib.sha256()
        for attr in [mesh.GetPointsAttr(),mesh.GetFaceVertexCountsAttr(),mesh.GetFaceVertexIndicesAttr()]:
            value=attr.Get();digest.update(np.asarray(value).tobytes() if value is not None else b'null')
        cache[path]=digest.hexdigest();return cache[path]
    for row in data['matched']:
        donor=stage.GetPrimAtPath(row['donor']);target=stage.GetPrimAtPath(row['path'])
        if not donor.HasAPI(UsdPhysics.CollisionAPI) or not UsdPhysics.CollisionAPI(donor).GetCollisionEnabledAttr().Get():raise ValueError('Donor lost collision')
        if geometry(row['donor'])!=row['geometry_sha256'] or geometry(row['path'])!=row['geometry_sha256']:raise ValueError('Mesh donor/instance bytes changed')
        profile=classify_scene_mesh(row['donor'],has_collision=True,has_rigid_body=donor.HasAPI(UsdPhysics.RigidBodyAPI))
        if profile!=row['donor_profile'] or profile not in ('ground','static_obstacle'):raise ValueError('Unexpected donor role')
        UsdPhysics.CollisionAPI.Apply(target).CreateCollisionEnabledAttr().Set(True)
        overrides[row['path']]=profile
        rows.append({'path':row['path'],'donor':row['donor'],'geometry_sha256':row['geometry_sha256'],'profile':profile})
    return {'scope':'private exact-geometry donor collision preparation, not semantic GT review',
            'matches_sha256':hashlib.sha256(matches_file.read_bytes()).hexdigest(),'seeded_count':len(rows),'rows':rows,'profile_overrides':overrides}
