from pathlib import Path
import datetime,json,os,subprocess,sys,time
root=Path('/mnt/d/xprogram/RAVEN-AirGround-github');cache=root.parent/'.raven-setup-cache'
data=json.loads((root/'docs/development/ugv-ogn/scene-resource-recovery-20261018.json').read_text())
output=root/'runs/partial_scene_geometry_20261019';output.mkdir(exist_ok=False)
rows=[];started=time.monotonic()
for scene in data['scenes']:
    name=scene['scene_id'];source=cache/'scene-resources-20261018'/scene['file']
    command=[sys.executable,str(cache/'audit-partial-scene-geometry.py'),'--scene',name,'--source',str(source),'--sha256',scene['sha256'],'--output',str(output/(name+'.json'))]
    row={'scene':name,'command':command,'started_at':datetime.datetime.now().astimezone().isoformat()}
    env=dict(os.environ,PXR_WORK_THREAD_LIMIT='4',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
    with (output/(name+'.log')).open('xb') as log:
        try:row['exit_code']=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,env=env,timeout=180).returncode
        except subprocess.TimeoutExpired:row.update(exit_code=None,status='bounded_timeout')
    if (output/(name+'.json')).exists():
        result=json.loads((output/(name+'.json')).read_text());row.update({k:result[k] for k in ('status','mesh_count_read','vertex_count','face_count','peak_rss_mib','elapsed_s')});row['targets_with_candidates']=sum(bool(x['rough_world_aabb_overlap_count']) for x in result['target_aabb_candidates']);row['target_count']=len(result['target_aabb_candidates'])
    rows.append(row)
    (output/'progress.json').write_text(json.dumps({'scope':'bounded CPU read-only diagnostics','completed_jobs':len(rows),'rows':rows,'formal_accepted':False,'elapsed_s':time.monotonic()-started},indent=2))
    print(json.dumps(row),flush=True)
