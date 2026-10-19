from pathlib import Path
import hashlib,json
from pxr import Usd,UsdGeom
root=Path('/mnt/d/xprogram/RAVEN-AirGround-github');run=root/'runs/partial_scene_geometry_20261019'
audit=json.loads((run/'DowntownWest.json').read_text());stage=Usd.Stage.Open(audit['source']);rows=[]
for error in audit['mesh_errors']:
    prim=stage.GetPrimAtPath(error['path']);mesh=UsdGeom.Mesh(prim)
    attrs={}
    for name in ('points','faceVertexCounts','faceVertexIndices','extent'):
        attr=prim.GetAttribute(name);value=attr.Get()
        attrs[name]={'authored':attr.HasAuthoredValueOpinion(),'is_none':value is None,'count':len(value) if value is not None else None}
    rows.append({'path':error['path'],'visibility':str(mesh.ComputeVisibility()),'active':prim.IsActive(),
                 'children':[str(p.GetPath()) for p in prim.GetChildren()], 'attributes':attrs,
                 'has_payload':prim.HasPayload(),'references':str(prim.GetMetadata('references'))})
snow=json.loads((run/'SnowyVillage.json').read_text())
result={'scope':'read-only follow-up of missing geometry values, not asset repair','downtown_meshes':rows,
        'snowy_composition_error_count':len(snow['composition_errors']),'snowy_meshes_read':snow['mesh_count_read'],
        'formal_accepted':False,'source_audits_sha256':{n:hashlib.sha256((run/(n+'.json')).read_bytes()).hexdigest() for n in ('DowntownWest','SnowyVillage')}}
path=run/'geometry-gap-detail.json';assert not path.exists();path.write_text(json.dumps(result,indent=2))
print(json.dumps({'downtown':rows[:4],'downtown_count':len(rows),'snowy_composition_errors':len(snow['composition_errors'])},indent=2))
