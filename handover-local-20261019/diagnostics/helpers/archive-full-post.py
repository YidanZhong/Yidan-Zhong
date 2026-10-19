from pathlib import Path
import json,zipfile
base=Path(r'D:\RAVEN-4060');logs=base/'logs'
execution=json.loads((logs/'full-post-a01/execution.json').read_text())
report=json.loads((logs/'full-post-a01-frames/report.json').read_text())
assert execution['exit_code']==0 and execution['status']=='completed' and report['status']=='passed'
with zipfile.ZipFile(logs/'full-post-a01-evidence.zip','x',zipfile.ZIP_DEFLATED) as archive:
    for dirname in ('full-post-a01','full-post-a01-frames'):
        for path in sorted((logs/dirname).rglob('*')):
            if path.is_file() and 'terrain' not in path.relative_to(logs/dirname).parts:
                archive.write(path,path.relative_to(logs))
    for filename in ('full-post-a01-launch.log','full-post-a01-command.json'):
        archive.write(logs/filename,filename)
    for path in sorted((base/'setup/full-post-v1').glob('*')):
        if path.is_file():archive.write(path,'source/'+path.name)
    archive.write(base/'setup/telemetry-v2/run_windows_probe.py','source/run_windows_probe.py')
print(json.dumps({'archive_bytes':(logs/'full-post-a01-evidence.zip').stat().st_size,
    'status':report['status'],'selected':report['selected_component'],
    'footprint':report['footprint_summary'],'reach':report['reach_summary'],
    'peak_job_commit_gib':execution['peak_job_commit_gib'],'elapsed_s':execution['elapsed_s']}))
