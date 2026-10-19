import ctypes
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

base=Path(r'D:\RAVEN-4060')
job=json.loads(Path(sys.argv[1]).read_text(encoding='utf-8-sig'))
code=(base/'setup/terrain-stream-v1').resolve(strict=True)
name=job['name']; snapshot=code/f'probe-{name}.py'
if snapshot.exists():raise RuntimeError('Source snapshot already exists')
shutil.copy2(code/'probe_windows_scene_render.py',snapshot)
os.environ['VK_LOADER_DRIVERS_SELECT']='nv-vk64.json'
os.environ['PYTHONUNBUFFERED']='1'
command=[sys.executable.replace('pythonw.exe','python.exe'),'-u',str(base/'setup/run_windows_probe.py'),
    '--output',str(base/f'logs/{name}'),'--cwd',str(base/'isaac45'),
    '--timeout',str(job['timeout']),'--memory-gib','14','--result-json',str(base/f'logs/{name}-frames/report.json'),
    '--','cmd.exe','/d','/c',str(base/'isaac45/python.bat'),str(snapshot),'--output',str(base/f'logs/{name}-frames')]+job['args']
ctypes.windll.kernel32.SetThreadExecutionState(0x80000001)
try:
    with (base/f'logs/{name}-launch.log').open('wb') as log:
        result=subprocess.run(command,stdout=log,stderr=log,creationflags=subprocess.CREATE_NO_WINDOW)
finally:
    ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)
if job.get('cleanup_task'):
    task=job['cleanup_task']
    if task!='RAVEN-Scene1-FullMap-20261018':raise RuntimeError('Unexpected cleanup task')
    result_cleanup=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',
        "Unregister-ScheduledTask -TaskName 'RAVEN-Scene1-FullMap-20261018' -Confirm:$false -ErrorAction Stop"],
        capture_output=True,text=True,creationflags=subprocess.CREATE_NO_WINDOW)
    (base/f'logs/{name}-task-cleanup.json').write_text(json.dumps({'task':task,'exit_code':result_cleanup.returncode,
        'stdout':result_cleanup.stdout,'stderr':result_cleanup.stderr}),encoding='utf-8')
raise SystemExit(result.returncode)
