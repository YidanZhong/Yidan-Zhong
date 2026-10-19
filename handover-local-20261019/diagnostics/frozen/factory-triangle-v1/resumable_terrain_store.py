"""Atomic, checksum-verified storage for private diagnostic terrain tiles."""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Iterator

import numpy as np

FIELDS = {'height':'float32', 'normal':'float32', 'support_mask':'bool',
          'obstacle_mask':'bool', 'ceiling_height':'float32', 'slope_rad':'float32',
          'step_height_m':'float32', 'overhead_clearance_m':'float32'}


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024*1024), b''):
            value.update(chunk)
    return value.hexdigest()


def atomic_json(path: Path, value: Any) -> None:
    temporary = path.with_name(path.name+'.tmp')
    with temporary.open('w', encoding='utf-8') as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


@contextmanager
def dataset_lock(root: Path) -> Iterator[None]:
    """OS lock releases on process exit/crash; a stale file is harmless."""
    root.mkdir(parents=True, exist_ok=True)
    with (root/'writer.lock').open('a+b') as handle:
        if handle.tell() == 0:
            handle.write(b'0'); handle.flush()
        handle.seek(0)
        if os.name == 'nt':
            import msvcrt
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield
        finally:
            handle.seek(0)
            if os.name == 'nt':
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def tile_layout(grid: dict[str, Any]) -> list[dict[str, Any]]:
    rows, cols = grid['shape']; size = grid['tile_cells']
    if any(type(v) is not int or v <= 0 for v in (rows, cols, size)):
        raise ValueError('Grid and tile dimensions must be positive integers')
    if size > 256 or rows*cols > 40000000 or grid['resolution_m'] != .05:
        raise ValueError('Diagnostic grid exceeds validated dimensions/resolution')
    if len(grid['origin_xy_m']) != 2 or not np.isfinite(grid['origin_xy_m']).all():
        raise ValueError('Grid origin must have two finite coordinates')
    result = []
    for r0 in range(0, rows, size):
        for c0 in range(0, cols, size):
            r1, c1 = min(rows,r0+size), min(cols,c0+size)
            result.append({'id':f'r{r0:05d}-c{c0:05d}', 'core':[r0,r1,c0,c1],
                'halo':[max(0,r0-1),min(rows,r1+1),max(0,c0-1),min(cols,c1+1)]})
    return result


class TileStore:
    """Use only while holding dataset_lock; JSON is the tile commit marker."""
    def __init__(self, root: Path, contract: dict[str, Any]):
        self.root = root
        self.tiles = tile_layout(contract['grid'])
        self.contract = contract
        self.contract_hash = hashlib.sha256(json.dumps(contract, sort_keys=True,
            separators=(',',':'), allow_nan=False).encode()).hexdigest()
        contract_path = root/'contract.json'
        if contract_path.exists():
            if json.loads(contract_path.read_text(encoding='utf-8')) != contract:
                raise ValueError('Dataset contract changed; refusing to mix runs')
        else:
            if (root/'tiles').exists() and any((root/'tiles').iterdir()):
                raise ValueError('Existing tiles have no contract')
            atomic_json(contract_path, contract)
        (root/'tiles').mkdir(exist_ok=True)
        allowed = {tile['id'] for tile in self.tiles}
        if any(p.stem not in allowed for p in (root/'tiles').glob('*.json')):
            raise ValueError('Unknown tile commit in dataset')
        self.completed: dict[str, dict[str, Any]] = {}
        for tile in self.tiles:
            path = root/'tiles'/(tile['id']+'.json')
            if path.exists():
                record = json.loads(path.read_text(encoding='utf-8'))
                if record['tile'] != tile or record['contract_sha256'] != self.contract_hash:
                    raise ValueError('Tile commit geometry/contract differs')
                array_path = root/'tiles'/(tile['id']+'.npz')
                if digest(array_path) != record['npz_sha256']:
                    raise ValueError(f'Tile checksum mismatch: {tile["id"]}')
                with np.load(array_path, allow_pickle=False) as arrays:
                    self.validate_arrays(tile, dict(arrays))
                self.completed[tile['id']] = record

    @staticmethod
    def validate_arrays(tile: dict[str, Any], arrays: dict[str, np.ndarray]) -> None:
        r0,r1,c0,c1 = tile['core']; shape=(r1-r0,c1-c0)
        if set(arrays) != set(FIELDS):
            raise ValueError('Unexpected terrain channels')
        for key, dtype in FIELDS.items():
            expected = (*shape,3) if key == 'normal' else shape
            if arrays[key].shape != expected or arrays[key].dtype != np.dtype(dtype):
                raise ValueError(f'Wrong tile shape/dtype: {key}')
            if not np.isfinite(arrays[key]).all():
                raise ValueError(f'Non-finite terrain: {key}')

    def commit(self, tile: dict[str, Any], arrays: dict[str, np.ndarray],
               provenance: dict[str, Any]) -> dict[str, Any]:
        if tile not in self.tiles or tile['id'] in self.completed:
            raise ValueError('Unknown or already committed tile')
        self.validate_arrays(tile, arrays)
        path = self.root/'tiles'/(tile['id']+'.npz')
        temporary = path.with_name(path.name+'.tmp')
        with temporary.open('wb') as stream:
            np.savez_compressed(stream, **arrays)
            stream.flush(); os.fsync(stream.fileno())
        os.replace(temporary, path)
        record = {'tile':tile,'contract_sha256':self.contract_hash,
                  'npz_sha256':digest(path),'provenance':provenance}
        atomic_json(path.with_suffix('.json'), record)
        self.completed[tile['id']] = record
        return record
