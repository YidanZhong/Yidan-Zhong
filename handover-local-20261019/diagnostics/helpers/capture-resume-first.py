from pathlib import Path
import json,shutil
base=Path(r'D:\RAVEN-4060\logs')
execution=json.loads((base/'resume-test-a01/execution.json').read_text())
assert execution['exit_code']==0
dataset=base/'resume-proof-20261018';out=base/'resume-test-a01-frames'
progress=json.loads((dataset/'progress.json').read_text());assert progress['completed_tiles']==2
records=[json.loads(p.read_text()) for p in sorted((dataset/'tiles').glob('*.json'))];assert len(records)==2
(out/'first-committed-records.json').write_text(json.dumps(records,indent=2),encoding='utf-8')
shutil.copy2(dataset/'progress.json',out/'first-checkpoint.json')
print('First two committed hashes captured before starting the second process.')
