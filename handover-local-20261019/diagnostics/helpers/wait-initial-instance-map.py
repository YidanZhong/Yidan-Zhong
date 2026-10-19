"""Finite dependency wait, then existing guarded continuation; never retries failure."""
from pathlib import Path
import ctypes,datetime,json,subprocess,sys,time,traceback
base=Path('D:/RAVEN-4060');output=base/'logs/construction-instance-continuation-wait-20261019'
output.mkdir(exist_ok=False)
state={'scope':'finite dependency wait and guarded map continuation','status':'waiting_initial_batch','formal_accepted':False}
def save():
    state['updated_at']=datetime.datetime.now().astimezone().isoformat()
    tmp=output/'progress.tmp.json';tmp.write_text(json.dumps(state,indent=2));tmp.replace(output/'progress.json')
ctypes.windll.kernel32.SetThreadExecutionState(0x80000001)
try:
    started=time.monotonic();initial=base/'logs/construction-instancemap-a01/execution.json';save()
    while not initial.exists():
        if (output/'STOP').exists():raise RuntimeError('Operator stop checkpoint')
        if time.monotonic()-started>1200:raise TimeoutError('Initial batch did not finish within bounded dependency wait')
        time.sleep(5)
    execution=json.loads(initial.read_text());state['initial_execution']=execution;save()
    if execution.get('exit_code')!=0 or execution.get('diagnostic_status')!='passed':
        raise RuntimeError('Initial guarded batch failed; continuation refused')
    # Wait only for already-finished task/process cleanup. No overlapping GPU jobs.
    for _ in range(18):
        command="$ErrorActionPreference='Stop'; $tasks=@(Get-ScheduledTask -TaskName 'RAVEN-*' -ErrorAction SilentlyContinue | Where-Object { $_.State -eq 'Running' -and $_.TaskName -ne 'RAVEN-ConstructionInstanceBatches-20261019' }); $processes=@(Get-CimInstance Win32_Process | Where-Object { $_.Name -match 'python|kit' -and $_.CommandLine -match 'RAVEN-4060.*(probe-|run_windows_probe|launch-)' }); [pscustomobject]@{tasks=$tasks.Count;processes=$processes.Count}|ConvertTo-Json -Compress"
        checked=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',command],capture_output=True,text=True,timeout=20,check=True,creationflags=subprocess.CREATE_NO_WINDOW)
        activity=json.loads(checked.stdout)
        if activity=={'tasks':0,'processes':0}:break
        time.sleep(5)
    else:raise RuntimeError('Other task or diagnostic process still active; continuation refused')
    state.update(status='running_finite_continuation',activity=activity);save()
    command=[sys.executable.replace('pythonw.exe','python.exe'),str(base/'setup/run-construction-instance-batches.py'),str(base/'setup/construction-instance-batches.json')]
    with (output/'continuation.log').open('xb') as log:
        result=subprocess.run(command,stdout=log,stderr=log,timeout=6300,creationflags=subprocess.CREATE_NO_WINDOW)
    state.update(status='continuation_finished' if result.returncode==0 else 'continuation_failed',worker_exit_code=result.returncode);save()
    sys.exit(result.returncode)
except Exception as error:
    state.update(status='stopped_requires_agent_diagnosis',error=str(error),traceback=traceback.format_exc());save();raise
finally:
    ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)
