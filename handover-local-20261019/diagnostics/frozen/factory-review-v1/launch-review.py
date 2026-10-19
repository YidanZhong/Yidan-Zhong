import json
import os
from pathlib import Path
import subprocess
import shutil
import sys

job = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8-sig'))
for key, value in job.get('env', {}).items():
    os.environ[key] = str(value)
if job.get('ros2'):
    os.environ['PATH'] += ';D:\\RAVEN-4060\\isaac45\\exts\\isaacsim.ros2.bridge\\humble\\lib'
os.environ['VK_LOADER_DRIVERS_SELECT'] = 'nv-vk64.json'
os.environ['PYTHONUNBUFFERED'] = '1'
base = Path(r'D:\RAVEN-4060')
name = job['name']
snapshot = base / f'setup/factory-review-v1/probe-{name}.py'
if snapshot.exists():
    raise RuntimeError('Refusing to overwrite a diagnostic source snapshot')
shutil.copy2(base / 'setup/factory-review-v1/probe_windows_scene_render.py', snapshot)
command = [sys.executable.replace('pythonw.exe', 'python.exe'), '-u', str(base / 'setup/telemetry-v2/run_windows_probe.py'),
           '--output', str(base / f'logs/{name}'), '--cwd', str(base / 'isaac45'),
           '--timeout', str(job.get('timeout', 450)), '--memory-gib', str(job.get('memory_gib', 10)),
           '--result-json', str(base / f'logs/{name}-frames/report.json'), '--',
           'cmd.exe', '/d', '/c', str(base / 'isaac45/python.bat'),
           str(snapshot), '--output',
           str(base / f'logs/{name}-frames')] + job['args']
with (base / f'logs/{name}-launch.log').open('wb') as log:
    result = subprocess.run(command, stdout=log, stderr=log, creationflags=subprocess.CREATE_NO_WINDOW)
raise SystemExit(result.returncode)
