from pathlib import Path
import json,os,subprocess,sys
root=Path('/mnt/d/xprogram/RAVEN-AirGround-github');run=root/'runs/partial_scene_geometry_20261019';rows=[]
for scene in ['AbandonedCity','DowntownWest','MilitaryBase','ModernCityDowntown','Shipyard']:
    command=[sys.executable,str(root.parent/'.raven-setup-cache/export-partial-source-candidates.py'),scene]
    row={'scene':scene,'command':command}
    with (run/(scene+'-source-candidates.log')).open('xb') as log:
        try:row['exit_code']=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,timeout=180,env=dict(os.environ,PXR_WORK_THREAD_LIMIT='4',OPENBLAS_NUM_THREADS='1')).returncode
        except subprocess.TimeoutExpired:row.update(exit_code=None,status='bounded_timeout')
    path=run/(scene+'-source-candidates/summary.json')
    if path.exists():row['summary']=json.loads(path.read_text())
    rows.append(row);(run/'candidate-progress.json').write_text(json.dumps(rows,indent=2));print(json.dumps(row),flush=True)
