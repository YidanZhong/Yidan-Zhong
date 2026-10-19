"""Copy immutable committed tiles from successful a01 while later batches run."""
from pathlib import Path
import hashlib
import json
import zipfile

base = Path('D:/RAVEN-4060')
dataset = base/'logs/construction-instance-map-20261019'
job = base/'logs/construction-instancemap-a01'
execution = json.loads((job/'execution.json').read_text())
if execution.get('status') != 'completed' or execution.get('exit_code') != 0:
    raise RuntimeError('Initial batch did not complete successfully')
contract_bytes = (dataset/'contract.json').read_bytes()
contract = json.loads(contract_bytes)
expected = 'dc30bf4ac8d061ceb549233a18a7a8206b29380bac5d97acebcc205c909e0366'
if hashlib.sha256(json.dumps(contract, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest() != expected:
    raise RuntimeError('Unexpected dataset contract')
payload = {(dataset/'contract.json').relative_to(base).as_posix(): contract_bytes}
rows, cols = contract['grid']['shape']
size = contract['grid']['tile_cells']
tile_ids = [f'r{r:05d}-c{c:05d}' for r in range(0, rows, size) for c in range(0, cols, size)][:20]
cells = 0
for tile_id in tile_ids:
    record_path = dataset/'tiles'/(tile_id+'.json')
    record_bytes = record_path.read_bytes()
    record = json.loads(record_bytes)
    array_path = record_path.with_suffix('.npz')
    array_bytes = array_path.read_bytes()
    if record['contract_sha256'] != expected or hashlib.sha256(array_bytes).hexdigest() != record['npz_sha256']:
        raise RuntimeError('Tile integrity mismatch '+tile_id)
    r0, r1, c0, c1 = record['tile']['core']
    cells += (r1-r0)*(c1-c0)
    for path, data in [(record_path, record_bytes), (array_path, array_bytes)]:
        payload[path.relative_to(base).as_posix()] = data
if cells != 1268736:
    raise RuntimeError('Initial batch cell count differs')
for directory in [job, base/'logs/construction-instancemap-a01-frames', base/'setup/construction-instance-map-v1', base/'setup/tile-benchmark-lf-v1']:
    for path in directory.rglob('*'):
        if path.is_file() and '__pycache__' not in path.parts and not path.name.startswith('probe-construction-instancemap-a0'):
            payload[path.relative_to(base).as_posix()] = path.read_bytes()
# The exact a01 script is immutable; exclude snapshots of later, still active jobs.
snapshot = base/'setup/construction-instance-map-v1/probe-construction-instancemap-a01.py'
payload[snapshot.relative_to(base).as_posix()] = snapshot.read_bytes()
payload['checkpoint-scope.json'] = json.dumps({'scope':'immutable first 20 committed tiles only; later batch still running', 'contract_sha256':expected, 'completed_tiles_in_archive':20, 'completed_cells_in_archive':cells, 'live_progress_excluded':True, 'formal_accepted':False}, indent=2).encode()
manifest = {name:hashlib.sha256(data).hexdigest() for name,data in payload.items()}
output = base/'logs/construction-instance-prefix20-evidence.zip'
with zipfile.ZipFile(output, 'x', zipfile.ZIP_DEFLATED, 6) as archive:
    for name, data in sorted(payload.items()):
        archive.writestr(name, data)
    archive.writestr('sha256.json', json.dumps(manifest, indent=2))
print(json.dumps({'archive':str(output), 'files':len(payload), 'bytes':output.stat().st_size, 'sha256':hashlib.sha256(output.read_bytes()).hexdigest()}))
