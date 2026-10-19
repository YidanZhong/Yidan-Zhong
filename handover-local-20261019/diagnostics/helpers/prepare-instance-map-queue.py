"""Prepare continuation only; requires a passed initial batch and measured contract."""
from pathlib import Path
import ast
base=Path('D:/xprogram/.raven-setup-cache')
replacements={'construction-ground-batches-20261019':'construction-instance-batches-20261019',
              'construction-ground-map-20261019':'construction-instance-map-20261019',
              'construction-groundmap-a':'construction-instancemap-a',
              'construction-ground-map-v2':'construction-instance-map-v1',
              'construction-groundpost-a01':'construction-instancepost-a01',
              'construction-ground-post-v2':'construction-instance-post-v1'}
s=(base/'run-construction-ground-batches.py').read_text(encoding='utf-8')
for a,b in replacements.items():s=s.replace(a,b)
ast.parse(s)
(base/'run-construction-instance-batches.py').write_text(s,encoding='utf-8')
s=(base/'start-construction-ground-batches.ps1').read_text(encoding='utf-8-sig')
for a,b in replacements.items():s=s.replace(a,b)
s=s.replace('ConstructionGroundBatches','ConstructionInstanceBatches').replace('run-construction-ground-batches.py','run-construction-instance-batches.py').replace('construction-ground-batches.json','construction-instance-batches.json')
guard="""$ravenProcesses=@(Get-CimInstance Win32_Process | Where-Object { $_.Name -match 'python|kit' -and $_.CommandLine -match 'RAVEN-4060.*(probe-|run_windows_probe|launch-)' })
if($ravenProcesses.Count){throw 'A diagnostic process is still active'}
$ravenInitial=Get-Content 'D:\\RAVEN-4060\\logs\\construction-instancemap-a01\\execution.json' -Raw | ConvertFrom-Json
if($ravenInitial.exit_code -ne 0 -or $ravenInitial.diagnostic_status -ne 'passed'){throw 'Initial fresh-map batch has not passed'}
"""
s=s.replace("$ravenName=",guard+"$ravenName=",1)
(base/'start-construction-instance-batches.ps1').write_text(s,encoding='utf-8-sig')
print('Continuation worker prepared; no config or running queue until initial batch passes.')
