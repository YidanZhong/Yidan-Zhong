import ctypes,json,subprocess,sys
from pathlib import Path
base=Path(r'D:\RAVEN-4060')
output=base/'logs/full-post-a01-frames'
cmd=[sys.executable.replace('pythonw.exe','python.exe'),'-u',str(base/'setup/telemetry-v2/run_windows_probe.py'),
 '--output',str(base/'logs/full-post-a01'),'--cwd',str(base/'isaac45'),'--timeout','3600','--memory-gib','14',
 '--result-json',str(output/'report.json'),'--','cmd.exe','/d','/c',str(base/'isaac45/python.bat'),
 str(base/'setup/full-post-v1/postprocess_terrain_tiles.py'),'--dataset',str(base/'logs/full-scene-map-20261018'),
 '--output',str(output),'--benchmark-package',str(base/'setup/tile-benchmark/airground_benchmark'),
 '--targets',str(base/'setup/full-post-v1/targets.binding-corrected.unreviewed.json'),
 '--reference-dir',str(base/'logs/tile-map-a01-frames')]
(base/'logs/full-post-a01-command.json').write_text(json.dumps(cmd,indent=2),encoding='utf-8')
ctypes.windll.kernel32.SetThreadExecutionState(0x80000001)
try:
    with (base/'logs/full-post-a01-launch.log').open('wb') as log:
        result=subprocess.run(cmd,stdout=log,stderr=log,creationflags=subprocess.CREATE_NO_WINDOW)
finally:
    ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)
raise SystemExit(result.returncode)
