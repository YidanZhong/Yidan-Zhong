"""Private runtime preparation candidate. Does not save any USD layer."""
from typing import Any

def expand_instances(stage: Any, root_path: str, *, max_roots: int = 10000) -> dict:
    from pxr import Usd, UsdPhysics
    root=stage.GetPrimAtPath(root_path)
    if not root:raise ValueError('Missing scene root')
    changed=[]
    for pass_index in range(8):
        roots=[p for p in Usd.PrimRange(root) if p.IsInstance()]
        if not roots:return {'scope':'in-memory instance expansion candidate','changed_roots':changed,'passes':pass_index,'saved_usd':False}
        if len(changed)+len(roots)>max_roots:raise ValueError('Instance expansion budget exceeded')
        for prim in roots:
            if prim.HasAPI(UsdPhysics.RigidBodyAPI) and UsdPhysics.RigidBodyAPI(prim).GetRigidBodyEnabledAttr().Get():
                raise ValueError('Dynamic instance requires separate review')
            path=str(prim.GetPath());prim.SetInstanceable(False)
            if prim.IsInstance():raise RuntimeError('Instance expansion did not take effect: '+path)
            changed.append(path)
    raise RuntimeError('Nested instance expansion exceeded eight passes')
