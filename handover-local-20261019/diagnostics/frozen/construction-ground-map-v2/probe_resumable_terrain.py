"""Stream private real-PhysX terrain tiles to disk with restart validation."""
from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
import logging
from pathlib import Path
import re
import shutil
import time
from typing import Any

import numpy as np
from resumable_terrain_store import FIELDS, TileStore, atomic_json, dataset_lock, digest


def run_stream(world: Any, output: Path, config: dict[str, Any], setup: dict[str, Any],
               raycast: Any, terrain_config: Any) -> dict[str, Any]:
    from airground_benchmark.config.schema import SCHEMA_VERSION
    from airground_benchmark.ground_truth import GridOrigin, TraversabilityMetadata
    from airground_benchmark.traversability import build_raycast_terrain_grid
    stream = config['stream']
    if not re.fullmatch(r'[a-z0-9-]+', stream['dataset']):
        raise ValueError('Dataset must be a simple directory name')
    root = output.parent/stream['dataset']
    if not root.resolve().is_relative_to(output.parent.resolve()) or root == output:
        raise ValueError('Dataset outside diagnostic logs directory')
    if not 1 <= stream['budget_seconds'] <= 27000 or not 1 <= stream['max_new_tiles'] <= 10000:
        raise ValueError('Invalid bounded sampling budget')
    if shutil.disk_usage(output.parent).free < 8*1024**3:
        raise RuntimeError('Less than 8 GiB disk reserve')
    own_sources = {name:digest(Path(__file__).with_name(name)) for name in
        ('probe_resumable_terrain.py','resumable_terrain_store.py','probe_tiled_terrain.py','probe_windows_scene_render.py')}
    if own_sources != stream['generator_sha256']:
        raise RuntimeError('Generator snapshot differs from pinned contract')
    contract = {'format':'diagnostic-terrain-tiles-v1','scene_sha256':config['scene_sha256'],
        'scene_id':config['scene_id'],'targets_sha256':config['targets_sha256'],
        'source_sha256':config['source_sha256'],'generator_sha256':own_sources,
        'setup':setup,'terrain_config':asdict(terrain_config),'grid':stream['grid'],
        'global_postprocess_complete':False,'formal_gt_approved':False}
    # Normalize tuples before equality checks against JSON loaded on resume.
    import json
    contract = json.loads(json.dumps(contract, allow_nan=False))
    started = time.monotonic(); frozen_time = float(world.current_time)
    with dataset_lock(root):
        store = TileStore(root, contract)
        skipped = len(store.completed); new_tiles = 0
        stopped = 'all_tiles_sampled'
        def progress(state: str) -> dict[str, Any]:
            done = sum((v['tile']['core'][1]-v['tile']['core'][0])*
                       (v['tile']['core'][3]-v['tile']['core'][2]) for v in store.completed.values())
            total = int(np.prod(stream['grid']['shape']))
            payload = {'updated_at':datetime.now(timezone.utc).isoformat(),'state':state,
                'session':output.name,'dataset':str(root),'contract_sha256':store.contract_hash,
                'completed_tiles':len(store.completed),'total_tiles':len(store.tiles),
                'completed_cells':done,'total_cells':total,'fraction':done/total,
                'skipped_existing_tiles':skipped,'new_tiles_this_session':new_tiles,
                'sampling_complete':len(store.completed)==len(store.tiles),
                'full_map_generated':False,'global_postprocess_complete':False,'formal_gt_approved':False,
                'elapsed_sampling_wall_s':time.monotonic()-started}
            atomic_json(root/'progress.json',payload)
            atomic_json(output/'stream-progress.json',payload)
            return payload
        progress('sampling')
        for tile in store.tiles:
            if tile['id'] in store.completed:
                continue
            if (root/'STOP').exists():
                stopped = 'operator_stop_file'; break
            if new_tiles >= stream['max_new_tiles'] or time.monotonic()-started >= stream['budget_seconds']:
                stopped = 'bounded_batch_complete'; break
            if shutil.disk_usage(root).free < 8*1024**3:
                raise RuntimeError('Disk reserve dropped below 8 GiB; completed tiles retained')
            if float(world.current_time) != frozen_time:
                raise RuntimeError('World advanced during static terrain sampling')
            r0,r1,c0,c1 = tile['core']; hr0,hr1,hc0,hc1 = tile['halo']
            grid = stream['grid']; res = grid['resolution_m']
            metadata = TraversabilityMetadata(schema_version=SCHEMA_VERSION, scene_id=config['scene_id'],
                frame='map',origin=GridOrigin(x_m=grid['origin_xy_m'][0]+hc0*res,
                    y_m=grid['origin_xy_m'][1]+hr0*res,z_m=0.), resolution_m=res,
                shape=(hr1-hr0,hc1-hc0),generator='native-physx-resumable-diagnostic',generator_version='v1')
            tile_started = time.monotonic()
            terrain = build_raycast_terrain_grid(metadata, raycast, terrain_config)
            core=(slice(r0-hr0,r1-hr0),slice(c0-hc0,c1-hc0))
            arrays = {key:getattr(terrain,key)[core].copy() for key in FIELDS}
            store.commit(tile,arrays,{'session':output.name,'sample_wall_s':time.monotonic()-tile_started,
                'frozen_sim_time_s':frozen_time})
            del terrain, arrays
            new_tiles += 1
            state = progress('sampling')
            logging.info('STREAM_TILE_COMMITTED: %s %d/%d', tile['id'],state['completed_tiles'],state['total_tiles'])
        final = progress(stopped)
        final['status'] = 'passed'
        final['scope'] = 'bounded_durable_sampling_not_formal_map'
        atomic_json(output/'stream-report.json',final)
        return final
