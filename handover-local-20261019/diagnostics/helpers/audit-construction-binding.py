from pathlib import Path
from pxr import Usd,UsdGeom,UsdShade
import json,math
base=Path('D:/RAVEN-4060');scene=base/'assets/handover-scenes-20261019/ConstructionSite/ConstructionSite_Export.usd'
s=Usd.Stage.Open(str(scene));cache=UsdGeom.BBoxCache(Usd.TimeCode.Default(),['default','render'])
targets=json.loads((base/'setup/construction-targets.unreviewed.json').read_text())['instances']
rows=[]
for p in Usd.PrimRange.Stage(s, Usd.TraverseInstanceProxies()):
 if not (p.IsA(UsdGeom.Mesh) or p.IsA(UsdGeom.Subset)):continue
 material,relationship=UsdShade.MaterialBindingAPI(p).ComputeBoundMaterial()
 path=str(material.GetPath()) if material else ''
 if not any(k in path.lower() for k in ['tarp','net']):continue
 geom=p.GetParent() if p.IsA(UsdGeom.Subset) else p
 b=cache.ComputeWorldBound(geom).ComputeAlignedRange()
 if b.IsEmpty():continue
 rows.append({'prim':str(p.GetPath()),'type':p.GetTypeName(),'bound_material':path,'geometry':str(geom.GetPath()),
  'center':list(b.GetMidpoint()),'size':list(b.GetSize())})
results=[]
for t in targets:
 if 'tarp' not in t['semantic_class'] and 'towercrane' not in t['semantic_class'] and 'construction_lift' not in t['instance_id']:continue
 c=t['obb']['center_xyz_m'];size=t['obb']['size_xyz_m']
 item={'instance_id':t['instance_id'],'current_binding':t.get('usd_prim_path'),'review_status':'pending','geometry_changes_applied':False}
 if 'tarp' in t['semantic_class']:
  # Broad AABB neighborhood is a search aid only, never semantic assignment.
  candidates=[r for r in rows if all(abs(r['center'][a]-c[a])<=size[a]/2+r['size'][a]/2+.5 for a in range(3))]
  candidates.sort(key=lambda r:math.dist(c,r['center']))
  item['material_geometry_candidates']=candidates
 else:
  p=s.GetPrimAtPath(t['usd_prim_path']);parents=[]
  while p and str(p.GetPath())!='/World/stage/ConstructionSite':
   b=cache.ComputeWorldBound(p).ComputeAlignedRange()
   if not b.IsEmpty():parents.append({'path':str(p.GetPath()),'type':p.GetTypeName(),'center':list(b.GetMidpoint()),'size':list(b.GetSize())})
   p=p.GetParent()
  item['ancestor_bounds']=parents
 results.append(item)
out={'scene_id':'ConstructionSite','scope':'read-only geometry/material proposal, not human binding approval','tarp_net_geometry_count':len(rows),'targets':results}
(base/'logs/construction-binding-proposals-with-proxies.json').write_text(json.dumps(out,indent=2))
print(json.dumps({'material_candidates':len(rows),'targets':[{'id':r['instance_id'],'candidates':len(r.get('material_geometry_candidates',r.get('ancestor_bounds',[])))} for r in results]}))
