#!/usr/bin/env python3
"""Validate UGV confirmation-region visibility with Isaac PhysX raycasts.

The script loads the annotation scene (RetroNeighborhood by default), obtains
the real PhysX scene-query interface, binds it to the benchmark validator, and writes
a deterministic report.  It requires target annotations that already contain
confirmation regions; it does not generate regions and does not mark targets as
human-reviewed.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import sys
import time
import types
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[4]
AIR_STACK_ISAAC_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_IGNORED_PRIM_PREFIXES = (
    "/World/UAV",
    "/World/uav",
    "/World/UGV",
    "/World/ugv",
)
CONFIRMATION_SENSOR_FRAME_TOPIC = "/ugv/confirmation_visibility_sensor_frames"


def _prepare_benchmark_package_import() -> None:
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
        if (candidate / "ground_truth.py").exists() and (candidate / "isaac_los.py").exists():
            package = types.ModuleType("airground_benchmark")
            package.__path__ = [str(candidate)]  # type: ignore[attr-defined]
            sys.modules.setdefault("airground_benchmark", package)
            return
    raise ModuleNotFoundError(
        "cannot locate airground_benchmark package; mount the repo benchmark/ "
        "directory or copy benchmark/airground_benchmark to /tmp/airground_benchmark"
    )


_prepare_benchmark_package_import()

from airground_benchmark.ground_truth import (  # noqa: E402
    canonical_raycast_confirmation_visibility_report_json,
    canonical_sensor_frame_confirmation_visibility_report_json,
    load_target_annotations,
    validate_confirmation_visibility_sensor_trace,
    validate_confirmation_visibility_with_raycast,
)
from airground_benchmark.isaac_los import make_isaac_physx_raycast_fn  # noqa: E402
from airground_benchmark.scenes import SCENE_IDS  # noqa: E402


def _resolve_scene_asset(
    scene_id: str, explicit: Path | None, expected_sha256: str | None = None,
) -> tuple[Path, str]:
    """Reject cross-scene defaults before starting Isaac; pin local asset bytes."""
    if scene_id not in SCENE_IDS:
        raise ValueError(f"Unknown annotation scene: {scene_id}")
    if scene_id != "RetroNeighborhood" and explicit is None:
        raise ValueError("Non-Retro annotations require --scene-usd; refusing the Retro default")
    project = Path(os.environ.get("AIRGROUND_PROJECT_ROOT") or AIR_STACK_ISAAC_ROOT.parents[1])
    candidate = explicit or Path(os.environ.get("AIRGROUND_ENV_URL") or
                                project / "scenes/RetroNeighborhood/RetroNeighborhood_Export.usd")
    scene = candidate.resolve(strict=True)
    if not scene.is_file():
        raise ValueError("Scene asset must be a local USD file")
    for known_scene in SCENE_IDS:
        if scene.stem == f"{known_scene}_Export" and known_scene != scene_id:
            raise ValueError(f"Asset filename identifies {known_scene}, annotations identify {scene_id}")
    checksum = hashlib.sha256()
    with scene.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            checksum.update(chunk)
    observed = checksum.hexdigest()
    if expected_sha256 is not None and observed != expected_sha256.lower():
        raise ValueError("Scene SHA256 differs from --scene-sha256")
    return scene, observed


def _validate_runtime_target_paths(manifest: Any, stage: Any) -> int:
    """Do not treat a missing target namespace as a successful visibility run."""
    bound = [instance for instance in manifest.instances if instance.usd_prim_path]
    missing = [instance.usd_prim_path for instance in bound
               if not stage.GetPrimAtPath(instance.usd_prim_path).IsValid()]
    if missing:
        raise RuntimeError(
            f"{len(missing)} target prim paths are missing in the loaded runtime; "
            f"check the asset reference namespace: {missing[:5]}")
    return len(bound)


def _project_reference_target_paths(
    manifest: Any, runtime_stage: Any, scene_asset: Path, reference_root: str,
) -> tuple[Any, list[dict[str, Any]]]:
    """Explicit private runtime projection, preserving source GT and world poses."""
    from pxr import Sdf, Usd, UsdGeom

    destination = Sdf.Path(reference_root)
    if not destination.IsAbsolutePath() or not destination.IsPrimPath():
        raise ValueError("--target-reference-root must be an absolute prim path")
    source_stage = Usd.Stage.Open(str(scene_asset))
    source_default = source_stage.GetDefaultPrim()
    if not source_default:
        raise ValueError("Scene has no default prim for reference path projection")
    source_root = source_default.GetPath()
    source_xforms = UsdGeom.XformCache()
    runtime_xforms = UsdGeom.XformCache()
    source_bounds = UsdGeom.BBoxCache(Usd.TimeCode.Default(), ["default", "render"])
    runtime_bounds = UsdGeom.BBoxCache(Usd.TimeCode.Default(), ["default", "render"])
    instances, mapping = [], []
    for instance in manifest.instances:
        if not instance.usd_prim_path:
            instances.append(instance)
            continue
        original_path = Sdf.Path(instance.usd_prim_path)
        if not original_path.HasPrefix(source_root):
            raise ValueError(f"Target is outside the referenced default prim: {original_path}")
        projected_path = original_path.ReplacePrefix(source_root, destination)
        original = source_stage.GetPrimAtPath(original_path)
        projected = runtime_stage.GetPrimAtPath(projected_path)
        if not original or not projected:
            raise RuntimeError(f"Reference target missing: {original_path} -> {projected_path}")
        original_matrix = source_xforms.GetLocalToWorldTransform(original)
        projected_matrix = runtime_xforms.GetLocalToWorldTransform(projected)
        matrix_delta = max(abs(original_matrix[i][j] - projected_matrix[i][j])
                           for i in range(4) for j in range(4))
        original_box = source_bounds.ComputeWorldBound(original).ComputeAlignedRange()
        projected_box = runtime_bounds.ComputeWorldBound(projected).ComputeAlignedRange()
        if original_box.IsEmpty() or projected_box.IsEmpty():
            raise RuntimeError(f"Reference target has empty geometry bounds: {original_path}")
        left = list(original_box.GetMin()) + list(original_box.GetMax())
        right = list(projected_box.GetMin()) + list(projected_box.GetMax())
        bounds_delta = max(abs(a - b) for a, b in zip(left, right))
        if (not all(math.isfinite(v) for v in left + right)
                or not math.isfinite(matrix_delta) or matrix_delta > 1e-8
                or bounds_delta > 1e-5):
            raise RuntimeError(f"Reference target world geometry changed: {original_path}")
        instances.append(instance.model_copy(update={"usd_prim_path": str(projected_path)}))
        mapping.append({"instance_id": instance.instance_id,
                        "source_prim": str(original_path), "runtime_prim": str(projected_path),
                        "world_matrix_max_error": matrix_delta,
                        "world_bounds_max_error_m": bounds_delta,
                        "source_verified_unchanged": instance.verified})
    return manifest.model_copy(update={"instances": tuple(instances)}), mapping


def _set_launch_defaults() -> None:
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


def _load_retro_launch_module(launch_script: Path) -> Any:
    spec = importlib.util.spec_from_file_location(
        "airground_retro_launch_for_confirmation_visibility",
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


def _simulation_time_s(app: Any) -> float:
    current_time = getattr(app.world, "current_time", None)
    if current_time is not None:
        return float(current_time() if callable(current_time) else current_time)
    step_index = getattr(app.world, "current_time_step_index", None)
    if step_index is not None:
        step_value = step_index() if callable(step_index) else step_index
        return float(step_value) * float(app.world.get_physics_dt())
    return 0.0


def _sensor_frame_records_from_report(
    report: Any,
    *,
    sim_time_s: float,
    camera_frame: str,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for region_metric in report.metrics:
        for pose_metric in region_metric.pose_metrics:
            records.append(
                {
                    "blocked_ray_count": pose_metric.blocked_ray_count,
                    "blocking_prim_paths": list(pose_metric.blocking_prim_paths),
                    "camera_frame": camera_frame,
                    "clear_ray_count": pose_metric.clear_ray_count,
                    "distance_to_target_m": pose_metric.distance_to_target_m,
                    "event": "confirmation_visibility_sensor_frame",
                    "instance_id": region_metric.instance_id,
                    "pose_index": pose_metric.pose_index,
                    "ray_count": pose_metric.ray_count,
                    "region_id": region_metric.region_id,
                    "sim_time_s": sim_time_s,
                    "visible_fraction": pose_metric.visible_fraction,
                    "yaw_error_rad": pose_metric.yaw_error_rad,
                }
            )
    return records


def _write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(
            json.dumps(record, ensure_ascii=True, sort_keys=True, separators=(",", ":")) + "\n"
            for record in records
        ),
        encoding="utf-8",
    )


def _publish_records_to_ros_topic(
    records: list[dict[str, Any]],
    *,
    topic: str,
    spin_s: float,
) -> dict[str, Any]:
    try:
        import rclpy  # type: ignore[import-not-found]
        from std_msgs.msg import String  # type: ignore[import-not-found]
    except Exception as exc:  # pragma: no cover - only executed inside Isaac/ROS.
        raise RuntimeError("rclpy/std_msgs unavailable; run topic smoke inside Isaac ROS image") from exc

    initialized_here = False
    if not rclpy.ok():
        rclpy.init()
        initialized_here = True

    received_payloads: list[str] = []
    node = rclpy.create_node("airground_confirmation_sensor_frame_topic_smoke")
    try:
        queue_depth = max(10, len(records))
        publisher = node.create_publisher(String, topic, queue_depth)
        node.create_subscription(String, topic, lambda message: received_payloads.append(message.data), queue_depth)
        warmup_deadline = time.monotonic() + min(0.25, max(0.0, spin_s / 4.0))
        while time.monotonic() < warmup_deadline:
            rclpy.spin_once(node, timeout_sec=0.02)
        for record in records:
            payload = json.dumps(record, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
            publisher.publish(String(data=payload))
        deadline = time.monotonic() + spin_s
        while time.monotonic() < deadline and len(received_payloads) < len(records):
            rclpy.spin_once(node, timeout_sec=0.02)
        received_records: list[dict[str, Any]] = []
        for payload in received_payloads:
            try:
                parsed = json.loads(payload)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                received_records.append(parsed)
        status = "ok" if len(received_payloads) >= len(records) else "failed"
        return {
            "generator": "airground-confirmation-sensor-frame-topic-smoke-v1",
            "camera_frame": records[0].get("camera_frame") if records else None,
            "published_count": len(records),
            "publisher_source": "isaac_physx_confirmation_visibility_raycast",
            "received_count": len(received_payloads),
            "received_record_count": len(received_records),
            "sample_received_records": received_records[:3],
            "spin_s": spin_s,
            "status": status,
            "topic": topic,
        }
    finally:
        node.destroy_node()
        if initialized_here:
            rclpy.shutdown()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--launch-script",
        type=Path,
        default=AIR_STACK_ISAAC_ROOT / "launch_scripts/RetroNeighborhood_Launch.py",
    )
    parser.add_argument("--annotations", type=Path, required=True)
    parser.add_argument("--scene-usd", type=Path,
                        help="local scene asset; required for non-Retro annotations")
    parser.add_argument("--scene-sha256", help="optional expected SHA256 of the scene asset")
    parser.add_argument("--instance-collider-manifest", type=Path,
                        help="explicit checksum-pinned static instance collision manifest; "
                             "does not approve semantic targets or arrival regions")
    parser.add_argument("--target-reference-root",
                        help="explicit reference mount (for example /World/stage); validates "
                             "world transforms/bounds and projects target paths only in memory")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--settle-steps", type=int, default=5)
    parser.add_argument("--camera-height", type=float, default=1.2)
    parser.add_argument("--min-distance", type=float, default=1.5)
    parser.add_argument("--max-distance", type=float, default=8.0)
    parser.add_argument("--horizontal-fov", type=float, default=math.radians(90.0))
    parser.add_argument("--min-visible-fraction", type=float, default=0.2)
    parser.add_argument("--required-consecutive-frames", type=int, default=5)
    parser.add_argument("--target-sample-count", type=int, choices=(1, 5, 9), default=5)
    parser.add_argument("--occlusion-epsilon", type=float, default=1.0e-3)
    parser.add_argument("--ignore-prim-prefix", action="append", default=[])
    parser.add_argument(
        "--sensor-trace-output",
        type=Path,
        help="optional JSONL output with per-sensor-frame confirmation visibility samples",
    )
    parser.add_argument(
        "--sensor-report-output",
        type=Path,
        help="optional report from airground gt targets validate-confirmation-sensor-trace",
    )
    parser.add_argument("--sensor-frame-count", type=int, default=5)
    parser.add_argument("--sensor-frame-stride-steps", type=int, default=25)
    parser.add_argument("--sensor-camera-frame", default="ugv/confirmation_camera")
    parser.add_argument("--max-frame-gap", type=float, default=0.15)
    parser.add_argument(
        "--publish-sensor-topic",
        nargs="?",
        const=CONFIRMATION_SENSOR_FRAME_TOPIC,
        help="optional ROS topic to publish generated confirmation sensor-frame records",
    )
    parser.add_argument(
        "--sensor-topic-report-output",
        type=Path,
        help="optional report proving ROS publish/receive of generated sensor-frame records",
    )
    parser.add_argument("--sensor-topic-spin-s", type=float, default=1.0)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    if args.settle_steps < 0:
        raise ValueError("--settle-steps must be non-negative")
    if args.sensor_frame_count <= 0:
        raise ValueError("--sensor-frame-count must be positive")
    if args.sensor_frame_stride_steps <= 0:
        raise ValueError("--sensor-frame-stride-steps must be positive")
    if args.sensor_report_output and not args.sensor_trace_output:
        raise ValueError("--sensor-report-output requires --sensor-trace-output")
    if args.sensor_topic_report_output and not args.publish_sensor_topic:
        raise ValueError("--sensor-topic-report-output requires --publish-sensor-topic")
    if args.sensor_topic_spin_s <= 0.0:
        raise ValueError("--sensor-topic-spin-s must be positive")

    manifest = load_target_annotations(args.annotations)
    scene_asset, scene_sha256 = _resolve_scene_asset(
        manifest.scene_id, args.scene_usd, args.scene_sha256)
    os.environ["AIRGROUND_ENV_URL"] = str(scene_asset)
    if args.instance_collider_manifest:
        os.environ["AIRGROUND_INSTANCE_COLLIDER_MANIFEST"] = str(
            args.instance_collider_manifest.resolve(strict=True))
    _set_launch_defaults()
    launch_module = _load_retro_launch_module(args.launch_script.resolve(strict=True))
    try:
        if Path(launch_module.ENV_URL).resolve(strict=True) != scene_asset:
            raise RuntimeError("Launch module did not select the pinned scene asset")
    except Exception:
        launch_module.simulation_app.close(wait_for_replicator=False, skip_cleanup=True)
        raise
    app = launch_module.PegasusApp()
    try:
        app.timeline.play()
        for _ in range(args.settle_steps):
            app.world.step(render=False)
        runtime_path_mapping = []
        if args.target_reference_root:
            manifest, runtime_path_mapping = _project_reference_target_paths(
                manifest, app.world.stage, scene_asset, args.target_reference_root)
        validated_target_paths = _validate_runtime_target_paths(manifest, app.world.stage)
        scene_query = _get_physx_scene_query()
        raycast_fn = make_isaac_physx_raycast_fn(scene_query)
        report = validate_confirmation_visibility_with_raycast(
            manifest,
            raycast_fn,
            camera_height_m=args.camera_height,
            min_distance_m=args.min_distance,
            max_distance_m=args.max_distance,
            horizontal_fov_rad=args.horizontal_fov,
            min_visible_fraction=args.min_visible_fraction,
            required_consecutive_frames=args.required_consecutive_frames,
            target_sample_count=args.target_sample_count,
            occlusion_epsilon_m=args.occlusion_epsilon,
            ignored_prim_prefixes=tuple(DEFAULT_IGNORED_PRIM_PREFIXES) + tuple(args.ignore_prim_prefix),
            generator_version="p1-07b",
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        output = canonical_raycast_confirmation_visibility_report_json(report)
        args.output.write_text(output, encoding="utf-8")
        scene_evidence = {
            "scope": "asset provenance for this actual raycast report; not human GT approval",
            "scene_id": manifest.scene_id,
            "scene_asset": str(scene_asset), "scene_sha256": scene_sha256,
            "annotations_sha256": hashlib.sha256(args.annotations.read_bytes()).hexdigest(),
            "launch_script_sha256": hashlib.sha256(args.launch_script.read_bytes()).hexdigest(),
            "raycast_report_sha256": hashlib.sha256(output.encode("utf-8")).hexdigest(),
            "raycast_status": report.status,
            "validated_runtime_target_paths": validated_target_paths,
            "runtime_path_mapping": runtime_path_mapping,
            "instance_collision_preparation": getattr(app, "instance_collision_launch_summary", None),
            "source_annotations_modified": False,
        }
        args.output.with_name(args.output.stem + ".scene-runtime.json").write_text(
            json.dumps(scene_evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        sensor_report_status = "ok"
        sensor_topic_report_status = "ok"
        if args.sensor_trace_output or args.publish_sensor_topic:
            sensor_records: list[dict[str, Any]] = []
            for frame_index in range(args.sensor_frame_count):
                if frame_index > 0:
                    for _ in range(args.sensor_frame_stride_steps):
                        app.world.step(render=False)
                frame_report = validate_confirmation_visibility_with_raycast(
                    manifest,
                    raycast_fn,
                    camera_height_m=args.camera_height,
                    min_distance_m=args.min_distance,
                    max_distance_m=args.max_distance,
                    horizontal_fov_rad=args.horizontal_fov,
                    min_visible_fraction=args.min_visible_fraction,
                    required_consecutive_frames=args.required_consecutive_frames,
                    target_sample_count=args.target_sample_count,
                    occlusion_epsilon_m=args.occlusion_epsilon,
                    ignored_prim_prefixes=tuple(DEFAULT_IGNORED_PRIM_PREFIXES)
                    + tuple(args.ignore_prim_prefix),
                    generator_version="p1-07d-sensor-sample",
                )
                sensor_records.extend(
                    _sensor_frame_records_from_report(
                        frame_report,
                        sim_time_s=_simulation_time_s(app),
                        camera_frame=args.sensor_camera_frame,
                    )
                )
            if args.sensor_trace_output:
                _write_jsonl(args.sensor_trace_output, sensor_records)
            sensor_report = validate_confirmation_visibility_sensor_trace(
                manifest,
                sensor_records,
                min_distance_m=args.min_distance,
                max_distance_m=args.max_distance,
                horizontal_fov_rad=args.horizontal_fov,
                min_visible_fraction=args.min_visible_fraction,
                required_consecutive_frames=args.required_consecutive_frames,
                max_frame_gap_s=args.max_frame_gap,
                require_raycast_evidence=True,
                generator_version="p1-07d-isaac-runner",
            )
            sensor_report_status = sensor_report.status
            if args.sensor_report_output:
                args.sensor_report_output.parent.mkdir(parents=True, exist_ok=True)
                args.sensor_report_output.write_text(
                    canonical_sensor_frame_confirmation_visibility_report_json(sensor_report),
                    encoding="utf-8",
                )
            if args.publish_sensor_topic:
                sensor_topic_report = _publish_records_to_ros_topic(
                    sensor_records,
                    topic=args.publish_sensor_topic,
                    spin_s=args.sensor_topic_spin_s,
                )
                sensor_topic_report_status = str(sensor_topic_report["status"])
                if args.sensor_topic_report_output:
                    args.sensor_topic_report_output.parent.mkdir(parents=True, exist_ok=True)
                    args.sensor_topic_report_output.write_text(
                        json.dumps(sensor_topic_report, indent=2, sort_keys=True) + "\n",
                        encoding="utf-8",
                    )
        print(output, end="")
        return 0 if report.status == "ok" and sensor_report_status == "ok" and sensor_topic_report_status == "ok" else 2
    finally:
        app.timeline.stop()
        try:
            launch_module.simulation_app.close(wait_for_replicator=False, skip_cleanup=True)
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
