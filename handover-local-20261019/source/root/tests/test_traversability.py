"""Traversability graph query tests."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pytest
import yaml

from airground_benchmark.ground_truth import (
    ConfirmationPose,
    ConfirmationRegion,
    GroundTruthError,
    TraversabilityGrid,
    TraversabilityMetadata,
)
from airground_benchmark.traversability import (
    FootprintSweepConfig,
    RaycastTerrainGridConfig,
    TerrainRaycastHit,
    TraversabilityQuery,
    build_jackal_ground_threshold_calibration_report,
    build_traversability_rollout_report,
    build_traversability_mismatch_review_report,
    canonical_jackal_ground_threshold_calibration_json,
    canonical_traversability_mismatch_review_report_json,
    canonical_traversability_rollout_report_json,
    build_raycast_terrain_grid,
    compute_local_traversability_features,
    jackal_ground_threshold_config_yaml,
    connected_components,
    estimate_jackal_footprint_from_asset_report,
    load_jackal_footprint_estimate_from_asset_report,
    load_raycast_terrain_grid,
    sweep_ugv_footprint_over_terrain,
    write_footprint_sweep_artifact,
    write_traversability_artifact,
)
from airground_benchmark.traversability import write_nav2_occupancy_grid


def test_obstacle_band_matches_local_avoidance_semantics() -> None:
    """2026-09-19 (user): GT obstacles must follow the local avoidance band.

    A shelter roof *above* the band leaves the ground underneath traversable -
    exactly what the Nav2 voxel layer sees - while a fence *inside* the band
    blocks the cell.  The previous rule ("anything hit before the ground")
    blocked under-roof cells, and because NavFn seeds its potential field at the
    robot's own cell, the UGV that drove under a bus-shelter roof became a
    one-cell hole inside the lethal footprint and could not plan any goal
    (``smoke_20260919_153113``).
    """

    metadata = _metadata((1, 3))

    def fake_raycast(origin, direction, max_distance):
        x_m, y_m, z_m = origin
        col = int(x_m)
        if direction == (0.0, 0.0, -1.0):
            hits: list[object] = []
            if col == 1:
                hits.append(
                    {
                        "distance": z_m - 2.8,
                        "position": (x_m, y_m, 2.8),
                        "normal": (0.0, 0.0, -1.0),
                        "prim_path": "/World/stage/BusStop/Roof",
                    }
                )
            hits.append(
                {
                    "distance": z_m,
                    "position": (x_m, y_m, 0.0),
                    "normal": (0.0, 0.0, 1.0),
                    "prim_path": f"/World/stage/Ground/{col}",
                }
            )
            return hits
        if direction == (0.0, 0.0, 1.0):
            if col == 1 and z_m < 2.0:
                return TerrainRaycastHit(
                    distance_m=2.8 - z_m,
                    position_xyz_m=(x_m, y_m, 2.8),
                    normal_xyz=(0.0, 0.0, -1.0),
                    prim_path="/World/stage/BusStop/Roof",
                )
            if col == 2:
                return TerrainRaycastHit(
                    distance_m=0.6 - z_m,
                    position_xyz_m=(x_m, y_m, 0.6),
                    normal_xyz=(1.0, 0.0, 0.0),
                    prim_path="/World/stage/Fence",
                )
            return None
        return None

    terrain = build_raycast_terrain_grid(
        metadata,
        fake_raycast,
        RaycastTerrainGridConfig(
            ray_start_z_m=10.0,
            ray_end_z_m=-2.0,
            overhead_ray_distance_m=4.0,
            min_ground_normal_z=0.35,
            min_obstacle_height_m=0.05,
            max_obstacle_height_m=1.0,
        ),
    )

    assert terrain.support_mask.tolist() == [[True, True, True]]
    # The downward ray keeps going past the roof: the ground under it (z=0) is
    # the driving surface, not the 2.8 m roof top.
    assert terrain.height[0, 1] == pytest.approx(0.0)
    # col 0: plain ground; col 1: roof 2.8 m up -> traversable; col 2: fence
    # 0.6 m -> inside the band -> blocked.
    assert terrain.obstacle_mask.tolist() == [[False, False, True]]
    assert terrain.ceiling_height[0, 1] == pytest.approx(2.8)
    assert terrain.overhead_clearance_m[0, 1] == pytest.approx(2.8)
    grid = terrain.traversability_grid()
    assert grid.mask.tolist() == [[1, 1, 0]]


def _metadata(shape: tuple[int, int]) -> TraversabilityMetadata:
    return TraversabilityMetadata.model_validate(
        {
            "schema_version": "1.0.0",
            "scene_id": "RetroNeighborhood",
            "frame": "map",
            "origin": {"x_m": 0.0, "y_m": 0.0, "z_m": 0.0},
            "resolution_m": 1.0,
            "shape": list(shape),
            "generator": "unit-test",
            "generator_version": "0",
        }
    )


JACKAL_REPORT = (
    Path(__file__).resolve().parents[1]
    / "AirStack/simulation/isaac-sim/assets/reports_verified/jackal_6_0_1.json"
)
JACKAL_THRESHOLDS = (
    Path(__file__).resolve().parents[1]
    / "benchmark/airground_benchmark/config/traversability/jackal_thresholds.yaml"
)


def _grid(mask: np.ndarray, *, height: np.ndarray | None = None) -> TraversabilityGrid:
    component = connected_components(mask, connectivity=8)
    return TraversabilityGrid(
        metadata=_metadata(mask.shape),
        height=(np.zeros(mask.shape, dtype=np.float32) if height is None else height.astype(np.float32)),
        mask=mask.astype(np.uint8),
        component=component,
        cost=np.ones(mask.shape, dtype=np.float32),
    )


def test_connected_components_are_deterministic_row_major() -> None:
    mask = np.array(
        [
            [1, 0, 1],
            [1, 0, 1],
            [0, 0, 1],
        ],
        dtype=np.uint8,
    )
    components = connected_components(mask, connectivity=4)
    assert components.tolist() == [
        [0, -1, 1],
        [0, -1, 1],
        [-1, -1, 1],
    ]


def test_connected_components_do_not_cut_diagonal_corners() -> None:
    mask = np.array(
        [
            [1, 0],
            [0, 1],
        ],
        dtype=np.uint8,
    )
    components = connected_components(mask, connectivity=8)
    assert components.tolist() == [
        [0, -1],
        [-1, 1],
    ]


def test_shortest_path_distance_routes_around_blocked_center() -> None:
    mask = np.array(
        [
            [1, 1, 1],
            [1, 0, 1],
            [1, 1, 1],
        ],
        dtype=np.uint8,
    )
    query = TraversabilityQuery(_grid(mask))
    assert query.shortest_path_distance_cells((1, 0), (1, 2)) == pytest.approx(4.0)
    assert query.shortest_path_distance_xy((0.5, 1.5), (2.5, 1.5)) == pytest.approx(4.0)


def test_shortest_path_distance_reuses_single_source_cache() -> None:
    mask = np.ones((4, 4), dtype=np.uint8)
    query = TraversabilityQuery(_grid(mask))

    assert query.shortest_path_distance_cells((0, 0), (3, 3)) == pytest.approx(3 * 2**0.5)
    assert len(query._single_source_cache) == 1
    cached = query._single_source_cache[(0, 0)]

    assert query.shortest_path_distance_cells((0, 0), (0, 3)) == pytest.approx(3.0)
    assert query._single_source_cache[(0, 0)] is cached
    assert len(query._single_source_cache) == 1


def test_detour_ratio_to_confirmation_region_uses_nearest_reachable_pose() -> None:
    mask = np.array(
        [
            [1, 1, 1],
            [1, 0, 1],
            [1, 1, 1],
        ],
        dtype=np.uint8,
    )
    query = TraversabilityQuery(_grid(mask))
    region = ConfirmationRegion(
        region_id="confirm/person",
        instance_id="person",
        reachable=True,
        yaw_range_rad=(-1.0, 1.0),
        poses=(
            ConfirmationPose(
                frame="map",
                position_xyz_m=(2.5, 1.5, 0.0),
                yaw_rad=0.0,
                distance_to_target_m=2.0,
                visible_fraction=0.5,
                traversability_component=0,
            ),
        ),
    )
    assert query.detour_ratio_to_confirmation_region((0.5, 1.5), region) == pytest.approx(2.0)


def test_detour_ratio_returns_none_for_unreachable_region() -> None:
    mask = np.array([[1, 0, 1]], dtype=np.uint8)
    query = TraversabilityQuery(_grid(mask))
    region = ConfirmationRegion(
        region_id="confirm/person",
        instance_id="person",
        reachable=True,
        yaw_range_rad=(-1.0, 1.0),
        poses=(
            ConfirmationPose(
                frame="map",
                position_xyz_m=(2.5, 0.5, 0.0),
                yaw_rad=0.0,
                distance_to_target_m=2.0,
                visible_fraction=0.5,
                traversability_component=1,
            ),
        ),
    )
    assert query.detour_ratio_to_confirmation_region((0.5, 0.5), region) is None


def test_detour_ratio_is_one_when_start_is_at_confirmation_pose() -> None:
    mask = np.array([[1]], dtype=np.uint8)
    query = TraversabilityQuery(_grid(mask))
    region = ConfirmationRegion(
        region_id="confirm/person",
        instance_id="person",
        reachable=True,
        yaw_range_rad=(-1.0, 1.0),
        poses=(
            ConfirmationPose(
                frame="map",
                position_xyz_m=(0.5, 0.5, 0.0),
                yaw_rad=0.0,
                distance_to_target_m=2.0,
                visible_fraction=0.5,
                traversability_component=0,
            ),
        ),
    )
    assert query.detour_ratio_to_confirmation_region((0.5, 0.5), region) == 1.0


def test_shortest_path_distance_returns_none_for_disconnected_cells() -> None:
    mask = np.array([[1, 0, 1]], dtype=np.uint8)
    query = TraversabilityQuery(_grid(mask))
    assert query.shortest_path_distance_cells((0, 0), (0, 2)) is None


def test_connected_components_reject_invalid_mask_values() -> None:
    with pytest.raises(GroundTruthError, match="0/1"):
        connected_components(np.array([[1, 2]], dtype=np.uint8))


def test_local_traversability_features_compute_slope_step_and_inflation() -> None:
    mask = np.ones((5, 5), dtype=np.uint8)
    mask[2, 2] = 0
    height = np.tile(np.arange(5, dtype=np.float32), (5, 1))
    height[1, 1] += 0.25

    features = compute_local_traversability_features(
        _grid(mask, height=height),
        robot_radius_m=1.0,
        robot_height_m=1.2,
        max_slope_rad=1.0,
        max_step_height_m=0.5,
        obstacle_inflation_radius_m=1.01,
    )

    assert features.slope_rad[4, 4] == pytest.approx(np.arctan(1.0), abs=1e-6)
    assert features.step_height_m[1, 1] == pytest.approx(1.25)
    assert features.body_clearance_m[2, 3] == pytest.approx(0.0)
    assert features.inflated_obstacle_mask[2, 3]
    assert not features.inflated_obstacle_mask[0, 0]
    assert not features.safe_mask[2, 3]
    assert features.summary()["inflated_obstacle_cells"] == 5


def test_local_traversability_features_apply_overhead_clearance() -> None:
    mask = np.ones((3, 3), dtype=np.uint8)
    ceiling = np.full((3, 3), 3.0, dtype=np.float32)
    ceiling[1, 1] = 1.0

    features = compute_local_traversability_features(
        _grid(mask),
        robot_radius_m=0.4,
        robot_height_m=1.2,
        max_slope_rad=0.5,
        max_step_height_m=0.1,
        obstacle_inflation_radius_m=0.0,
        ceiling_height=ceiling,
        overhead_clearance_margin_m=0.1,
    )

    assert features.overhead_clearance_m[1, 1] == pytest.approx(1.0)
    assert not features.safe_mask[1, 1]
    assert features.safe_mask[0, 0]


def test_local_traversability_features_reject_bad_inputs() -> None:
    with pytest.raises(GroundTruthError, match="robot_radius"):
        compute_local_traversability_features(
            _grid(np.ones((1, 1), dtype=np.uint8)),
            robot_radius_m=0.0,
            robot_height_m=1.0,
            max_slope_rad=0.5,
            max_step_height_m=0.1,
        )


def test_raycast_terrain_grid_builds_height_normal_obstacle_and_headroom() -> None:
    metadata = _metadata((2, 3))

    def fake_raycast(origin, direction, max_distance):
        x_m, y_m, z_m = origin
        col = int(x_m)
        row = int(y_m)
        # 2026-09-19: the obstacle band is *absolute* (map-frame), exactly like
        # the Nav2 voxel layer, so the fixture ground sits at z ~= 0 (the real
        # RetroNeighborhood roads do).  ``max_distance`` separates the two
        # up-rays: < 1 m is the obstacle-band probe, 4 m is the headroom probe.
        ground_z = 0.04 if (row, col) == (1, 1) else 0.0
        is_band_ray = direction == (0.0, 0.0, 1.0) and max_distance < 1.5
        if direction == (0.0, 0.0, -1.0):
            if (row, col) == (1, 2):
                return []
            ground_distance = z_m - ground_z
            ground_hit = TerrainRaycastHit(
                distance_m=ground_distance,
                position_xyz_m=(x_m, y_m, ground_z),
                normal_xyz=(0.0, 0.0, 1.0),
                prim_path=f"/World/stage/Ground/cell_{row}_{col}",
            )
            if (row, col) == (0, 1):
                return [
                    {
                        "distance": z_m - (ground_z + 0.25),
                        "position": (x_m, y_m, ground_z + 0.25),
                        "normal": (1.0, 0.0, 0.0),
                        "prim_path": "/World/stage/Wall/blocker",
                    },
                    ground_hit,
                ]
            return {"hits": [ground_hit]}
        if direction == (0.0, 0.0, 1.0):
            if (row, col) == (0, 0):
                if is_band_ray:
                    # The band probe only reaches 1.0 m: the canopy is above it.
                    return None
                # A canopy 1.5 m above the ground: above the obstacle band, so
                # it contributes headroom diagnostics only.
                return TerrainRaycastHit(
                    distance_m=1.5,
                    position_xyz_m=(x_m, y_m, z_m + 1.5),
                    normal_xyz=(0.0, 0.0, -1.0),
                    prim_path="/World/stage/Canopy",
                )
            if (row, col) == (0, 1):
                # A 0.25 m wall slab sits inside the absolute [0.05, 1.0] band,
                # so both the band probe and the headroom probe hit it.
                wall_z = 0.25
                return TerrainRaycastHit(
                    distance_m=wall_z - z_m,
                    position_xyz_m=(x_m, y_m, wall_z),
                    normal_xyz=(1.0, 0.0, 0.0),
                    prim_path="/World/stage/Wall/blocker",
                )
        return None

    terrain = build_raycast_terrain_grid(
        metadata,
        fake_raycast,
        RaycastTerrainGridConfig(
            ray_start_z_m=10.0,
            ray_end_z_m=-2.0,
            overhead_ray_distance_m=4.0,
            min_ground_normal_z=0.35,
        ),
    )

    assert terrain.height[0, 2] == pytest.approx(0.0)
    assert terrain.height[1, 1] == pytest.approx(0.04)
    assert terrain.normal[0, 2].tolist() == [0.0, 0.0, 1.0]
    assert terrain.support_mask.tolist() == [[True, True, True], [True, True, False]]
    assert terrain.obstacle_mask.tolist() == [[False, True, False], [False, False, False]]
    assert terrain.overhead_clearance_m[0, 0] == pytest.approx(1.5)
    assert terrain.overhead_clearance_m[0, 2] == pytest.approx(4.0)
    assert terrain.slope_rad[0, 1] > 0.0
    assert terrain.step_height_m[0, 1] > 0.0

    grid = terrain.traversability_grid()
    assert grid.mask.tolist() == [[1, 0, 1], [1, 1, 0]]
    assert grid.component[0, 1] == -1
    arrays = terrain.arrays_for_npz()
    assert set(arrays) == {
        "height",
        "normal",
        "cost",
        "mask",
        "component",
        "ceiling_height",
        "obstacle_mask",
        "overhead_clearance_m",
        "slope_rad",
        "step_height_m",
        "support_mask",
    }
    assert arrays["support_mask"].shape == metadata.shape
    assert arrays["overhead_clearance_m"][0, 0] == pytest.approx(1.5)
    assert arrays["normal"].shape == (2, 3, 3)
    assert terrain.summary()["traversable_seed_cells"] == 4


def test_headroom_ray_ignores_ground_surface_self_hits() -> None:
    """A ray that starts on a collider must not report that collider as ceiling.

    PhysX answers such a ray with an initial-overlap hit whose position sits at
    or below the origin (measured 2026-09-17 on the runtime
    ``/World/AirGroundGroundSupportPlane``: up-ray from the plane top z=0.00
    returned a hit at z=-0.04).  Counting it as headroom makes every ground cell
    look like it has ~0 m clearance and rejects the whole ROI in the footprint
    sweep.
    """

    metadata = _metadata((1, 2))

    def raycast(origin, direction, max_distance):
        x_m, y_m, z_m = origin
        if direction == (0.0, 0.0, -1.0):
            return TerrainRaycastHit(
                distance_m=z_m,
                position_xyz_m=(x_m, y_m, 0.0),
                normal_xyz=(0.0, 0.0, 1.0),
                prim_path="/World/AirGroundGroundSupportPlane",
            )
        if direction == (0.0, 0.0, 1.0):
            hits = [
                TerrainRaycastHit(
                    distance_m=0.141,
                    position_xyz_m=(x_m, y_m, -0.04),
                    normal_xyz=(0.0, 0.0, -1.0),
                    prim_path="/World/AirGroundGroundSupportPlane",
                )
            ]
            if x_m > 1.0:
                hits.append(
                    TerrainRaycastHit(
                        distance_m=2.0,
                        position_xyz_m=(x_m, y_m, 2.0),
                        normal_xyz=(0.0, 0.0, -1.0),
                        prim_path="/World/stage/Canopy",
                    )
                )
            return hits
        return None

    terrain = build_raycast_terrain_grid(
        metadata,
        raycast,
        RaycastTerrainGridConfig(
            ray_start_z_m=4.0,
            ray_end_z_m=-1.0,
            overhead_ray_distance_m=3.0,
        ),
    )

    # Cell without any real ceiling: the surface self-hit is ignored, so the
    # cell keeps the full headroom instead of a ~0 m clearance.
    assert terrain.height[0, 0] == pytest.approx(0.0)
    assert terrain.overhead_clearance_m[0, 0] == pytest.approx(3.0)
    # Cell with a real canopy above the self-hit: the canopy is the ceiling.
    assert terrain.overhead_clearance_m[0, 1] == pytest.approx(2.0)


def test_headroom_self_hit_margin_is_validated() -> None:
    with pytest.raises(GroundTruthError, match="overhead_hit_min_clearance_m"):
        RaycastTerrainGridConfig(
            ray_start_z_m=4.0,
            ray_end_z_m=-1.0,
            overhead_ray_distance_m=3.0,
            overhead_hit_min_clearance_m=-0.1,
        )
    with pytest.raises(GroundTruthError, match="overhead_hit_min_clearance_m"):
        RaycastTerrainGridConfig(
            ray_start_z_m=4.0,
            ray_end_z_m=-1.0,
            overhead_ray_distance_m=3.0,
            overhead_hit_min_clearance_m=3.0,
        )


def test_raycast_terrain_grid_rejects_bad_hits_and_config() -> None:
    metadata = _metadata((1, 1))

    with pytest.raises(GroundTruthError, match="ray_start_z_m"):
        RaycastTerrainGridConfig(
            ray_start_z_m=0.0,
            ray_end_z_m=0.0,
            overhead_ray_distance_m=1.0,
        )

    def bad_raycast(origin, direction, max_distance):
        return {"distance": 1.0, "normal": (0.0, 0.0, 0.0)}

    with pytest.raises(GroundTruthError, match="non-zero"):
        build_raycast_terrain_grid(
            metadata,
            bad_raycast,
            RaycastTerrainGridConfig(
                ray_start_z_m=2.0,
                ray_end_z_m=-1.0,
                overhead_ray_distance_m=1.0,
            ),
        )


def test_footprint_sweep_generates_mask_component_inflation_and_cost() -> None:
    metadata = _metadata((7, 7))

    def ground_raycast(origin, direction, max_distance):
        x_m, y_m, z_m = origin
        if direction == (0.0, 0.0, -1.0):
            return TerrainRaycastHit(
                distance_m=z_m,
                position_xyz_m=(x_m, y_m, 0.0),
                normal_xyz=(0.0, 0.0, 1.0),
                prim_path="/World/stage/Ground",
            )
        return None

    terrain = build_raycast_terrain_grid(
        metadata,
        ground_raycast,
        RaycastTerrainGridConfig(
            ray_start_z_m=2.0,
            ray_end_z_m=-1.0,
            overhead_ray_distance_m=3.0,
        ),
    )
    terrain.obstacle_mask[3, 3] = True
    terrain.slope_rad[1, 1] = np.float32(1.0)
    terrain.step_height_m[5, 5] = np.float32(0.5)
    terrain.overhead_clearance_m[0, 6] = np.float32(0.1)

    sweep = sweep_ugv_footprint_over_terrain(
        terrain,
        FootprintSweepConfig(
            footprint_length_m=1.0,
            footprint_width_m=1.0,
            yaw_samples=4,
            max_slope_rad=0.5,
            max_step_height_m=0.2,
            min_overhead_clearance_m=0.5,
        ),
    )

    assert not sweep.traversable_mask[3, 3]
    assert not sweep.traversable_mask[1, 1]
    assert not sweep.traversable_mask[5, 5]
    assert not sweep.traversable_mask[0, 6]
    assert sweep.inflation_mask[3, 2] or sweep.inflation_mask[2, 3]
    assert sweep.component.shape == (7, 7)
    assert sweep.cost[3, 3] == pytest.approx(1.0e6)
    assert sweep.cost[sweep.traversable_mask].min() >= 1.0
    grid = sweep.traversability_grid()
    assert grid.mask.dtype == np.uint8
    assert grid.cost is not None
    arrays = sweep.arrays_for_npz()
    assert arrays["normal"].shape == (7, 7, 3)
    assert sweep.summary()["generator"] == "airground-jackal-footprint-sweep-v1"


def test_footprint_sweep_rejects_bad_config_and_shapes() -> None:
    metadata = _metadata((1, 1))

    with pytest.raises(GroundTruthError, match="footprint_length"):
        FootprintSweepConfig(footprint_length_m=0.0)

    terrain = build_raycast_terrain_grid(
        metadata,
        lambda origin, direction, max_distance: TerrainRaycastHit(
            distance_m=1.0,
            position_xyz_m=(origin[0], origin[1], 0.0),
            normal_xyz=(0.0, 0.0, 1.0),
            prim_path="/World/stage/Ground",
        )
        if direction == (0.0, 0.0, -1.0)
        else None,
        RaycastTerrainGridConfig(
            ray_start_z_m=1.0,
            ray_end_z_m=-1.0,
            overhead_ray_distance_m=1.0,
        ),
    )
    bad = type(
        "BadTerrain",
        (),
        {
            **terrain.__dict__,
            "support_mask": np.ones((2, 1), dtype=bool),
        },
    )()
    with pytest.raises(GroundTruthError, match="support_mask shape"):
        sweep_ugv_footprint_over_terrain(bad, FootprintSweepConfig())


def test_jackal_footprint_estimate_uses_asset_report_collisions_and_joints() -> None:
    report = {
        "asset_id": "isaac_sim.clearpath_jackal",
        "simulator_version": "6.0.1",
        "collisions": [
            {
                "path": "/jackal/base_link/collisions/body",
                "attributes": {"extent": [[-0.20, -0.15, -0.09], [0.20, 0.15, 0.09]]},
            },
            {
                "path": "/jackal/front_left_wheel_link/collisions",
                "attributes": {"radius": 0.10, "height": 0.04},
            },
            {
                "path": "/jackal/front_right_wheel_link/collisions",
                "attributes": {"radius": 0.10, "height": 0.04},
            },
            {
                "path": "/jackal/rear_left_wheel_link/collisions",
                "attributes": {"radius": 0.10, "height": 0.04},
            },
            {
                "path": "/jackal/rear_right_wheel_link/collisions",
                "attributes": {"radius": 0.10, "height": 0.04},
            },
        ],
        "joints": [
            {
                "path": "/jackal/front_left_wheel_joint",
                "body0": ["/jackal/base_link"],
                "body1": ["/jackal/front_left_wheel_link"],
                "attributes": {"physics:localPos0": [0.13, 0.18, 0.03]},
            },
            {
                "path": "/jackal/front_right_wheel_joint",
                "body0": ["/jackal/base_link"],
                "body1": ["/jackal/front_right_wheel_link"],
                "attributes": {"physics:localPos0": [0.13, -0.18, 0.03]},
            },
            {
                "path": "/jackal/rear_left_wheel_joint",
                "body0": ["/jackal/base_link"],
                "body1": ["/jackal/rear_left_wheel_link"],
                "attributes": {"physics:localPos0": [-0.13, 0.18, 0.03]},
            },
            {
                "path": "/jackal/rear_right_wheel_joint",
                "body0": ["/jackal/base_link"],
                "body1": ["/jackal/rear_right_wheel_link"],
                "attributes": {"physics:localPos0": [-0.13, -0.18, 0.03]},
            },
        ],
    }

    estimate = estimate_jackal_footprint_from_asset_report(
        report,
        padding_m=0.02,
        report_sha256="abc123",
    )

    assert estimate.length_m == pytest.approx(0.50)
    assert estimate.width_m == pytest.approx(0.44)
    assert estimate.source == "asset_report"
    assert estimate.report_sha256 == "abc123"
    assert estimate.report_asset_id == "isaac_sim.clearpath_jackal"
    assert len(estimate.wheel_joint_paths) == 4
    config = estimate.sweep_config(yaw_samples=16)
    assert config.footprint_source == "asset_report"
    assert config.footprint_report_sha256 == "abc123"
    assert config.footprint_padding_m == pytest.approx(0.02)


def test_jackal_footprint_estimate_matches_verified_isaac_6_report() -> None:
    estimate = load_jackal_footprint_estimate_from_asset_report(JACKAL_REPORT, padding_m=0.025)

    assert estimate.report_asset_id == "isaac_sim.clearpath_jackal"
    assert estimate.report_simulator_version == "6.0.1"
    assert estimate.length_m == pytest.approx(0.508, abs=1.0e-6)
    assert estimate.width_m == pytest.approx(0.46559, abs=1.0e-6)
    assert estimate.report_sha256 is not None
    assert "/jackal/base_link/collisions/body" in estimate.body_collision_paths
    assert "/jackal/front_left_wheel_joint" in estimate.wheel_joint_paths


def test_jackal_footprint_estimate_rejects_missing_wheel_evidence() -> None:
    with pytest.raises(GroundTruthError, match="wheel joint footprint evidence"):
        estimate_jackal_footprint_from_asset_report(
            {
                "collisions": [
                    {
                        "path": "/jackal/base_link/collisions/body",
                        "attributes": {"extent": [[-0.20, -0.15, 0.0], [0.20, 0.15, 0.1]]},
                    }
                ],
                "joints": [],
            }
        )


def test_write_nav2_occupancy_grid_writes_yaml_and_flipped_pgm(tmp_path) -> None:
    mask = np.array(
        [
            [1, 0, 1],
            [0, 1, 0],
        ],
        dtype=np.uint8,
    )
    export = write_nav2_occupancy_grid(_grid(mask), tmp_path, stem="retro_nav2")

    assert export.summary()["status"] == "ok"
    assert export.free_cells == 3
    assert export.occupied_cells == 3
    assert export.unknown_cells == 0
    assert export.yaml_sha256 == hashlib.sha256(export.yaml_path.read_bytes()).hexdigest()
    yaml_text = export.yaml_path.read_text(encoding="utf-8")
    assert "image: retro_nav2.pgm" in yaml_text
    assert "resolution: 1.0" in yaml_text
    assert "origin:" in yaml_text

    pgm = export.image_path.read_bytes()
    header = b"P5\n# RAVEN-AirGround traversability occupancy grid\n3 2\n255\n"
    assert pgm.startswith(header)
    # PGM row 0 is topmost, so it should contain the last traversability grid row.
    assert list(pgm[len(header):]) == [0, 254, 0, 254, 0, 254]


def test_write_nav2_occupancy_grid_rejects_unsafe_stem(tmp_path) -> None:
    with pytest.raises(GroundTruthError, match="stem"):
        write_nav2_occupancy_grid(_grid(np.ones((1, 1), dtype=np.uint8)), tmp_path, stem="../bad")


def test_footprint_sweep_artifact_writes_auxiliary_and_deterministic_outputs(tmp_path) -> None:
    metadata = _metadata((5, 5))

    def ground_raycast(origin, direction, max_distance):
        x_m, y_m, z_m = origin
        if direction == (0.0, 0.0, -1.0):
            return TerrainRaycastHit(
                distance_m=z_m,
                position_xyz_m=(x_m, y_m, 0.0),
                normal_xyz=(0.0, 0.0, 1.0),
                prim_path="/World/stage/Ground",
            )
        return None

    terrain = build_raycast_terrain_grid(
        metadata,
        ground_raycast,
        RaycastTerrainGridConfig(
            ray_start_z_m=2.0,
            ray_end_z_m=-1.0,
            overhead_ray_distance_m=3.0,
        ),
    )
    terrain.obstacle_mask[2, 2] = True
    raycast_npz = tmp_path / "raycast_seed.npz"
    np.savez(raycast_npz, **terrain.arrays_for_npz())

    loaded = load_raycast_terrain_grid(metadata, raycast_npz)
    assert loaded.support_mask.shape == (5, 5)
    assert loaded.obstacle_mask[2, 2]
    assert loaded.overhead_clearance_m.min() == pytest.approx(3.0)

    first = write_footprint_sweep_artifact(
        metadata,
        raycast_npz,
        tmp_path / "first",
        stem="retro_sweep",
        config=FootprintSweepConfig(
            footprint_length_m=1.0,
            footprint_width_m=1.0,
            yaw_samples=4,
        ),
    )
    second = write_footprint_sweep_artifact(
        metadata,
        raycast_npz,
        tmp_path / "second",
        stem="retro_sweep",
        config=FootprintSweepConfig(
            footprint_length_m=1.0,
            footprint_width_m=1.0,
            yaw_samples=4,
        ),
    )

    assert first.summary()["status"] == "ok"
    assert first.traversability_export.npz_sha256 == second.traversability_export.npz_sha256
    assert first.auxiliary_npz_sha256 == second.auxiliary_npz_sha256
    assert first.sweep_summary["traversable_cells"] < 25
    with np.load(first.auxiliary_npz_path) as data:
        assert "inflation_mask" in data.files
        assert data["inflation_mask"].shape == (5, 5)
    assert first.summary_path.is_file()


def test_write_traversability_artifact_is_deterministic_and_self_describing(tmp_path) -> None:
    metadata = _metadata((2, 2))
    arrays = {
        "height": np.zeros((2, 2), dtype=np.float32),
        "normal": np.dstack(
            [
                np.zeros((2, 2), dtype=np.float32),
                np.zeros((2, 2), dtype=np.float32),
                np.ones((2, 2), dtype=np.float32),
            ]
        ),
        "cost": np.ones((2, 2), dtype=np.float32),
        "mask": np.array([[1, 0], [0, 1]], dtype=np.uint8),
        "component": np.array([[1, -1], [-1, 1]], dtype=np.int32),
    }

    first = write_traversability_artifact(metadata, arrays, tmp_path / "first", stem="retro")
    second = write_traversability_artifact(metadata, arrays, tmp_path / "second", stem="retro")

    assert first.summary()["status"] == "ok"
    assert first.npz_sha256 == second.npz_sha256
    assert first.metadata_sha256 == second.metadata_sha256
    assert first.validation_summary["traversable_cells"] == 2
    assert "npz_sha256" in first.metadata_path.read_text(encoding="utf-8")
    assert (tmp_path / "first" / "retro.nav2.yaml").is_file()
    assert (tmp_path / "first" / "retro.nav2.pgm").is_file()
    assert first.manifest_path.is_file()


def test_traversability_rollout_report_tracks_consistency_and_mismatches() -> None:
    report = build_traversability_rollout_report(
        (
            {
                "sample_id": "open-cell",
                "sample_kind": "cell",
                "start_cell": [0, 0],
                "expected_traversable": True,
                "rollout_success": True,
            },
            {
                "sample_id": "blocked-edge",
                "sample_kind": "edge",
                "start_cell": [1, 1],
                "end_cell": [1, 2],
                "expected_traversable": False,
                "rollout_success": True,
                "reason": "jackal crossed inflated obstacle",
            },
        ),
        min_samples=2,
        min_consistency=0.5,
    )
    summary = report.summary()

    assert summary["status"] == "ok"
    assert summary["sample_count"] == 2
    assert summary["match_count"] == 1
    assert summary["mismatch_count"] == 1
    assert summary["kind_counts"] == {"cell": 1, "edge": 1, "short_path": 0}
    assert summary["mismatches"][0]["sample_id"] == "blocked-edge"
    assert canonical_traversability_rollout_report_json(report) == canonical_traversability_rollout_report_json(report)


def test_traversability_mismatch_review_accepts_zero_mismatch_run() -> None:
    report = build_traversability_mismatch_review_report(
        (
            {
                "sample_id": "route-000",
                "sample_kind": "short_path",
                "start_cell": [10, 10],
                "end_cell": [10, 20],
                "expected_traversable": True,
                "rollout_success": True,
            },
        )
    )
    summary = report.summary()

    assert summary["status"] == "ok"
    assert summary["sample_count"] == 1
    assert summary["mismatch_count"] == 0
    assert summary["entries"] == []
    assert json.loads(canonical_traversability_mismatch_review_report_json(report))["status"] == "ok"


def test_traversability_mismatch_review_requires_artifacts_for_mismatch() -> None:
    records = (
        {
            "sample_id": "blocked-edge",
            "sample_kind": "edge",
            "start_cell": [1, 1],
            "end_cell": [1, 2],
            "expected_traversable": False,
            "rollout_success": True,
            "reason": "jackal crossed inflated obstacle",
        },
    )

    missing = build_traversability_mismatch_review_report(records).summary()
    reviewed = build_traversability_mismatch_review_report(
        records,
        screenshot_paths={"blocked-edge": "screenshots/blocked-edge.png"},
        final_dispositions={"blocked-edge": "mark static cell traversable after replay review"},
    ).summary()

    assert missing["status"] == "failed"
    assert missing["issue_counts"] == {
        "missing_final_disposition": 1,
        "missing_screenshot": 1,
    }
    assert missing["unreviewed_count"] == 1
    assert reviewed["status"] == "ok"
    assert reviewed["reviewed_count"] == 1
    assert reviewed["entries"][0]["screenshot_path"] == "screenshots/blocked-edge.png"


def test_jackal_ground_threshold_calibration_derives_max_tested_stable_values() -> None:
    records = (
        {
            "event": "jackal_ground_testbed_outcome",
            "test_id": "slope-05",
            "test_kind": "slope",
            "slope_deg": 5.0,
            "status": "ok",
            "collision_count": 0,
            "max_tilt_rad": 0.10,
        },
        {
            "event": "jackal_ground_testbed_outcome",
            "test_id": "slope-10",
            "test_kind": "slope",
            "slope_deg": 10.0,
            "status": "ok",
            "collision_count": 0,
            "max_tilt_rad": 0.18,
        },
        {
            "event": "jackal_ground_testbed_outcome",
            "test_id": "slope-15",
            "test_kind": "slope",
            "slope_deg": 15.0,
            "status": "failed",
            "collision_count": 0,
            "tipped": True,
            "max_tilt_rad": 0.80,
        },
        {
            "event": "jackal_ground_testbed_outcome",
            "test_id": "step-05",
            "test_kind": "step",
            "step_height_m": 0.05,
            "status": "ok",
            "collision_count": 0,
            "max_tilt_rad": 0.12,
        },
        {
            "event": "jackal_ground_testbed_outcome",
            "test_id": "step-10",
            "test_kind": "step",
            "step_height_m": 0.10,
            "status": "ok",
            "collision_count": 0,
            "max_tilt_rad": 0.20,
        },
        {
            "event": "jackal_ground_testbed_outcome",
            "test_id": "step-15",
            "test_kind": "step",
            "step_height_m": 0.15,
            "status": "failed",
            "collision_count": 0,
            "excessive_slip": True,
            "max_tilt_rad": 0.22,
        },
    )

    report = build_jackal_ground_threshold_calibration_report(records)
    summary = report.summary()
    config = report.versioned_config()

    assert summary["status"] == "ok"
    assert summary["max_stable_slope_deg"] == 10.0
    assert summary["max_step_height_m"] == 0.10
    assert config["threshold_scope"] == "max_tested_stable"
    assert "max_stable_slope_deg: 10.0" in jackal_ground_threshold_config_yaml(report)
    assert json.loads(canonical_jackal_ground_threshold_calibration_json(report))["status"] == "ok"


def test_jackal_ground_threshold_calibration_rejects_non_monotonic_outcomes() -> None:
    report = build_jackal_ground_threshold_calibration_report(
        (
            {
                "event": "jackal_ground_testbed_outcome",
                "test_kind": "slope",
                "slope_deg": 5.0,
                "status": "failed",
                "collision_count": 0,
                "tipped": True,
            },
            {
                "event": "jackal_ground_testbed_outcome",
                "test_kind": "slope",
                "slope_deg": 10.0,
                "status": "ok",
                "collision_count": 0,
            },
            {
                "event": "jackal_ground_testbed_outcome",
                "test_kind": "step",
                "step_height_m": 0.05,
                "status": "ok",
                "collision_count": 0,
            },
        )
    )
    summary = report.summary()

    assert summary["status"] == "failed"
    assert summary["issue_counts"]["non_monotonic_slope_outcomes"] == 1
    with pytest.raises(GroundTruthError, match="failed calibration"):
        report.versioned_config()


def test_checked_in_jackal_ground_threshold_config_is_versioned() -> None:
    config = yaml.safe_load(JACKAL_THRESHOLDS.read_text(encoding="utf-8"))

    assert config == {
        "calibration_version": "airground-jackal-ground-threshold-calibration-v1",
        "max_stable_slope_deg": 15.0,
        "max_step_height_m": 0.2,
        "robot_id": "isaacsim.clearpath_jackal",
        "schema_version": "1.0.0",
        "testbed_version": "airground-jackal-ground-testbed-v1",
        "threshold_scope": "max_tested_stable",
    }


def test_traversability_rollout_report_rejects_bad_samples() -> None:
    with pytest.raises(GroundTruthError, match="sample_kind"):
        build_traversability_rollout_report(
            (
                {
                    "sample_kind": "teleport",
                    "start_cell": [0, 0],
                    "expected_traversable": True,
                    "rollout_success": True,
                },
            ),
            min_samples=1,
        )
