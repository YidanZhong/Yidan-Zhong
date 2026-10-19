from pathlib import Path
import hashlib,json
root=Path('D:/xprogram/RAVEN-AirGround-github')
path=root/'docs/development/ugv-ogn/unreviewed-arrival-candidates-20261019.json'
result=json.loads(path.read_text())
result['additional_cpu_validation']={}
for label,relative in [('scalar_distance','runs/arrival_candidates_20261019/RetroNeighborhood-a02/independent-check.json'),('input_guards','runs/arrival_candidates_20261019/guard-check/result.json')]:
    source=root/relative
    result['additional_cpu_validation'][label]={'file':relative,'sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'result':json.loads(source.read_text())}
result['validation_scope']='CPU geometry and guards only; no real visibility or human GT acceptance'
path.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print('Recorded independent geometry checks and guard evidence without rerunning or replacing outputs')
