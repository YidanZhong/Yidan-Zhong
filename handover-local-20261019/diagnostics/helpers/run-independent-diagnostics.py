"""Finite serial diagnostic jobs after the existing map queue releases the GPU."""
from pathlib import Path
import ctypes
import datetime
import hashlib
import json
import subprocess
import sys
import time
import traceback

BASE = Path('D:/RAVEN-4060')
TASK = 'RAVEN-IndependentDiagnostics-20261019'

def activity():
    command = r'''$ErrorActionPreference='Stop'; $ProgressPreference='SilentlyContinue'; [pscustomobject]@{tasks=@(Get-ScheduledTask -TaskName 'RAVEN-*' -ErrorAction SilentlyContinue | Where-Object { $_.State -eq 'Running' -and $_.TaskName -ne 'RAVEN-IndependentDiagnostics-20261019' } | Select-Object -ExpandProperty TaskName); processes=@(Get-CimInstance Win32_Process | Where-Object { $_.Name -match 'python|kit' -and $_.CommandLine -match 'RAVEN-4060.*(probe-|run_windows_probe|launch-)' } | Select-Object ProcessId,Name)} | ConvertTo-Json -Depth 4 -Compress'''
    result = subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',command],capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=25,creationflags=subprocess.CREATE_NO_WINDOW,check=True)
    return json.loads(result.stdout)

def verify(config):
    if [job['name'] for job in config['jobs']] != ['construction-portable-a01','construction-clock-a01','factory-triangle-a01','construction-review-a04']:
        raise ValueError('Expected exactly the four prepared independent jobs, without retries')
    for name, digest in config['source_sha256'].items():
        if hashlib.sha256(Path(name).read_bytes()).hexdigest() != digest:
            raise RuntimeError('Frozen source changed: '+name)
    for job in config['jobs']:
        spec = json.loads(Path(job['config']).read_text(encoding='utf-8-sig'))
        if spec['name'] != job['name'] or spec['timeout'] != 840 or spec['memory_gib'] != 14 or spec.get('ros2'):
            raise RuntimeError('Diagnostic budget or identity changed')

def main():
    config_path = Path(sys.argv[1])
    config = json.loads(config_path.read_text(encoding='utf-8'))
    output = BASE/'logs/independent-diagnostics-20261019'
    output.mkdir(exist_ok=False)
    started = time.monotonic()
    state = {'scope':'finite independent diagnostics; no human GT or formal acceptance','status':'waiting_for_existing_map_queue','steps':[], 'formal_accepted':False,'config_sha256':hashlib.sha256(config_path.read_bytes()).hexdigest()}
    def save():
        state.update(updated_at=datetime.datetime.now().astimezone().isoformat(),elapsed_s=time.monotonic()-started)
        temp = output/'progress.tmp.json'
        temp.write_text(json.dumps(state,indent=2),encoding='utf-8')
        temp.replace(output/'progress.json')
    ctypes.windll.kernel32.SetThreadExecutionState(0x80000001)
    try:
        verify(config)
        save()
        deadline = time.monotonic()+3600
        while True:
            if (output/'STOP').exists():
                state['status']='operator_stop_before_next_job';save();return 0
            map_state = json.loads((BASE/'logs/construction-instance-batches-20261019/progress.json').read_text())
            observed = activity()
            state.update(map_queue_status=map_state['status'],activity=observed)
            save()
            if map_state['status'] not in ('starting','running') and not observed['tasks'] and not observed['processes']:
                break
            if time.monotonic() >= deadline:
                raise TimeoutError('Existing queue did not release GPU within bounded wait')
            time.sleep(15)
        for job in config['jobs']:
            if (output/'STOP').exists():
                state['status']='operator_stop_before_next_job';save();return 0
            verify(config)
            observed = activity()
            if observed['tasks'] or observed['processes']:
                raise RuntimeError('Another diagnostic became active; refusing overlap')
            name = job['name']
            if (BASE/'logs'/name).exists() or (BASE/'logs'/(name+'-frames')).exists():
                raise RuntimeError('Existing result must not be overwritten: '+name)
            row={'job':name,'status':'running','started_at':datetime.datetime.now().astimezone().isoformat()}
            state['steps'].append(row);state.update(status='running',current_job=name);save()
            command=[sys.executable.replace('pythonw.exe','python.exe'),job['launcher'],job['config']]
            row['command']=command;save()
            with (output/(name+'-coordinator.log')).open('xb') as stream:
                result=subprocess.run(command,stdout=stream,stderr=stream,timeout=960,creationflags=subprocess.CREATE_NO_WINDOW)
            execution=json.loads((BASE/'logs'/name/'execution.json').read_text())
            passed = result.returncode == 0 and execution.get('exit_code') == 0 and execution.get('diagnostic_status') == 'passed'
            row.update(status='passed' if passed else 'failed',launcher_exit=result.returncode,execution=execution)
            state['current_job']=None;save()
            if execution.get('status') != 'completed':
                raise RuntimeError('Resource/launch guard failure; remaining jobs left unstarted')
            # A normally exited failed scientific check does not block independent jobs.
        state['status']='finite_jobs_finished';save();return 0
    except Exception as error:
        state.update(status='stopped_requires_agent_diagnosis',error=str(error),traceback=traceback.format_exc())
        save();raise
    finally:
        ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)

if __name__ == '__main__':
    raise SystemExit(main())
