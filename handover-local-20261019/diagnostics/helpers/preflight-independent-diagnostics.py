from pathlib import Path
import copy
import importlib.util
import json
import tempfile

base=Path('D:/RAVEN-4060/setup')
spec=importlib.util.spec_from_file_location('queue_preflight',base/'run-independent-diagnostics.py')
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
config=json.loads((base/'independent-diagnostics.json').read_text())
module.verify(config)
checks=['50 frozen files and four original 14GiB/840s budgets verified']
bad=copy.deepcopy(config);bad['jobs'].append(bad['jobs'][0])
try:module.verify(bad)
except ValueError:checks.append('duplicate fifth job rejected')
else:raise AssertionError('Extra retry accepted')
bad=copy.deepcopy(config);bad['source_sha256'][str(base/'run-independent-diagnostics.py').replace('\\','/')]='0'*64
try:module.verify(bad)
except RuntimeError:checks.append('source drift rejected')
else:raise AssertionError('Changed source accepted')
with tempfile.TemporaryDirectory(prefix='raven-queue-preflight-',dir=base) as temporary:
    path=Path(temporary)/'invalid-budget.json'
    job=json.loads(Path(config['jobs'][0]['config']).read_text());job['memory_gib']=15
    path.write_text(json.dumps(job))
    bad=copy.deepcopy(config);bad['jobs'][0]['config']=str(path)
    try:module.verify(bad)
    except RuntimeError:checks.append('increased memory budget rejected')
    else:raise AssertionError('Increased budget accepted')
activity=module.activity()
if not activity['processes'] or not activity['tasks']:
    raise AssertionError('Expected actual active map task/process to be detected')
checks.append('actual active map task and GPU diagnostic processes detected; no GPU job launched')
result={'passed':True,'checks':checks,'activity':activity,'scope':'scheduler safeguards only; not scientific validation'}
path=base/'independent-diagnostics-preflight.json'
with path.open('x',encoding='utf-8') as stream:json.dump(result,stream,indent=2)
print(json.dumps(result))
