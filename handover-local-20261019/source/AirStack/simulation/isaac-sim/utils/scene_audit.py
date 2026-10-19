"""USD scene audit helpers for AirGround Isaac Sim scenes.

The module intentionally keeps the `pxr` dependency optional at import time.
It is available inside Isaac Sim and can also be installed as `usd-core` for
offline audits.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any


GROUND_PATH_TERMS = (
    "ground",
    "road",
    "sidewalk",
    "asphalt",
    "alley",
    "pavement",
    "curb",
    "terrain",
    "floor",
    "driveway",
    "parking",
    "crosswalk",
)
VISUAL_ONLY_PATH_TERMS = (
    "sky",
    "cloud",
    "compass",
    "render",
    "camera",
    "light",
    "omniversekit",
)

# Exact scene-relative mesh identities, not a broad "land" substring rule.
# ConstructionSite's two open terrain surfaces otherwise become convex solids,
# filling valleys above the actual mesh. Preserve their concave ground shape.
SCENE_GROUND_MESH_SUFFIXES = (
    "/constructionsite/land/landscape/landscape_0",
    "/constructionsite/land/landscape2/landscape2",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def classify_scene_mesh(path_string: str, *, has_collision: bool, has_rigid_body: bool) -> str:
    """Classify one mesh into the Phase 6 scene-profile buckets.

    This is an explicit static profile, not a traversability or physics result.
    Ground terms are matched first after dynamic objects; collidable non-ground
    meshes become static obstacles. Non-collidable sky/camera/render helpers are
    visual-only.
    """

    normalized = path_string.lower()
    if has_rigid_body:
        return "dynamic"
    if normalized.endswith(SCENE_GROUND_MESH_SUFFIXES):
        return "ground"
    if any(term in normalized for term in GROUND_PATH_TERMS):
        return "ground"
    if any(term in normalized for term in VISUAL_ONLY_PATH_TERMS) and not has_collision:
        return "visual_only"
    if has_collision:
        return "static_obstacle"
    return "uncategorized"


def collision_approximation_for_profile(profile: str) -> str | None:
    """Return the launch-time mesh collision approximation for a profile."""

    if profile == "ground":
        return "meshSimplification"
    if profile == "static_obstacle":
        return "convexDecomposition"
    return None


def _rounded_vec3(value) -> list[float]:
    return [round(float(value[0]), 4), round(float(value[1]), 4), round(float(value[2]), 4)]


def audit_usd_scene(scene_path: str | Path, *, sample_limit: int = 20) -> dict[str, Any]:
    """Return a deterministic USD scene audit report.

    The report covers the Phase 6 static scene surface: root/default prims,
    stage units, mesh/material counts, PhysicsScene count, collision coverage,
    and representative paths for manual review.
    """

    try:
        from pxr import Usd, UsdGeom, UsdPhysics, UsdShade
    except ModuleNotFoundError as exc:  # pragma: no cover - exercised in non-USD envs
        raise RuntimeError(
            "USD Python bindings are required; run inside Isaac Sim or install usd-core"
        ) from exc

    path = Path(scene_path)
    stage = Usd.Stage.Open(str(path))
    if stage is None:
        raise RuntimeError(f"failed to open USD stage: {path}")

    default_prim = stage.GetDefaultPrim()
    type_counts: Counter[str] = Counter()
    root_prims: list[str] = []
    mesh_paths: list[str] = []
    material_paths: list[str] = []
    physics_scene_paths: list[str] = []
    collision_paths: list[str] = []
    meshes_without_collision: list[str] = []
    rigid_body_paths: list[str] = []
    mass_api_paths: list[str] = []
    profile_counts: Counter[str] = Counter()
    profile_samples: dict[str, list[str]] = {
        "ground": [],
        "static_obstacle": [],
        "dynamic": [],
        "visual_only": [],
        "uncategorized": [],
    }
    geometry_thresholds = {
        "deep_min_z_m": -1.0,
        "floating_ground_min_z_m": 0.5,
        "thin_extent_m": 0.02,
        "thin_wall_xy_extent_m": 0.05,
        "thin_wall_min_height_m": 2.0,
    }
    geometry_counts: Counter[str] = Counter()
    geometry_samples: dict[str, list[dict[str, Any]]] = {
        "deep_min_z_lt_minus_1m": [],
        "entirely_below_minus_1m": [],
        "invisible_colliders": [],
        "thin_z_lt_2cm": [],
        "thin_any_dim_lt_2cm": [],
        "floating_ground_min_z_gt_0_5m": [],
        "thin_vertical_wall_candidates": [],
    }
    bbox_cache = UsdGeom.BBoxCache(
        Usd.TimeCode.Default(),
        [UsdGeom.Tokens.default_, UsdGeom.Tokens.render, UsdGeom.Tokens.proxy],
    )

    for prim in stage.Traverse():
        type_counts[prim.GetTypeName() or "<none>"] += 1
        path_string = prim.GetPath().pathString
        if path_string.count("/") == 1:
            root_prims.append(path_string)
        if prim.IsA(UsdGeom.Mesh):
            mesh_paths.append(path_string)
            has_collision = prim.HasAPI(UsdPhysics.CollisionAPI)
            has_rigid_body = prim.HasAPI(UsdPhysics.RigidBodyAPI)
            if not has_collision:
                meshes_without_collision.append(path_string)
            profile = classify_scene_mesh(
                path_string,
                has_collision=has_collision,
                has_rigid_body=has_rigid_body,
            )
            profile_counts[profile] += 1
            if len(profile_samples[profile]) < sample_limit:
                profile_samples[profile].append(path_string)
        if prim.IsA(UsdShade.Material):
            material_paths.append(path_string)
        if prim.IsA(UsdPhysics.Scene):
            physics_scene_paths.append(path_string)
        if prim.HasAPI(UsdPhysics.CollisionAPI):
            collision_paths.append(path_string)
            box = bbox_cache.ComputeWorldBound(prim).ComputeAlignedBox()
            bounds_min = box.GetMin()
            bounds_max = box.GetMax()
            extent = bounds_max - bounds_min
            visibility = UsdGeom.Imageable(prim).ComputeVisibility()
            profile = classify_scene_mesh(
                path_string,
                has_collision=True,
                has_rigid_body=prim.HasAPI(UsdPhysics.RigidBodyAPI),
            )
            sample = {
                "path": path_string,
                "profile": profile,
                "min": _rounded_vec3(bounds_min),
                "max": _rounded_vec3(bounds_max),
                "extent": _rounded_vec3(extent),
            }

            def _flag(name: str):
                geometry_counts[name] += 1
                if len(geometry_samples[name]) < sample_limit:
                    geometry_samples[name].append(sample)

            if bounds_min[2] < geometry_thresholds["deep_min_z_m"]:
                _flag("deep_min_z_lt_minus_1m")
            if bounds_max[2] < geometry_thresholds["deep_min_z_m"]:
                _flag("entirely_below_minus_1m")
            if visibility == UsdGeom.Tokens.invisible:
                _flag("invisible_colliders")
            if extent[2] < geometry_thresholds["thin_extent_m"]:
                _flag("thin_z_lt_2cm")
            if min(extent) < geometry_thresholds["thin_extent_m"]:
                _flag("thin_any_dim_lt_2cm")
            if profile == "ground" and bounds_min[2] > geometry_thresholds["floating_ground_min_z_m"]:
                _flag("floating_ground_min_z_gt_0_5m")
            if (
                min(extent[0], extent[1]) < geometry_thresholds["thin_wall_xy_extent_m"]
                and extent[2] > geometry_thresholds["thin_wall_min_height_m"]
            ):
                _flag("thin_vertical_wall_candidates")
        if prim.HasAPI(UsdPhysics.RigidBodyAPI):
            rigid_body_paths.append(path_string)
        if prim.HasAPI(UsdPhysics.MassAPI):
            mass_api_paths.append(path_string)

    counts = {
        "prims": sum(type_counts.values()),
        "meshes": len(mesh_paths),
        "materials": len(material_paths),
        "physics_scenes": len(physics_scene_paths),
        "collision_api": len(collision_paths),
        "meshes_without_collision": len(meshes_without_collision),
        "rigid_body_api": len(rigid_body_paths),
        "mass_api": len(mass_api_paths),
    }

    return {
        "schema_version": "1.0.0",
        "scene": {
            "name": path.parent.name,
            "path": path.as_posix(),
            "sha256": _sha256(path),
            "size_bytes": path.stat().st_size,
        },
        "stage": {
            "default_prim": str(default_prim.GetPath()) if default_prim else None,
            "root_prims": root_prims,
            "meters_per_unit": float(UsdGeom.GetStageMetersPerUnit(stage) or 1.0),
            "up_axis": str(UsdGeom.GetStageUpAxis(stage)),
        },
        "counts": counts,
        "profile": {
            "rules": {
                "ground_path_terms": list(GROUND_PATH_TERMS),
                "visual_only_path_terms": list(VISUAL_ONLY_PATH_TERMS),
                "dynamic_source": "UsdPhysics.RigidBodyAPI",
                "static_obstacle_source": "UsdPhysics.CollisionAPI minus ground/dynamic",
                "collision_approximation_policy": {
                    "ground": collision_approximation_for_profile("ground"),
                    "static_obstacle": collision_approximation_for_profile("static_obstacle"),
                    "dynamic": collision_approximation_for_profile("dynamic"),
                    "visual_only": collision_approximation_for_profile("visual_only"),
                    "uncategorized": collision_approximation_for_profile("uncategorized"),
                },
            },
            "counts": {key: profile_counts.get(key, 0) for key in profile_samples},
            "samples": profile_samples,
        },
        "geometry_diagnostics": {
            "thresholds": geometry_thresholds,
            "counts": {
                "duplicate_physics_scenes": max(0, len(physics_scene_paths) - 1),
                **{key: geometry_counts.get(key, 0) for key in geometry_samples},
            },
            "samples": geometry_samples,
        },
        "type_counts": dict(sorted(type_counts.items())),
        "samples": {
            "meshes": mesh_paths[:sample_limit],
            "materials": material_paths[:sample_limit],
            "physics_scenes": physics_scene_paths[:sample_limit],
            "collision_api": collision_paths[:sample_limit],
            "meshes_without_collision": meshes_without_collision[:sample_limit],
            "rigid_body_api": rigid_body_paths[:sample_limit],
            "mass_api": mass_api_paths[:sample_limit],
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit a USD scene for AirGround physics work")
    parser.add_argument("scene", help="Path to the USD/USDC scene")
    parser.add_argument("--sample-limit", type=int, default=20)
    args = parser.parse_args(argv)

    report = audit_usd_scene(args.scene, sample_limit=args.sample_limit)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
