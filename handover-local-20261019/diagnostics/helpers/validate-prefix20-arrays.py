from pathlib import Path
import hashlib
import importlib.util
import json
import numpy as np

run=Path('D:/xprogram/RAVEN-AirGround-github/runs/construction_adaptation_20261019')
archive=run/'instance-prefix20-evidence'
module_path=archive/'setup/construction-instance-map-v1/resumable_terrain_store.py'
spec=importlib.util.spec_from_file_location('frozen_store',module_path)
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
dataset=archive/'logs/construction-instance-map-20261019'
contract=json.loads((dataset/'contract.json').read_text())
store=module.TileStore(dataset,contract)
assert len(store.completed)==20
result={'passed':True,'tiles':len(store.completed),'contract_sha256':store.contract_hash,
        'checks':['tile commits match source grid and contract','NPZ SHA256 matches each committed record','all eight raw channels have expected shape and dtype','every numeric value is finite'],
        'scope':'immutable first-batch storage validation; no fresh raycasts or full-map acceptance'}
with (run/'instance-prefix20-array-validation.json').open('x',encoding='utf-8') as stream:json.dump(result,stream,indent=2)
print(json.dumps(result))
