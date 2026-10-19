from pathlib import Path
import hashlib
import json
import subprocess
import sys
import time

root=Path('/mnt/d/xprogram/RAVEN-AirGround-github')
output=root/'runs/partial_scene_collisions_20261019'
output.mkdir(exist_ok=False)
script=Path('/mnt/d/xprogram/.raven-setup-cache/audit-partial-collider-coverage.py')
state={'scope':'bounded sequential CPU inspections, no GPU jobs','rows':[],'formal_accepted':False,'script_sha256':hashlib.sha256(script.read_bytes()).hexdigest()}
for scene in ['AbandonedCity','DowntownWest','MilitaryBase','ModernCityDowntown','Shipyard']:
    command=[sys.executable,str(script),'--scene',scene]
    state['current_scene']=scene;state['status']='running'
    (output/'progress.json').write_text(json.dumps(state,indent=2))
    started=time.monotonic()
    try:
        with (output/(scene+'.log')).open('xb') as stream:
            result=subprocess.run(command,stdout=stream,stderr=stream,timeout=180)
        row={'scene':scene,'command':command,'exit_code':result.returncode,'elapsed_s':time.monotonic()-started}
    except subprocess.TimeoutExpired:
        row={'scene':scene,'command':command,'exit_code':None,'status':'parent_timeout_180s','elapsed_s':time.monotonic()-started}
    state['rows'].append(row)
    print(json.dumps(row),flush=True)
state.update(status='completed_bounded_inspections',current_scene=None)
(output/'progress.json').write_text(json.dumps(state,indent=2))
