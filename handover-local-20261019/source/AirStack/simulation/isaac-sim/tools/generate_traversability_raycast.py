#!/usr/bin/env python3
"""Generate a traversability raycast seed grid inside Isaac Sim.

This tool is intentionally Isaac-side.  It launches the explicit scene through
the shared AirGround runtime (Retro by default), obtains the PhysX query interface, casts
downward and upward rays through ``airground_benchmark.traversability``, and
writes schema-compatible traversability metadata/NPZ plus a compact summary.

The output is a raycast seed surface only.  Jackal footprint sweep, dynamics
rollout validation, target confirmation regions, and release GT freezing stay
in later P1 tasks.
"""

from __future__ import annotations

import argparse
from collections.abc import Iterable
import importlib.util
import json
import math
import logging
import os
from pathlib import Path
import sys
import time
import types
from typing import Any

import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[4]
AIR_STACK_ISAAC_ROOT = Path(__file__).resolve().parents[1]


def _prepare_benchmark_package_import() -> None:
    """Import submodules without executing benchmark package ``__init__``.

    Isaac containers used by AirStack may only mount the AirStack tree.  During
    development, callers can copy ``benchmark/airground_benchmark`` to
    ``/tmp/airground_benchmark`` or point ``AIRGROUND_BENCHMARK_PACKAGE`` to the
    package directory.  We register a lightweight namespace package so imports
    like ``airground_benchmark.traversability`` do not trigger the public package
    surface, which depends on Gym/PettingZoo and is unnecessary for this tool.
    """
    candidates = []
    explicit = os.environ.get("AIRGROUND_BENCHMARK_PACKAGE")
    if explicit:
        candidates.append(Path(explicit))
    candidates.extend(
        [
            REPO_ROOT / "benchmark/airground_benchmark",
            Path("/tmp/airground_benchmark"),
        ]
    )
    for candidate in candidates:
        if (candidate / "ground_truth.py").exists() and (candidate / "traversability.py").exists():
            package = types.ModuleType("airground_benchmark")
            package.__path__ = [str(candidate)]  # type: ignore[attr-defined]
            sys.modules.setdefault("airground_benchmark", package)
            return
    raise ModuleNotFoundError(
        "cannot locate airground_benchmark package; mount the repo benchmark/ "
        "directory or copy benchmark/airground_benchmark to /tmp/airground_benchmark"
    )


_prepare_benchmark_package_import()

from airground_benchmark.config.schema import SCHEMA_VERSION  # noqa: E402
from airground_benchmark.scenes import SCENE_IDS  # noqa: E402
from airground_benchmark.ground_truth import (  # noqa: E402
    GridOrigin,
    TraversabilityMetadata,
    canonical_traversability_metadata_json,
    traversability_npz_sha256,
)
from airground_benchmark.traversability import (  # noqa: E402
    RaycastTerrainGridConfig,
    build_raycast_terrain_grid, FootprintSweepConfig, raycast_terrain_grid_from_arrays,
    sweep_ugv_footprint_over_terrain,
)


DEFAULT_IGNORED_PRIM_PREFIXES = (
    "/World/uav",
    "/World/UAV",
    "/World/ugv",
    "/World/UGV",
)


def _set_launch_defaults() -> None:
    """Keep the launch minimal unless the caller explicitly overrides it."""
    defaults = {
        "AIRGROUND_ALIGN_UAV_TO_DOCK": "false",
        "AIRGROUND_CREATE_DOCK_JOINT": "false",
        "AIRGROUND_ENABLE_SENSOR_GRAPHS": "false",
        "AIRGROUND_ENABLE_UAV_STATE_PUBLISHERS": "false",
        "AIRGROUND_ENABLE_UGV_CONTACT_PUBLISHER": "false",
        "AIRGROUND_ENABLE_UGV_STATE_PUBLISHERS": "false",
        "AIRGROUND_HEADLESS": "true",
        "AIRGROUND_RENDER": "false",
        "AIRGROUND_SCENE_COLLIDER_MODE": "profiled",
        "AIRGROUND_SKIP_CLEANUP_ON_CLOSE": "true",
        "AIRGROUND_UAV_MODEL": "quadcopter",
        "AIRGROUND_UAV_PX4_AUTOLAUNCH": "false",
        "ISAAC_SIM_GUI": "false",
        "PLAY_SIM_ON_START": "false",
    }
    for name, value in defaults.items():
        os.environ.setdefault(name, value)


