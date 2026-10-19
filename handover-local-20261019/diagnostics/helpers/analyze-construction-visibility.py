from pathlib import Path
import argparse,collections,hashlib,json
p=argparse.ArgumentParser();p.add_argument('frames',type=Path);a=p.parse_args()
trace=a.frames/'visibility-frames.unreviewed.jsonl'
groups=collections.defaultdict(list)
for line in trace.read_text().splitlines():
 row=json.loads(line);groups[row['instance_id']].append(row)
rows=[]
for instance,samples in sorted(groups.items()):
 blockers=collections.Counter(path for s in samples for path in s['metric']['blocking_prim_paths'])
 poses=sorted({s['pose_index'] for s in samples})
 times=sorted({s['sim_time_s'] for s in samples});gaps=[b-a for a,b in zip(times,times[1:])]
 passed=[]
 for pose in poses:
  values=[s for s in samples if s['pose_index']==pose]
  if len(values)==5 and len(times)==5 and all(0<g<=.15 for g in gaps) and all(s['metric']['valid'] and s['zero_distance_hit_count']==0 for s in values) and sum(s['target_prim_hit_count'] for s in values)>0:passed.append(pose)
 rows.append({'instance_id':instance,'poses':len(poses),'frame_samples':len(samples),'times_s':times,'frame_gaps_s':gaps,
  'distance_and_occlusion_valid_samples':sum(s['metric']['valid'] for s in samples),'raw_target_hits':sum(s['target_prim_hit_count'] for s in samples),
  'zero_distance_hits':sum(s['zero_distance_hit_count'] for s in samples),'passing_diagnostic_poses':passed,'top_blockers':blockers.most_common(4)})
result={'scope':'analysis of actual private diagnostic ray trace, not approved GT','trace_sha256':hashlib.sha256(trace.read_bytes()).hexdigest(),'instances':rows,'instances_with_passing_pose':sum(bool(r['passing_diagnostic_poses']) for r in rows)}
with (a.frames/'trace-analysis.json').open('x') as f:json.dump(result,f,indent=2)
print(json.dumps({'instances':len(rows),'passing':result['instances_with_passing_pose'],'valid_samples_without_time_gate':sum(r['distance_and_occlusion_valid_samples'] for r in rows),'total_samples':sum(r['frame_samples'] for r in rows)}))
