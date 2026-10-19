"""Finite serial coordinator for existing guarded diagnostic jobs; no formal approval."""
from pathlib import Path
import ctypes,datetime,hashlib,json,subprocess,sys,time,traceback

base=Path('D:/RAVEN-4060')
output=base/'logs/construction-instance-batches-20261019'
dataset=base/'logs/construction-instance-map-20261019'
config_path=Path(sys.argv[1])
config=json.loads(config_path.read_text(encoding='utf-8-sig'))
if config.get('map_jobs') != [f'construction-instancemap-a{i:02}' for i in range(2,6)]:
    raise ValueError('Expected the four prepared finite map batches only')
output.mkdir(exist_ok=False)
state={'scope':'finite unreviewed diagnostic queue','status':'starting','steps':[],
       'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
       'config_sha256':hashlib.sha256(config_path.read_bytes()).hexdigest(),'formal_accepted':False}
start=time.monotonic()

def save():
    state.update(updated_at=datetime.datetime.now().astimezone().isoformat(),elapsed_s=time.monotonic()-start)
    temp=output/'progress.tmp.json';temp.write_text(json.dumps(state,indent=2),encoding='utf-8')
    temp.replace(output/'progress.json')

def read_progress():
    p=json.loads((dataset/'progress.json').read_text(encoding='utf-8-sig'))
    if p['contract_sha256']!=config['contract_sha256'] or p['total_tiles']!=70:
        raise RuntimeError('Dataset identity changed')
    if p['formal_gt_approved']:raise RuntimeError('Expected unreviewed diagnostic data')
    return p

def run_guarded(job,launcher,job_file,limit):
    logs=base/'logs'/job
    if logs.exists() or (base/'logs'/(job+'-frames')).exists():
        raise RuntimeError('Refusing existing job output: '+job)
    command=[sys.executable.replace('pythonw.exe','python.exe'),str(launcher)]
    if job_file:command.append(str(job_file))
    row={'job':job,'command':command,'started_at':datetime.datetime.now().astimezone().isoformat(),'status':'running'}
    state['steps'].append(row);state['current_job']=job;state['status']='running';save()
    with (output/(job+'-coordinator.log')).open('xb') as log:
        # The child launcher retains the existing Windows Job Object guard.
        # A coordinator timeout stops this queue; it never starts another GPU job.
        result=subprocess.run(command,stdout=log,stderr=log,timeout=limit+120,creationflags=subprocess.CREATE_NO_WINDOW)
    execution=json.loads((logs/'execution.json').read_text(encoding='utf-8-sig'))
    row.update(launcher_exit=result.returncode,execution=execution,status='finished')
    save()
    if result.returncode or execution.get('exit_code')!=0 or execution.get('diagnostic_status')!='passed':
        raise RuntimeError('Guarded job did not pass: '+job)

ctypes.windll.kernel32.SetThreadExecutionState(0x80000001)
try:
    for filename,digest in config['source_sha256'].items():
        if hashlib.sha256(Path(filename).read_bytes()).hexdigest()!=digest:
            raise RuntimeError('Prepared source differs: '+filename)
    initial=read_progress();state['initial_progress']=initial;save()
    for job in config['map_jobs']:
        if (output/'STOP').exists() or (dataset/'STOP').exists():
            state.update(status='agent_stop_checkpoint_saved', current_job=None);save();sys.exit(0)
        for filename,digest in config['source_sha256'].items():
            if hashlib.sha256(Path(filename).read_bytes()).hexdigest()!=digest:
                raise RuntimeError('Prepared source changed before next batch: '+filename)
        before=read_progress()
        if before['sampling_complete']:break
        job_file=base/'setup/construction-instance-map-v1'/(job+'.json')
        spec=json.loads(job_file.read_text())
        if spec['name']!=job or spec['timeout']!=1200 or spec['memory_gib']!=14:
            raise RuntimeError('Map resource budget changed')
        run_guarded(job,base/'setup/construction-instance-map-v1/launch-tiles.py',job_file,1200)
        after=read_progress()
        if after['completed_tiles']<=before['completed_tiles'] or after['completed_tiles']>70:
            raise RuntimeError('No committed progress or invalid tile count')
        state['steps'][-1]['dataset_progress']=after;save()
    latest=read_progress();state['final_sampling_progress']=latest
    if (output/'STOP').exists() or (dataset/'STOP').exists():
        state.update(status='agent_stop_checkpoint_saved', current_job=None);save();sys.exit(0)
    if latest['sampling_complete'] and latest['completed_tiles']==70:
        run_guarded('construction-instancepost-a01',base/'setup/construction-instance-post-v1/launch-post.py',None,600)
        report=json.loads((base/'logs/construction-instancepost-a01-frames/report.json').read_text())
        if not report['reference_comparison_passed'] or report['formal_gt_approved']:
            raise RuntimeError('Postprocess reference check failed or approval changed')
        state['postprocess_report']='D:/RAVEN-4060/logs/construction-instancepost-a01-frames/report.json'
        state['status']='diagnostic_map_completed_pending_review'
    else:
        state['status']='batch_limit_reached_checkpoint_saved'
    state['current_job']=None;save()
except Exception as error:
    state.update(status='stopped_requires_agent_diagnosis',error=str(error),traceback=traceback.format_exc())
    save()
    raise
finally:
    ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)