def _load_launch_module(launch_script: Path) -> Any:
    spec = importlib.util.spec_from_file_location(
        "airground_launch_for_traversability",
        launch_script,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import launch script: {launch_script}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _get_physx_scene_query() -> Any:
    try:
        import omni.physx  # type: ignore[import-not-found]
    except Exception as exc:  # pragma: no cover - only executed inside Isaac.
        raise RuntimeError("omni.physx is unavailable; run this tool inside Isaac Sim") from exc
    try:
        return omni.physx.get_physx_scene_query_interface()
    except AttributeError as exc:  # pragma: no cover - Isaac API guard.
        raise RuntimeError("omni.physx does not expose get_physx_scene_query_interface()") from exc


def _hit_value(hit: Any, names: tuple[str, ...]) -> Any:
    if isinstance(hit, dict):
        for name in names:
            if name in hit:
                return hit[name]
    for name in names:
        if hasattr(hit, name):
            return getattr(hit, name)
    return None


def _xyz_or_none(value: Any) -> tuple[float, float, float] | None:
    if value is None:
        return None
    try:
        x, y, z = value
    except Exception:
        return None
    result = (float(x), float(y), float(z))
    if not all(math.isfinite(item) for item in result):
        return None
    return result


def _normalize_physx_hit(hit: Any) -> dict[str, Any] | None:
    distance = _hit_value(hit, ("distance_m", "distance"))
    if distance is None:
        return None
    distance_m = float(distance)
    if not math.isfinite(distance_m) or distance_m < 0.0:
        return None
    normal = _xyz_or_none(_hit_value(hit, ("normal_xyz", "normal", "world_normal")))
    if normal is None:
        return None
    position = _xyz_or_none(
        _hit_value(hit, ("position_xyz_m", "position", "world_position"))
    )
    prim_path = _hit_value(
        hit,
        (
            "prim_path",
            "primPath",
            "path",
            "rigid_body",
            "rigidBody",
            "collision",
            "collider",
        ),
    )
    payload: dict[str, Any] = {
        "distance_m": distance_m,
        "normal_xyz": normal,
    }
    if position is not None:
        payload["position_xyz_m"] = position
    if prim_path is not None:
        payload["prim_path"] = str(prim_path)
    return payload


def _snapshot_physx_hit(hit: Any) -> dict[str, Any]:
    """RaycastHit bindings expose attributes and are not iterable mappings."""
    result=_normalize_physx_hit(hit) or {}
    collision=_hit_value(hit,("collision","collider"))
    if collision is not None: result["collision"]=str(collision)
    for name,aliases in (("face_index",("face_index","faceIndex")),("proto_index",("proto_index","protoIndex"))):
        value=_hit_value(hit,aliases)
        if value is not None: result[name]=int(value)
    return result


def _iter_returned_hits(result: Any) -> Iterable[Any]:
    if result is None or isinstance(result, (int, float, str, bytes, bool)):
        return ()
    if isinstance(result, dict):
        hits = result.get("hits")
        if hits is not None:
            return hits
        return (result,)
    try:
        return tuple(result)
    except TypeError:
        return (result,)


def _make_raycast_fn(scene_query: Any):
    def raycast_fn(
        origin_xyz_m: tuple[float, float, float],
        direction_xyz: tuple[float, float, float],
        max_distance_m: float,
    ) -> tuple[dict[str, Any], ...]:
        raw_hits: list[Any] = []

        def collect(hit: Any) -> bool:
            raw_hits.append(hit)
            return True

        try:
            result = scene_query.raycast_all(
                origin_xyz_m,
                direction_xyz,
                float(max_distance_m),
                collect,
            )
        except TypeError:
            result = scene_query.raycast_all(
                origin_xyz_m,
                direction_xyz,
                float(max_distance_m),
            )
        raw_hits.extend(_iter_returned_hits(result))
        hits = [_normalize_physx_hit(hit) for hit in raw_hits]
        return tuple(hit for hit in hits if hit is not None)

    return raycast_fn


def _write_npz(path: Path, arrays: dict[str, np.ndarray]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as handle:
        np.savez_compressed(handle, **arrays)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scene-id',choices=SCENE_IDS,default='RetroNeighborhood')
    parser.add_argument('--scene-usd',type=Path,help='Explicit scene asset; required for non-Retro scenes')
    parser.add_argument(
        "--launch-script",
        type=Path,
        default=AIR_STACK_ISAAC_ROOT / "launch_scripts/RetroNeighborhood_Launch.py",
    )
    parser.add_argument("--output-metadata", type=Path, required=True)
    parser.add_argument("--output-npz", type=Path, required=True)
    parser.add_argument("--output-summary", type=Path, required=True)
    parser.add_argument("--origin-x-m", type=float, required=True)
    parser.add_argument("--origin-y-m", type=float, required=True)
    parser.add_argument("--origin-z-m", type=float, default=0.0)
    parser.add_argument("--rows", type=int, required=True)
    parser.add_argument("--cols", type=int, required=True)
    parser.add_argument("--resolution-m", type=float, default=0.1)
    parser.add_argument("--ray-start-z-m", type=float, default=8.0)
    parser.add_argument("--ray-end-z-m", type=float, default=-2.0)
    parser.add_argument("--overhead-ray-distance-m", type=float, default=3.0)
    parser.add_argument("--min-ground-normal-z", type=float, default=0.35)
    # 2026-09-19 (user): mark obstacles the way the local costmap does - any
    # geometry inside this height band above the ground surface.  Geometry above
    # the band (a bus-shelter roof, an awning) no longer blocks the ground
    # underneath, which is what the Nav2 voxel layer sees at runtime.
    parser.add_argument("--obstacle-band-min-height-m", type=float, default=0.05)
    parser.add_argument("--obstacle-band-max-height-m", type=float, default=1.0)
    parser.add_argument(
        "--ignored-prim-prefix",
        action="append",
        default=list(DEFAULT_IGNORED_PRIM_PREFIXES),
    )
    parser.add_argument("--settle-steps", type=int, default=5)
    parser.add_argument("--backend", choices=("physx", "warp", "probe"), default="physx")
    parser.add_argument("--reference-npz", type=Path)
    parser.add_argument("--verify-physx", action="store_true")
    parser.add_argument("--query-world",nargs=2,type=float,action="append")
    parser.add_argument("--save-repx",action="store_true",help="preserve the loaded PhysX scene's native collision serialization")
    return parser.parse_args()


def main() -> int:
    logging.basicConfig(level=logging.INFO)
    args = _parse_args()
    if args.rows <= 0 or args.cols <= 0:
        raise ValueError("--rows and --cols must be positive")
    if args.settle_steps < 0:
        raise ValueError("--settle-steps must be non-negative")

    _set_launch_defaults()
    if args.scene_id!='RetroNeighborhood' and args.scene_usd is None:
        raise ValueError('Non-Retro metadata requires an explicit --scene-usd')
    if args.scene_usd is not None:
        os.environ['AIRGROUND_ENV_URL']=str(args.scene_usd.resolve(strict=True))
    launch_module = _load_launch_module(args.launch_script.resolve(strict=True))
    app = launch_module.PegasusApp()
    try:
        app.timeline.play()
        for _ in range(args.settle_steps):
            app.world.step(render=False)
        scene_query = _get_physx_scene_query()
        if args.backend == "probe":
            import omni.physx
            import omni.usd
            import warp as wp
            from pxr import UsdGeom, UsdPhysics, Usd
            stage = omni.usd.get_context().get_stage()
            cooking = omni.physx.get_physx_cooking_interface()
            counts: dict[str, int] = {}
            samples: list[dict[str, Any]] = []
            for prim in Usd.PrimRange.Stage(stage, Usd.TraverseInstanceProxies()):
                if not prim.HasAPI(UsdPhysics.CollisionAPI):
                    continue
                if UsdPhysics.CollisionAPI(prim).GetCollisionEnabledAttr().Get() is False:
                    continue
                kind = prim.GetTypeName()
                approximation = str(UsdPhysics.MeshCollisionAPI(prim).GetApproximationAttr().Get()) if prim.IsA(UsdGeom.Mesh) else kind
                counts[approximation] = counts.get(approximation, 0) + 1
                if len(samples) < 6 or (approximation == "meshSimplification" and len(samples) < 15):
                    item = {"path":str(prim.GetPath()), "type":kind,"approximation":approximation}
                    if prim.IsA(UsdGeom.Mesh):
                        number = cooking.get_nb_convex_mesh_data(str(prim.GetPath()))
                        item["convex_count"] = number
                        if number:
                            data = cooking.get_convex_mesh_data(str(prim.GetPath()), 0)
                            item["cooked_keys"] = sorted(data)
                            item["first_vertices"] = [list(v) for v in data.get("vertices", [])[:2]]
                        item["points"] = len(UsdGeom.Mesh(prim).GetPointsAttr().Get() or [])
                    samples.append(item)
            wp.init()
            summary={"status":"ok","backend":"probe","warp_version":wp.__version__,"devices":[str(d) for d in wp.get_devices()],"cooking_methods":[n for n in dir(cooking) if not n.startswith('_')],"counts":counts,"samples":samples}
            args.output_summary.write_text(json.dumps(summary, indent=2)+"\n")
            print(json.dumps(summary))
            return 0
        metadata = TraversabilityMetadata(
            schema_version=SCHEMA_VERSION,
            scene_id=args.scene_id,
            frame="map",
            origin=GridOrigin(
                x_m=float(args.origin_x_m),
                y_m=float(args.origin_y_m),
                z_m=float(args.origin_z_m),
            ),
            resolution_m=float(args.resolution_m),
            shape=(int(args.rows), int(args.cols)),
            generator="airground-isaac-raycast-terrain-grid-v1",
            generator_version="p1-01a",
        )
        config = RaycastTerrainGridConfig(
            ray_start_z_m=float(args.ray_start_z_m), ray_end_z_m=float(args.ray_end_z_m),
            overhead_ray_distance_m=float(args.overhead_ray_distance_m),
            min_ground_normal_z=float(args.min_ground_normal_z),
            min_obstacle_height_m=float(args.obstacle_band_min_height_m),
            max_obstacle_height_m=float(args.obstacle_band_max_height_m),
            ignored_prim_path_prefixes=tuple(args.ignored_prim_prefix),
        )
        if args.query_world:
            import omni.usd
            from pxr import UsdGeom, Usd, UsdPhysics
            query_stage=omni.usd.get_context().get_stage()
            snapshots=[]
            for x,y in args.query_world:
                item={"xy_m":[x,y],"queries":{}}
                for label,origin,direction,distance in [("down",(x,y,config.ray_start_z_m),(0.,0.,-1.),config.ray_start_z_m-config.ray_end_z_m),("band",(x,y,config.min_obstacle_height_m),(0.,0.,1.),config.max_obstacle_height_m-config.min_obstacle_height_m),("ceiling",(x,y,0.),(0.,0.,1.),config.overhead_ray_distance_m)]:
                    raw=[]
                    def capture(hit: Any) -> bool:
                        snapshot=_snapshot_physx_hit(hit)
                        prim=query_stage.GetPrimAtPath(snapshot.get("collision",""))
                        if prim and prim.IsA(UsdGeom.Mesh):
                            mesh=UsdGeom.Mesh(prim); attr=mesh.GetPointsAttr()
                            snapshot["source_mesh"]={"subdivision_scheme":mesh.GetSubdivisionSchemeAttr().Get(),
                                                     "point_time_samples":attr.GetTimeSamples(),
                                                     "face_counts":list(mesh.GetFaceVertexCountsAttr().Get()),
                                                     "physics_attributes":{a.GetName():str(a.Get()) for a in prim.GetAttributes() if "physics" in a.GetName().lower()}}
                            for time_label,time_code in [("default",Usd.TimeCode.Default()),("zero",Usd.TimeCode(0))]:
                                points=np.asarray(attr.Get(time_code),dtype=float)
                                snapshot["source_mesh"][time_label+"_bounds"]=[points.min(axis=0).tolist(),points.max(axis=0).tolist()]
                        raw.append(snapshot); return True
                    returned=scene_query.raycast_all(origin,direction,distance,capture)
                    raw.extend(_snapshot_physx_hit(hit) for hit in _iter_returned_hits(returned))
                    item["queries"][label]=raw
                snapshots.append(item)
            args.output_summary.with_name("pre_export_queries.json").write_text(json.dumps(snapshots,indent=2,default=lambda v:list(v))+"\n")
        live_reference=None
        reference_wall_s=None
        if args.verify_physx:
            reference_started=time.perf_counter()
            live_reference=build_raycast_terrain_grid(metadata, _make_raycast_fn(scene_query), config).arrays_for_npz()
            reference_wall_s=time.perf_counter()-reference_started
            _write_npz(args.output_summary.with_name("physx_reference.npz"),live_reference)
        generation_started = time.perf_counter()
        backend_evidence = {"backend":"physx_cpu"}
        repx_wall_s=None
        if args.save_repx or args.backend == "warp":
            import omni.physx
            repx_started=time.perf_counter()
            if not omni.physx.get_physx_interface().save_scene_to_repx(str(args.output_summary.with_name("physx_scene.repx"))):
                raise RuntimeError("failed to serialize the live PhysX scene")
            repx_wall_s=time.perf_counter()-repx_started
        if args.backend == "warp":
            import omni.physx
            import omni.usd
            from gpu_terrain_raycast import build_gpu_terrain
            # Export the live actor poses after settling, including actors
            # whose transforms normally remain in the PhysX/Fabric cache.
            # This only updates the in-memory stage; the source USD is read-only.
            omni.physx.get_physx_interface().update_transformations(False,True)
            metadata = metadata.model_copy(update={"generator":"airground-isaac-warp-cuda-terrain-grid-v1","generator_version":"single-gpu-v1"})
            terrain, backend_evidence = build_gpu_terrain(metadata, config, omni.usd.get_context().get_stage(), omni.physx.get_physx_cooking_interface(),geometry_snapshot=args.output_summary.with_name("collision_geometry.npz"),repx_path=args.output_summary.with_name("physx_scene.repx"))
            import carb
            backend_evidence["native_export_capabilities"]={
                "physx_methods":[name for name in dir(omni.physx.get_physx_interface()) if not name.startswith('_')],
                "framework_methods":[name for name in dir(carb.get_framework()) if not name.startswith('_')],
            }
        else:
            terrain = build_raycast_terrain_grid(metadata, _make_raycast_fn(scene_query), config)
        backend_evidence["generation_wall_s"] = time.perf_counter()-generation_started
        if repx_wall_s is not None: backend_evidence["repx_export_wall_s"]=repx_wall_s
        comparison = None
        if args.reference_npz or args.verify_physx:
            if args.reference_npz and args.verify_physx:
                raise ValueError("choose existing reference or live PhysX verification")
            if args.verify_physx:
                reference=live_reference
                backend_evidence["physx_reference_wall_s"]=reference_wall_s
            else:
                with np.load(args.reference_npz, allow_pickle=False) as data:
                    reference={k:data[k] for k in data.files}
            fields=("height","normal","support_mask","obstacle_mask","ceiling_height","overhead_clearance_m")
            current={"height":terrain.height,"normal":terrain.normal,"support_mask":terrain.support_mask,"obstacle_mask":terrain.obstacle_mask,"ceiling_height":terrain.ceiling_height,"overhead_clearance_m":terrain.overhead_clearance_m}
            comparison={"reference_npz":str(args.reference_npz) if args.reference_npz else "same_live_scene_physx", "tolerance_m":1e-4,"fields":{}}
            for name in fields:
                previous=reference[name]; value=current[name]
                if previous.shape != value.shape:
                    raise ValueError(f"reference shape mismatch for {name}")
                error=np.abs(value.astype(np.float64)-previous.astype(np.float64))
                difference=error> (0 if name.endswith("mask") else 1e-4)
                comparison["fields"][name]={"different_values":int(difference.sum()),"max_absolute_error":float(error.max()),"first_difference_indices":np.argwhere(difference)[:12].tolist()}
            footprint_config=FootprintSweepConfig(max_step_height_m=.05)
            gpu_sweep=sweep_ugv_footprint_over_terrain(terrain,footprint_config)
            cpu_sweep=sweep_ugv_footprint_over_terrain(raycast_terrain_grid_from_arrays(metadata,reference),footprint_config)
            footprint_difference=gpu_sweep.traversable_mask!=cpu_sweep.traversable_mask
            usable=gpu_sweep.traversable_mask|cpu_sweep.traversable_mask
            comparison["footprint"]={"max_step_height_m":.05,"different_cells":int(np.count_nonzero(footprint_difference)),
                                     "first_difference_indices":np.argwhere(footprint_difference)[:12].tolist()}
            for name in fields:
                error=np.abs(current[name].astype(np.float64)-reference[name].astype(np.float64))
                different=error>(0 if name.endswith("mask") else 1e-4)
                if different.ndim==3: different=np.any(different,axis=2)
                comparison["fields"][name]["different_cells_on_either_traversable"]=int(np.count_nonzero(different&usable))
            comparison["status"]="ok" if not any(v["different_values"] for v in comparison["fields"].values()) and comparison["footprint"]["different_cells"]==0 else "different"
            if comparison["status"]!="ok":
                import omni.usd
                from pxr import UsdGeom
                stage=omni.usd.get_context().get_stage()
                query_samples=[]
                cells=set()
                for field in comparison["fields"].values():
                    for index in field["first_difference_indices"][:3]: cells.add(tuple(index[:2]))
                for row,col in sorted(cells):
                    x=float(metadata.origin.x_m+(col+.5)*metadata.resolution_m)
                    y=float(metadata.origin.y_m+(row+.5)*metadata.resolution_m)
                    sample={"row":row,"col":col,"xy_m":[x,y],"gpu":{k:np.asarray(v[row,col]).tolist() for k,v in current.items()},"physx":{k:np.asarray(reference[k][row,col]).tolist() for k in fields},"queries":{}}
                    for label,origin,direction,distance in [("down",(x,y,config.ray_start_z_m),(0.,0.,-1.),config.ray_start_z_m-config.ray_end_z_m),("band",(x,y,config.min_obstacle_height_m),(0.,0.,1.),config.max_obstacle_height_m-config.min_obstacle_height_m),("ceiling",(x,y,float(reference["height"][row,col])),(0.,0.,1.),config.overhead_ray_distance_m)]:
                        hits=[]
                        def collect_debug(hit: Any) -> bool:
                            hit=_snapshot_physx_hit(hit)
                            path=hit.get("collision")
                            if path:
                                prim=stage.GetPrimAtPath(path)
                                hit["world_matrix"]=np.asarray(UsdGeom.Xformable(prim).ComputeLocalToWorldTransform(0)).tolist()
                                hit["approximation"]=str(prim.GetAttribute("physics:approximation").Get())
                                if label=="down" and hit["approximation"] in ("convexDecomposition","convexHull"):
                                    cook=omni.physx.get_physx_cooking_interface()
                                    hit["first_cooked_vertices"]=[list(v) for v in cook.get_convex_mesh_data(path,0).get("vertices",[])[:3]]
                                if label=="down" and hit["approximation"]=="meshSimplification":
                                    hit["cooked_attributes"]=[a.GetName() for a in prim.GetAttributes() if "ooked" in a.GetName()]
                            hits.append(hit)
                            return True
                        returned=scene_query.raycast_all(origin,direction,distance,collect_debug)
                        for hit in _iter_returned_hits(returned): collect_debug(hit)
                        sample["queries"][label]=hits
                    query_samples.append(sample)
                args.output_summary.with_name("gpu_difference_queries.json").write_text(json.dumps(query_samples,indent=2,default=lambda v:list(v))+"\n")
            args.output_summary.with_name("gpu_physx_comparison.json").write_text(json.dumps(comparison,indent=2)+"\n")
            backend_evidence["comparison_status"]=comparison["status"]
        else:
            backend_evidence["comparison_status"]="not_run"
        args.output_summary.with_name("raycast_backend.json").write_text(json.dumps(backend_evidence,indent=2)+"\n")
        _write_npz(args.output_npz, terrain.arrays_for_npz())
        metadata_with_checksum = metadata.model_copy(
            update={"npz_sha256": traversability_npz_sha256(args.output_npz)}
        )
        if comparison is not None:
            comparison["gpu_npz_sha256"]=metadata_with_checksum.npz_sha256
            reference_path=args.reference_npz or args.output_summary.with_name("physx_reference.npz")
            comparison["reference_npz_sha256"]=traversability_npz_sha256(reference_path)
            args.output_summary.with_name("gpu_physx_comparison.json").write_text(json.dumps(comparison,indent=2)+"\n")
            if args.verify_physx:
                reference_metadata=metadata.model_copy(update={"generator":"airground-isaac-raycast-terrain-grid-v1","npz_sha256":comparison["reference_npz_sha256"]})
                args.output_summary.with_name("physx_reference.metadata.json").write_text(canonical_traversability_metadata_json(reference_metadata))
        backend_evidence["npz_sha256"]=metadata_with_checksum.npz_sha256
        args.output_summary.with_name("raycast_backend.json").write_text(json.dumps(backend_evidence,indent=2)+"\n")
        args.output_metadata.parent.mkdir(parents=True, exist_ok=True)
        args.output_metadata.write_text(
            canonical_traversability_metadata_json(metadata_with_checksum),
            encoding="utf-8",
        )
        summary = {
            "event": "isaac_traversability_raycast_grid",
            "metadata": metadata_with_checksum.model_dump(mode="json"),
            "npz": str(args.output_npz),
            "npz_sha256": metadata_with_checksum.npz_sha256,
            "raycast": terrain.summary(),
            "backend": backend_evidence,
            "status": "ok",
        }
        args.output_summary.parent.mkdir(parents=True, exist_ok=True)
        args.output_summary.write_text(
            json.dumps(summary, ensure_ascii=True, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        print(json.dumps(summary, ensure_ascii=True, sort_keys=True))
        return 0
    finally:
        app.timeline.stop()
        try:
            launch_module.simulation_app.close(wait_for_replicator=False, skip_cleanup=True)
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
