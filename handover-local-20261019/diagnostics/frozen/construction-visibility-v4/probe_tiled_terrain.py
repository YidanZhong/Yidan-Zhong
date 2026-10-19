"""Bounded real PhysX tile-equivalence experiment; never approves release GT."""
from __future__ import annotations

from dataclasses import asdict
import hashlib
import json
import logging
from pathlib import Path
import sys
import time
import types
from typing import Any


def run_validation(world: Any, stage: Any, output: Path, config_path: Path,
                   air_stack: Path, benchmark_path: Path) -> dict[str, Any]:
    import numpy as np
    import omni.physx
    from pxr import Usd, UsdGeom, UsdPhysics

    config = json.loads(config_path.read_text(encoding='utf-8-sig'))
    windows = config.get('windows', [])
    streaming = config.get('mode') == 'resumable_sampling'
    audit_points = config.get('ray_audit_points_xy_m', [])
    if audit_points:
        points = np.asarray(audit_points, dtype=float)
        if streaming or not 1 <= len(points) <= 25 or points.shape != (len(points), 2) or not np.isfinite(points).all():
            raise ValueError('Raw ray audit requires 1..25 finite XY points in a separate non-streaming diagnostic')
    if not streaming and (not windows or len(windows) > 3):
        raise ValueError('Expected one to three explicit diagnostic windows')
    if sum(int(w['rows'])*int(w['cols']) for w in windows) > 131072:
        raise ValueError('Bounded validation exceeds 131072 reference cells')
    for window in windows:
        if not 2 <= window['rows'] <= 512 or not 2 <= window['cols'] <= 512:
            raise ValueError('Invalid window dimensions')
        if window['resolution_m'] != .05 or not 16 <= window['tile_cells'] <= 128:
            raise ValueError('Expected 0.05 m diagnostic grid and 16..128 cell tiles')

    def sha(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    for relative, expected in config['source_sha256'].items():
        path = air_stack/relative[9:] if relative.startswith('AirStack/') else benchmark_path/relative[10:]
        if sha(path) != expected:
            raise RuntimeError(f'Source checksum mismatch: {relative}')
    sys.path.insert(0, str(air_stack/'simulation/isaac-sim/utils'))
    import scene_prep
    import ugv_traction_setup as traction
    from scene_physics_profile import DEFAULT_AIRGROUND_PHYSICS_PROFILE
    package = types.ModuleType('airground_benchmark')
    package.__path__ = [str(benchmark_path)]
    sys.modules.setdefault('airground_benchmark', package)
    from airground_benchmark.config.schema import SCHEMA_VERSION
    from airground_benchmark.scenes import SCENE_IDS
    from airground_benchmark.ground_truth import GridOrigin, TraversabilityMetadata
    from airground_benchmark.traversability import (
        RaycastTerrainGrid, RaycastTerrainGridConfig, build_raycast_terrain_grid,
        FootprintSweepConfig, sweep_ugv_footprint_over_terrain, build_reach_region,
    )
    scene_id=config['scene_id']
    if scene_id not in SCENE_IDS or not config['corrected_target']['instance_id'].startswith(scene_id+'.'):
        raise ValueError('Scene identity differs from the coordinate anchor')
    if len(config['targets_sha256'])!=64:
        raise ValueError('A pinned target manifest is required')

    for prim in list(stage.Traverse()):
        if prim.IsA(UsdPhysics.Scene) and str(prim.GetPath()) != '/World/PhysicsScene':
            prim.SetActive(False)
    scene_root = stage.GetPrimAtPath('/World/stage')
    if not scene_root.IsValid():
        raise RuntimeError('Scene root missing')
    setup = {'colliders': scene_prep.add_profiled_colliders(scene_root)}
    setup['physics_profile'] = scene_prep.configure_airground_physics_profile(
        stage, root_prim_path='/World/stage', profile=DEFAULT_AIRGROUND_PHYSICS_PROFILE)
    setup['support_plane'] = scene_prep.add_ground_support_plane(stage,
        contact_offset_m=traction.AIRGROUND_GROUND_SUPPORT_CONTACT_OFFSET_M,
        rest_offset_m=traction.AIRGROUND_GROUND_SUPPORT_REST_OFFSET_M)
    setup['support_collision_enabled'] = bool(UsdPhysics.CollisionAPI(
        stage.GetPrimAtPath(setup['support_plane']['prim_path'])).GetCollisionEnabledAttr().Get())
    if setup['support_plane']['geometry'] != 'plane' or not setup['support_collision_enabled']:
        raise RuntimeError('Runtime ground plane configuration failed')
    collider_rows = []
    for prim in Usd.PrimRange.Stage(stage, Usd.TraverseInstanceProxies()):
        if prim.HasAPI(UsdPhysics.CollisionAPI):
            collider_rows.append({'path': str(prim.GetPath()),
                'enabled': UsdPhysics.CollisionAPI(prim).GetCollisionEnabledAttr().Get(),
                'approximation': str(UsdPhysics.MeshCollisionAPI(prim).GetApproximationAttr().Get())
                    if prim.HasAPI(UsdPhysics.MeshCollisionAPI) else prim.GetTypeName()})
    (output/'colliders.json').write_text(json.dumps(collider_rows, indent=2), encoding='utf-8')
    setup['colliders_sha256'] = sha(output/'colliders.json')
    bounds = UsdGeom.BBoxCache(Usd.TimeCode.Default(), ['default','render'])
    target = config['corrected_target']
    prim = stage.GetPrimAtPath(target['usd_prim_path'])
    if not prim.IsValid() or target['verified'] or target['ground_reachable'] != 'unknown':
        raise RuntimeError('Corrected candidate must exist and remain unapproved')
    box = bounds.ComputeWorldBound(prim).ComputeAlignedRange()
    binding = {'instance_id':target['instance_id'],'prim':target['usd_prim_path'],
               'center':list(box.GetMidpoint()),'size':list(box.GetSize()),'human_review':'pending'}
    if not np.allclose(binding['center'], config['expected_bounds']['center_xyz_m'], atol=.02, rtol=0):
        raise RuntimeError('Corrected candidate center differs from exported bounds')
    if not np.allclose(binding['size'], config['expected_bounds']['size_xyz_m'], atol=.02, rtol=0):
        raise RuntimeError('Corrected candidate size differs from exported bounds')
    world.reset()
    for _ in range(5):
        world.step(render=False)
    from probe_unreviewed_visibility import run_visibility
    visibility = run_visibility(world, stage, output, config_path.with_name('visibility-input.json'))
    query = omni.physx.get_physx_scene_query_interface()
    ray_count = 0
    hit_paths: dict[str, int] = {}

    def raycast(origin: tuple, direction: tuple, distance: float) -> tuple:
        nonlocal ray_count
        ray_count += 1
        hits: list[dict] = []
        errors: list[Exception] = []
        def collect(hit: Any) -> bool:
            try:
                # PhysX callback values are owned by native code: copy immediately.
                get = hit.get if isinstance(hit, dict) else lambda key: getattr(hit, key, None)
                path = str(get('collision') or get('rigid_body') or get('rigidBody') or '')
                if not path:
                    raise RuntimeError('Ray hit missing collider identity')
                hits.append({'distance_m':float(get('distance')),
                    'position_xyz_m':tuple(float(v) for v in get('position')),
                    'normal_xyz':tuple(float(v) for v in get('normal')),'prim_path':path})
                hit_paths[path] = hit_paths.get(path, 0) + 1
                return True
            except Exception as exc:
                errors.append(exc)
                return False
        query.raycast_all(origin, direction, float(distance), collect)
        if errors:
            raise RuntimeError('PhysX callback failed') from errors[0]
        return tuple(hits)

    terrain_config = RaycastTerrainGridConfig(ray_start_z_m=8., ray_end_z_m=-2.,
        overhead_ray_distance_m=3., min_ground_normal_z=.35,
        min_obstacle_height_m=.05, max_obstacle_height_m=1.,
        ignored_prim_path_prefixes=('/World/uav','/World/UAV','/World/ugv','/World/UGV'))
    if audit_points:
        audit_time = float(world.current_time)
        rows = []
        for x, y in audit_points:
            rows.append({'xy_m': [x, y],
                         'down_hits': raycast((x, y, 8.), (0., 0., -1.), 10.),
                         'absolute_obstacle_band_up_hits': raycast((x, y, .05), (0., 0., 1.), .95)})
        if float(world.current_time) != audit_time:
            raise RuntimeError('World advanced during raw ray audit')
        raw_report = {'scope': 'raw actual PhysX hit diagnostic, no collision changes or GT approval',
                      'scene_id': scene_id, 'config_sha256': sha(config_path),
                      'frozen_sim_time_s': audit_time, 'obstacle_band_absolute_z_m': [.05, 1.],
                      'formal_gt_approved': False, 'points': rows}
        (output/'raw-ray-audit.json').write_text(json.dumps(raw_report, indent=2), encoding='utf-8')
    if streaming:
        from probe_resumable_terrain import run_stream
        return run_stream(world, output, config, setup, raycast, terrain_config)
    fields = ('height','normal','support_mask','obstacle_mask','ceiling_height',
              'slope_rad','step_height_m','overhead_clearance_m')
    results = []
    frozen_time = float(world.current_time)
    for index, window in enumerate(windows):
        metadata = TraversabilityMetadata(schema_version=SCHEMA_VERSION, scene_id=scene_id,
            frame='map', origin=GridOrigin(x_m=window['origin'][0], y_m=window['origin'][1], z_m=0.),
            resolution_m=window['resolution_m'], shape=(window['rows'],window['cols']),
            generator='native-physx-tile-validation', generator_version='diagnostic-v1')
        logging.info('TILE_REFERENCE_START: %s', window['name'])
        started = time.perf_counter()
        count_before = ray_count
        reference = build_raycast_terrain_grid(metadata, raycast, terrain_config)
        reference_seconds = time.perf_counter()-started
        reference_rays = ray_count-count_before
        stitched = {key:np.empty_like(getattr(reference,key)) for key in fields}
        coverage = np.zeros(metadata.shape, dtype=np.uint8)
        rows, cols = metadata.shape
        tile = window['tile_cells']
        tile_records = []
        started = time.perf_counter()
        count_before = ray_count
        for r0 in range(0, rows, tile):
            for c0 in range(0, cols, tile):
                r1, c1 = min(r0+tile, rows), min(c0+tile, cols)
                hr0, hc0, hr1, hc1 = max(0,r0-1), max(0,c0-1), min(rows,r1+1), min(cols,c1+1)
                local = metadata.model_copy(update={'shape':(hr1-hr0,hc1-hc0),
                    'origin':GridOrigin(x_m=metadata.origin.x_m+hc0*metadata.resolution_m,
                        y_m=metadata.origin.y_m+hr0*metadata.resolution_m, z_m=0.)})
                chunk = build_raycast_terrain_grid(local, raycast, terrain_config)
                core = (slice(r0-hr0,r1-hr0),slice(c0-hc0,c1-hc0))
                for key in fields:
                    stitched[key][r0:r1,c0:c1] = getattr(chunk,key)[core]
                coverage[r0:r1,c0:c1] += 1
                tile_records.append({'core':[r0,r1,c0,c1],'with_halo':[hr0,hr1,hc0,hc1]})
                logging.info('TILE_COMPLETE: %s %s', window['name'], tile_records[-1]['core'])
                del chunk
        tiled_seconds = time.perf_counter()-started
        tiled_rays = ray_count-count_before
        if not np.all(coverage == 1):
            raise RuntimeError('Tiles have missing or overlapping core cells')
        merged = RaycastTerrainGrid(metadata=metadata, **stitched, obstacle_band_m=(.05,1.))
        # Component IDs and footprint/reach operations are computed over the entire
        # stitched window, never concatenated from independent per-tile labels.
        ref_arrays = reference.arrays_for_npz()
        tile_arrays = merged.arrays_for_npz()
        ref_sweep = sweep_ugv_footprint_over_terrain(reference, FootprintSweepConfig(max_step_height_m=.05))
        tile_sweep = sweep_ugv_footprint_over_terrain(merged, FootprintSweepConfig(max_step_height_m=.05))
        ref_reach = build_reach_region(reference.support_mask & ~reference.obstacle_mask, resolution_m=.05)
        tile_reach = build_reach_region(merged.support_mask & ~merged.obstacle_mask, resolution_m=.05)
        for name, left, right in [('footprint_mask', ref_sweep.traversable_mask,tile_sweep.traversable_mask),
            ('footprint_component',ref_sweep.component,tile_sweep.component),
            ('reach_component',ref_reach.reach_component,tile_reach.reach_component)]:
            ref_arrays[name], tile_arrays[name] = left, right
        seam = np.zeros(metadata.shape, dtype=bool)
        for boundary in range(tile,rows,tile): seam[boundary-1:boundary+1,:] = True
        for boundary in range(tile,cols,tile): seam[:,boundary-1:boundary+1] = True
        comparisons = {}
        for key, left in ref_arrays.items():
            right = tile_arrays[key]
            delta = np.abs(left.astype(np.float64)-right.astype(np.float64))
            tolerance = 1e-5 if left.dtype.kind == 'f' else 0.
            mismatch = delta > tolerance
            comparisons[key] = {'exact_mismatch_values':int(np.count_nonzero(left != right)),
                'outside_tolerance':int(mismatch.sum()), 'tolerance':tolerance,
                'max_abs_error':float(delta.max()), 'seam_mismatch_values':int(mismatch[seam].sum())}
        np.savez_compressed(output/f'window-{index}-reference.npz', **ref_arrays)
        np.savez_compressed(output/f'window-{index}-tiled.npz', **tile_arrays)
        (output/f'window-{index}-metadata.json').write_text(metadata.model_dump_json(indent=2),encoding='utf-8')
        result = {'name':window['name'],'metadata':metadata.model_dump(mode='json'),
            'reference_seconds':reference_seconds,'tiled_seconds':tiled_seconds,
            'reference_rays':reference_rays,'tiled_rays':tiled_rays,'tile_count':len(tile_records),
            'halo_cells':1,'tiles':tile_records,'comparisons':comparisons,
            'terrain_summary':reference.summary(),'footprint_summary':ref_sweep.summary(),
            'reach_summary':ref_reach.summary(), 'coverage_all_exactly_once':True,
            'passed':not any(c['outside_tolerance'] for c in comparisons.values())}
        results.append(result)
        (output/'tile-progress.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
    passed = all(r['passed'] for r in results)
    observed_support = hit_paths.get('/World/AirGroundGroundSupportPlane', 0)
    if not observed_support or float(world.current_time) != frozen_time:
        raise RuntimeError('Support plane not observed or world advanced during comparison')
    report = {'scope':'native_small_window_equivalence_only','passed':passed,
        'visibility_diagnostic':visibility,'config_sha256':sha(config_path),'setup':setup,'corrected_binding':binding,
        'terrain_config':asdict(terrain_config),'windows':results,'ray_count':ray_count,
        'observed_collider_hits':hit_paths,'frozen_sim_time_s':frozen_time,
        'formal_gt_approved':False,'full_map_generated':False,
        'limitations':['Small windows only; no full-scene mapping or server artifact equivalence.',
            'No camera, ROS, live robot motion or semantic detector in this experiment.',
            'One-cell halo validates terrain derivatives only; footprint and component operations run globally.']}
    (output/'tile-validation.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    if not passed:
        raise RuntimeError('Whole-window and tiled PhysX results differ; inspect tile-validation.json')
    return report
