"""Traversability graph queries for UGV planning and episode difficulty."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
import hashlib
import heapq
import io
import json
import math
from pathlib import Path
import re
from typing import Any
import zipfile

import numpy as np
import yaml

from airground_benchmark.ground_truth import (
    ConfirmationRegion,
    GroundTruthError,
    TraversabilityMetadata,
    TraversabilityGrid,
    canonical_traversability_metadata_json,
    traversability_npz_sha256,
    validate_traversability_npz,
)


GridCell = tuple[int, int]
TerrainRaycastFn = Callable[
    [tuple[float, float, float], tuple[float, float, float], float],
    Any,
]


@dataclass(frozen=True)
class TerrainRaycastHit:
    """One normalized terrain raycast hit.

    The real Isaac adapter can construct this directly from PhysX scene-query
    results. Unit tests can use the same dataclass without importing Isaac.
    """

    distance_m: float
    position_xyz_m: tuple[float, float, float]
    normal_xyz: tuple[float, float, float]
    prim_path: str | None = None


@dataclass(frozen=True)
class RaycastTerrainGrid:
    """Terrain arrays produced by adapter-provided scene raycasts."""

    metadata: TraversabilityMetadata
    height: np.ndarray
    normal: np.ndarray
    support_mask: np.ndarray
    obstacle_mask: np.ndarray
    ceiling_height: np.ndarray
    slope_rad: np.ndarray
    step_height_m: np.ndarray
    overhead_clearance_m: np.ndarray
    #: Obstacle height band used for ``obstacle_mask`` (2026-09-19).  ``None``
    #: for artifacts produced before the band rule existed.
    obstacle_band_m: tuple[float, float] | None = None

    def traversability_grid(self) -> TraversabilityGrid:
        """Return a conservative TraversabilityGrid from raycast support data."""
        traversable = self.support_mask.astype(bool) & ~self.obstacle_mask.astype(bool)
        component = connected_components(traversable.astype(np.uint8), connectivity=8)
        return TraversabilityGrid(
            metadata=self.metadata,
            height=self.height.astype(np.float32),
            mask=traversable.astype(np.uint8),
            component=component,
            cost=np.ones(self.metadata.shape, dtype=np.float32),
        )

    def arrays_for_npz(self) -> dict[str, np.ndarray]:
        """Return schema-compatible traversability arrays.

        This is a raycast input surface only. Footprint sweep and dynamics
        rollout can replace mask/cost/component later before release.
        """
        grid = self.traversability_grid()
        return {
            "height": self.height.astype(np.float32),
            "normal": self.normal.astype(np.float32),
            "cost": grid.cost.astype(np.float32) if grid.cost is not None else np.ones(self.metadata.shape, dtype=np.float32),
            "mask": grid.mask.astype(np.uint8),
            "component": grid.component.astype(np.int32),
            "ceiling_height": self.ceiling_height.astype(np.float32),
            "obstacle_mask": self.obstacle_mask.astype(np.uint8),
            "overhead_clearance_m": self.overhead_clearance_m.astype(np.float32),
            "slope_rad": self.slope_rad.astype(np.float32),
            "step_height_m": self.step_height_m.astype(np.float32),
            "support_mask": self.support_mask.astype(np.uint8),
        }

    def summary(self) -> dict[str, Any]:
        """Return deterministic aggregate raycast-grid statistics."""
        result: dict[str, Any] = {
            "generator": "airground-isaac-raycast-terrain-grid-v1",
            "height_max_m": float(np.max(self.height)),
            "height_min_m": float(np.min(self.height)),
            "obstacle_cells": int(self.obstacle_mask.astype(bool).sum()),
            "overhead_clearance_min_m": float(np.min(self.overhead_clearance_m)),
            "shape": list(self.metadata.shape),
            "slope_max_rad": float(np.max(self.slope_rad)),
            "status": "ok",
            "step_height_max_m": float(np.max(self.step_height_m)),
            "support_cells": int(self.support_mask.astype(bool).sum()),
            "traversable_seed_cells": int(
                (self.support_mask.astype(bool) & ~self.obstacle_mask.astype(bool)).sum()
            ),
        }
        if self.obstacle_band_m is not None:
            # The obstacle band is part of the artifact contract: it decides
            # which geometry blocks a cell, so it has to be auditable without
            # re-reading the generator invocation (2026-09-19).
            result["obstacle_band_min_height_m"] = float(self.obstacle_band_m[0])
            result["obstacle_band_max_height_m"] = float(self.obstacle_band_m[1])
        return result


@dataclass(frozen=True)
class RaycastTerrainGridConfig:
    """Configuration for converting scene raycasts into terrain arrays."""

    ray_start_z_m: float
    ray_end_z_m: float
    overhead_ray_distance_m: float
    min_ground_normal_z: float = 0.35
    #: Minimum height (m) above the ground surface for a hit to count as a
    #: headroom ceiling.  PhysX answers a ray that starts exactly on a surface
    #: (or inside a collider's contact offset) with an "initial overlap" hit
    #: whose reported position is at or below the origin, so without this margin
    #: every ground cell looks like it has zero headroom.  The 2026-09-17 probe
    #: of the runtime RetroNeighborhood scene measured that self-hit on
    #: ``/World/AirGroundGroundSupportPlane`` (position z=-0.04 for an up-ray
    #: that starts at the plane top z=0.00), which made 95% of the ROI fail the
    #: 0.50 m footprint-sweep clearance gate.
    overhead_hit_min_clearance_m: float = 0.01
    #: 2026-09-19 (user): the GT must mark obstacles the *same way the local
    #: costmap does* - geometry inside a height band above the ground.  The
    #: previous rule ("something was hit before the ground") also blocked every
    #: cell *under* a shelter roof, which the runtime costmap treats as free
    #: space: ``smoke_20260919_153113`` drove the UGV under a bus-shelter roof,
    #: the NavFn potential field is seeded at the robot's own cell, and the
    #: robot then became a one-cell hole inside the lethal footprint, so no goal
    #: could be planned.  The band now matches the Nav2 voxel layer
    #: (``min_obstacle_height`` / ``max_obstacle_height``).
    min_obstacle_height_m: float = 0.05
    max_obstacle_height_m: float = 1.0
    ignored_prim_path_prefixes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not math.isfinite(self.ray_start_z_m) or not math.isfinite(self.ray_end_z_m):
            raise GroundTruthError("ray_start_z_m and ray_end_z_m must be finite")
        if self.ray_start_z_m <= self.ray_end_z_m:
            raise GroundTruthError("ray_start_z_m must be greater than ray_end_z_m")
        if not math.isfinite(self.overhead_ray_distance_m) or self.overhead_ray_distance_m <= 0.0:
            raise GroundTruthError("overhead_ray_distance_m must be positive")
        if (
            not math.isfinite(self.overhead_hit_min_clearance_m)
            or self.overhead_hit_min_clearance_m < 0.0
        ):
            raise GroundTruthError("overhead_hit_min_clearance_m must be finite and non-negative")
        if self.overhead_hit_min_clearance_m >= self.overhead_ray_distance_m:
            raise GroundTruthError(
                "overhead_hit_min_clearance_m must be smaller than overhead_ray_distance_m"
            )
        if not 0.0 <= self.min_ground_normal_z <= 1.0:
            raise GroundTruthError("min_ground_normal_z must be in [0, 1]")
        for label, value in (
            ("min_obstacle_height_m", self.min_obstacle_height_m),
            ("max_obstacle_height_m", self.max_obstacle_height_m),
        ):
            if not math.isfinite(value) or value < 0.0:
                raise GroundTruthError(f"{label} must be finite and non-negative")
        if self.max_obstacle_height_m <= self.min_obstacle_height_m:
            raise GroundTruthError(
                "max_obstacle_height_m must be greater than min_obstacle_height_m"
            )
        if self.max_obstacle_height_m > self.overhead_ray_distance_m:
            raise GroundTruthError(
                "max_obstacle_height_m must not exceed overhead_ray_distance_m"
            )
        for prefix in self.ignored_prim_path_prefixes:
            if not prefix.startswith("/"):
                raise GroundTruthError("ignored prim path prefixes must be absolute USD paths")


@dataclass(frozen=True)
class FootprintSweepConfig:
    """Deterministic rectangular UGV footprint sweep configuration."""

    footprint_length_m: float = 0.508
    footprint_width_m: float = 0.430
    yaw_samples: int = 16
    max_slope_rad: float = math.radians(15.0)
    max_step_height_m: float = 0.10
    min_overhead_clearance_m: float = 0.50
    blocked_cost: float = 1.0e6
    footprint_source: str = "manual"
    footprint_report_sha256: str | None = None
    footprint_padding_m: float | None = None

    def __post_init__(self) -> None:
        if self.footprint_length_m <= 0.0:
            raise GroundTruthError("footprint_length_m must be positive")
        if self.footprint_width_m <= 0.0:
            raise GroundTruthError("footprint_width_m must be positive")
        if self.yaw_samples <= 0:
            raise GroundTruthError("yaw_samples must be positive")
        if not 0.0 <= self.max_slope_rad < math.pi / 2.0:
            raise GroundTruthError("max_slope_rad must satisfy 0 <= max_slope_rad < pi/2")
        if self.max_step_height_m < 0.0:
            raise GroundTruthError("max_step_height_m must be non-negative")
        if self.min_overhead_clearance_m < 0.0:
            raise GroundTruthError("min_overhead_clearance_m must be non-negative")
        if self.blocked_cost <= 0.0 or not math.isfinite(self.blocked_cost):
            raise GroundTruthError("blocked_cost must be finite and positive")
        if not self.footprint_source:
            raise GroundTruthError("footprint_source must be non-empty")
        if self.footprint_padding_m is not None and self.footprint_padding_m < 0.0:
            raise GroundTruthError("footprint_padding_m must be non-negative")


@dataclass(frozen=True)
class JackalFootprintEstimate:
    """Rectangular footprint derived from a Jackal asset collision report."""

    length_m: float
    width_m: float
    padding_m: float
    robot_root: str
    source: str
    body_collision_paths: tuple[str, ...]
    wheel_collision_paths: tuple[str, ...]
    wheel_joint_paths: tuple[str, ...]
    report_asset_id: str | None = None
    report_simulator_version: str | None = None
    report_sha256: str | None = None

    def as_dict(self) -> dict[str, Any]:
        """Return deterministic JSON-compatible footprint evidence."""
        result: dict[str, Any] = {
            "body_collision_paths": list(self.body_collision_paths),
            "length_m": float(self.length_m),
            "padding_m": float(self.padding_m),
            "robot_root": self.robot_root,
            "source": self.source,
            "wheel_collision_paths": list(self.wheel_collision_paths),
            "wheel_joint_paths": list(self.wheel_joint_paths),
            "width_m": float(self.width_m),
        }
        if self.report_asset_id is not None:
            result["report_asset_id"] = self.report_asset_id
        if self.report_simulator_version is not None:
            result["report_simulator_version"] = self.report_simulator_version
        if self.report_sha256 is not None:
            result["report_sha256"] = self.report_sha256
        return result

    def sweep_config(
        self,
        *,
        yaw_samples: int = 16,
        max_slope_rad: float = math.radians(15.0),
        max_step_height_m: float = 0.10,
        min_overhead_clearance_m: float = 0.50,
        blocked_cost: float = 1.0e6,
    ) -> FootprintSweepConfig:
        """Return a sweep config using the derived footprint dimensions."""
        return FootprintSweepConfig(
            footprint_length_m=self.length_m,
            footprint_width_m=self.width_m,
            yaw_samples=yaw_samples,
            max_slope_rad=max_slope_rad,
            max_step_height_m=max_step_height_m,
            min_overhead_clearance_m=min_overhead_clearance_m,
            blocked_cost=blocked_cost,
            footprint_source=self.source,
            footprint_report_sha256=self.report_sha256,
            footprint_padding_m=self.padding_m,
        )


@dataclass(frozen=True)
class FootprintSweepResult:
    """Result arrays from sweeping a UGV footprint over raycast terrain."""

    terrain: RaycastTerrainGrid
    config: FootprintSweepConfig
    traversable_mask: np.ndarray
    inflation_mask: np.ndarray
    component: np.ndarray
    cost: np.ndarray
    footprint_offsets_by_yaw: tuple[tuple[GridCell, ...], ...]

    def traversability_grid(self) -> TraversabilityGrid:
        """Return final schema-compatible grid arrays for this sweep pass."""
        return TraversabilityGrid(
            metadata=self.terrain.metadata,
            height=self.terrain.height.astype(np.float32),
            mask=self.traversable_mask.astype(np.uint8),
            component=self.component.astype(np.int32),
            cost=self.cost.astype(np.float32),
        )

    def arrays_for_npz(self) -> dict[str, np.ndarray]:
        """Return schema-compatible arrays for traversability NPZ writing."""
        return {
            "height": self.terrain.height.astype(np.float32),
            "normal": self.terrain.normal.astype(np.float32),
            "cost": self.cost.astype(np.float32),
            "mask": self.traversable_mask.astype(np.uint8),
            "component": self.component.astype(np.int32),
        }

    def summary(self) -> dict[str, Any]:
        """Return deterministic aggregate sweep statistics."""
        result: dict[str, Any] = {
            "blocked_cost": float(self.config.blocked_cost),
            "component_count": int(len(set(int(v) for v in self.component[self.traversable_mask]))),
            "footprint_length_m": float(self.config.footprint_length_m),
            "footprint_source": self.config.footprint_source,
            "footprint_width_m": float(self.config.footprint_width_m),
            "generator": "airground-jackal-footprint-sweep-v1",
            "inflated_cells": int(self.inflation_mask.astype(bool).sum()),
            # The sweep thresholds are the artefact's contract: a 0.05 m step
            # floor means "5 cm and higher is blocked".  Keep them in the
            # summary so a run's geometry can be audited without re-reading
            # the CLI invocation.
            "max_slope_rad": float(self.config.max_slope_rad),
            "max_step_height_m": float(self.config.max_step_height_m),
            "min_overhead_clearance_m": float(self.config.min_overhead_clearance_m),
            "shape": list(self.terrain.metadata.shape),
            "status": "ok",
            "traversable_cells": int(self.traversable_mask.astype(bool).sum()),
            "yaw_samples": int(self.config.yaw_samples),
        }
        if self.config.footprint_report_sha256 is not None:
            result["footprint_report_sha256"] = self.config.footprint_report_sha256
        if self.config.footprint_padding_m is not None:
            result["footprint_padding_m"] = float(self.config.footprint_padding_m)
        return result


@dataclass(frozen=True)
class FootprintSweepArtifactExport:
    """Files and checksums for a Jackal footprint sweep artifact."""

    traversability_export: "TraversabilityArtifactExport"
    auxiliary_npz_path: Path
    summary_path: Path
    auxiliary_npz_sha256: str
    summary_sha256: str
    sweep_summary: dict[str, Any]
    footprint_evidence: dict[str, Any] | None = None

    def summary(self) -> dict[str, Any]:
        """Return a stable machine-readable footprint sweep summary."""
        result: dict[str, Any] = {
            "auxiliary": {
                "path": str(self.auxiliary_npz_path),
                "sha256": self.auxiliary_npz_sha256,
            },
            "files": {
                **self.traversability_export.summary()["files"],
                "sweep_auxiliary_npz": {
                    "path": str(self.auxiliary_npz_path),
                    "sha256": self.auxiliary_npz_sha256,
                },
                "sweep_summary": {
                    "path": str(self.summary_path),
                    "sha256": self.summary_sha256,
                },
            },
            "generator": "airground-jackal-footprint-sweep-artifact-v1",
            "status": "ok",
            "sweep": self.sweep_summary,
            "traversability": self.traversability_export.summary(),
        }
        if self.footprint_evidence is not None:
            result["footprint_estimate"] = self.footprint_evidence
        return result


def load_jackal_footprint_estimate_from_asset_report(
    report_path: Path,
    *,
    padding_m: float = 0.025,
    robot_root: str = "/jackal",
) -> JackalFootprintEstimate:
    """Load a verified Jackal asset report and derive a rectangular footprint.

    The report format is the JSON emitted by the Isaac asset audit and stored
    under ``AirStack/simulation/isaac-sim/assets/reports_verified``. The
    derived rectangle uses base-link collision extents plus wheel joint centers
    and wheel collision radius/thickness, then applies symmetric safety padding.
    """
    resolved_path = Path(report_path).expanduser().resolve()
    payload = resolved_path.read_bytes()
    try:
        report = json.loads(payload.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise GroundTruthError(f"invalid Jackal asset report JSON: {resolved_path}") from exc
    return estimate_jackal_footprint_from_asset_report(
        report,
        padding_m=padding_m,
        robot_root=robot_root,
        report_sha256=hashlib.sha256(payload).hexdigest(),
    )


def estimate_jackal_footprint_from_asset_report(
    report: Mapping[str, Any],
    *,
    padding_m: float = 0.025,
    robot_root: str = "/jackal",
    report_sha256: str | None = None,
) -> JackalFootprintEstimate:
    """Derive the Jackal rectangular sweep footprint from an asset report.

    The Isaac report records collision extents and revolute-joint local
    positions. For planar traversability we use base-link collision X/Y extents,
    wheel joint ``physics:localPos0`` X/Y centers, wheel ``radius`` as the
    rolling front/back radius, and wheel ``height`` as lateral thickness.
    """
    if padding_m < 0.0 or not math.isfinite(padding_m):
        raise GroundTruthError("padding_m must be finite and non-negative")
    if not robot_root.startswith("/"):
        raise GroundTruthError("robot_root must be an absolute USD path")
    collisions = report.get("collisions")
    joints = report.get("joints")
    if not isinstance(collisions, list):
        raise GroundTruthError("Jackal asset report must contain a collisions list")
    if not isinstance(joints, list):
        raise GroundTruthError("Jackal asset report must contain a joints list")

    half_length_m = 0.0
    half_width_m = 0.0
    body_collision_paths: list[str] = []
    wheel_collision_paths: list[str] = []
    wheel_joint_paths: list[str] = []

    root = robot_root.rstrip("/")
    body_prefix = f"{root}/base_link/collisions"
    for collision in collisions:
        if not isinstance(collision, Mapping):
            continue
        path = str(collision.get("path", ""))
        if not path.startswith(body_prefix):
            continue
        half_extents = _collision_half_extents_xyz(collision)
        if half_extents is None:
            continue
        body_collision_paths.append(path)
        half_length_m = max(half_length_m, half_extents[0])
        half_width_m = max(half_width_m, half_extents[1])

    for joint in joints:
        if not isinstance(joint, Mapping):
            continue
        body0 = _first_path(joint.get("body0"))
        body1 = _first_path(joint.get("body1"))
        if body0 != f"{root}/base_link" or body1 is None or not body1.endswith("_wheel_link"):
            continue
        attrs = joint.get("attributes")
        if not isinstance(attrs, Mapping):
            continue
        local_pos = _finite_float_triplet(attrs.get("physics:localPos0"))
        if local_pos is None:
            continue
        wheel_collisions = _collisions_for_link(collisions, body1)
        wheel_radius_m = _wheel_radius_from_collisions(wheel_collisions)
        wheel_thickness_m = _wheel_thickness_from_collisions(wheel_collisions)
        if wheel_radius_m is None or wheel_thickness_m is None:
            continue
        wheel_joint_paths.append(str(joint.get("path", "")))
        wheel_collision_paths.extend(
            str(collision.get("path", ""))
            for collision in wheel_collisions
            if isinstance(collision, Mapping) and collision.get("path") is not None
        )
        half_length_m = max(half_length_m, abs(local_pos[0]) + wheel_radius_m)
        half_width_m = max(half_width_m, abs(local_pos[1]) + 0.5 * wheel_thickness_m)

    if not body_collision_paths:
        raise GroundTruthError(f"no base-link collision extents found under {body_prefix}")
    if not wheel_joint_paths:
        raise GroundTruthError(f"no wheel joint footprint evidence found under {robot_root}")
    if half_length_m <= 0.0 or half_width_m <= 0.0:
        raise GroundTruthError("derived Jackal footprint dimensions are invalid")

    return JackalFootprintEstimate(
        length_m=2.0 * (half_length_m + padding_m),
        width_m=2.0 * (half_width_m + padding_m),
        padding_m=padding_m,
        robot_root=robot_root,
        source="asset_report",
        body_collision_paths=tuple(sorted(set(body_collision_paths))),
        wheel_collision_paths=tuple(sorted(set(wheel_collision_paths))),
        wheel_joint_paths=tuple(sorted(path for path in set(wheel_joint_paths) if path)),
        report_asset_id=_optional_str(report.get("asset_id")),
        report_simulator_version=_optional_str(report.get("simulator_version")),
        report_sha256=report_sha256,
    )


def build_raycast_terrain_grid(
    metadata: TraversabilityMetadata,
    raycast_fn: TerrainRaycastFn,
    config: RaycastTerrainGridConfig,
) -> RaycastTerrainGrid:
    """Build terrain height/normal/headroom arrays from adapter raycasts.

    The caller supplies an Isaac/PhysX-compatible raycast function with the
    signature ``(origin_xyz_m, direction_xyz, max_distance_m) -> hits``. The
    function may return ``None``, one hit, dictionaries/objects with hit fields,
    or an iterable of hits. Hits are sorted by distance and normalized here.

    This function deliberately stops at the raycast surface. Jackal footprint
    sweep, rollout validation, final traversability cost, and release artifact
    freezing remain later phases.
    """
    rows, cols = metadata.shape
    height = np.full((rows, cols), float(metadata.origin.z_m), dtype=np.float32)
    normal = np.zeros((rows, cols, 3), dtype=np.float32)
    normal[:, :, 2] = 1.0
    support_mask = np.zeros((rows, cols), dtype=bool)
    obstacle_mask = np.zeros((rows, cols), dtype=bool)
    ceiling_height = np.full((rows, cols), config.ray_start_z_m, dtype=np.float32)

    down_distance_m = config.ray_start_z_m - config.ray_end_z_m
    down_direction = (0.0, 0.0, -1.0)
    up_direction = (0.0, 0.0, 1.0)
    for row in range(rows):
        for col in range(cols):
            x_m, y_m = _cell_center_xy(metadata, row, col)
            down_origin = (x_m, y_m, config.ray_start_z_m)
            down_hits = _normalized_terrain_hits(
                raycast_fn(down_origin, down_direction, down_distance_m),
                origin=down_origin,
                direction=down_direction,
                max_distance_m=down_distance_m,
                ignored_prefixes=config.ignored_prim_path_prefixes,
            )
            ground_hit, blocked_before_ground = _select_ground_hit(
                down_hits,
                min_ground_normal_z=config.min_ground_normal_z,
                max_height_z=(
                    float(metadata.origin.z_m) + float(config.max_obstacle_height_m)
                ),
            )
            if ground_hit is not None:
                support_mask[row, col] = True
                height[row, col] = np.float32(ground_hit.position_xyz_m[2])
                normal[row, col, :] = np.asarray(_normalized_vector(ground_hit.normal_xyz), dtype=np.float32)

            # 2026-09-19 (user): obstacle == geometry inside the *same absolute
            # map-frame height band the local costmap voxelizes*
            # (``min/max_obstacle_height``); geometry above it (a bus-shelter
            # roof, an awning, a tree canopy) leaves the ground underneath
            # traversable, exactly like the live Nav2 voxel layer.  The band is
            # absolute because that is what the runtime gate compares against -
            # relative-to-ground would mark the road slab itself as an obstacle
            # wherever the terrain under it sits below the slab (measured: 622596
            # obstacle cells, 74x the previous rule).
            band_origin = (
                x_m,
                y_m,
                float(metadata.origin.z_m) + float(config.min_obstacle_height_m),
            )
            band_distance_m = float(config.max_obstacle_height_m) - float(
                config.min_obstacle_height_m
            )
            band_hits = _normalized_terrain_hits(
                raycast_fn(band_origin, up_direction, band_distance_m),
                origin=band_origin,
                direction=up_direction,
                max_distance_m=band_distance_m,
                ignored_prefixes=config.ignored_prim_path_prefixes,
            )
            # Any hit counts, including a PhysX "initial overlap" hit: a band ray
            # that *starts inside* a collider means solid geometry fills the band
            # floor (a 5-10 cm curb, a kerb stone), which the local costmap marks
            # as an obstacle just the same.
            obstacle_mask[row, col] = bool(band_hits)

            if support_mask[row, col]:
                up_origin = (x_m, y_m, float(height[row, col]))
                up_hits = _normalized_terrain_hits(
                    raycast_fn(up_origin, up_direction, config.overhead_ray_distance_m),
                    origin=up_origin,
                    direction=up_direction,
                    max_distance_m=config.overhead_ray_distance_m,
                    ignored_prefixes=config.ignored_prim_path_prefixes,
                )
                first_ceiling = _select_ceiling_hit(
                    up_hits,
                    ground_z_m=float(height[row, col]),
                    min_clearance_m=config.overhead_hit_min_clearance_m,
                )
                if first_ceiling is None:
                    ceiling_height[row, col] = np.float32(height[row, col] + config.overhead_ray_distance_m)
                else:
                    ceiling_height[row, col] = np.float32(first_ceiling.position_xyz_m[2])
            else:
                ceiling_height[row, col] = np.float32(height[row, col])

    slope_rad = _slope_from_height(height, metadata.resolution_m).astype(np.float32)
    step_height_m = _max_neighbor_height_delta(height).astype(np.float32)
    overhead_clearance_m = np.maximum(0.0, ceiling_height - height).astype(np.float32)
    return RaycastTerrainGrid(
        metadata=metadata,
        height=height,
        normal=normal,
        support_mask=support_mask,
        obstacle_mask=obstacle_mask,
        ceiling_height=ceiling_height,
        slope_rad=slope_rad,
        step_height_m=step_height_m,
        overhead_clearance_m=overhead_clearance_m,
        obstacle_band_m=(
            float(config.min_obstacle_height_m),
            float(config.max_obstacle_height_m),
        ),
    )


def raycast_terrain_grid_from_arrays(
    metadata: TraversabilityMetadata,
    arrays: Mapping[str, np.ndarray],
) -> RaycastTerrainGrid:
    """Reconstruct a RaycastTerrainGrid from a raycast seed NPZ mapping.

    The Isaac-side raycast generator writes both schema arrays and auxiliary
    terrain arrays.  For older seed artifacts that only contain schema arrays,
    this loader derives the minimum safe fields from mask/height/normal so the
    footprint sweep CLI can still produce an explicit report, while real P1-02
    evidence should prefer artifacts containing the auxiliary arrays.
    """
    rows, cols = metadata.shape
    keys = metadata.arrays
    height = np.asarray(_artifact_array(arrays, "height", keys.height), dtype=np.float32)
    normal = np.asarray(_artifact_array(arrays, "normal", keys.normal), dtype=np.float32)
    mask = np.asarray(_artifact_array(arrays, "mask", keys.mask), dtype=np.uint8)
    _require_array_shape(keys.height, height, (rows, cols))
    _require_array_shape(keys.normal, normal, (rows, cols, 3))
    _require_array_shape(keys.mask, mask, (rows, cols))

    support_mask = _optional_bool_array(arrays, "support_mask", metadata.shape, default=mask.astype(bool))
    obstacle_mask = _optional_bool_array(arrays, "obstacle_mask", metadata.shape, default=np.zeros(metadata.shape, dtype=bool))
    slope_rad = _optional_float_array(
        arrays,
        "slope_rad",
        metadata.shape,
        default=_slope_from_height(height, metadata.resolution_m).astype(np.float32),
    )
    step_height_m = _optional_float_array(
        arrays,
        "step_height_m",
        metadata.shape,
        default=_max_neighbor_height_delta(height).astype(np.float32),
    )
    overhead_clearance_m = _optional_float_array(
        arrays,
        "overhead_clearance_m",
        metadata.shape,
        default=np.full(metadata.shape, 1.0e6, dtype=np.float32),
    )
    ceiling_height = _optional_float_array(
        arrays,
        "ceiling_height",
        metadata.shape,
        default=(height + overhead_clearance_m).astype(np.float32),
    )
    return RaycastTerrainGrid(
        metadata=metadata,
        height=height,
        normal=normal,
        support_mask=support_mask,
        obstacle_mask=obstacle_mask,
        ceiling_height=ceiling_height,
        slope_rad=slope_rad,
        step_height_m=step_height_m,
        overhead_clearance_m=overhead_clearance_m,
    )


def load_raycast_terrain_grid(
    metadata: TraversabilityMetadata,
    npz_path: Path,
) -> RaycastTerrainGrid:
    """Load a raycast seed NPZ as a RaycastTerrainGrid."""
    resolved = Path(npz_path).expanduser().resolve(strict=True)
    with np.load(resolved) as data:
        arrays = {key: np.array(data[key], copy=True) for key in data.files}
    return raycast_terrain_grid_from_arrays(metadata, arrays)


def sweep_ugv_footprint_over_terrain(
    terrain: RaycastTerrainGrid,
    config: FootprintSweepConfig = FootprintSweepConfig(),
) -> FootprintSweepResult:
    """Sweep a rectangular UGV footprint over raycast terrain arrays.

    This is a deterministic grid collision pass. It uses the raycast support,
    obstacle, slope, step and overhead arrays to reject cells where the Jackal
    footprint would overlap blocked or unsafe terrain at any sampled yaw. The
    footprint dimensions may be supplied manually or derived from a verified
    Jackal asset collision report via
    :func:`estimate_jackal_footprint_from_asset_report`.
    """
    _validate_raycast_terrain_shapes(terrain)
    base_safe = (
        terrain.support_mask.astype(bool)
        & ~terrain.obstacle_mask.astype(bool)
        & (terrain.slope_rad <= config.max_slope_rad)
        & (terrain.step_height_m <= config.max_step_height_m)
        & (terrain.overhead_clearance_m >= config.min_overhead_clearance_m)
    )
    offsets_by_yaw = tuple(
        _footprint_offsets_for_yaw(
            yaw_rad=2.0 * math.pi * index / config.yaw_samples,
            resolution_m=terrain.metadata.resolution_m,
            length_m=config.footprint_length_m,
            width_m=config.footprint_width_m,
        )
        for index in range(config.yaw_samples)
    )

    rows, cols = terrain.metadata.shape
    # Intersection of shifted masks is exactly the former all-offset/all-yaw
    # cell loop, including blocked out-of-grid cells. Avoid billions of Python
    # offset checks for the full annotation-AABB map.
    traversable = base_safe.copy()
    for d_row, d_col in sorted({offset for offsets in offsets_by_yaw for offset in offsets}):
        shifted = np.zeros_like(base_safe)
        r0, r1 = max(0, -d_row), min(rows, rows - d_row)
        c0, c1 = max(0, -d_col), min(cols, cols - d_col)
        if r1 > r0 and c1 > c0:
            shifted[r0:r1, c0:c1] = base_safe[r0+d_row:r1+d_row, c0+d_col:c1+d_col]
        traversable &= shifted

    inflation = base_safe & ~traversable
    component = connected_components(traversable.astype(np.uint8), connectivity=8)
    cost = _footprint_sweep_cost(
        traversable,
        slope_rad=terrain.slope_rad,
        step_height_m=terrain.step_height_m,
        max_slope_rad=config.max_slope_rad,
        max_step_height_m=config.max_step_height_m,
        blocked_cost=config.blocked_cost,
    )
    return FootprintSweepResult(
        terrain=terrain,
        config=config,
        traversable_mask=traversable,
        inflation_mask=inflation,
        component=component,
        cost=cost,
        footprint_offsets_by_yaw=offsets_by_yaw,
    )


def write_footprint_sweep_artifact(
    metadata: TraversabilityMetadata,
    raycast_npz_path: Path,
    output_dir: Path,
    *,
    config: FootprintSweepConfig = FootprintSweepConfig(),
    footprint_evidence: Mapping[str, Any] | None = None,
    stem: str = "traversability_footprint",
    generator_version: str = "p1-02",
    export_nav2: bool = False,
    occupied_thresh: float = 0.65,
    free_thresh: float = 0.196,
) -> FootprintSweepArtifactExport:
    """Run Jackal footprint sweep over raycast terrain and write artifacts."""
    terrain = load_raycast_terrain_grid(metadata, raycast_npz_path)
    sweep = sweep_ugv_footprint_over_terrain(terrain, config)
    output_root = Path(output_dir).expanduser().resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    sweep_metadata = metadata.model_copy(
        update={
            "generator": "airground-jackal-footprint-sweep-v1",
            "generator_version": generator_version,
            "npz_sha256": None,
        }
    )
    traversability_export = write_traversability_artifact(
        sweep_metadata,
        sweep.arrays_for_npz(),
        output_root,
        stem=stem,
        export_nav2=export_nav2,
        occupied_thresh=occupied_thresh,
        free_thresh=free_thresh,
    )
    auxiliary_npz_path = output_root / f"{stem}.sweep_auxiliary.npz"
    _write_deterministic_npz(
        auxiliary_npz_path,
        {
            "ceiling_height": terrain.ceiling_height.astype(np.float32),
            "inflation_mask": sweep.inflation_mask.astype(np.uint8),
            "obstacle_mask": terrain.obstacle_mask.astype(np.uint8),
            "overhead_clearance_m": terrain.overhead_clearance_m.astype(np.float32),
            "slope_rad": terrain.slope_rad.astype(np.float32),
            "step_height_m": terrain.step_height_m.astype(np.float32),
            "support_mask": terrain.support_mask.astype(np.uint8),
        },
    )
    auxiliary_npz_sha256 = hashlib.sha256(auxiliary_npz_path.read_bytes()).hexdigest()
    summary_path = output_root / f"{stem}.sweep_summary.json"
    sweep_summary = sweep.summary()
    summary_body = {
        "artifact": traversability_export.summary(),
        "auxiliary_npz": {
            "path": auxiliary_npz_path.name,
            "sha256": auxiliary_npz_sha256,
        },
        "generator": "airground-jackal-footprint-sweep-artifact-v1",
        "raycast_npz_sha256": traversability_npz_sha256(raycast_npz_path),
        "status": "ok",
        "sweep": sweep_summary,
    }
    if footprint_evidence is not None:
        summary_body["footprint_estimate"] = dict(footprint_evidence)
    summary_text = json.dumps(summary_body, ensure_ascii=True, sort_keys=True, separators=(",", ":")) + "\n"
    summary_path.write_text(summary_text, encoding="utf-8")
    return FootprintSweepArtifactExport(
        traversability_export=traversability_export,
        auxiliary_npz_path=auxiliary_npz_path,
        summary_path=summary_path,
        auxiliary_npz_sha256=auxiliary_npz_sha256,
        summary_sha256=hashlib.sha256(summary_text.encode("utf-8")).hexdigest(),
        sweep_summary=sweep_summary,
        footprint_evidence=dict(footprint_evidence) if footprint_evidence is not None else None,
    )


@dataclass(frozen=True)
class Nav2OccupancyGridExport:
    """Files and summary data for a Nav2 map_server occupancy export."""

    yaml_path: Path
    image_path: Path
    free_cells: int
    occupied_cells: int
    unknown_cells: int
    image_sha256: str
    yaml_sha256: str

    def summary(self) -> dict[str, Any]:
        """Return a stable machine-readable export summary."""
        return {
            "free_cells": self.free_cells,
            "image_path": str(self.image_path),
            "image_sha256": self.image_sha256,
            "occupied_cells": self.occupied_cells,
            "status": "ok",
            "unknown_cells": self.unknown_cells,
            "yaml_path": str(self.yaml_path),
            "yaml_sha256": self.yaml_sha256,
        }


@dataclass(frozen=True)
class TraversabilityArtifactExport:
    """Files and checksums for a packaged traversability artifact."""

    metadata_path: Path
    npz_path: Path
    manifest_path: Path
    metadata_sha256: str
    npz_sha256: str
    manifest_sha256: str
    validation_summary: dict[str, Any]
    nav2_export: Nav2OccupancyGridExport | None = None

    def summary(self) -> dict[str, Any]:
        """Return a stable machine-readable artifact summary."""
        files: dict[str, dict[str, str]] = {
            "manifest": {
                "path": str(self.manifest_path),
                "sha256": self.manifest_sha256,
            },
            "metadata": {
                "path": str(self.metadata_path),
                "sha256": self.metadata_sha256,
            },
            "npz": {
                "path": str(self.npz_path),
                "sha256": self.npz_sha256,
            },
        }
        nav2 = self.nav2_export.summary() if self.nav2_export is not None else None
        if self.nav2_export is not None:
            files["nav2_yaml"] = {
                "path": str(self.nav2_export.yaml_path),
                "sha256": self.nav2_export.yaml_sha256,
            }
            files["nav2_pgm"] = {
                "path": str(self.nav2_export.image_path),
                "sha256": self.nav2_export.image_sha256,
            }
        return {
            "files": files,
            "generator": "airground-traversability-artifact-v1",
            "nav2": nav2,
            "scene_id": self.validation_summary["scene_id"],
            "shape": self.validation_summary["shape"],
            "status": "ok",
            "validation": self.validation_summary,
        }


@dataclass(frozen=True)
class RolloutValidationSample:
    """One Jackal rollout validation sample against traversability truth."""

    sample_id: str
    sample_kind: str
    start_cell: GridCell
    expected_traversable: bool
    rollout_success: bool
    end_cell: GridCell | None = None
    reason: str | None = None

    @property
    def matches(self) -> bool:
        """Whether simulated rollout outcome agrees with traversability truth."""
        return self.expected_traversable == self.rollout_success

    def as_dict(self) -> dict[str, Any]:
        """Return deterministic JSON-compatible sample data."""
        return {
            "end_cell": list(self.end_cell) if self.end_cell is not None else None,
            "expected_traversable": self.expected_traversable,
            "matches": self.matches,
            "reason": self.reason,
            "rollout_success": self.rollout_success,
            "sample_id": self.sample_id,
            "sample_kind": self.sample_kind,
            "start_cell": list(self.start_cell),
        }


@dataclass(frozen=True)
class TraversabilityRolloutReport:
    """Aggregate Jackal rollout consistency report."""

    samples: tuple[RolloutValidationSample, ...]
    min_samples: int
    min_consistency: float
    max_mismatches: int = 50

    def summary(self) -> dict[str, Any]:
        """Return stable aggregate rollout validation statistics."""
        sample_count = len(self.samples)
        match_count = sum(1 for sample in self.samples if sample.matches)
        mismatch_samples = tuple(sample for sample in self.samples if not sample.matches)
        consistency = match_count / sample_count if sample_count else 0.0
        status = (
            "ok"
            if sample_count >= self.min_samples and consistency >= self.min_consistency
            else "failed"
        )
        return {
            "consistency": consistency,
            "generator": "airground-jackal-rollout-validation-v1",
            "kind_counts": _rollout_kind_counts(self.samples),
            "match_count": match_count,
            "max_mismatches_reported": self.max_mismatches,
            "min_consistency": self.min_consistency,
            "min_samples": self.min_samples,
            "mismatch_count": len(mismatch_samples),
            "mismatches": [
                sample.as_dict() for sample in mismatch_samples[: self.max_mismatches]
            ],
            "sample_count": sample_count,
            "status": status,
        }


@dataclass(frozen=True)
class TraversabilityMismatchReviewEntry:
    """One static-vs-dynamic traversability mismatch requiring review."""

    sample: RolloutValidationSample
    screenshot_path: str | None = None
    final_disposition: str | None = None

    def issues(
        self,
        *,
        require_screenshot: bool,
        require_final_disposition: bool,
    ) -> tuple[str, ...]:
        """Return missing review artifacts for this mismatch."""
        issues: list[str] = []
        if require_screenshot and not self.screenshot_path:
            issues.append("missing_screenshot")
        if require_final_disposition and not self.final_disposition:
            issues.append("missing_final_disposition")
        return tuple(issues)

    def as_dict(
        self,
        *,
        require_screenshot: bool,
        require_final_disposition: bool,
    ) -> dict[str, Any]:
        """Return deterministic JSON-compatible mismatch review entry."""
        return {
            "final_disposition": self.final_disposition,
            "issues": list(
                self.issues(
                    require_screenshot=require_screenshot,
                    require_final_disposition=require_final_disposition,
                )
            ),
            "sample": self.sample.as_dict(),
            "screenshot_path": self.screenshot_path,
        }


@dataclass(frozen=True)
class TraversabilityMismatchReviewReport:
    """Review status for rollout mismatches against static traversability GT."""

    samples: tuple[RolloutValidationSample, ...]
    entries: tuple[TraversabilityMismatchReviewEntry, ...]
    require_screenshots: bool = True
    require_final_dispositions: bool = True

    def summary(self) -> dict[str, Any]:
        """Return stable aggregate mismatch review status."""
        issue_counts: dict[str, int] = {}
        reviewed_count = 0
        entry_dicts: list[dict[str, Any]] = []
        for entry in self.entries:
            issues = entry.issues(
                require_screenshot=self.require_screenshots,
                require_final_disposition=self.require_final_dispositions,
            )
            if not issues:
                reviewed_count += 1
            for issue in issues:
                issue_counts[issue] = issue_counts.get(issue, 0) + 1
            entry_dicts.append(
                entry.as_dict(
                    require_screenshot=self.require_screenshots,
                    require_final_disposition=self.require_final_dispositions,
                )
            )
        mismatch_count = len(self.entries)
        return {
            "entries": entry_dicts,
            "generator": "airground-traversability-mismatch-review-v1",
            "issue_counts": issue_counts,
            "mismatch_count": mismatch_count,
            "reviewed_count": reviewed_count,
            "sample_count": len(self.samples),
            "status": "ok" if not issue_counts else "failed",
            "unreviewed_count": mismatch_count - reviewed_count,
        }


@dataclass(frozen=True)
class JackalGroundThresholdOutcome:
    """One standard ground-testbed outcome used for Jackal threshold calibration."""

    test_id: str
    test_kind: str
    value: float
    status: str
    route_index: int | None = None
    max_tilt_rad: float | None = None
    issues: tuple[str, ...] = ()

    @property
    def stable(self) -> bool:
        """Return whether this outcome is safe/stable at the tested value."""
        return self.status == "ok" and not self.issues

    def as_dict(self) -> dict[str, Any]:
        """Return deterministic JSON-compatible outcome data."""
        payload: dict[str, Any] = {
            "issues": list(self.issues),
            "stable": self.stable,
            "status": self.status,
            "test_id": self.test_id,
            "test_kind": self.test_kind,
            "value": self.value,
        }
        if self.route_index is not None:
            payload["route_index"] = self.route_index
        if self.max_tilt_rad is not None:
            payload["max_tilt_rad"] = self.max_tilt_rad
        if self.test_kind == "slope":
            payload["slope_deg"] = self.value
        elif self.test_kind == "step":
            payload["step_height_m"] = self.value
        return payload


@dataclass(frozen=True)
class JackalGroundThresholdCalibrationReport:
    """Automatic threshold calibration from standard Jackal ground-testbed outcomes."""

    outcomes: tuple[JackalGroundThresholdOutcome, ...]
    robot_id: str = "isaacsim.clearpath_jackal"
    testbed_version: str = "airground-jackal-ground-testbed-v1"
    calibration_version: str = "airground-jackal-ground-threshold-calibration-v1"

    def summary(self) -> dict[str, Any]:
        """Return stable aggregate threshold calibration data."""
        slopes = tuple(outcome for outcome in self.outcomes if outcome.test_kind == "slope")
        steps = tuple(outcome for outcome in self.outcomes if outcome.test_kind == "step")
        slope_issue_counts = _threshold_group_issue_counts(slopes, "slope")
        step_issue_counts = _threshold_group_issue_counts(steps, "step")
        issue_counts = _merge_issue_counts(slope_issue_counts, step_issue_counts)
        slope_threshold = _max_stable_threshold(slopes)
        step_threshold = _max_stable_threshold(steps)
        if slope_threshold is None:
            issue_counts["missing_stable_slope_outcome"] = issue_counts.get("missing_stable_slope_outcome", 0) + 1
        if step_threshold is None:
            issue_counts["missing_stable_step_outcome"] = issue_counts.get("missing_stable_step_outcome", 0) + 1
        status = "ok" if not issue_counts else "failed"
        config = (
            {
                "calibration_version": self.calibration_version,
                "max_stable_slope_deg": slope_threshold,
                "max_step_height_m": step_threshold,
                "robot_id": self.robot_id,
                "schema_version": "1.0.0",
                "testbed_version": self.testbed_version,
                "threshold_scope": "max_tested_stable",
            }
            if status == "ok"
            else None
        )
        return {
            "calibration_version": self.calibration_version,
            "config": config,
            "generator": self.calibration_version,
            "issue_counts": issue_counts,
            "max_stable_slope_deg": slope_threshold,
            "max_step_height_m": step_threshold,
            "outcome_count": len(self.outcomes),
            "outcomes": [outcome.as_dict() for outcome in self.outcomes],
            "robot_id": self.robot_id,
            "slope_values": _threshold_value_summaries(slopes),
            "status": status,
            "step_values": _threshold_value_summaries(steps),
            "testbed_version": self.testbed_version,
        }

    def versioned_config(self) -> dict[str, Any]:
        """Return the versioned YAML config payload or raise if calibration failed."""
        summary = self.summary()
        config = summary["config"]
        if not isinstance(config, dict):
            raise GroundTruthError("cannot write Jackal ground threshold config from failed calibration")
        return config


@dataclass(frozen=True)
class LocalTraversabilityFeatures:
    """Local terrain features derived from a traversability height grid."""

    slope_rad: np.ndarray
    step_height_m: np.ndarray
    body_clearance_m: np.ndarray
    overhead_clearance_m: np.ndarray
    inflated_obstacle_mask: np.ndarray
    safe_mask: np.ndarray
    max_slope_rad: float
    max_step_height_m: float
    robot_radius_m: float
    robot_height_m: float
    overhead_clearance_margin_m: float

    def summary(self) -> dict[str, Any]:
        """Return stable aggregate feature statistics."""
        finite_body_clearance = self.body_clearance_m[np.isfinite(self.body_clearance_m)]
        finite_overhead = self.overhead_clearance_m[np.isfinite(self.overhead_clearance_m)]
        return {
            "body_clearance_min_m": (
                float(finite_body_clearance.min()) if finite_body_clearance.size else None
            ),
            "inflated_obstacle_cells": int(self.inflated_obstacle_mask.sum()),
            "max_slope_rad": float(self.max_slope_rad),
            "max_step_height_m": float(self.max_step_height_m),
            "overhead_clearance_min_m": (
                float(finite_overhead.min()) if finite_overhead.size else None
            ),
            "robot_height_m": float(self.robot_height_m),
            "robot_radius_m": float(self.robot_radius_m),
            "safe_cells": int(self.safe_mask.sum()),
            "slope_max_rad": float(np.max(self.slope_rad)),
            "status": "ok",
            "step_height_max_m": float(np.max(self.step_height_m)),
        }


#: 2026-09-24 reach-region calibration rule: a non-obstacle connected component
#: counts as reachable only when the UGV can pass a corridor of 1.5x its own
#: width (0.430 m Jackal width -> 0.645 m).  The traversability mask already
#: contains every cell where the 0.508x0.430 m footprint fits, so the extra
#: requirement is a 0.1075 m margin to the nearest non-traversable cell.
REACH_REGION_RULE_CORRIDOR_1P5X = "corridor_1p5x_ugv_width"
DEFAULT_REACH_FOOTPRINT_WIDTH_M = 0.430
DEFAULT_REACH_CLEARANCE_MARGIN_M = 0.5 * (1.5 * DEFAULT_REACH_FOOTPRINT_WIDTH_M - DEFAULT_REACH_FOOTPRINT_WIDTH_M)


@dataclass(frozen=True)
class ReachRegionResult:
    """Recalibrated reachable region and its connected components."""

    reach_mask: np.ndarray
    reach_component: np.ndarray
    component_cell_counts: tuple[int, ...]
    clearance_margin_m: float
    footprint_width_m: float
    min_clearance_m: float

    @property
    def corridor_width_m(self) -> float:
        return float(self.footprint_width_m) + 2.0 * float(self.clearance_margin_m)

    @property
    def component_count(self) -> int:
        return len(self.component_cell_counts)

    def component_sizes_desc(self) -> list[tuple[int, int]]:
        """Return ``[(component_id, cell_count), ...]`` sorted largest first."""

        return sorted(
            enumerate(self.component_cell_counts),
            key=lambda item: (-item[1], item[0]),
        )

    def summary(self) -> dict[str, Any]:
        return {
            "clearance_margin_m": round(float(self.clearance_margin_m), 6),
            "component_cell_counts": [int(value) for value in self.component_cell_counts],
            "component_count": int(self.component_count),
            "corridor_width_m": round(float(self.corridor_width_m), 6),
            "footprint_width_m": round(float(self.footprint_width_m), 6),
            "min_clearance_m": round(float(self.min_clearance_m), 6),
            "passable_cells": int(self.reach_mask.sum()),
            "reach_rule": REACH_REGION_RULE_CORRIDOR_1P5X,
        }


def build_reach_region(
    mask: np.ndarray,
    *,
    resolution_m: float,
    clearance_margin_m: float = DEFAULT_REACH_CLEARANCE_MARGIN_M,
    footprint_width_m: float = DEFAULT_REACH_FOOTPRINT_WIDTH_M,
    connectivity: int = 8,
) -> ReachRegionResult:
    """Recalibrate the reachable region from an existing traversability mask.

    The result keeps the repo's component convention: ``-1`` marks a cell that
    is not part of the reachable region, ``0..N-1`` are 8-connected components
    ordered deterministically by the label pass.
    """

    if mask.ndim != 2:
        raise GroundTruthError(f"mask must be 2D, got shape {mask.shape}")
    if not math.isfinite(resolution_m) or resolution_m <= 0.0:
        raise GroundTruthError("resolution_m must be finite and positive")
    if not math.isfinite(clearance_margin_m) or clearance_margin_m < 0.0:
        raise GroundTruthError("clearance_margin_m must be finite and non-negative")
    if not math.isfinite(footprint_width_m) or footprint_width_m <= 0.0:
        raise GroundTruthError("footprint_width_m must be finite and positive")
    if connectivity not in {4, 8}:
        raise GroundTruthError("connectivity must be 4 or 8")
    try:
        from scipy import ndimage  # type: ignore[import-not-found]
    except ImportError as exc:  # pragma: no cover - the repo venv ships scipy
        raise GroundTruthError(
            "reach-region calibration requires scipy; install the test extra "
            "with 'pip install -e .[test]'"
        ) from exc

    traversable = np.asarray(mask).astype(bool)
    distance_cells = ndimage.distance_transform_edt(traversable)
    distance_m = distance_cells * float(resolution_m)
    reach_mask = traversable & (distance_m >= float(clearance_margin_m) - 1.0e-9)
    structure = (
        np.ones((3, 3), dtype=int)
        if connectivity == 8
        else np.array([[0, 1, 0], [1, 1, 1], [0, 1, 0]], dtype=int)
    )
    labels, count = ndimage.label(reach_mask, structure=structure)
    reach_component = np.where(reach_mask, labels - 1, -1).astype(np.int32)
    counts = np.bincount(reach_component[reach_mask].ravel(), minlength=count).astype(int)
    min_clearance_m = float(distance_m[reach_mask].min()) if reach_mask.any() else 0.0
    return ReachRegionResult(
        reach_mask=reach_mask.astype(np.uint8),
        reach_component=reach_component,
        component_cell_counts=tuple(int(value) for value in counts.tolist()),
        clearance_margin_m=float(clearance_margin_m),
        footprint_width_m=float(footprint_width_m),
        min_clearance_m=min_clearance_m,
    )


def connected_components(mask: np.ndarray, *, connectivity: int = 8) -> np.ndarray:
    """Compute deterministic connected component ids for a traversability mask."""
    if mask.ndim != 2:
        raise GroundTruthError(f"mask must be 2D, got shape {mask.shape}")
    if connectivity not in {4, 8}:
        raise GroundTruthError("connectivity must be 4 or 8")
    if not np.isin(mask, [0, 1, False, True]).all():
        raise GroundTruthError("mask must contain only 0/1 values")

    traversable = mask.astype(bool)
    try:
        from scipy import ndimage
    except ImportError:
        pass  # Preserve offline import/use without the test extra.
    else:
        # The legacy 8-neighbor traversal only permits diagonals when BOTH
        # adjacent cardinal cells are free. Such an edge cannot join distinct
        # 4-connected components, so cardinal labeling gives exactly the same
        # partition/row-major ids for either setting, without cutting corners.
        structure = np.array([[0, 1, 0], [1, 1, 1], [0, 1, 0]])
        labels, _ = ndimage.label(traversable, structure=structure)
        return np.where(traversable, labels - 1, -1).astype(np.int32)
    components = np.full(mask.shape, -1, dtype=np.int32)
    component_id = 0
    rows, cols = mask.shape
    for row in range(rows):
        for col in range(cols):
            if not traversable[row, col] or components[row, col] >= 0:
                continue
            _flood_fill_component(
                traversable,
                components,
                start=(row, col),
                component_id=component_id,
                connectivity=connectivity,
            )
            component_id += 1
    return components


def compute_local_traversability_features(
    grid: TraversabilityGrid,
    *,
    robot_radius_m: float,
    robot_height_m: float,
    max_slope_rad: float,
    max_step_height_m: float,
    obstacle_inflation_radius_m: float | None = None,
    ceiling_height: np.ndarray | None = None,
    overhead_clearance_margin_m: float = 0.10,
) -> LocalTraversabilityFeatures:
    """Compute local terrain features used by UGV traversability generation.

    This is the deterministic post-processing layer that runs after the Isaac
    height/raycast pass has produced a grid. It does not create geometry or
    perform collision sweeps by itself; it converts height, mask, component and
    optional ceiling height arrays into slope, step, lateral body-clearance,
    headroom and inflated-obstacle masks that downstream GT generation can
    threshold and audit.
    """
    _validate_local_feature_config(
        grid,
        robot_radius_m=robot_radius_m,
        robot_height_m=robot_height_m,
        max_slope_rad=max_slope_rad,
        max_step_height_m=max_step_height_m,
        overhead_clearance_margin_m=overhead_clearance_margin_m,
        ceiling_height=ceiling_height,
    )
    inflation_radius = robot_radius_m if obstacle_inflation_radius_m is None else obstacle_inflation_radius_m
    if inflation_radius < 0.0:
        raise GroundTruthError("obstacle_inflation_radius_m must be non-negative")

    base_traversable = grid.mask.astype(bool) & (grid.component >= 0)
    slope_rad = _slope_from_height(grid.height, grid.metadata.resolution_m)
    step_height_m = _max_neighbor_height_delta(grid.height)
    distance_to_blocked_m = _distance_to_nearest_blocked_cell(
        base_traversable,
        resolution_m=grid.metadata.resolution_m,
    )
    # Approximate lateral clearance from the robot body edge to the nearest
    # blocked cell center. Positive values mean the footprint fits without
    # intersecting the inflated obstacle boundary.
    body_clearance_m = distance_to_blocked_m - robot_radius_m
    body_clearance_m[~base_traversable] = 0.0
    inflated_obstacle_mask = (~base_traversable) | (distance_to_blocked_m <= inflation_radius)

    if ceiling_height is None:
        overhead_clearance_m = np.full(grid.metadata.shape, math.inf, dtype=np.float32)
    else:
        overhead_clearance_m = (ceiling_height.astype(np.float32) - grid.height.astype(np.float32)).astype(np.float32)

    safe_mask = (
        base_traversable
        & ~inflated_obstacle_mask
        & (slope_rad <= max_slope_rad)
        & (step_height_m <= max_step_height_m)
        & (body_clearance_m >= 0.0)
        & (overhead_clearance_m >= robot_height_m + overhead_clearance_margin_m)
    )
    return LocalTraversabilityFeatures(
        slope_rad=slope_rad.astype(np.float32),
        step_height_m=step_height_m.astype(np.float32),
        body_clearance_m=body_clearance_m.astype(np.float32),
        overhead_clearance_m=overhead_clearance_m.astype(np.float32),
        inflated_obstacle_mask=inflated_obstacle_mask.astype(bool),
        safe_mask=safe_mask.astype(bool),
        max_slope_rad=max_slope_rad,
        max_step_height_m=max_step_height_m,
        robot_radius_m=robot_radius_m,
        robot_height_m=robot_height_m,
        overhead_clearance_margin_m=overhead_clearance_margin_m,
    )


@dataclass(frozen=True)
class TraversabilityQuery:
    """On-demand path queries over a validated traversability grid."""

    grid: TraversabilityGrid
    connectivity: int = 8
    _single_source_cache: dict[GridCell, dict[GridCell, float]] = field(
        default_factory=dict,
        init=False,
        repr=False,
        compare=False,
    )

    def __post_init__(self) -> None:
        if self.connectivity not in {4, 8}:
            raise GroundTruthError("connectivity must be 4 or 8")

    def shortest_path_distance_cells(
        self,
        start: GridCell,
        goal: GridCell,
    ) -> float | None:
        """Return shortest traversable ground distance between two cells."""
        self._validate_cell(start, "start")
        self._validate_cell(goal, "goal")
        if start == goal:
            return 0.0 if self._is_traversable(start) else None
        if not self._is_traversable(start) or not self._is_traversable(goal):
            return None
        if int(self.grid.component[start]) != int(self.grid.component[goal]):
            return None

        best = self._shortest_path_tree_from_cell(start)
        return best.get(goal)

    def _shortest_path_tree_from_cell(self, start: GridCell) -> dict[GridCell, float]:
        cached = self._single_source_cache.get(start)
        if cached is not None:
            return cached

        queue: list[tuple[float, GridCell]] = [(0.0, start)]
        best: dict[GridCell, float] = {start: 0.0}
        while queue:
            distance_m, cell = heapq.heappop(queue)
            if distance_m > best[cell]:
                continue
            for neighbor, edge_cost_m in self._neighbors(cell):
                next_distance_m = distance_m + edge_cost_m
                if next_distance_m < best.get(neighbor, math.inf):
                    best[neighbor] = next_distance_m
                    heapq.heappush(queue, (next_distance_m, neighbor))
        self._single_source_cache[start] = best
        return best

    def shortest_path_distance_xy(
        self,
        start_xy_m: tuple[float, float],
        goal_xy_m: tuple[float, float],
    ) -> float | None:
        """Return shortest ground distance between two map-frame XY points."""
        start = self.grid.cell_for_xy(*start_xy_m)
        goal = self.grid.cell_for_xy(*goal_xy_m)
        if start is None or goal is None:
            return None
        return self.shortest_path_distance_cells(start, goal)

    def detour_ratio_to_confirmation_region(
        self,
        start_xy_m: tuple[float, float],
        region: ConfirmationRegion,
    ) -> float | None:
        """Return min ground-path / Euclidean ratio to a confirmation region."""
        if not region.reachable:
            return None
        ratios: list[float] = []
        for pose in region.poses:
            px, py, _ = pose.position_xyz_m
            shortest_path_m = self.shortest_path_distance_xy(start_xy_m, (px, py))
            if shortest_path_m is None:
                continue
            euclidean_m = math.hypot(start_xy_m[0] - px, start_xy_m[1] - py)
            if euclidean_m <= 1e-9:
                ratios.append(1.0)
            else:
                ratios.append(max(1.0, shortest_path_m / euclidean_m))
        return min(ratios) if ratios else None

    def _validate_cell(self, cell: GridCell, name: str) -> None:
        row, col = cell
        rows, cols = self.grid.metadata.shape
        if row < 0 or col < 0 or row >= rows or col >= cols:
            raise GroundTruthError(f"{name} cell {cell} is outside traversability grid")

    def _is_traversable(self, cell: GridCell) -> bool:
        row, col = cell
        return bool(self.grid.mask[row, col]) and int(self.grid.component[row, col]) >= 0

    def _neighbors(self, cell: GridCell) -> Iterable[tuple[GridCell, float]]:
        row, col = cell
        for d_row, d_col in _neighbor_offsets(self.connectivity):
            neighbor = (row + d_row, col + d_col)
            if not self._cell_in_bounds(neighbor) or not self._is_traversable(neighbor):
                continue
            if abs(d_row) == 1 and abs(d_col) == 1 and not self._diagonal_allowed(cell, d_row, d_col):
                continue
            yield neighbor, self._edge_cost(cell, neighbor, diagonal=abs(d_row) == 1 and abs(d_col) == 1)

    def _cell_in_bounds(self, cell: GridCell) -> bool:
        row, col = cell
        rows, cols = self.grid.metadata.shape
        return 0 <= row < rows and 0 <= col < cols

    def _diagonal_allowed(self, cell: GridCell, d_row: int, d_col: int) -> bool:
        row, col = cell
        return self._is_traversable((row + d_row, col)) and self._is_traversable((row, col + d_col))

    def _edge_cost(self, current: GridCell, neighbor: GridCell, *, diagonal: bool) -> float:
        base_m = self.grid.metadata.resolution_m * (math.sqrt(2.0) if diagonal else 1.0)
        if self.grid.cost is None:
            return base_m
        current_cost = float(self.grid.cost[current])
        neighbor_cost = float(self.grid.cost[neighbor])
        return base_m * (current_cost + neighbor_cost) / 2.0


def write_nav2_occupancy_grid(
    grid: TraversabilityGrid,
    output_dir: Path,
    *,
    stem: str = "traversability",
    occupied_thresh: float = 0.65,
    free_thresh: float = 0.196,
) -> Nav2OccupancyGridExport:
    """Write a Nav2 map_server YAML+PGM derived from traversability truth.

    Traversable cells are encoded as free space. Non-traversable cells are
    encoded as occupied, because the current traversability schema has no
    separate unknown mask. Grid row 0 is the lowest map-frame y row, while PGM
    row 0 is visually topmost, so the image is flipped vertically and the YAML
    origin remains the map-frame lower-left corner.
    """
    _validate_nav2_export_config(stem, occupied_thresh, free_thresh)
    rows, cols = grid.metadata.shape
    if grid.mask.shape != (rows, cols) or grid.component.shape != (rows, cols):
        raise GroundTruthError("traversability grid arrays do not match metadata shape")

    output_dir = Path(output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    image_path = output_dir / f"{stem}.pgm"
    yaml_path = output_dir / f"{stem}.yaml"

    free = grid.mask.astype(bool) & (grid.component >= 0)
    occupied = ~free
    image = np.where(free, 254, 0).astype(np.uint8)
    image_bytes = _pgm_bytes(np.flipud(image))
    image_path.write_bytes(image_bytes)

    map_yaml = {
        "image": image_path.name,
        "mode": "trinary",
        "resolution": float(grid.metadata.resolution_m),
        "origin": [
            float(grid.metadata.origin.x_m),
            float(grid.metadata.origin.y_m),
            0.0,
        ],
        "negate": 0,
        "occupied_thresh": float(occupied_thresh),
        "free_thresh": float(free_thresh),
    }
    yaml_text = yaml.safe_dump(map_yaml, sort_keys=False, allow_unicode=False)
    yaml_path.write_bytes(yaml_text.encode("utf-8"))

    return Nav2OccupancyGridExport(
        yaml_path=yaml_path,
        image_path=image_path,
        free_cells=int(free.sum()),
        occupied_cells=int(occupied.sum()),
        unknown_cells=0,
        image_sha256=hashlib.sha256(image_bytes).hexdigest(),
        yaml_sha256=hashlib.sha256(yaml_text.encode("utf-8")).hexdigest(),
    )


def write_traversability_artifact(
    metadata: TraversabilityMetadata,
    arrays: Mapping[str, np.ndarray],
    output_dir: Path,
    *,
    stem: str = "traversability",
    export_nav2: bool = True,
    occupied_thresh: float = 0.65,
    free_thresh: float = 0.196,
) -> TraversabilityArtifactExport:
    """Write metadata, deterministic NPZ, optional Nav2 map and manifest.

    The input arrays can use canonical keys (``height``, ``normal``, ``cost``,
    ``mask``, ``component``) or the names declared in ``metadata.arrays``. The
    writer always emits NPZ entries using ``metadata.arrays`` and writes metadata
    with the resulting NPZ SHA-256 filled in. The NPZ is a deterministic ZIP
    archive with fixed timestamps and sorted entries, so rerunning the same
    export produces stable bytes.
    """
    _validate_artifact_export_config(stem, occupied_thresh, free_thresh)
    output_root = Path(output_dir).expanduser().resolve()
    output_root.mkdir(parents=True, exist_ok=True)

    keys = metadata.arrays
    npz_arrays = {
        keys.height: _artifact_array(arrays, "height", keys.height),
        keys.normal: _artifact_array(arrays, "normal", keys.normal),
        keys.cost: _artifact_array(arrays, "cost", keys.cost),
        keys.mask: _artifact_array(arrays, "mask", keys.mask),
        keys.component: _artifact_array(arrays, "component", keys.component),
    }

    npz_path = output_root / f"{stem}.npz"
    metadata_path = output_root / f"{stem}.metadata.yaml"
    manifest_path = output_root / f"{stem}.manifest.json"

    _write_deterministic_npz(npz_path, npz_arrays)
    npz_sha256 = traversability_npz_sha256(npz_path)
    metadata_with_checksum = metadata.model_copy(update={"npz_sha256": npz_sha256})
    validation_summary = validate_traversability_npz(npz_path, metadata_with_checksum)

    metadata_text = canonical_traversability_metadata_json(metadata_with_checksum)
    metadata_path.write_text(metadata_text, encoding="utf-8")
    metadata_sha256 = hashlib.sha256(metadata_text.encode("utf-8")).hexdigest()

    grid = TraversabilityGrid(
        metadata=metadata_with_checksum,
        height=np.asarray(npz_arrays[keys.height], dtype=np.float32),
        mask=np.asarray(npz_arrays[keys.mask], dtype=np.uint8),
        component=np.asarray(npz_arrays[keys.component], dtype=np.int32),
        cost=np.asarray(npz_arrays[keys.cost], dtype=np.float32),
    )
    nav2_export = (
        write_nav2_occupancy_grid(
            grid,
            output_root,
            stem=f"{stem}.nav2",
            occupied_thresh=occupied_thresh,
            free_thresh=free_thresh,
        )
        if export_nav2
        else None
    )

    manifest = {
        "files": {
            "metadata": {
                "path": metadata_path.name,
                "sha256": metadata_sha256,
            },
            "npz": {
                "path": npz_path.name,
                "sha256": npz_sha256,
            },
        },
        "generator": "airground-traversability-artifact-v1",
        "nav2": nav2_export.summary() if nav2_export is not None else None,
        "scene_id": metadata_with_checksum.scene_id,
        "shape": list(metadata_with_checksum.shape),
        "status": "ok",
        "validation": validation_summary,
    }
    if nav2_export is not None:
        manifest["files"]["nav2_yaml"] = {
            "path": nav2_export.yaml_path.name,
            "sha256": nav2_export.yaml_sha256,
        }
        manifest["files"]["nav2_pgm"] = {
            "path": nav2_export.image_path.name,
            "sha256": nav2_export.image_sha256,
        }
    manifest_text = json.dumps(manifest, ensure_ascii=True, sort_keys=True, separators=(",", ":")) + "\n"
    manifest_path.write_text(manifest_text, encoding="utf-8")
    manifest_sha256 = hashlib.sha256(manifest_text.encode("utf-8")).hexdigest()

    return TraversabilityArtifactExport(
        metadata_path=metadata_path,
        npz_path=npz_path,
        manifest_path=manifest_path,
        metadata_sha256=metadata_sha256,
        npz_sha256=npz_sha256,
        manifest_sha256=manifest_sha256,
        validation_summary=validation_summary,
        nav2_export=nav2_export,
    )


def build_traversability_rollout_report(
    records: Iterable[Mapping[str, Any]],
    *,
    min_samples: int = 200,
    min_consistency: float = 0.98,
    max_mismatches: int = 50,
) -> TraversabilityRolloutReport:
    """Build a deterministic report from Jackal rollout validation samples.

    This function consumes simulator-produced rollout records and checks whether
    the physical outcome agrees with the traversability label. It does not run
    Isaac itself; it fixes the report surface that the later real rollout stage
    must produce.
    """
    _validate_rollout_report_config(
        min_samples=min_samples,
        min_consistency=min_consistency,
        max_mismatches=max_mismatches,
    )
    samples = tuple(
        _coerce_rollout_sample(record, index)
        for index, record in enumerate(records)
    )
    if not samples:
        raise GroundTruthError("rollout validation requires at least one sample")
    return TraversabilityRolloutReport(
        samples=samples,
        min_samples=min_samples,
        min_consistency=min_consistency,
        max_mismatches=max_mismatches,
    )


def canonical_traversability_rollout_report_json(report: TraversabilityRolloutReport) -> str:
    """Serialize a rollout validation report deterministically."""
    return json.dumps(report.summary(), ensure_ascii=True, sort_keys=True, separators=(",", ":")) + "\n"


def build_traversability_mismatch_review_report(
    records: Iterable[Mapping[str, Any]],
    *,
    screenshot_paths: Mapping[str, str] | None = None,
    final_dispositions: Mapping[str, str] | None = None,
    require_screenshots: bool = True,
    require_final_dispositions: bool = True,
) -> TraversabilityMismatchReviewReport:
    """Build a review artifact for static/dynamic traversability mismatches."""
    samples = tuple(
        _coerce_rollout_sample(record, index)
        for index, record in enumerate(records)
    )
    if not samples:
        raise GroundTruthError("mismatch review requires at least one rollout sample")
    screenshot_paths = screenshot_paths or {}
    final_dispositions = final_dispositions or {}
    entries = tuple(
        TraversabilityMismatchReviewEntry(
            sample=sample,
            screenshot_path=_optional_review_value(screenshot_paths.get(sample.sample_id)),
            final_disposition=_optional_review_value(final_dispositions.get(sample.sample_id)),
        )
        for sample in samples
        if not sample.matches
    )
    return TraversabilityMismatchReviewReport(
        samples=samples,
        entries=entries,
        require_screenshots=require_screenshots,
        require_final_dispositions=require_final_dispositions,
    )


def canonical_traversability_mismatch_review_report_json(
    report: TraversabilityMismatchReviewReport,
) -> str:
    """Serialize a mismatch review report deterministically."""
    return json.dumps(report.summary(), ensure_ascii=True, sort_keys=True, separators=(",", ":")) + "\n"


def build_jackal_ground_threshold_calibration_report(
    records: Iterable[Mapping[str, Any]],
    *,
    robot_id: str = "isaacsim.clearpath_jackal",
    testbed_version: str = "airground-jackal-ground-testbed-v1",
    max_tilt_rad: float = 0.7,
) -> JackalGroundThresholdCalibrationReport:
    """Derive Jackal slope/step thresholds from standard ground-testbed outcomes.

    Input records are expected to come from a real Isaac/ROS Jackal testbed run.
    Relevant records must carry ``test_kind`` of ``slope`` or ``step`` and either
    ``slope_deg`` or ``step_height_m``. Regular route-smoke traces without these
    fields are ignored and therefore fail the calibration due to missing evidence.
    """
    if not math.isfinite(max_tilt_rad) or max_tilt_rad < 0.0:
        raise GroundTruthError("max_tilt_rad must be finite and non-negative")
    outcomes = tuple(
        outcome
        for index, record in enumerate(records)
        if (outcome := _coerce_ground_threshold_outcome(record, index, max_tilt_rad=max_tilt_rad)) is not None
    )
    return JackalGroundThresholdCalibrationReport(
        outcomes=outcomes,
        robot_id=str(robot_id),
        testbed_version=str(testbed_version),
    )


def canonical_jackal_ground_threshold_calibration_json(
    report: JackalGroundThresholdCalibrationReport,
) -> str:
    """Serialize Jackal ground-threshold calibration deterministically."""
    return json.dumps(report.summary(), ensure_ascii=True, sort_keys=True, separators=(",", ":")) + "\n"


def jackal_ground_threshold_config_yaml(
    report: JackalGroundThresholdCalibrationReport,
) -> str:
    """Serialize a successful Jackal ground-threshold config deterministically."""
    return yaml.safe_dump(
        report.versioned_config(),
        allow_unicode=False,
        sort_keys=True,
    )


def _cell_center_xy(metadata: TraversabilityMetadata, row: int, col: int) -> tuple[float, float]:
    resolution = metadata.resolution_m
    return (
        float(metadata.origin.x_m + (col + 0.5) * resolution),
        float(metadata.origin.y_m + (row + 0.5) * resolution),
    )


def _normalized_terrain_hits(
    value: Any,
    *,
    origin: tuple[float, float, float],
    direction: tuple[float, float, float],
    max_distance_m: float,
    ignored_prefixes: tuple[str, ...],
) -> list[TerrainRaycastHit]:
    hits: list[TerrainRaycastHit] = []
    if value is None:
        return hits
    if isinstance(value, TerrainRaycastHit):
        hits = [value]
    elif isinstance(value, Mapping):
        if "hits" in value:
            for item in value["hits"]:
                hits.append(_coerce_terrain_hit(item, origin=origin, direction=direction))
        else:
            hits = [_coerce_terrain_hit(value, origin=origin, direction=direction)]
    elif isinstance(value, Iterable) and not isinstance(value, (str, bytes)):
        for item in value:
            hits.append(_coerce_terrain_hit(item, origin=origin, direction=direction))
    else:
        hits = [_coerce_terrain_hit(value, origin=origin, direction=direction)]
    filtered = [
        hit
        for hit in hits
        if 0.0 <= hit.distance_m <= max_distance_m
        and not _prim_path_has_prefix(hit.prim_path, ignored_prefixes)
    ]
    return sorted(filtered, key=lambda hit: hit.distance_m)


def _coerce_terrain_hit(
    value: Any,
    *,
    origin: tuple[float, float, float],
    direction: tuple[float, float, float],
) -> TerrainRaycastHit:
    if isinstance(value, TerrainRaycastHit):
        _validate_terrain_hit(value)
        return value
    if isinstance(value, Mapping):
        getter = value.get
    else:
        getter = lambda key, default=None: getattr(value, key, default)

    distance = getter("distance_m", getter("distance", None))
    if distance is None:
        raise GroundTruthError("raycast hit is missing distance_m")
    distance_m = float(distance)
    if not math.isfinite(distance_m) or distance_m < 0.0:
        raise GroundTruthError("raycast hit distance_m must be finite and non-negative")

    position = getter("position_xyz_m", None)
    if position is None:
        position = getter("position", None)
    if position is None:
        position = getter("world_position", None)
    if position is None:
        position = _position_from_distance(origin, direction, distance_m)
    normal = getter("normal_xyz", None)
    if normal is None:
        normal = getter("normal", None)
    if normal is None:
        normal = getter("world_normal", None)
    if normal is None:
        raise GroundTruthError("raycast hit is missing normal_xyz")
    prim_path = getter("prim_path", getter("path", None))
    if prim_path is not None:
        prim_path = str(prim_path)
    hit = TerrainRaycastHit(
        distance_m=distance_m,
        position_xyz_m=_xyz_tuple(position, "position_xyz_m"),
        normal_xyz=_normalized_vector(_xyz_tuple(normal, "normal_xyz")),
        prim_path=prim_path,
    )
    _validate_terrain_hit(hit)
    return hit


def _validate_terrain_hit(hit: TerrainRaycastHit) -> None:
    if not math.isfinite(hit.distance_m) or hit.distance_m < 0.0:
        raise GroundTruthError("raycast hit distance_m must be finite and non-negative")
    _xyz_tuple(hit.position_xyz_m, "position_xyz_m")
    _normalized_vector(_xyz_tuple(hit.normal_xyz, "normal_xyz"))
    if hit.prim_path is not None and hit.prim_path and not hit.prim_path.startswith("/"):
        raise GroundTruthError("raycast hit prim_path must be an absolute USD path when provided")


def _position_from_distance(
    origin: tuple[float, float, float],
    direction: tuple[float, float, float],
    distance_m: float,
) -> tuple[float, float, float]:
    unit = _normalized_vector(direction)
    return (
        float(origin[0] + unit[0] * distance_m),
        float(origin[1] + unit[1] * distance_m),
        float(origin[2] + unit[2] * distance_m),
    )


def _xyz_tuple(value: Any, name: str) -> tuple[float, float, float]:
    try:
        x, y, z = value
    except Exception as error:  # noqa: BLE001 - normalize third-party hit objects.
        raise GroundTruthError(f"{name} must contain exactly three numeric values") from error
    result = (float(x), float(y), float(z))
    if not all(math.isfinite(item) for item in result):
        raise GroundTruthError(f"{name} must contain finite values")
    return result


def _normalized_vector(value: Any) -> tuple[float, float, float]:
    x, y, z = _xyz_tuple(value, "vector")
    norm = math.sqrt(x * x + y * y + z * z)
    if norm <= 0.0:
        raise GroundTruthError("raycast normal/direction vector must be non-zero")
    return x / norm, y / norm, z / norm


def _select_ground_hit(
    hits: list[TerrainRaycastHit],
    *,
    min_ground_normal_z: float,
    max_height_z: float | None = None,
) -> tuple[TerrainRaycastHit | None, bool]:
    """Return the first drivable ground-like hit and whether anything preceded it.

    2026-09-19 (user): the GT must describe the surface the UGV actually drives
    on.  Ground-like surfaces *above the vehicle's height envelope*
    (``max_height_z`` = map ground + max obstacle height) are skipped, so a bus
    shelter roof no longer becomes the cell's "ground": the ray keeps going and
    takes the road/floor underneath, exactly like the runtime ground support
    plane.  Before this change a shelter roof gave ``height = 2.8 m``, the step
    test reported a 2.8 m wall and the ground underneath was blocked
    (``smoke_20260919_153113``).
    """

    blocked_before_ground = False
    for hit in hits:
        if hit.normal_xyz[2] >= min_ground_normal_z:
            if max_height_z is not None and hit.position_xyz_m[2] > float(max_height_z):
                # Above the vehicle envelope (a roof, a canopy): not drivable,
                # and its own cell is judged by the obstacle band instead.
                continue
            return hit, blocked_before_ground
        blocked_before_ground = True
    return None, blocked_before_ground


def _select_ceiling_hit(
    hits: list[TerrainRaycastHit],
    *,
    ground_z_m: float,
    min_clearance_m: float,
) -> TerrainRaycastHit | None:
    """First headroom hit that is genuinely above the ground surface.

    PhysX reports the surface a ray starts on as an initial-overlap hit whose
    position lies at or below the ray origin, so the raw first hit is not the
    ceiling.  Anything within ``min_clearance_m`` of the ground is treated as
    the ground surface itself.
    """
    minimum_z = float(ground_z_m) + float(min_clearance_m)
    for hit in hits:
        if hit.position_xyz_m[2] > minimum_z:
            return hit
    return None


def _prim_path_has_prefix(path: str | None, prefixes: tuple[str, ...]) -> bool:
    if path is None:
        return False
    for prefix in prefixes:
        if path == prefix or path.startswith(prefix.rstrip("/") + "/"):
            return True
    return False


def _validate_raycast_terrain_shapes(terrain: RaycastTerrainGrid) -> None:
    rows, cols = terrain.metadata.shape
    expected = (rows, cols)
    arrays = {
        "height": terrain.height,
        "support_mask": terrain.support_mask,
        "obstacle_mask": terrain.obstacle_mask,
        "ceiling_height": terrain.ceiling_height,
        "slope_rad": terrain.slope_rad,
        "step_height_m": terrain.step_height_m,
        "overhead_clearance_m": terrain.overhead_clearance_m,
    }
    for name, value in arrays.items():
        if value.shape != expected:
            raise GroundTruthError(f"{name} shape {value.shape} does not match metadata shape {expected}")
    if terrain.normal.shape != (rows, cols, 3):
        raise GroundTruthError(f"normal shape {terrain.normal.shape} does not match metadata shape {(rows, cols, 3)}")
    for name in ("height", "normal", "ceiling_height", "slope_rad", "step_height_m", "overhead_clearance_m"):
        value = getattr(terrain, name)
        if not np.isfinite(value).all():
            raise GroundTruthError(f"{name} contains non-finite values")


def _first_path(value: Any) -> str | None:
    if isinstance(value, str):
        return value
    if isinstance(value, (list, tuple)) and value:
        first = value[0]
        if isinstance(first, str):
            return first
    return None


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def _finite_float_triplet(value: Any) -> tuple[float, float, float] | None:
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        return None
    try:
        result = (float(value[0]), float(value[1]), float(value[2]))
    except (TypeError, ValueError):
        return None
    if not all(math.isfinite(item) for item in result):
        return None
    return result


def _collision_half_extents_xyz(collision: Mapping[str, Any]) -> tuple[float, float, float] | None:
    attrs = collision.get("attributes")
    if not isinstance(attrs, Mapping):
        return None
    extent = attrs.get("extent")
    if not isinstance(extent, (list, tuple)) or len(extent) != 2:
        return None
    min_corner = _finite_float_triplet(extent[0])
    max_corner = _finite_float_triplet(extent[1])
    if min_corner is None or max_corner is None:
        return None
    return (
        max(abs(min_corner[0]), abs(max_corner[0])),
        max(abs(min_corner[1]), abs(max_corner[1])),
        max(abs(min_corner[2]), abs(max_corner[2])),
    )


def _collisions_for_link(collisions: list[Any], link_path: str) -> tuple[Mapping[str, Any], ...]:
    prefix = link_path.rstrip("/") + "/collisions"
    result: list[Mapping[str, Any]] = []
    for collision in collisions:
        if not isinstance(collision, Mapping):
            continue
        path = str(collision.get("path", ""))
        if path == prefix or path.startswith(prefix + "/"):
            result.append(collision)
    return tuple(result)


def _positive_attr(attrs: Mapping[str, Any], name: str) -> float | None:
    value = attrs.get(name)
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    if result > 0.0 and math.isfinite(result):
        return result
    return None


def _wheel_radius_from_collisions(collisions: tuple[Mapping[str, Any], ...]) -> float | None:
    candidates: list[float] = []
    for collision in collisions:
        attrs = collision.get("attributes")
        if isinstance(attrs, Mapping):
            radius = _positive_attr(attrs, "radius")
            if radius is not None:
                candidates.append(radius)
        half_extents = _collision_half_extents_xyz(collision)
        if half_extents is not None:
            candidates.append(max(half_extents))
    return max(candidates) if candidates else None


def _wheel_thickness_from_collisions(collisions: tuple[Mapping[str, Any], ...]) -> float | None:
    candidates: list[float] = []
    for collision in collisions:
        attrs = collision.get("attributes")
        if isinstance(attrs, Mapping):
            height = _positive_attr(attrs, "height")
            if height is not None:
                candidates.append(height)
                continue
        half_extents = _collision_half_extents_xyz(collision)
        if half_extents is not None:
            positive = sorted(extent for extent in half_extents if extent > 0.0)
            if positive:
                candidates.append(2.0 * positive[0])
    return max(candidates) if candidates else None


def _footprint_offsets_for_yaw(
    *,
    yaw_rad: float,
    resolution_m: float,
    length_m: float,
    width_m: float,
) -> tuple[GridCell, ...]:
    half_rows = max(1, math.ceil((length_m + width_m) / (2.0 * resolution_m)))
    cos_yaw = math.cos(yaw_rad)
    sin_yaw = math.sin(yaw_rad)
    offsets: set[GridCell] = set()
    for d_row in range(-half_rows, half_rows + 1):
        for d_col in range(-half_rows, half_rows + 1):
            x_m = d_col * resolution_m
            y_m = d_row * resolution_m
            local_x = cos_yaw * x_m + sin_yaw * y_m
            local_y = -sin_yaw * x_m + cos_yaw * y_m
            if abs(local_x) <= length_m / 2.0 + resolution_m / 2.0 and abs(local_y) <= width_m / 2.0 + resolution_m / 2.0:
                offsets.add((d_row, d_col))
    offsets.add((0, 0))
    return tuple(sorted(offsets))


def _footprint_offsets_fit(mask: np.ndarray, row: int, col: int, offsets: tuple[GridCell, ...]) -> bool:
    rows, cols = mask.shape
    for d_row, d_col in offsets:
        test_row = row + d_row
        test_col = col + d_col
        if test_row < 0 or test_col < 0 or test_row >= rows or test_col >= cols:
            return False
        if not bool(mask[test_row, test_col]):
            return False
    return True


def _footprint_sweep_cost(
    traversable: np.ndarray,
    *,
    slope_rad: np.ndarray,
    step_height_m: np.ndarray,
    max_slope_rad: float,
    max_step_height_m: float,
    blocked_cost: float,
) -> np.ndarray:
    slope_scale = max(max_slope_rad, 1.0e-6)
    step_scale = max(max_step_height_m, 1.0e-6)
    normalized_slope = np.clip(slope_rad.astype(np.float32) / slope_scale, 0.0, 1.0)
    normalized_step = np.clip(step_height_m.astype(np.float32) / step_scale, 0.0, 1.0)
    cost = (1.0 + 0.5 * normalized_slope + 0.5 * normalized_step).astype(np.float32)
    cost[~traversable.astype(bool)] = np.float32(blocked_cost)
    return cost


def _artifact_array(
    arrays: Mapping[str, np.ndarray],
    canonical_key: str,
    metadata_key: str,
) -> np.ndarray:
    if canonical_key in arrays:
        return np.asarray(arrays[canonical_key])
    if metadata_key in arrays:
        return np.asarray(arrays[metadata_key])
    raise GroundTruthError(
        f"traversability artifact arrays missing {canonical_key!r} / {metadata_key!r}"
    )


def _require_array_shape(name: str, value: np.ndarray, expected: tuple[int, ...]) -> None:
    if value.shape != expected:
        raise GroundTruthError(f"{name} shape {value.shape} does not match expected {expected}")


def _require_finite_float_array(name: str, value: np.ndarray) -> None:
    if value.dtype.kind != "f":
        raise GroundTruthError(f"{name} must be floating-point, got {value.dtype}")
    if not np.isfinite(value).all():
        raise GroundTruthError(f"{name} contains non-finite values")


def _optional_bool_array(
    arrays: Mapping[str, np.ndarray],
    key: str,
    shape: tuple[int, int],
    *,
    default: np.ndarray,
) -> np.ndarray:
    if key not in arrays:
        value = np.asarray(default, dtype=bool)
    else:
        value = np.asarray(arrays[key])
    _require_array_shape(key, value, shape)
    if value.dtype.kind not in {"b", "u", "i"}:
        raise GroundTruthError(f"{key} must be boolean or integer, got {value.dtype}")
    if not np.isin(value, [0, 1, False, True]).all():
        raise GroundTruthError(f"{key} must contain only 0/1 values")
    return value.astype(bool)


def _optional_float_array(
    arrays: Mapping[str, np.ndarray],
    key: str,
    shape: tuple[int, int],
    *,
    default: np.ndarray,
) -> np.ndarray:
    value = np.asarray(arrays[key] if key in arrays else default, dtype=np.float32)
    _require_array_shape(key, value, shape)
    _require_finite_float_array(key, value)
    return value.astype(np.float32)


def _write_deterministic_npz(path: Path, arrays: Mapping[str, np.ndarray]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, mode="w", compression=zipfile.ZIP_STORED) as archive:
        for key in sorted(arrays):
            array_buffer = io.BytesIO()
            np.lib.format.write_array(
                array_buffer,
                np.asarray(arrays[key]),
                allow_pickle=False,
            )
            info = zipfile.ZipInfo(f"{key}.npy")
            info.date_time = (1980, 1, 1, 0, 0, 0)
            info.compress_type = zipfile.ZIP_STORED
            info.external_attr = 0o644 << 16
            archive.writestr(info, array_buffer.getvalue())


def _validate_artifact_export_config(
    stem: str,
    occupied_thresh: float,
    free_thresh: float,
) -> None:
    if not re.match(r"^[A-Za-z0-9_.-]+$", stem):
        raise GroundTruthError("artifact stem must contain only letters, numbers, dot, dash or underscore")
    _validate_nav2_export_config(f"{stem}.nav2", occupied_thresh, free_thresh)


def _coerce_rollout_sample(record: Mapping[str, Any], index: int) -> RolloutValidationSample:
    if not isinstance(record, Mapping):
        raise GroundTruthError(f"rollout sample {index} must be a mapping")
    sample_kind = str(record.get("sample_kind", "cell"))
    if sample_kind not in {"cell", "edge", "short_path"}:
        raise GroundTruthError(f"rollout sample {index} has unsupported sample_kind: {sample_kind}")
    sample_id = str(record.get("sample_id", f"sample-{index:04d}"))
    start_cell = _coerce_grid_cell(record.get("start_cell"), f"rollout sample {index} start_cell")
    end_cell_value = record.get("end_cell")
    end_cell = (
        _coerce_grid_cell(end_cell_value, f"rollout sample {index} end_cell")
        if end_cell_value is not None
        else None
    )
    expected = record.get("expected_traversable")
    rollout_success = record.get("rollout_success")
    if not isinstance(expected, bool):
        raise GroundTruthError(f"rollout sample {index} expected_traversable must be boolean")
    if not isinstance(rollout_success, bool):
        raise GroundTruthError(f"rollout sample {index} rollout_success must be boolean")
    reason = record.get("reason")
    if reason is not None:
        reason = str(reason)
    return RolloutValidationSample(
        sample_id=sample_id,
        sample_kind=sample_kind,
        start_cell=start_cell,
        end_cell=end_cell,
        expected_traversable=expected,
        rollout_success=rollout_success,
        reason=reason,
    )


def _coerce_grid_cell(value: Any, name: str) -> GridCell:
    if not isinstance(value, list | tuple) or len(value) != 2:
        raise GroundTruthError(f"{name} must be a [row, col] pair")
    row, col = value
    if not isinstance(row, int) or not isinstance(col, int):
        raise GroundTruthError(f"{name} values must be integers")
    if row < 0 or col < 0:
        raise GroundTruthError(f"{name} values must be non-negative")
    return row, col


def _optional_review_value(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _coerce_ground_threshold_outcome(
    record: Mapping[str, Any],
    index: int,
    *,
    max_tilt_rad: float,
) -> JackalGroundThresholdOutcome | None:
    event = record.get("event")
    if event not in {None, "jackal_ground_testbed_outcome", "jackal_ground_route"}:
        return None
    test_kind = record.get("test_kind", record.get("kind"))
    if test_kind not in {"slope", "step"}:
        return None
    value_key = "slope_deg" if test_kind == "slope" else "step_height_m"
    raw_value = record.get(value_key)
    if not isinstance(raw_value, (int, float)) or not math.isfinite(float(raw_value)) or float(raw_value) < 0.0:
        raise GroundTruthError(f"{test_kind} threshold outcome requires finite non-negative {value_key}")
    status = record.get("status")
    if status not in {"ok", "failed"}:
        raise GroundTruthError("ground threshold outcome status must be 'ok' or 'failed'")
    route_index = record.get("route_index")
    if route_index is not None and (not isinstance(route_index, int) or route_index < 0):
        raise GroundTruthError("ground threshold outcome route_index must be a non-negative integer")
    max_tilt = record.get("max_tilt_rad")
    if max_tilt is not None:
        if not isinstance(max_tilt, (int, float)) or not math.isfinite(float(max_tilt)) or float(max_tilt) < 0.0:
            raise GroundTruthError("ground threshold outcome max_tilt_rad must be finite and non-negative")
        max_tilt_value: float | None = float(max_tilt)
    else:
        max_tilt_value = None

    issues: list[str] = []
    if status == "failed":
        issues.append("status_failed")
    collision_count = record.get("collision_count", 0)
    if not isinstance(collision_count, int) or collision_count < 0:
        raise GroundTruthError("ground threshold outcome collision_count must be a non-negative integer")
    if collision_count > 0:
        issues.append("collision")
    for flag in ("penetrated", "sunk", "excessive_slip", "tipped"):
        value = record.get(flag, False)
        if not isinstance(value, bool):
            raise GroundTruthError(f"ground threshold outcome {flag} must be boolean when present")
        if value:
            issues.append(flag)
    if max_tilt_value is not None and max_tilt_value > max_tilt_rad:
        issues.append("tilt_exceeded")

    raw_test_id = record.get("test_id")
    if raw_test_id is None:
        route_suffix = f"route-{route_index}" if route_index is not None else f"record-{index}"
        raw_test_id = f"{test_kind}-{float(raw_value):g}-{route_suffix}"
    return JackalGroundThresholdOutcome(
        test_id=str(raw_test_id),
        test_kind=str(test_kind),
        value=float(raw_value),
        status=str(status),
        route_index=route_index,
        max_tilt_rad=max_tilt_value,
        issues=tuple(sorted(set(issues))),
    )


def _threshold_value_summaries(
    outcomes: tuple[JackalGroundThresholdOutcome, ...],
) -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []
    for value in sorted({outcome.value for outcome in outcomes}):
        records = tuple(outcome for outcome in outcomes if outcome.value == value)
        stable_count = sum(1 for outcome in records if outcome.stable)
        failed_count = len(records) - stable_count
        summaries.append(
            {
                "failed_count": failed_count,
                "sample_count": len(records),
                "stable": failed_count == 0,
                "stable_count": stable_count,
                "value": value,
            }
        )
    return summaries


def _max_stable_threshold(
    outcomes: tuple[JackalGroundThresholdOutcome, ...],
) -> float | None:
    stable_values = [
        summary["value"]
        for summary in _threshold_value_summaries(outcomes)
        if summary["stable"] is True
    ]
    return max(stable_values) if stable_values else None


def _threshold_group_issue_counts(
    outcomes: tuple[JackalGroundThresholdOutcome, ...],
    kind: str,
) -> dict[str, int]:
    issue_counts: dict[str, int] = {}
    if not outcomes:
        issue_counts[f"missing_{kind}_outcomes"] = 1
        return issue_counts

    summaries = _threshold_value_summaries(outcomes)
    for summary in summaries:
        if summary["stable_count"] and summary["failed_count"]:
            issue_counts[f"inconsistent_{kind}_repeats"] = issue_counts.get(f"inconsistent_{kind}_repeats", 0) + 1

    failed_values = [summary["value"] for summary in summaries if summary["stable"] is False]
    if failed_values:
        first_failed = min(failed_values)
        stable_after_failed = [
            summary["value"]
            for summary in summaries
            if summary["stable"] is True and summary["value"] > first_failed
        ]
        if stable_after_failed:
            issue_counts[f"non_monotonic_{kind}_outcomes"] = len(stable_after_failed)
    return issue_counts


def _merge_issue_counts(*issue_count_maps: Mapping[str, int]) -> dict[str, int]:
    merged: dict[str, int] = {}
    for issue_counts in issue_count_maps:
        for issue, count in issue_counts.items():
            merged[issue] = merged.get(issue, 0) + int(count)
    return merged


def _validate_rollout_report_config(
    *,
    min_samples: int,
    min_consistency: float,
    max_mismatches: int,
) -> None:
    if min_samples <= 0:
        raise GroundTruthError("min_samples must be positive")
    if not 0.0 <= min_consistency <= 1.0:
        raise GroundTruthError("min_consistency must be in [0, 1]")
    if max_mismatches < 0:
        raise GroundTruthError("max_mismatches must be non-negative")


def _rollout_kind_counts(samples: tuple[RolloutValidationSample, ...]) -> dict[str, int]:
    counts = {"cell": 0, "edge": 0, "short_path": 0}
    for sample in samples:
        counts[sample.sample_kind] += 1
    return counts


def _flood_fill_component(
    traversable: np.ndarray,
    components: np.ndarray,
    *,
    start: GridCell,
    component_id: int,
    connectivity: int,
) -> None:
    stack = [start]
    components[start] = component_id
    while stack:
        row, col = stack.pop()
        for d_row, d_col in _neighbor_offsets(connectivity):
            neighbor = (row + d_row, col + d_col)
            n_row, n_col = neighbor
            if n_row < 0 or n_col < 0 or n_row >= traversable.shape[0] or n_col >= traversable.shape[1]:
                continue
            if abs(d_row) == 1 and abs(d_col) == 1:
                if not (traversable[row + d_row, col] and traversable[row, col + d_col]):
                    continue
            if not traversable[neighbor] or components[neighbor] >= 0:
                continue
            components[neighbor] = component_id
            stack.append(neighbor)


def _neighbor_offsets(connectivity: int) -> tuple[GridCell, ...]:
    cardinal = ((-1, 0), (0, -1), (0, 1), (1, 0))
    if connectivity == 4:
        return cardinal
    return (
        (-1, -1),
        (-1, 0),
        (-1, 1),
        (0, -1),
        (0, 1),
        (1, -1),
        (1, 0),
        (1, 1),
    )


def _validate_local_feature_config(
    grid: TraversabilityGrid,
    *,
    robot_radius_m: float,
    robot_height_m: float,
    max_slope_rad: float,
    max_step_height_m: float,
    overhead_clearance_margin_m: float,
    ceiling_height: np.ndarray | None,
) -> None:
    rows, cols = grid.metadata.shape
    expected_shape = (rows, cols)
    for name, array in (
        ("height", grid.height),
        ("mask", grid.mask),
        ("component", grid.component),
    ):
        if array.shape != expected_shape:
            raise GroundTruthError(f"{name} shape {array.shape} does not match metadata shape {expected_shape}")
    if not np.isfinite(grid.height).all():
        raise GroundTruthError("height array must contain only finite values")
    if ceiling_height is not None:
        if ceiling_height.shape != expected_shape:
            raise GroundTruthError(
                f"ceiling_height shape {ceiling_height.shape} does not match metadata shape {expected_shape}"
            )
        if not np.isfinite(ceiling_height).all():
            raise GroundTruthError("ceiling_height array must contain only finite values")
    if robot_radius_m <= 0.0:
        raise GroundTruthError("robot_radius_m must be positive")
    if robot_height_m <= 0.0:
        raise GroundTruthError("robot_height_m must be positive")
    if not 0.0 <= max_slope_rad < math.pi / 2.0:
        raise GroundTruthError("max_slope_rad must satisfy 0 <= max_slope_rad < pi/2")
    if max_step_height_m < 0.0:
        raise GroundTruthError("max_step_height_m must be non-negative")
    if overhead_clearance_margin_m < 0.0:
        raise GroundTruthError("overhead_clearance_margin_m must be non-negative")


def _slope_from_height(height: np.ndarray, resolution_m: float) -> np.ndarray:
    values = height.astype(np.float64)
    grad_y = np.zeros_like(values)
    grad_x = np.zeros_like(values)
    rows, cols = values.shape
    if rows > 1:
        grad_y[1:-1, :] = (values[2:, :] - values[:-2, :]) / (2.0 * resolution_m)
        grad_y[0, :] = (values[1, :] - values[0, :]) / resolution_m
        grad_y[-1, :] = (values[-1, :] - values[-2, :]) / resolution_m
    if cols > 1:
        grad_x[:, 1:-1] = (values[:, 2:] - values[:, :-2]) / (2.0 * resolution_m)
        grad_x[:, 0] = (values[:, 1] - values[:, 0]) / resolution_m
        grad_x[:, -1] = (values[:, -1] - values[:, -2]) / resolution_m
    return np.arctan(np.hypot(grad_x, grad_y))


def _max_neighbor_height_delta(height: np.ndarray) -> np.ndarray:
    rows, cols = height.shape
    result = np.zeros((rows, cols), dtype=np.float64)
    for d_row, d_col in _neighbor_offsets(8):
        src_row_start = max(0, -d_row)
        src_row_end = min(rows, rows - d_row)
        src_col_start = max(0, -d_col)
        src_col_end = min(cols, cols - d_col)
        dst_row_start = max(0, d_row)
        dst_row_end = min(rows, rows + d_row)
        dst_col_start = max(0, d_col)
        dst_col_end = min(cols, cols + d_col)
        delta = np.abs(
            height[src_row_start:src_row_end, src_col_start:src_col_end]
            - height[dst_row_start:dst_row_end, dst_col_start:dst_col_end]
        )
        result[src_row_start:src_row_end, src_col_start:src_col_end] = np.maximum(
            result[src_row_start:src_row_end, src_col_start:src_col_end],
            delta,
        )
    return result


def _distance_to_nearest_blocked_cell(traversable: np.ndarray, *, resolution_m: float) -> np.ndarray:
    rows, cols = traversable.shape
    distances = np.full((rows, cols), math.inf, dtype=np.float64)
    queue: list[tuple[float, GridCell]] = []
    for row in range(rows):
        for col in range(cols):
            if not traversable[row, col]:
                distances[row, col] = 0.0
                heapq.heappush(queue, (0.0, (row, col)))
    if not queue:
        return distances
    while queue:
        distance_m, cell = heapq.heappop(queue)
        if distance_m > distances[cell]:
            continue
        row, col = cell
        for d_row, d_col in _neighbor_offsets(8):
            neighbor = (row + d_row, col + d_col)
            n_row, n_col = neighbor
            if n_row < 0 or n_col < 0 or n_row >= rows or n_col >= cols:
                continue
            edge_m = resolution_m * (math.sqrt(2.0) if abs(d_row) == 1 and abs(d_col) == 1 else 1.0)
            next_distance_m = distance_m + edge_m
            if next_distance_m < distances[neighbor]:
                distances[neighbor] = next_distance_m
                heapq.heappush(queue, (next_distance_m, neighbor))
    return distances


def _validate_nav2_export_config(stem: str, occupied_thresh: float, free_thresh: float) -> None:
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", stem):
        raise GroundTruthError("Nav2 export stem may only contain letters, digits, '.', '_' and '-'")
    if not 0.0 < free_thresh < occupied_thresh < 1.0:
        raise GroundTruthError("Nav2 thresholds must satisfy 0 < free_thresh < occupied_thresh < 1")


def _pgm_bytes(image: np.ndarray) -> bytes:
    if image.ndim != 2:
        raise GroundTruthError("PGM image must be 2D")
    if image.dtype != np.uint8:
        raise GroundTruthError("PGM image must be uint8")
    rows, cols = image.shape
    header = f"P5\n# RAVEN-AirGround traversability occupancy grid\n{cols} {rows}\n255\n"
    return header.encode("ascii") + image.tobytes(order="C")
