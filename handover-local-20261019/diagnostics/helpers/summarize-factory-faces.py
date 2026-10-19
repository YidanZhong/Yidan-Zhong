from pathlib import Path
import hashlib,json
root=Path('D:/xprogram/RAVEN-AirGround-github');run=root/'runs/factory_adaptation_20261019';base=run/'face-candidates-a01';report=json.loads((base/'report.json').read_text())
for name,entry in report['files'].items():assert hashlib.sha256((base/name).read_bytes()).hexdigest()==entry['sha256']
groups={}
for mesh in report['meshes']:
 if '/Prototypes/' in mesh['prim']:continue
 for target in mesh['targets']:
  count=target['counts']['vertex_mean_inside']
  groups.setdefault(target['instance_id'],[])
  if count:groups[target['instance_id']].append({'prim':mesh['prim'],'candidate_faces':count,'total_mesh_faces':mesh['faces'],'candidate_fraction':count/mesh['faces'],'full_mesh_inside_annotation':count==mesh['faces']})
entries=[{'instance_id':key,'candidate_meshes':len(value),'candidate_faces':sum(v['candidate_faces'] for v in value),'largest_candidates':sorted(value,key=lambda v:v['candidate_faces'],reverse=True)[:5],'human_ownership_review_required':True} for key,value in groups.items()]
result={'scope':'geometric face candidates, not semantic ownership or approved binding','formal_accepted':False,'raw_report_sha256':hashlib.sha256((base/'report.json').read_bytes()).hexdigest(),'files_verified':len(report['files']),'meshes_audited':len(report['meshes']),'prototype_meshes_excluded_from_this_summary':sum('/Prototypes/' in m['prim'] for m in report['meshes']),'entries':entries,'original_11_target_manifest_unchanged':True,'excluded_originally_bound_instance':'AbandonedFactory.building.0001','limitation':'Prototypes in raw mesh audit are source geometry, not placed point-instancer instances; they are excluded here. Geometry inside OBB is not class ownership.'}
(run/'face-candidate-summary.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps([{k:v for k,v in e.items() if k!='largest_candidates'} for e in entries],indent=2))
