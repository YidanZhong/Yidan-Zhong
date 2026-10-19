"""Command-line entry point for benchmark tooling."""

from __future__ import annotations

from airground_benchmark.scenes import SCENE_IDS

import argparse
import hashlib
from collections.abc import Mapping
import importlib.metadata
import json
import logging
import math
import os
from pathlib import Path
import platform
import subprocess
import sys
from typing import Any, Sequence

import numpy as np
import yaml
from pydantic import ValidationError

from airground_benchmark.assets import (
    AssetError,
    AssetManifest,
    DEFAULT_ASSET_SIMULATOR_VERSION,
    PACKAGED_ASSET_MANIFESTS,
    asset_manifest_sha256,
    check_assets,
    fetch_assets,
    load_asset_manifest,
    results_json,
)
from airground_benchmark.episode_audit import (
    EpisodeAuditError,
    audit_episode_manifest_against_ground_truth,
    canonical_episode_audit_report_json,
)
from airground_benchmark.config import (
    canonical_config_json,
    canonical_schema_json,
    load_config,
)
from airground_benchmark.episode_generation import (
    CandidatePoolBuildConfig,
    EpisodeGenerationError,
    PairedStartConfig,
    attach_oracle_evidence_to_candidate_pool,
    audit_candidate_pool,
    audit_difficulty_metadata,
    build_candidate_pool_from_artifacts,
    build_manifest_from_candidates,
    build_paired_start_candidates,
    build_release_pair_from_candidates,
    canonical_candidate_pool_audit_json,
    canonical_candidate_oracle_evidence_json,
    canonical_candidate_pool_json,
    canonical_difficulty_metadata_audit_json,
    canonical_difficulty_metadata_json,
    canonical_paired_start_candidates_json,
    canonical_release_pair_report_json,
    difficulty_metadata_from_candidates,
    estimate_candidate_grid_oracle_evidence,
    load_candidate_oracle_evidence,
    load_candidate_pool,
    load_difficulty_metadata,
    load_paired_start_candidates,
    validate_candidate_labels_against_metadata,
)
from airground_benchmark.episode_manifest import (
    EpisodeManifestError,
    apply_oracle_timeouts,
    canonical_episode_manifest_json,
    canonical_episode_schema_json,
    episode_manifest_sha256,
    hidden_release_metadata,
    load_episode_manifest,
)
from airground_benchmark.faults import (
    canonical_fault_catalog_json,
    canonical_fault_injection_report_json,
    fault_scenario_catalog,
    run_contract_fault_injection,
)
from airground_benchmark.full_mission_evidence import (
    FullMissionEvidenceError,
    build_confirmation_evidence_from_sensor_trace,
    canonical_confirmation_evidence_json,
)
from airground_benchmark.ground_truth import (
    GroundTruthError,
    apply_target_review_ledger,
    audit_target_annotations,
    bind_target_annotations_to_usd_prims,
    build_confirmation_regions_from_traversability,
    build_target_review_ledger_template,
    build_visibility_occlusion_report_from_traversability,
    canonical_confirmation_visibility_report_json,
    canonical_sensor_frame_confirmation_visibility_report_json,
    canonical_target_annotation_audit_report_json,
    canonical_target_annotations_json,
    canonical_target_prim_binding_report_json,
    canonical_target_annotations_schema_json,
    canonical_target_review_apply_report_json,
    canonical_target_review_ledger_template_json,
    canonical_pose_visibility_report_json,
    canonical_traversability_schema_json,
    canonical_visibility_occlusion_report_json,
    convert_rayfronts_bbox_annotations,
    evaluate_target_visibility_at_pose,
    load_arrival_region_labels,
    load_default_target_annotations,
    load_target_annotations,
    load_target_review_ledger,
    load_traversability_grid,
    load_traversability_metadata,
    load_usd_prim_candidate_manifest,
    target_annotations_sha256,
    validate_traversability_npz,
    validate_confirmation_visibility_from_traversability,
    validate_confirmation_visibility_sensor_trace,
    VisibilityOcclusionReport,
    write_target_review_artifacts,
)
from airground_benchmark.headless_integration import (
    canonical_headless_integration_report_json,
    validate_headless_integration_artifacts,
)
from airground_benchmark.runtime_fault_suite import (
    canonical_runtime_fault_suite_report_json,
    validate_runtime_fault_suite_artifacts,
)
from airground_benchmark.system_run import (
    canonical_system_run_bundle_report_json,
    validate_system_run_bundle_artifacts,
)
from airground_benchmark.metrics import (
    MetricsError,
    canonical_run_metrics_validation_report_json,
    canonical_summary_json,
    evaluate_events_file,
    validate_run_metrics_artifacts,
)
from airground_benchmark.task_catalog import (
    CATALOG_ID,
    TaskCatalogError,
    build_task_catalog,
    canonical_task_catalog_json,
    catalog_diagnostics,
    find_catalog_entry,
    load_task_catalog,
)
from airground_benchmark.ugv_progress import (
    ArrivalRegionContext,
    UgvProgressError,
    aggregate_ugv_progress,
    canonical_ugv_progress_aggregate_json,
    canonical_ugv_progress_json,
    compute_ugv_progress,
    load_ugv_pose_samples,
    load_ugv_progress_report,
    ugv_progress_sha256,
)
from airground_benchmark.performance import (
    build_performance_report,
    canonical_performance_report_json,
)
from airground_benchmark.traversability import (
    FootprintSweepConfig,
    DEFAULT_REACH_CLEARANCE_MARGIN_M,
    DEFAULT_REACH_FOOTPRINT_WIDTH_M,
    build_reach_region,
    build_jackal_ground_threshold_calibration_report,
    build_traversability_mismatch_review_report,
    build_traversability_rollout_report,
    canonical_jackal_ground_threshold_calibration_json,
    canonical_traversability_mismatch_review_report_json,
    canonical_traversability_rollout_report_json,
    jackal_ground_threshold_config_yaml,
    load_jackal_footprint_estimate_from_asset_report,
    write_nav2_occupancy_grid,
    write_footprint_sweep_artifact,
    write_traversability_artifact,
)
from airground_benchmark.release_checklist import (
    build_release_checklist,
    canonical_release_checklist_report_json,
)
from airground_benchmark.release_audit import (
    ReleaseAuditError,
    audit_release_pair_directory,
    canonical_release_audit_report_json,
)
from airground_benchmark.release_manifest import (
    ReleaseManifestError,
    build_release_manifest,
    canonical_release_manifest_report_json,
    parse_named_paths,
)
from airground_benchmark.reproducibility import (
    FreshCloneReproPlan,
    attach_fresh_clone_artifact_checksums,
    build_fresh_clone_repro_plan,
    build_fresh_clone_repro_report,
    canonical_fresh_clone_repro_plan_json,
    canonical_fresh_clone_repro_report_json,
    load_fresh_clone_step_results_json,
)
from airground_benchmark.reset import (
    REQUIRED_HEALTH_COMPONENTS,
    build_reset_plan,
    canonical_reset_plan_json,
    canonical_reset_run_validation_report_json,
    decide_reset_recovery,
    validate_hard_restart_full_health_artifact,
    validate_production_reset_orchestrator_artifacts,
    validate_reset_airstack_trajectory_clear_surface,
    validate_reset_control_hold_surface,
    validate_reset_nav2_cancel_surface,
    validate_reset_recovery_artifact,
    validate_reset_run_artifacts,
    validate_reset_state_run_artifacts,
    validate_reset_stable_health_handshake_surface,
    validate_reset_trace,
    validate_reset_trace_event_status,
    validate_reset_uav_px4_cancel_surface,
    validate_soft_reset_full_action_artifact,
)
from airground_benchmark.run import (
    RESOURCE_GUARD_DEFAULT_HOST_MEMORY_MAX_GB,
    RESOURCE_GUARD_DEFAULT_MAX_CONSECUTIVE_FAILURES,
    RESOURCE_GUARD_DEFAULT_MAX_GPU_MEMORY_FRACTION,
    RESOURCE_GUARD_DEFAULT_MAX_SYSTEM_MEMORY_FRACTION,
    RESOURCE_GUARD_DEFAULT_MIN_AVAILABLE_MEMORY_GB,
    RESOURCE_GUARD_DEFAULT_POLL_S,
    RESOURCE_GUARD_DEFAULT_PROFILE,
    RESOURCE_GUARD_PROFILE_ENV,
    RunError,
    canonical_hidden_oracle_run_redacted_json,
    canonical_oracle_run_validation_report_json,
    redacted_hidden_oracle_run_report,
    resource_guard_host_address_space_limit,
    run_contract,
    run_isaac_smoke,
    validate_isaac_resource_guard_configuration,
    validate_oracle_run_artifacts,
)
from airground_benchmark.trajectory_replay import (
    DEFAULT_REVIEW_K,
    DEFAULT_REVIEW_PRE_ROLL_S,
    DEFAULT_REVIEW_TAIL_S,
    REVIEW_WINDOW_FULL,
    REVIEW_WINDOW_TAKEOFF_TO_K,
    TrajectoryReplayError,
    build_trajectory_video_manifest,
    load_camera_specs,
    write_run_replay_manifest,
)
from airground_benchmark.smoke import (
    DEFAULT_ISAAC_SIMULATOR_VERSION,
    ISAAC_RUNTIME_DEFAULTS_BY_VERSION,
    canonical_clock_sync_trace_check_json,
    canonical_dock_contact_impulse_trace_check_json,
    canonical_dock_takeoff_loop_trace_check_json,
    canonical_isaac_headless_launch_plan_json,
    canonical_isaac_headless_preflight_json,
    canonical_isaac_headless_smoke_trace_check_json,
    canonical_jackal_route_trace_check_json,
    canonical_nav2_smoke_trace_check_json,
    canonical_rayfronts_baseline_run_check_json,
    canonical_rayfronts_baseline_smoke_trace_check_json,
    canonical_runtime_api_sample_check_json,
    canonical_runtime_barrier_trace_check_json,
    canonical_runtime_fault_smoke_check_json,
    canonical_runtime_interface_bundle_check_json,
    canonical_ugv_topic_trace_check_json,
    canonical_uav_smoke_trace_check_json,
    canonical_ugv_precision_trace_check_json,
    build_isaac_headless_preflight_report,
    build_isaac_headless_launch_plan,
    build_rayfronts_baseline_contract_smoke_records,
    check_clock_sync_trace,
    check_dock_contact_impulse_trace,
    check_dock_takeoff_loop_trace,
    check_isaac_headless_smoke_trace,
    check_jackal_route_trace,
    check_nav2_smoke_trace,
    check_rayfronts_baseline_smoke_trace,
    check_runtime_api_sample,
    check_runtime_barrier_trace,
    check_runtime_fault_artifacts,
    check_runtime_interface_bundle,
    check_ugv_topic_trace,
    check_uav_smoke_trace,
    check_ugv_precision_trace,
    validate_rayfronts_baseline_run_artifacts,
)

LOGGER = logging.getLogger("airground")


def _config_paths(values: Sequence[str] | None) -> tuple[Path, ...]:
    return tuple(Path(value) for value in values or ())


def _write_json(value: object) -> None:
    sys.stdout.write(
        json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
        + "\n"
    )


def _read_jsonl_records(path: Path) -> list[dict[str, object]]:
    resolved = Path(path).expanduser().resolve(strict=True)
    records: list[dict[str, object]] = []
    for line_number, line in enumerate(resolved.read_text(encoding="utf-8").splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            continue
        value = json.loads(stripped)
        if not isinstance(value, dict):
            raise ValueError(f"JSONL record {line_number} must be an object")
        records.append(value)
    return records


def _read_string_mapping(path: Path) -> dict[str, str]:
    resolved = Path(path).expanduser().resolve(strict=True)
    value = json.loads(resolved.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON mapping file must contain an object: {resolved}")
    return {str(key): str(child) for key, child in value.items()}


def _validate_config(args: argparse.Namespace) -> int:
    config = load_config(_config_paths(args.config))
    if args.output == "canonical-json":
        sys.stdout.write(canonical_config_json(config))
    else:
        _write_json(
            {
                "schema_version": config.schema_version,
                "status": "ok",
            }
        )
    return 0


def _write_schema(_: argparse.Namespace) -> int:
    sys.stdout.write(canonical_schema_json())
    return 0


def _doctor(args: argparse.Namespace) -> int:
    config = load_config(_config_paths(args.config))
    packages = {
        name: importlib.metadata.version(name)
        for name in (
            "gymnasium",
            "mcap",
            "numpy",
            "pettingzoo",
            "pydantic",
            "pyarrow",
            "PyYAML",
        )
    }
    _write_json(
        {
            "config_schema_version": config.schema_version,
            "dependency_versions": packages,
            "python": platform.python_version(),
            "scope": "benchmark_core_tools",
            "status": "ok",
        }
    )
    return 0


def _asset_manifest(args: argparse.Namespace) -> AssetManifest:
    return load_asset_manifest(
        Path(args.manifest) if args.manifest else None,
        simulator_version=getattr(args, "simulator_version", DEFAULT_ASSET_SIMULATOR_VERSION),
    )


def _asset_source_root(args: argparse.Namespace) -> Path | None:
    value = args.source_root or os.environ.get("ISAAC_ASSET_ROOT")
    if not value:
        return None
    source_root = Path(value).expanduser().resolve(strict=True)
    if not source_root.is_dir():
        raise ValueError(f"asset source root is not a directory: {source_root}")
    return source_root


def _asset_fetch(args: argparse.Namespace) -> int:
    results = fetch_assets(
        _asset_manifest(args),
        Path(args.cache),
        asset_ids=args.asset,
        source_root=_asset_source_root(args),
        offline=args.offline,
    )
    sys.stdout.write(results_json(results))
    return 0


def _asset_check(args: argparse.Namespace) -> int:
    results = check_assets(_asset_manifest(args), Path(args.cache))
    sys.stdout.write(results_json(results))
    return 0


def _asset_root(args: argparse.Namespace) -> int:
    manifest = _asset_manifest(args)
    source_root = _asset_source_root(args)
    _write_json(
        {
            "kind": "local" if source_root is not None else "https",
            "root": str(source_root) if source_root is not None else manifest.source_root_url,
            "simulator_version": manifest.simulator_version,
        }
    )
    return 0


def _asset_manifest_summary(args: argparse.Namespace) -> int:
    manifest = _asset_manifest(args)
    _write_json(
        {
            "asset_count": len(manifest.assets),
            "file_count": sum(len(asset.files) for asset in manifest.assets),
            "schema_version": manifest.schema_version,
            "sha256": asset_manifest_sha256(manifest),
            "simulator": manifest.simulator,
            "simulator_version": manifest.simulator_version,
            "total_size_bytes": sum(
                asset_file.size_bytes
                for asset in manifest.assets
                for asset_file in asset.files
            ),
        }
    )
    return 0


def _episode_validate(args: argparse.Namespace) -> int:
    manifest = load_episode_manifest(Path(args.manifest) if args.manifest else None)
    if args.output == "canonical-json":
        sys.stdout.write(canonical_episode_manifest_json(manifest))
    else:
        _write_json(
            {
                "catalog_id": manifest.catalog_id,
                "difficulty_version": manifest.difficulty_version,
                "episode_count": len(manifest.episodes),
                "expected_total": manifest.expected_counts.total,
                "public": manifest.public,
                "release_channel": manifest.release_channel,
                "schema_version": manifest.schema_version,
                "sha256": episode_manifest_sha256(manifest),
                "split": manifest.split,
                "status": manifest.status,
                "task_counts": manifest.task_counts,
            }
        )
    return 0


def _episode_schema(_: argparse.Namespace) -> int:
    sys.stdout.write(canonical_episode_schema_json())
    return 0


def _episode_apply_timeouts(args: argparse.Namespace) -> int:
    manifest = load_episode_manifest(Path(args.manifest))
    oracle_times = _load_oracle_times(Path(args.oracle_times))
    updated = apply_oracle_timeouts(manifest, oracle_times)
    output = canonical_episode_manifest_json(updated)
    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
    else:
        sys.stdout.write(output)
    return 0


def _episode_hidden_summary(args: argparse.Namespace) -> int:
    manifest = load_episode_manifest(Path(args.manifest))
    metadata = hidden_release_metadata(manifest, _load_manifest_salt(args))
    output = json.dumps(
        metadata,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ) + "\n"
    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
    else:
        sys.stdout.write(output)
    return 0


def _episode_generate_from_candidates(args: argparse.Namespace) -> int:
    pool = load_candidate_pool(Path(args.candidates))
    exclude_manifests = tuple(
        load_episode_manifest(Path(path)) for path in (args.exclude_manifest or ())
    )
    manifest = build_manifest_from_candidates(
        pool,
        split=args.split,
        exclude_manifests=exclude_manifests,
        seed_base=args.seed_base,
        status=args.status,
        use_oracle_timeouts=args.use_oracle_timeouts,
    )
    output = canonical_episode_manifest_json(manifest)
    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
    else:
        sys.stdout.write(output)
    return 0


def _episode_difficulty_metadata(args: argparse.Namespace) -> int:
    pool = load_candidate_pool(Path(args.candidates))
    metadata = difficulty_metadata_from_candidates(pool)
    if args.validate_labels:
        validate_candidate_labels_against_metadata(metadata)
    output = canonical_difficulty_metadata_json(metadata)
    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
    else:
        sys.stdout.write(output)
    return 0


def _episode_audit_difficulty(args: argparse.Namespace) -> int:
    pool = load_candidate_pool(Path(args.candidates))
    metadata = load_difficulty_metadata(Path(args.metadata))
    report = audit_difficulty_metadata(pool, metadata)
    output = canonical_difficulty_metadata_audit_json(report)
    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
    else:
        sys.stdout.write(output)
    return 0 if report.status == "ok" else 2


def _episode_audit_candidates(args: argparse.Namespace) -> int:
    pool = load_candidate_pool(Path(args.candidates))
    report = audit_candidate_pool(
        pool,
        require_oracle=args.require_oracle,
        max_issues=args.max_issues,
    )
    output = canonical_candidate_pool_audit_json(report)
    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
    else:
        sys.stdout.write(output)
    return 0 if report.status == "ok" else 2


def _episode_attach_oracle(args: argparse.Namespace) -> int:
    pool = load_candidate_pool(Path(args.candidates))
    records = load_candidate_oracle_evidence(Path(args.oracle_evidence))
    updated = attach_oracle_evidence_to_candidate_pool(
        pool,
        records,
        require_all=args.require_all,
        allow_extra=args.allow_extra,
    )
    output = canonical_candidate_pool_json(updated)
    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
    else:
        sys.stdout.write(output)
    return 0


def _episode_grid_oracle_estimate(args: argparse.Namespace) -> int:
    pool = load_candidate_pool(Path(args.candidates))
    target_manifest = load_target_annotations(Path(args.targets))
    bundle = estimate_candidate_grid_oracle_evidence(
        pool,
        target_manifest,
        source=args.source,
        uav_speed_mps=args.uav_speed,
        ugv_speed_mps=args.ugv_speed,
        detection_overhead_s_per_target=args.detection_overhead_per_target,
        confirmation_overhead_s_per_target=args.confirmation_overhead_per_target,
    )
    output = canonical_candidate_oracle_evidence_json(bundle)
    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
    else:
        sys.stdout.write(output)
    return 0


def _episode_build_candidates(args: argparse.Namespace) -> int:
    paired_starts = load_paired_start_candidates(Path(args.paired_starts))
    target_manifest = load_target_annotations(Path(args.targets))
    visibility_report = _load_visibility_occlusion_report(Path(args.visibility_occlusion))
    metadata = load_traversability_metadata(Path(args.metadata))
    grid = load_traversability_grid(Path(args.npz), metadata)
    pool = build_candidate_pool_from_artifacts(
        paired_starts,
        target_manifest,
        visibility_report,
        grid,
        ground_truth={
            "traversability": args.gt_traversability,
            "targets": args.gt_targets,
            "confirmation_regions": args.gt_confirmation_regions,
            "checksum_sha256": args.gt_checksum,
        },
        config=CandidatePoolBuildConfig(
            difficulty_version=args.difficulty_version,
            source=args.source,
            max_single_target_candidates=args.max_single,
            max_unordered_multi_target_candidates=args.max_unordered,
            max_sequential_target_candidates=args.max_sequential,
            multi_target_size=args.multi_target_size,
            min_start_confirmation_distance_m=args.min_start_confirmation_distance,
            seed_material=args.seed_material,
        ),
    )
    output = canonical_candidate_pool_json(pool)
    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
    else:
        sys.stdout.write(output)
    return 0


def _episode_paired_starts(args: argparse.Namespace) -> int:
    target_manifest = load_target_annotations(Path(args.targets))
    metadata = load_traversability_metadata(Path(args.metadata))
    grid = load_traversability_grid(Path(args.npz), metadata)
    ceiling_height = None
    if args.ceiling_npz:
        with np.load(Path(args.ceiling_npz), allow_pickle=False) as data:
            if args.ceiling_key not in data:
                raise EpisodeGenerationError(
                    f"ceiling key {args.ceiling_key!r} not found in {args.ceiling_npz}"
                )
            ceiling_height = data[args.ceiling_key]
    candidates = build_paired_start_candidates(
        grid,
        target_manifest.confirmation_regions,
        config=PairedStartConfig(
            uav_parent_frame=args.uav_parent_frame,
            uav_x_m=args.uav_x,
            uav_y_m=args.uav_y,
            uav_z_m=args.uav_z,
            uav_yaw_rad=args.uav_yaw,
            min_takeoff_clearance_m=args.min_takeoff_clearance,
            exclude_confirmation_radius_m=args.exclude_confirmation_radius,
            max_starts_per_component=args.max_starts_per_component,
        ),
        ceiling_height=ceiling_height,
        seed_material=args.seed_material,
    )
    output = canonical_paired_start_candidates_json(candidates)
    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
    else:
        sys.stdout.write(output)
    return 0


def _episode_audit_ground_truth(args: argparse.Namespace) -> int:
    manifest = load_episode_manifest(Path(args.manifest))
    targets = load_target_annotations(Path(args.targets))
    metadata = load_traversability_metadata(Path(args.metadata))
    report = audit_episode_manifest_against_ground_truth(
        manifest,
        targets,
        metadata,
        Path(args.npz),
        reject_immediate_confirmation=not args.allow_immediate_confirmation,
    )
    output = canonical_episode_audit_report_json(report)
    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
    else:
        sys.stdout.write(output)
    return 0 if report.status == "ok" else 2


def _load_visibility_occlusion_report(path: Path) -> VisibilityOcclusionReport:
    resolved = Path(path).expanduser().resolve(strict=True)
    value = yaml.safe_load(resolved.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise GroundTruthError(f"visibility/occlusion report must be a YAML/JSON mapping: {resolved}")
    return VisibilityOcclusionReport.model_validate(dict(value))


def _episode_release_pair(args: argparse.Namespace) -> int:
    pool = load_candidate_pool(Path(args.candidates))
    salt = _load_manifest_salt(args)
    public_manifest, hidden_manifest, difficulty_metadata, report = (
        build_release_pair_from_candidates(
            pool,
            hidden_salt=salt,
            public_seed_base=args.public_seed_base,
            hidden_seed_base=args.hidden_seed_base,
            use_oracle_timeouts=args.use_oracle_timeouts,
        )
    )
    output_dir = Path(args.output_dir).expanduser().resolve()
    _prepare_release_output_dir(output_dir, overwrite=args.overwrite)
    (output_dir / "public_episodes.json").write_text(
        canonical_episode_manifest_json(public_manifest),
        encoding="utf-8",
    )
    (output_dir / "hidden_episodes.private.json").write_text(
        canonical_episode_manifest_json(hidden_manifest),
        encoding="utf-8",
    )
    (output_dir / "difficulty_metadata.json").write_text(
        canonical_difficulty_metadata_json(difficulty_metadata),
        encoding="utf-8",
    )
    (output_dir / "hidden_summary.json").write_text(
        json.dumps(
            hidden_release_metadata(hidden_manifest, salt),
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n",
        encoding="utf-8",
    )
    report_json = canonical_release_pair_report_json(report)
    (output_dir / "release_pair_report.json").write_text(report_json, encoding="utf-8")
    sys.stdout.write(report_json)
    return 0


def _prepare_release_output_dir(output_dir: Path, *, overwrite: bool) -> None:
    if output_dir.exists():
        if not output_dir.is_dir():
            raise EpisodeGenerationError(f"release output path is not a directory: {output_dir}")
        if any(output_dir.iterdir()) and not overwrite:
            raise EpisodeGenerationError(
                f"release output directory is not empty: {output_dir}; use --overwrite"
            )
    output_dir.mkdir(parents=True, exist_ok=True)


def _load_manifest_salt(args: argparse.Namespace) -> bytes:
    sources = [
        args.salt is not None,
        args.salt_file is not None,
        args.salt_env is not None,
    ]
    if sum(sources) != 1:
        raise EpisodeManifestError("provide exactly one of --salt, --salt-file, or --salt-env")
    if args.salt is not None:
        salt = str(args.salt).encode("utf-8")
    elif args.salt_file is not None:
        salt = Path(args.salt_file).expanduser().resolve(strict=True).read_bytes().strip()
    else:
        value = os.environ.get(str(args.salt_env))
        if value is None:
            raise EpisodeManifestError(f"salt environment variable is unset: {args.salt_env}")
        salt = value.encode("utf-8")
    if not salt:
        raise EpisodeManifestError("manifest checksum salt must be non-empty")
    return salt


def _load_oracle_times(path: Path) -> dict[str, float]:
    resolved = Path(path).expanduser().resolve(strict=True)
    value = yaml.safe_load(resolved.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise EpisodeManifestError("oracle times file must be a mapping")
    result: dict[str, float] = {}
    for episode_id, oracle_time_s in value.items():
        if not isinstance(episode_id, str):
            raise EpisodeManifestError("oracle time episode ids must be strings")
        if not isinstance(oracle_time_s, int | float):
            raise EpisodeManifestError(
                f"oracle time for {episode_id!r} must be numeric seconds"
            )
        result[episode_id] = float(oracle_time_s)
    return result


def _evaluate(args: argparse.Namespace) -> int:
    if args.check_artifacts:
        if not args.run:
            raise ValueError("--check-artifacts requires --run")
        report = validate_run_metrics_artifacts(
            Path(args.run),
            require_success=args.require_success,
        )
        output = canonical_run_metrics_validation_report_json(report)
        if args.output_dir:
            output_dir = Path(args.output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)
            (output_dir / "metrics_validation_report.json").write_text(
                output,
                encoding="utf-8",
            )
        sys.stdout.write(output)
        return 0 if report["status"] == "ok" else 2
    if args.events:
        events_path = Path(args.events)
    else:
        run_dir = Path(args.run).expanduser().resolve(strict=True)
        if not run_dir.is_dir():
            raise ValueError(f"run path is not a directory: {run_dir}")
        events_path = run_dir / "events.jsonl"
    output_dir = Path(args.output_dir) if args.output_dir else None
    summary = evaluate_events_file(events_path, output_dir)
    sys.stdout.write(canonical_summary_json(summary))
    return 0


def _release_audit_pair(args: argparse.Namespace) -> int:
    report = audit_release_pair_directory(Path(args.release_dir))
    output = canonical_release_audit_report_json(report)
    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
    else:
        sys.stdout.write(output)
    return 0 if report.status == "ok" else 2


def _tasks_build_catalog(args: argparse.Namespace) -> int:
    manifest = (
        load_target_annotations(Path(args.targets))
        if args.targets
        else load_default_target_annotations()
    )
    catalog = build_task_catalog(
        manifest,
        catalog_id=args.catalog_id,
        source_annotation_path=args.targets,
    )
    output = canonical_task_catalog_json(catalog)
    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
    else:
        sys.stdout.write(output)
    if args.diagnostics_output:
        Path(args.diagnostics_output).write_text(
            json.dumps(catalog_diagnostics(catalog), ensure_ascii=True, indent=2, sort_keys=True)
            + "\n",
            encoding="utf-8",
        )
    return 0


def _metrics_ugv_progress(args: argparse.Namespace) -> int:
    manifest = load_target_annotations(Path(args.targets))
    catalog = load_task_catalog(Path(args.catalog))
    entry = find_catalog_entry(catalog, args.task_id)
    if entry.status == "blocked":
        raise UgvProgressError(
            f"task {entry.task_id} is blocked (no reachable goal instances)"
        )
    grid = None
    if args.traversability_npz or args.traversability_metadata:
        if not (args.traversability_npz and args.traversability_metadata):
            raise UgvProgressError(
                "--traversability-npz and --traversability-metadata must be provided together"
            )
        metadata = load_traversability_metadata(Path(args.traversability_metadata))
        grid = load_traversability_grid(Path(args.traversability_npz), metadata)
    start_xy_m = None
    if args.start_x is not None or args.start_y is not None:
        if args.start_x is None or args.start_y is None:
            raise UgvProgressError("--start-x and --start-y must be provided together")
        start_xy_m = (float(args.start_x), float(args.start_y))
    arrival_regions = None
    if args.arrival_regions or args.arrival_region_index:
        if not (args.arrival_regions and args.arrival_region_index):
            raise UgvProgressError(
                "--arrival-regions and --arrival-region-index must be provided together"
            )
        if grid is None:
            raise UgvProgressError(
                "--arrival-regions requires --traversability-npz/--traversability-metadata "
                "to locate the raster in the map frame"
            )
        index_payload = json.loads(Path(args.arrival_region_index).read_text(encoding="utf-8"))
        label_by_region_id = {
            str(row["region_id"]): int(row["label"]) for row in index_payload.get("regions", [])
        }
        arrival_regions = ArrivalRegionContext(
            labels=load_arrival_region_labels(Path(args.arrival_regions)),
            origin_xy_m=(grid.metadata.origin.x_m, grid.metadata.origin.y_m),
            resolution_m=float(grid.metadata.resolution_m),
            label_by_region_id=label_by_region_id,
        )
    report = compute_ugv_progress(
        pose_samples=load_ugv_pose_samples(Path(args.trajectory)),
        manifest=manifest,
        goal_instance_ids=entry.goal_instance_ids,
        budget_s=float(args.budget_s),
        traversability_grid=grid,
        query_classes=entry.query_classes,
        start_xy_m=start_xy_m,
        task_id=entry.task_id,
        task_family=entry.family,
        episode_id=args.episode_id,
        reach_tolerance_m=float(args.reach_tolerance_m),
        window_start_s=float(args.window_start_s),
        arrival_regions=arrival_regions,
    )
    output = canonical_ugv_progress_json(report)
    if args.output_dir:
        output_dir = Path(args.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "ugv_progress_report.json").write_text(output, encoding="utf-8")
        (output_dir / "ugv_progress_report.sha256").write_text(
            ugv_progress_sha256(report) + "\n",
            encoding="utf-8",
        )
    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
    else:
        sys.stdout.write(output)
    return 0


def _metrics_aggregate_progress(args: argparse.Namespace) -> int:
    reports = [load_ugv_progress_report(Path(path)) for path in args.report]
    aggregate = aggregate_ugv_progress(reports)
    output = canonical_ugv_progress_aggregate_json(aggregate)
    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
    else:
        sys.stdout.write(output)
    return 0


def _release_checklist(args: argparse.Namespace) -> int:
    strict_release = bool(args.strict_release)
    report = build_release_checklist(
        release_dir=Path(args.release_dir),
        repo_root=Path(args.repo_root),
        run_dir=Path(args.run_dir) if args.run_dir else None,
        release_manifest=Path(args.release_manifest) if args.release_manifest else None,
        gt_artifacts=parse_named_paths(tuple(args.gt_artifact or ())),
        fresh_clone_report=(
            Path(args.fresh_clone_report) if args.fresh_clone_report else None
        ),
        fresh_clone_plan=Path(args.fresh_clone_plan) if args.fresh_clone_plan else None,
        fault_report=Path(args.fault_report) if args.fault_report else None,
        performance_report=(
            Path(args.performance_report) if args.performance_report else None
        ),
        reset_state_report=(
            Path(args.reset_state_report) if args.reset_state_report else None
        ),
        reset_state_run_dir=(
            Path(args.reset_state_run_dir) if args.reset_state_run_dir else None
        ),
        soft_reset_full_action_report=(
            Path(args.soft_reset_full_action_report)
            if args.soft_reset_full_action_report
            else None
        ),
        strict_clean=args.strict_clean or strict_release,
        fail_on_warn=args.fail_on_warn or strict_release,
        require_metrics_evidence=args.require_metrics_evidence or strict_release,
        require_gt_artifacts=args.require_gt_artifacts or strict_release,
        require_simulator_version=(
            args.require_simulator_version
            or (DEFAULT_ISAAC_SIMULATOR_VERSION if strict_release else None)
        ),
        require_release_id=args.require_release_id,
        require_fresh_clone=args.require_fresh_clone or strict_release,
        require_fault_report=args.require_fault_report or strict_release,
        require_performance_report=args.require_performance_report or strict_release,
        require_reset_state_report=args.require_reset_state_report or strict_release,
        require_soft_reset_full_action_report=(
            args.require_soft_reset_full_action_report or strict_release
        ),
        require_target_review=args.require_target_review or strict_release,
    )
    output = canonical_release_checklist_report_json(report)
    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
    else:
        sys.stdout.write(output)
    return 0 if report.status == "ok" else 2


def _release_manifest(args: argparse.Namespace) -> int:
    report = build_release_manifest(
        release_dir=Path(args.release_dir),
        repo_root=Path(args.repo_root),
        release_id=args.release_id,
        asset_manifest_path=Path(args.asset_manifest) if args.asset_manifest else None,
        asset_simulator_version=args.simulator_version,
        gt_artifacts=parse_named_paths(tuple(args.gt_artifact or ())),
        container_tags=tuple(args.container_tag or ()),
        run_dir=Path(args.run_dir) if args.run_dir else None,
    )
    output = canonical_release_manifest_report_json(report)
    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
    else:
        sys.stdout.write(output)
    return 0 if report.status == "ok" else 2


def _release_performance_report(args: argparse.Namespace) -> int:
    report = build_performance_report(
        Path(args.run_dir),
        Path(args.resource_trace),
        min_episode_count=args.min_episodes,
        min_resource_samples=args.min_resource_samples,
        max_system_memory_growth_mb=args.max_system_memory_growth_mb,
        max_gpu_memory_fraction=args.max_gpu_memory_fraction,
        max_gpu_memory_growth_mb=args.max_gpu_memory_growth_mb,
        max_gpu_memory_used_mb=args.max_gpu_memory_used_mb,
        require_real_backend=not args.allow_contract_backend,
        require_success=not args.allow_failed_episodes,
        require_energy_evidence=not args.allow_missing_energy_evidence,
    )
    output = canonical_performance_report_json(report)
    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
    else:
        sys.stdout.write(output)
    return 0 if report["status"] == "ok" else 2


def _release_repro_plan(args: argparse.Namespace) -> int:
    plan = build_fresh_clone_repro_plan(
        repo_url=args.repo_url,
        target_dir=args.target_dir,
        include_real_episode=not args.contract_only,
        real_episode_manifest=args.real_episode_manifest,
        real_episode_id=args.real_episode_id,
        real_episode_output_dir=args.real_episode_output_dir,
        real_episode_repo_root=args.real_episode_repo_root,
        real_episode_container=args.real_episode_container,
    )
    output = canonical_fresh_clone_repro_plan_json(plan)
    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
    else:
        sys.stdout.write(output)
    return 0


def _release_repro_report(args: argparse.Namespace) -> int:
    plan = FreshCloneReproPlan.model_validate_json(
        Path(args.plan).expanduser().resolve(strict=True).read_text(encoding="utf-8")
    )
    results = load_fresh_clone_step_results_json(
        Path(args.results).expanduser().resolve(strict=True).read_text(encoding="utf-8")
    )
    if args.artifact_root:
        results = attach_fresh_clone_artifact_checksums(
            results,
            Path(args.artifact_root),
        )
    repo_commit = args.repo_commit
    if repo_commit is None:
        repo_root = args.repo_root or args.artifact_root
        if repo_root:
            repo_commit = _git_head_commit(Path(repo_root), required=bool(args.repo_root))
    report = build_fresh_clone_repro_report(
        plan=plan,
        results=results,
        repo_commit=repo_commit,
    )
    output = canonical_fresh_clone_repro_report_json(report)
    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
    else:
        sys.stdout.write(output)
    return 0 if report.status == "ok" else 2


def _git_head_commit(repo_root: Path, *, required: bool) -> str | None:
    """Return HEAD commit for a git checkout, or ``None`` when optional."""
    root = repo_root.expanduser().resolve()
    try:
        result = subprocess.run(
            ("git", "-C", str(root), "rev-parse", "HEAD"),
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        if required:
            raise
        return None
    commit = result.stdout.strip()
    if len(commit) != 40 or set(commit) - set("0123456789abcdef"):
        if required:
            raise ValueError(f"git HEAD is not a full lowercase SHA-1 commit: {commit}")
        return None
    return commit


def _reset_plan(args: argparse.Namespace) -> int:
    sys.stdout.write(canonical_reset_plan_json(build_reset_plan(args.mode)))
    return 0


def _reset_check_trace(args: argparse.Namespace) -> int:
    plan = build_reset_plan(args.mode)
    trace_path = Path(args.trace)
    trace_value = _load_reset_trace_mapping(trace_path)
    report = validate_reset_trace(
        plan,
        _reset_trace_steps_from_value(trace_value),
        allow_extra_steps=args.allow_extra_steps,
    )
    output = report.as_dict()
    event_status_report = validate_reset_trace_event_status(plan, trace_value).as_dict()
    output["event_status_surface"] = event_status_report
    if event_status_report["status"] != "ok":
        output["status"] = "failed"
    if args.require_sensor_payloads:
        payload_report = _load_reset_sensor_payload_report(trace_path)
        output["sensor_payloads_required"] = True
        output["sensor_payload_surface"] = payload_report
        if payload_report["status"] != "ok":
            output["status"] = "failed"
    if args.require_adapter_state_clear:
        adapter_report = _load_reset_adapter_state_clear_report(trace_path)
        output["adapter_state_clear_required"] = True
        output["adapter_state_clear_surface"] = adapter_report
        if adapter_report["status"] != "ok":
            output["status"] = "failed"
    if args.require_ros_queue_clear:
        ros_queue_report = _load_reset_ros_queue_clear_report(trace_path)
        output["ros_queue_clear_required"] = True
        output["ros_queue_clear_surface"] = ros_queue_report
        if ros_queue_report["status"] != "ok":
            output["status"] = "failed"
    if args.require_airstack_trajectory_clear:
        trajectory_report = _load_reset_airstack_trajectory_clear_report(trace_path)
        output["airstack_trajectory_clear_required"] = True
        output["airstack_trajectory_clear_surface"] = trajectory_report
        if trajectory_report["status"] != "ok":
            output["status"] = "failed"
    if args.require_nav2_cancel:
        nav2_report = _load_reset_nav2_cancel_report(trace_path)
        output["nav2_cancel_required"] = True
        output["nav2_cancel_surface"] = nav2_report
        if nav2_report["status"] != "ok":
            output["status"] = "failed"
    if args.require_uav_px4_cancel:
        uav_report = _load_reset_uav_px4_cancel_report(trace_path)
        output["uav_px4_cancel_required"] = True
        output["uav_px4_cancel_surface"] = uav_report
        if uav_report["status"] != "ok":
            output["status"] = "failed"
    if args.require_control_hold:
        control_report = _load_reset_control_hold_report(trace_path)
        output["control_hold_required"] = True
        output["control_hold_surface"] = control_report
        if control_report["status"] != "ok":
            output["status"] = "failed"
    if args.require_rayfronts_reset:
        rayfronts_report = _load_reset_rayfronts_reset_report(trace_path)
        output["rayfronts_reset_required"] = True
        output["rayfronts_reset_surface"] = rayfronts_report
        if rayfronts_report["status"] != "ok":
            output["status"] = "failed"
    if args.require_stable_health_handshake:
        stable_health_report = _load_reset_stable_health_handshake_report(trace_path)
        output["stable_health_handshake_required"] = True
        output["stable_health_handshake_surface"] = stable_health_report
        if stable_health_report["status"] != "ok":
            output["status"] = "failed"
    if args.require_healthy_components:
        output["healthy_components_required"] = True
        if not args.health:
            output["component_health_surface"] = {
                "failed_components": [],
                "reason": "missing_health_artifact",
                "restart_components": [],
                "retry_episode": False,
                "status": "failed",
            }
            output["status"] = "failed"
        else:
            health_decision = decide_reset_recovery(
                _load_reset_health(Path(args.health)),
                previous_infra_retries=args.previous_infra_retries,
                max_infra_retries=args.max_infra_retries,
            )
            health_output = health_decision.as_dict()
            output["component_health_surface"] = health_output
            if health_decision.status != "ready":
                output["status"] = "failed"
    _write_json(output)
    return 0 if output["status"] == "ok" else 2


def _reset_check_run(args: argparse.Namespace) -> int:
    report = validate_reset_run_artifacts(
        Path(args.run_dir),
        mode=args.mode,
        expected_episode_count=args.expected_episodes,
        require_sensor_payloads=args.require_sensor_payloads,
        require_healthy_components=not args.no_require_healthy_components,
        require_reset_support=args.require_reset_support,
        require_stable_health_handshake=args.require_stable_health_handshake,
        require_airstack_trajectory_clear=args.require_airstack_trajectory_clear,
        allow_extra_steps=args.allow_extra_steps,
    )
    output = canonical_reset_run_validation_report_json(report)
    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
    else:
        sys.stdout.write(output)
    return 0 if report["status"] == "ok" else 2



def _reset_audit_state_run(args: argparse.Namespace) -> int:
    report = validate_reset_state_run_artifacts(
        Path(args.run_dir),
        mode=args.mode,
        expected_episode_count=args.expected_episodes,
        require_reset_support=not args.no_require_reset_support,
        require_reset_run_validation=not args.no_require_reset_run_validation,
        require_mission_success=not args.allow_mission_failures,
        require_single_attempt=not args.allow_multi_attempt,
    )
    output = canonical_reset_run_validation_report_json(report)
    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
    else:
        sys.stdout.write(output)
    return 0 if report["status"] == "ok" else 2

def _reset_check_hard_restart_run(args: argparse.Namespace) -> int:
    report = validate_hard_restart_full_health_artifact(
        Path(args.run_dir),
        require_clock_epoch_reset=args.require_clock_epoch_reset,
    )
    output = canonical_reset_run_validation_report_json(report)
    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
    else:
        sys.stdout.write(output)
    return 0 if report["status"] == "ok" else 2


def _reset_check_soft_full_action_run(args: argparse.Namespace) -> int:
    report = validate_soft_reset_full_action_artifact(Path(args.run_dir))
    output = canonical_reset_run_validation_report_json(report)
    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
    else:
        sys.stdout.write(output)
    return 0 if report["status"] == "ok" else 2


def _reset_check_recovery_run(args: argparse.Namespace) -> int:
    report = validate_reset_recovery_artifact(
        Path(args.run_dir),
        require_clock_epoch_reset=args.require_clock_epoch_reset,
    )
    output = canonical_reset_run_validation_report_json(report)
    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
    else:
        sys.stdout.write(output)
    return 0 if report["status"] == "ok" else 2


def _reset_check_production_orchestrator(args: argparse.Namespace) -> int:
    report = validate_production_reset_orchestrator_artifacts(
        soft_full_action_run_dir=Path(args.soft_full_action_run_dir),
        recovery_run_dir=Path(args.recovery_run_dir),
        hard_restart_run_dir=Path(args.hard_restart_run_dir),
        reset_state_run_dir=Path(args.reset_state_run_dir),
        dock_reset_pose_report=Path(args.dock_reset_pose_report),
        dock_reset_sequence_report=Path(args.dock_reset_sequence_report),
        expected_episode_count=args.expected_episodes,
        require_clock_epoch_reset=args.require_clock_epoch_reset,
    )
    output = canonical_reset_run_validation_report_json(report)
    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
    else:
        sys.stdout.write(output)
    return 0 if report["status"] == "ok" else 2


def _reset_run_hard_restart_full_health(args: argparse.Namespace) -> int:
    command = [
        str(Path(args.python).expanduser()),
        str(Path(args.runner).expanduser()),
        "--artifact-dir",
        str(Path(args.artifact_dir).expanduser()),
        "--container",
        args.container,
        "--airground-cli",
        args.airground_cli,
        "--docker-health-timeout-s",
        str(args.docker_health_timeout_s),
        "--docker-health-poll-s",
        str(args.docker_health_poll_s),
        "--post-restart-settle-s",
        str(args.post_restart_settle_s),
        "--clock-sample-timeout-s",
        str(args.clock_sample_timeout_s),
        "--pre-restart-clock-min-s",
        str(args.pre_restart_clock_min_s),
        "--pre-restart-clock-wait-timeout-s",
        str(args.pre_restart_clock_wait_timeout_s),
        "--post-restart-clock-max-s",
        str(args.post_restart_clock_max_s),
        "--post-restart-clock-delta-s",
        str(args.post_restart_clock_delta_s),
        "--post-restart-clock-wait-timeout-s",
        str(args.post_restart_clock_wait_timeout_s),
        "--rayfronts-duration-s",
        str(args.rayfronts_duration_s),
        "--nav2-tf-startup-timeout-s",
        str(args.nav2_tf_startup_timeout_s),
        "--nav2-hold-after-success-s",
        str(args.nav2_hold_after_success_s),
        "--postflight-wait-s",
        str(args.postflight_wait_s),
    ]
    if args.require_clock_epoch_reset:
        command.append("--require-clock-epoch-reset")
    if args.container_artifact_dir:
        command.extend(["--container-artifact-dir", args.container_artifact_dir])
    if args.dry_run:
        _write_json({"command": command, "status": "dry_run"})
        return 0

    completed = subprocess.run(
        command,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    report: dict[str, Any] = {
        "command": command,
        "returncode": completed.returncode,
        "runner_stderr_tail": completed.stderr[-4000:],
        "runner_stdout_tail": completed.stdout[-4000:],
        "status": "ok" if completed.returncode == 0 else "failed",
    }
    if completed.returncode == 0:
        artifact_report = validate_hard_restart_full_health_artifact(
            Path(args.artifact_dir),
            require_clock_epoch_reset=args.require_clock_epoch_reset,
        )
        report["artifact_gate"] = artifact_report
        if artifact_report["status"] != "ok":
            report["status"] = "failed"
    if args.output:
        Path(args.output).write_text(
            json.dumps(report, ensure_ascii=True, sort_keys=True, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )
    else:
        _write_json(report)
    return 0 if report["status"] == "ok" else 2


def _reset_run_recovery(args: argparse.Namespace) -> int:
    command = [
        str(Path(args.python).expanduser()),
        str(Path(args.runner).expanduser()),
        "--artifact-dir",
        str(Path(args.artifact_dir).expanduser()),
        "--health",
        str(Path(args.health).expanduser()),
        "--container",
        args.container,
        "--airground-cli",
        args.airground_cli,
        "--previous-infra-retries",
        str(args.previous_infra_retries),
        "--max-infra-retries",
        str(args.max_infra_retries),
        "--soft-runner",
        args.soft_runner,
        "--hard-runner",
        args.hard_runner,
        "--rayfronts-duration-s",
        str(args.rayfronts_duration_s),
        "--rayfronts-ready-timeout-s",
        str(args.rayfronts_ready_timeout_s),
        "--nav2-tf-startup-timeout-s",
        str(args.nav2_tf_startup_timeout_s),
        "--nav2-hold-after-success-s",
        str(args.nav2_hold_after_success_s),
        "--nav2-ready-timeout-s",
        str(args.nav2_ready_timeout_s),
        "--reset-trace-timeout-s",
        str(args.reset_trace_timeout_s),
        "--stable-health-samples",
        str(args.stable_health_samples),
        "--stable-health-period-s",
        str(args.stable_health_period_s),
        "--stable-health-timeout-s",
        str(args.stable_health_timeout_s),
        "--docker-health-timeout-s",
        str(args.docker_health_timeout_s),
        "--docker-health-poll-s",
        str(args.docker_health_poll_s),
        "--post-restart-settle-s",
        str(args.post_restart_settle_s),
        "--postflight-wait-s",
        str(args.postflight_wait_s),
    ]
    if args.container_artifact_dir:
        command.extend(["--container-artifact-dir", args.container_artifact_dir])
    if args.require_clock_epoch_reset:
        command.append("--require-clock-epoch-reset")
    if args.dry_run:
        command.append("--dry-run")

    completed = subprocess.run(
        command,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    report: dict[str, Any] = {
        "command": command,
        "returncode": completed.returncode,
        "runner_stderr_tail": completed.stderr[-4000:],
        "runner_stdout_tail": completed.stdout[-4000:],
        "status": "ok" if completed.returncode == 0 else "failed",
    }
    if completed.returncode == 0 and not args.dry_run:
        artifact_report = validate_reset_recovery_artifact(
            Path(args.artifact_dir),
            require_clock_epoch_reset=args.require_clock_epoch_reset,
        )
        report["artifact_gate"] = artifact_report
        if artifact_report["status"] != "ok":
            report["status"] = "failed"
    if args.output:
        Path(args.output).write_text(
            json.dumps(report, ensure_ascii=True, sort_keys=True, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )
    else:
        _write_json(report)
    return 0 if report["status"] == "ok" else 2


def _reset_run_soft_full_action(args: argparse.Namespace) -> int:
    command = [
        str(Path(args.python).expanduser()),
        str(Path(args.runner).expanduser()),
        "--artifact-dir",
        str(Path(args.artifact_dir).expanduser()),
        "--container",
        args.container,
        "--airground-cli",
        args.airground_cli,
        "--rayfronts-duration-s",
        str(args.rayfronts_duration_s),
        "--rayfronts-ready-timeout-s",
        str(args.rayfronts_ready_timeout_s),
        "--nav2-tf-startup-timeout-s",
        str(args.nav2_tf_startup_timeout_s),
        "--nav2-hold-after-success-s",
        str(args.nav2_hold_after_success_s),
        "--nav2-ready-timeout-s",
        str(args.nav2_ready_timeout_s),
        "--reset-trace-timeout-s",
        str(args.reset_trace_timeout_s),
        "--stable-health-samples",
        str(args.stable_health_samples),
        "--stable-health-period-s",
        str(args.stable_health_period_s),
        "--stable-health-timeout-s",
        str(args.stable_health_timeout_s),
        "--postflight-wait-s",
        str(args.postflight_wait_s),
    ]
    if args.container_artifact_dir:
        command.extend(["--container-artifact-dir", args.container_artifact_dir])
    if args.dry_run:
        _write_json({"command": command, "status": "dry_run"})
        return 0

    completed = subprocess.run(
        command,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    report: dict[str, Any] = {
        "command": command,
        "returncode": completed.returncode,
        "runner_stderr_tail": completed.stderr[-4000:],
        "runner_stdout_tail": completed.stdout[-4000:],
        "status": "ok" if completed.returncode == 0 else "failed",
    }
    if completed.returncode == 0:
        artifact_report = validate_soft_reset_full_action_artifact(Path(args.artifact_dir))
        report["artifact_gate"] = artifact_report
        if artifact_report["status"] != "ok":
            report["status"] = "failed"
    if args.output:
        Path(args.output).write_text(
            json.dumps(report, ensure_ascii=True, sort_keys=True, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )
    else:
        _write_json(report)
    return 0 if report["status"] == "ok" else 2


def _reset_decide_recovery(args: argparse.Namespace) -> int:
    decision = decide_reset_recovery(
        _load_reset_health(Path(args.health)),
        previous_infra_retries=args.previous_infra_retries,
        max_infra_retries=args.max_infra_retries,
    )
    _write_json(decision.as_dict())
    return 0


def _faults_catalog(_: argparse.Namespace) -> int:
    sys.stdout.write(canonical_fault_catalog_json())
    return 0


def _faults_run_contract(args: argparse.Namespace) -> int:
    scenarios = (
        tuple(scenario.scenario_id for scenario in fault_scenario_catalog())
        if args.all
        else tuple(args.scenario or ())
    )
    if not scenarios:
        raise ValueError("provide --scenario or --all")
    report_objects = [
        run_contract_fault_injection(scenario, max_cycles=args.max_cycles)
        for scenario in scenarios
    ]
    reports = [report.as_dict() for report in report_objects]
    if len(reports) == 1:
        output = canonical_fault_injection_report_json(report_objects[0])
        if args.output:
            Path(args.output).write_text(output, encoding="utf-8")
        else:
            sys.stdout.write(output)
        return 0 if reports[0]["status"] == "ok" else 2

    payload = {
        "reports": reports,
        "schema_version": "1.0.0",
        "status": "ok" if all(report["status"] == "ok" for report in reports) else "failed",
    }
    output = json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":")) + "\n"
    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
    else:
        sys.stdout.write(output)
    return 0 if payload["status"] == "ok" else 2


def _smoke_check_uav(args: argparse.Namespace) -> int:
    report = check_uav_smoke_trace(
        _read_jsonl_records(Path(args.trace)),
        min_hover_s=args.min_hover_s,
        max_hover_drift_m=args.max_hover_drift_m,
        min_waypoint_x_m=args.min_waypoint_x_m,
        max_waypoint_error_m=args.max_waypoint_error_m,
    )
    output = canonical_uav_smoke_trace_check_json(report)
    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
    else:
        sys.stdout.write(output)
    return 0 if report.status == "ok" else 2


def _smoke_check_ugv_topics(args: argparse.Namespace) -> int:
    report = check_ugv_topic_trace(_read_jsonl_records(Path(args.trace)))
    output = canonical_ugv_topic_trace_check_json(report)
    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
    else:
        sys.stdout.write(output)
    return 0 if report.status == "ok" else 2


def _smoke_check_nav2(args: argparse.Namespace) -> int:
    report = check_nav2_smoke_trace(_read_jsonl_records(Path(args.trace)))
    output = canonical_nav2_smoke_trace_check_json(report)
    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
    else:
        sys.stdout.write(output)
    return 0 if report.status == "ok" else 2


def _smoke_check_dock_takeoff(args: argparse.Namespace) -> int:
    report = check_dock_takeoff_loop_trace(
        _read_jsonl_records(Path(args.trace)),
        expected_cycles=args.expected_cycles,
        min_clearance_m=args.min_clearance_m,
        require_docked_clearance=args.require_docked_clearance,
        min_docked_clearance_m=args.min_docked_clearance_m,
        require_fresh_reset=args.require_fresh_reset,
        require_pose_trace=args.require_pose_trace,
        pose_trace_root=Path(args.pose_trace_root) if args.pose_trace_root else None,
        require_reset_sequence=args.require_reset_sequence,
    )
    output = canonical_dock_takeoff_loop_trace_check_json(report)
    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
    else:
        sys.stdout.write(output)
    return 0 if report.status == "ok" else 2


def _smoke_check_dock_contact_impulse(args: argparse.Namespace) -> int:
    report = check_dock_contact_impulse_trace(
        _read_jsonl_records(Path(args.trace)),
        expected_cycles=args.expected_cycles,
        max_unexpected_collision_impulse_n_s=args.max_unexpected_collision_impulse_n_s,
    )
    output = canonical_dock_contact_impulse_trace_check_json(report)
    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
    else:
        sys.stdout.write(output)
    return 0 if report.status == "ok" else 2


def _smoke_check_jackal_routes(args: argparse.Namespace) -> int:
    report = check_jackal_route_trace(
        _read_jsonl_records(Path(args.trace)),
        expected_routes=args.expected_routes,
        max_tilt_rad=args.max_tilt_rad,
    )
    output = canonical_jackal_route_trace_check_json(report)
    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
    else:
        sys.stdout.write(output)
    return 0 if report.status == "ok" else 2


def _smoke_check_ugv_precision(args: argparse.Namespace) -> int:
    report = check_ugv_precision_trace(
        _read_jsonl_records(Path(args.trace)),
        min_static_s=args.min_static_s,
        max_static_drift_m=args.max_static_drift_m,
        min_straight_distance_m=args.min_straight_distance_m,
        max_straight_endpoint_error_m=args.max_straight_endpoint_error_m,
        max_tilt_rad=args.max_tilt_rad,
    )
    output = canonical_ugv_precision_trace_check_json(report)
    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
    else:
        sys.stdout.write(output)
    return 0 if report.status == "ok" else 2


def _smoke_check_headless_integration(args: argparse.Namespace) -> int:
    report = validate_headless_integration_artifacts(
        headless_artifact_dir=Path(args.headless_artifact_dir),
        headless_run_dir=Path(args.headless_run_dir),
        dock_trace=Path(args.dock_trace),
        jackal_trace=Path(args.jackal_trace),
        confirmation_annotations=Path(args.confirmation_annotations),
        confirmation_trace=Path(args.confirmation_trace),
        reset_recovery_run_dir=Path(args.reset_recovery_run_dir),
        simulator_version=args.simulator_version,
        expected_headless_episodes=args.expected_headless_episodes,
        headless_split=args.headless_split,
        require_headless_render=args.require_headless_render,
        require_energy_evidence=args.require_energy_evidence,
        dock_expected_cycles=args.dock_expected_cycles,
        dock_min_clearance_m=args.dock_min_clearance_m,
        dock_require_docked_clearance=not args.no_dock_require_docked_clearance,
        dock_min_docked_clearance_m=args.dock_min_docked_clearance_m,
        jackal_expected_routes=args.jackal_expected_routes,
        jackal_max_tilt_rad=args.jackal_max_tilt_rad,
        confirmation_required_consecutive_frames=(
            args.confirmation_required_consecutive_frames
        ),
    )
    output = canonical_headless_integration_report_json(report)
    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
    else:
        sys.stdout.write(output)
    return 0 if report["status"] == "ok" else 2


def _smoke_check_clock_sync(args: argparse.Namespace) -> int:
    report = check_clock_sync_trace(
        _read_jsonl_records(Path(args.trace)),
        expected_steps=args.expected_steps,
        agent_hz=args.agent_hz,
        sensor_hz=args.sensor_hz,
        tolerance_s=args.tolerance_s,
    )
    output = canonical_clock_sync_trace_check_json(report)
    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
    else:
        sys.stdout.write(output)
    return 0 if report.status == "ok" else 2


def _smoke_check_runtime_barrier(args: argparse.Namespace) -> int:
    report = check_runtime_barrier_trace(
        _read_jsonl_records(Path(args.trace)),
        expected_steps=args.expected_steps,
        agent_hz=args.agent_hz,
        sensor_hz=args.sensor_hz,
        physics_hz=args.physics_hz,
        tolerance_s=args.tolerance_s,
        require_communication=not args.no_require_communication,
        require_sensor_payloads=args.require_sensor_payloads,
    )
    output = canonical_runtime_barrier_trace_check_json(report)
    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
    else:
        sys.stdout.write(output)
    return 0 if report.status == "ok" else 2


def _smoke_check_runtime_fault(args: argparse.Namespace) -> int:
    report = check_runtime_fault_artifacts(
        Path(args.run_dir),
        expected_reason_code=args.expected_reason_code,
        expected_category=args.expected_category,
        require_sensor_payloads=args.require_sensor_payloads,
        require_watchdog_evidence=args.require_watchdog_evidence,
        require_crash_evidence=args.require_crash_evidence,
        require_action_validation_evidence=args.require_action_validation_evidence,
        require_safety_evidence=args.require_safety_evidence,
        require_fault_injection_evidence=args.require_fault_injection_evidence,
    )
    output = canonical_runtime_fault_smoke_check_json(report)
    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
    else:
        sys.stdout.write(output)
    return 0 if report.status == "ok" else 2


def _smoke_check_runtime_fault_suite(args: argparse.Namespace) -> int:
    report = validate_runtime_fault_suite_artifacts(
        Path(args.suite_dir),
        require_sensor_payloads=args.require_sensor_payloads,
        forbid_manual_trigger=args.forbid_manual_trigger,
        require_fault_injection_evidence=args.require_fault_injection_evidence,
    )
    output = canonical_runtime_fault_suite_report_json(report)
    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
    else:
        sys.stdout.write(output)
    return 0 if report["status"] == "ok" else 2


def _smoke_check_runtime_api(args: argparse.Namespace) -> int:
    sample_path = Path(args.sample).expanduser().resolve(strict=True)
    sample = json.loads(sample_path.read_text(encoding="utf-8"))
    if not isinstance(sample, Mapping):
        raise ValueError(f"runtime API sample must be a JSON object: {sample_path}")
    report = check_runtime_api_sample(
        sample,
        require_full_surface=args.require_full_surface,
        require_task_feedback=args.require_task_feedback,
        require_sensor_payloads=args.require_sensor_payloads,
    )
    output = canonical_runtime_api_sample_check_json(report)
    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
    else:
        sys.stdout.write(output)
    return 0 if report["status"] == "ok" else 2


def _smoke_check_runtime_interface_bundle(args: argparse.Namespace) -> int:
    sample_path = Path(args.runtime_api_sample).expanduser().resolve(strict=True)
    sample = json.loads(sample_path.read_text(encoding="utf-8"))
    if not isinstance(sample, Mapping):
        raise ValueError(f"runtime API sample must be a JSON object: {sample_path}")
    report = check_runtime_interface_bundle(
        runtime_api_sample=sample,
        runtime_barrier_records=_read_jsonl_records(Path(args.runtime_barrier_trace)),
        expected_steps=args.expected_steps,
        agent_hz=args.agent_hz,
        sensor_hz=args.sensor_hz,
        physics_hz=args.physics_hz,
        tolerance_s=args.tolerance_s,
        require_task_feedback=not args.no_require_task_feedback,
        require_sensor_payloads=not args.no_require_sensor_payloads,
        require_communication=not args.no_require_communication,
    )
    output = canonical_runtime_interface_bundle_check_json(report)
    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
    else:
        sys.stdout.write(output)
    return 0 if report["status"] == "ok" else 2


def _smoke_check_system_run_bundle(args: argparse.Namespace) -> int:
    report = validate_system_run_bundle_artifacts(
        soft_full_action_run_dir=Path(args.soft_full_action_run_dir),
        recovery_run_dir=Path(args.recovery_run_dir),
        hard_restart_run_dir=Path(args.hard_restart_run_dir),
        reset_state_run_dir=Path(args.reset_state_run_dir),
        dock_reset_pose_report=Path(args.dock_reset_pose_report),
        dock_reset_sequence_report=Path(args.dock_reset_sequence_report),
        public_run_dir=Path(args.public_run_dir),
        performance_report=Path(args.performance_report),
        fault_suite_dir=Path(args.fault_suite_dir),
        expected_episode_count=args.expected_episodes,
        require_clock_epoch_reset=args.require_clock_epoch_reset,
    )
    output = canonical_system_run_bundle_report_json(report)
    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
    else:
        sys.stdout.write(output)
    return 0 if report["status"] == "ok" else 2


def _smoke_check_oracle_run(args: argparse.Namespace) -> int:
    report = validate_oracle_run_artifacts(
        Path(args.run_dir),
        expected_episode_count=args.expected_episodes,
        split=args.split,
        require_success=not args.no_require_success,
        require_energy_evidence=args.require_energy_evidence,
    )
    if args.redact_private:
        redacted = redacted_hidden_oracle_run_report(
            report,
            salt=_load_manifest_salt(args),
        )
        output = canonical_hidden_oracle_run_redacted_json(redacted)
        status = redacted["status"]
    else:
        output = canonical_oracle_run_validation_report_json(report)
        status = report["status"]
    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
    else:
        sys.stdout.write(output)
    return 0 if status == "ok" else 2



def _smoke_rayfronts_baseline_contract(args: argparse.Namespace) -> int:
    records = build_rayfronts_baseline_contract_smoke_records(
        Path(args.manifest),
        rayfronts_root=Path(args.rayfronts_root),
    )
    trace_text = "".join(
        json.dumps(record, ensure_ascii=True, sort_keys=True, separators=(",", ":")) + "\n"
        for record in records
    )
    Path(args.trace_output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.trace_output).write_text(trace_text, encoding="utf-8")
    report = check_rayfronts_baseline_smoke_trace(records)
    output = canonical_rayfronts_baseline_smoke_trace_check_json(report)
    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
    else:
        sys.stdout.write(output)
    return 0 if report.status == "ok" else 2

def _smoke_check_rayfronts_baseline(args: argparse.Namespace) -> int:
    report = check_rayfronts_baseline_smoke_trace(_read_jsonl_records(Path(args.trace)))
    output = canonical_rayfronts_baseline_smoke_trace_check_json(report)
    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
    else:
        sys.stdout.write(output)
    return 0 if report.status == "ok" else 2


def _smoke_check_rayfronts_baseline_run(args: argparse.Namespace) -> int:
    report = validate_rayfronts_baseline_run_artifacts(
        Path(args.run_dir),
        expected_episode_count=args.expected_episodes,
        split=args.split,
        require_success=not args.no_require_success,
        require_energy_evidence=not args.no_require_energy_evidence,
        require_policy_evidence=args.require_policy_evidence,
        require_reset_support_dependencies=args.require_reset_support_dependencies,
        require_mapper_derived_hypothesis=args.require_mapper_derived_hypothesis,
        require_selected_behavior_mode=args.require_selected_behavior_mode,
        require_physical_mission=args.require_physical_mission,
        min_time_to_confirmation_s=args.min_time_to_confirmation_s,
        min_detection_to_confirmation_s=args.min_detection_to_confirmation_s,
        min_uav_path_m=args.min_uav_path_m,
        min_ugv_path_m=args.min_ugv_path_m,
    )
    output = canonical_rayfronts_baseline_run_check_json(report)
    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
    else:
        sys.stdout.write(output)
    return 0 if report["status"] == "ok" else 2


def _smoke_isaac_preflight(args: argparse.Namespace) -> int:
    report = build_isaac_headless_preflight_report(
        isaac_python=args.isaac_python,
        isaac_sim=args.isaac_sim,
        asset_root=args.asset_root,
        isaac_version_file=args.isaac_version_file,
        expected_simulator_version=args.simulator_version,
        require_gpu=not args.allow_missing_gpu,
        require_asset_root=not args.allow_missing_asset_root,
    )
    output = canonical_isaac_headless_preflight_json(report)
    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
    else:
        sys.stdout.write(output)
    return 0 if report.status == "ok" else 2


def _smoke_isaac_launch_plan(args: argparse.Namespace) -> int:
    report = build_isaac_headless_launch_plan(
        repo_root=args.repo_root,
        asset_root=args.asset_root,
        log_dir=args.log_dir,
        simulator_version=args.simulator_version,
        require_docker=not args.allow_missing_docker,
        require_asset_root=not args.allow_missing_asset_root,
    )
    output = canonical_isaac_headless_launch_plan_json(report)
    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
    else:
        sys.stdout.write(output)
    return 0 if report.status == "ok" else 2


def _smoke_check_isaac_headless(args: argparse.Namespace) -> int:
    report = check_isaac_headless_smoke_trace(
        _read_jsonl_records(Path(args.trace)),
        expected_simulator_version=args.simulator_version,
    )
    output = canonical_isaac_headless_smoke_trace_check_json(report)
    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
    else:
        sys.stdout.write(output)
    return 0 if report.status == "ok" else 2


def _load_reset_trace_mapping(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(Path(path).expanduser().resolve(strict=True).read_text(encoding="utf-8"))
    if isinstance(value, Mapping):
        return dict(value)
    if isinstance(value, list):
        return {"steps": value}
    raise ValueError("reset trace must be a list or mapping with a 'steps' list")


def _reset_trace_steps_from_value(value: Mapping[str, Any]) -> tuple[str, ...]:
    if isinstance(value, Mapping):
        value = value.get("steps")
    if not isinstance(value, list):
        raise ValueError("reset trace must be a list or mapping with a 'steps' list")
    result: list[str] = []
    for index, item in enumerate(value):
        if isinstance(item, str):
            result.append(item)
        elif isinstance(item, Mapping) and isinstance(item.get("step_id"), str):
            result.append(str(item["step_id"]))
        else:
            raise ValueError(f"reset trace item {index} must be a step id or mapping with step_id")
    return tuple(result)


def _load_reset_trace(path: Path) -> tuple[str, ...]:
    return _reset_trace_steps_from_value(_load_reset_trace_mapping(path))


def _load_reset_health(path: Path) -> dict[str, bool]:
    value = yaml.safe_load(Path(path).expanduser().resolve(strict=True).read_text(encoding="utf-8"))
    if isinstance(value, Mapping) and isinstance(value.get("health"), Mapping):
        value = value["health"]
    if not isinstance(value, Mapping):
        raise ValueError("reset health file must be a mapping or mapping with a 'health' object")
    result: dict[str, bool] = {}
    for component, healthy in value.items():
        if not isinstance(component, str):
            raise ValueError("reset health component names must be strings")
        if not isinstance(healthy, bool):
            raise ValueError(f"reset health value for {component!r} must be boolean")
        result[component] = healthy
    return result


def _load_reset_sensor_payload_report(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(Path(path).expanduser().resolve(strict=True).read_text(encoding="utf-8"))
    payloads = value.get("sensor_payloads") if isinstance(value, Mapping) else None
    failures: list[str] = []
    if not isinstance(payloads, Mapping):
        return {"failures": ["sensor_payloads must be an object"], "status": "failed"}
    for agent in ("uav", "ugv"):
        raw_agent = payloads.get(agent)
        if not isinstance(raw_agent, Mapping):
            failures.append(f"sensor_payloads.{agent} must be an object")
            continue
        for source in ("rgb", "depth", "lidar"):
            raw_source = raw_agent.get(source)
            label = f"sensor_payloads.{agent}.{source}"
            if not isinstance(raw_source, Mapping):
                failures.append(f"{label} must be an object")
                continue
            byte_count = raw_source.get("byte_count")
            if not isinstance(byte_count, int) or byte_count <= 0:
                failures.append(f"{label}.byte_count must be a positive integer")
            digest = raw_source.get("data_sha256")
            if not isinstance(digest, str) or len(digest) != 64 or any(
                char not in "0123456789abcdef" for char in digest
            ):
                failures.append(f"{label}.data_sha256 must be lowercase SHA-256 hex")
            topic = raw_source.get("topic")
            if not isinstance(topic, str) or not topic.startswith("/"):
                failures.append(f"{label}.topic must be an absolute ROS topic")
            stamp_s = raw_source.get("stamp_s")
            if not isinstance(stamp_s, (int, float)) or not math.isfinite(float(stamp_s)):
                failures.append(f"{label}.stamp_s must be finite")
            if source == "lidar":
                for field in ("point_count", "point_step"):
                    value_int = raw_source.get(field)
                    if not isinstance(value_int, int) or value_int <= 0:
                        failures.append(f"{label}.{field} must be a positive integer")
            else:
                for field in ("height", "width"):
                    value_int = raw_source.get(field)
                    if not isinstance(value_int, int) or value_int <= 0:
                        failures.append(f"{label}.{field} must be a positive integer")
                encoding = raw_source.get("encoding")
                if not isinstance(encoding, str) or not encoding:
                    failures.append(f"{label}.encoding must be a non-empty string")
    return {
        "agent_count": sum(1 for agent in ("uav", "ugv") if isinstance(payloads.get(agent), Mapping)),
        "failures": failures,
        "status": "ok" if not failures else "failed",
    }


def _load_reset_adapter_state_clear_report(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(Path(path).expanduser().resolve(strict=True).read_text(encoding="utf-8"))
    evidence = value.get("adapter_state_clear_evidence") if isinstance(value, Mapping) else None
    failures: list[str] = []
    if not isinstance(evidence, Mapping):
        return {
            "failures": ["adapter_state_clear_evidence must be an object"],
            "status": "failed",
        }

    if evidence.get("status") != "ok":
        failures.append("adapter_state_clear_evidence.status must be ok")
    source = evidence.get("source")
    if source != "RuntimeCommunicationBridge.reset_episode_state":
        failures.append(
            "adapter_state_clear_evidence.source must be RuntimeCommunicationBridge.reset_episode_state"
        )

    required_surfaces = {
        "communication_queue",
        "communication_inbox",
        "communication_history",
        "communication_metrics",
        "metric_accumulators",
        "radio_pose_cache",
    }
    raw_surfaces = evidence.get("reset_surfaces")
    if not isinstance(raw_surfaces, list) or not all(
        isinstance(item, str) for item in raw_surfaces
    ):
        failures.append("adapter_state_clear_evidence.reset_surfaces must be a string list")
    else:
        missing_surfaces = sorted(required_surfaces.difference(raw_surfaces))
        if missing_surfaces:
            failures.append(
                "adapter_state_clear_evidence.reset_surfaces missing "
                + ",".join(missing_surfaces)
            )

    communication = evidence.get("communication")
    if not isinstance(communication, Mapping):
        failures.append("adapter_state_clear_evidence.communication must be an object")
    else:
        before = communication.get("before")
        after = communication.get("after")
        if not isinstance(before, Mapping):
            failures.append("adapter_state_clear_evidence.communication.before must be an object")
        else:
            for field in (
                "submitted_messages",
                "queued_messages",
                "delivered_messages",
                "dropped_messages",
                "delivered_history_count",
                "dropped_message_count",
                "inbox_message_count",
                "link_airtime_queue_count",
                "link_delivery_queue_count",
                "pending_message_count",
                "snapshot_pose_count",
            ):
                _require_positive_int(
                    before,
                    field,
                    failures,
                    label=f"adapter_state_clear_evidence.communication.before.{field}",
                )
            drop_reasons = before.get("drop_reasons")
            if not isinstance(drop_reasons, Mapping) or not drop_reasons:
                failures.append(
                    "adapter_state_clear_evidence.communication.before.drop_reasons must be a non-empty object"
                )
        if not isinstance(after, Mapping):
            failures.append("adapter_state_clear_evidence.communication.after must be an object")
        else:
            for field in (
                "submitted_messages",
                "queued_messages",
                "delivered_messages",
                "dropped_messages",
                "delivered_history_count",
                "dropped_message_count",
                "inbox_message_count",
                "link_airtime_queue_count",
                "link_delivery_queue_count",
                "late_delivery_count_after_reset",
                "pending_message_count",
                "snapshot_pose_count",
            ):
                _require_zero_int(
                    after,
                    field,
                    failures,
                    label=f"adapter_state_clear_evidence.communication.after.{field}",
                )
            drop_reasons = after.get("drop_reasons")
            if not isinstance(drop_reasons, Mapping) or drop_reasons:
                failures.append(
                    "adapter_state_clear_evidence.communication.after.drop_reasons must be an empty object"
                )

    metrics = evidence.get("metrics")
    if not isinstance(metrics, Mapping):
        failures.append("adapter_state_clear_evidence.metrics must be an object")
    else:
        before = metrics.get("before")
        after = metrics.get("after")
        metric_fields = (
            "event_count",
            "trajectory_sample_count",
            "energy_sample_count",
            "communication_event_count",
            "collision_count",
            "score_accumulator_count",
        )
        if not isinstance(before, Mapping):
            failures.append("adapter_state_clear_evidence.metrics.before must be an object")
        else:
            for field in metric_fields:
                _require_positive_int(
                    before,
                    field,
                    failures,
                    label=f"adapter_state_clear_evidence.metrics.before.{field}",
                )
        if not isinstance(after, Mapping):
            failures.append("adapter_state_clear_evidence.metrics.after must be an object")
        else:
            for field in metric_fields:
                _require_zero_int(
                    after,
                    field,
                    failures,
                    label=f"adapter_state_clear_evidence.metrics.after.{field}",
                )

    return {
        "failures": failures,
        "reset_surfaces": (
            sorted(item for item in raw_surfaces if isinstance(item, str))
            if isinstance(raw_surfaces, list)
            else []
        ),
        "status": "ok" if not failures else "failed",
    }


def _require_positive_int(
    mapping: Mapping[str, Any],
    field: str,
    failures: list[str],
    *,
    label: str,
) -> None:
    value = mapping.get(field)
    if not isinstance(value, int) or value <= 0:
        failures.append(f"{label} must be a positive integer")


def _require_zero_int(
    mapping: Mapping[str, Any],
    field: str,
    failures: list[str],
    *,
    label: str,
) -> None:
    value = mapping.get(field)
    if not isinstance(value, int) or value != 0:
        failures.append(f"{label} must be 0")


def _load_reset_ros_queue_clear_report(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(Path(path).expanduser().resolve(strict=True).read_text(encoding="utf-8"))
    evidence = value.get("ros_queue_clear_evidence") if isinstance(value, Mapping) else None
    failures: list[str] = []
    if not isinstance(evidence, Mapping):
        return {
            "failures": ["ros_queue_clear_evidence must be an object"],
            "status": "failed",
        }
    if evidence.get("status") != "ok":
        failures.append("ros_queue_clear_evidence.status must be ok")
    if evidence.get("reset_surface") != "adapter_ros_subscription_queue":
        failures.append(
            "ros_queue_clear_evidence.reset_surface must be adapter_ros_subscription_queue"
        )
    topic = evidence.get("topic")
    if not isinstance(topic, str) or not topic.startswith("/"):
        failures.append("ros_queue_clear_evidence.topic must be an absolute ROS topic")
    if evidence.get("publisher_subscriber_matched") is not True:
        failures.append("ros_queue_clear_evidence.publisher_subscriber_matched must be true")
    if evidence.get("stale_messages_observed") is not True:
        failures.append("ros_queue_clear_evidence.stale_messages_observed must be true")
    stale_count = evidence.get("stale_message_count")
    if not isinstance(stale_count, int) or stale_count <= 0:
        failures.append("ros_queue_clear_evidence.stale_message_count must be positive")
    before = evidence.get("before")
    after = evidence.get("after")
    if not isinstance(before, Mapping):
        failures.append("ros_queue_clear_evidence.before must be an object")
    else:
        _require_positive_int(
            before,
            "queue_message_count",
            failures,
            label="ros_queue_clear_evidence.before.queue_message_count",
        )
        _require_positive_int(
            before,
            "received_message_count",
            failures,
            label="ros_queue_clear_evidence.before.received_message_count",
        )
        if (
            isinstance(stale_count, int)
            and isinstance(before.get("queue_message_count"), int)
            and before["queue_message_count"] < stale_count
        ):
            failures.append(
                "ros_queue_clear_evidence.before.queue_message_count must be >= stale_message_count"
            )
    if not isinstance(after, Mapping):
        failures.append("ros_queue_clear_evidence.after must be an object")
    else:
        _require_zero_int(
            after,
            "queue_message_count",
            failures,
            label="ros_queue_clear_evidence.after.queue_message_count",
        )
        _require_zero_int(
            after,
            "late_message_count_after_clear",
            failures,
            label="ros_queue_clear_evidence.after.late_message_count_after_clear",
        )
    return {
        "failures": failures,
        "status": "ok" if not failures else "failed",
        "topic": topic if isinstance(topic, str) else None,
    }


def _load_reset_airstack_trajectory_clear_report(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(Path(path).expanduser().resolve(strict=True).read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        return {
            "failures": ["reset trace must be a JSON object"],
            "issues": ["reset trace must be a JSON object"],
            "status": "failed",
        }
    return validate_reset_airstack_trajectory_clear_surface(value)


def _load_reset_nav2_cancel_report(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(Path(path).expanduser().resolve(strict=True).read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        return {
            "failures": ["reset trace must be a JSON object"],
            "issues": ["reset trace must be a JSON object"],
            "status": "failed",
        }
    return validate_reset_nav2_cancel_surface(value)


def _load_reset_uav_px4_cancel_report(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(Path(path).expanduser().resolve(strict=True).read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        return {
            "failures": ["reset trace must be a JSON object"],
            "issues": ["reset trace must be a JSON object"],
            "status": "failed",
        }
    return validate_reset_uav_px4_cancel_surface(value)


def _load_reset_control_hold_report(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(Path(path).expanduser().resolve(strict=True).read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        return {
            "failures": ["reset trace must be a JSON object"],
            "issues": ["reset trace must be a JSON object"],
            "status": "failed",
        }
    return validate_reset_control_hold_surface(value)


def _load_reset_rayfronts_reset_report(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(Path(path).expanduser().resolve(strict=True).read_text(encoding="utf-8"))
    evidence = value.get("rayfronts_reset_evidence") if isinstance(value, Mapping) else None
    failures: list[str] = []
    if not isinstance(evidence, Mapping):
        return {
            "failures": ["rayfronts_reset_evidence must be an object"],
            "status": "failed",
        }
    if evidence.get("status") != "ok":
        failures.append("rayfronts_reset_evidence.status must be ok")
    for field in (
        "service_available",
        "input_subscriber_seen",
        "map_probe_subscriber_seen",
        "query_observed",
        "map_state_observed",
        "reset_observed",
        "hypotheses_empty_after_reset",
        "map_state_empty_after_reset",
    ):
        if evidence.get(field) is not True:
            failures.append(f"rayfronts_reset_evidence.{field} must be true")
    for field in ("health_topic", "hypotheses_topic", "map_probe_topic", "reset_service"):
        topic = evidence.get(field)
        if not isinstance(topic, str) or not topic.startswith("/"):
            failures.append(f"rayfronts_reset_evidence.{field} must be an absolute ROS name")

    after_query = evidence.get("after_query")
    if not isinstance(after_query, Mapping):
        failures.append("rayfronts_reset_evidence.after_query must be an object")
    else:
        if after_query.get("has_active_query") is not True:
            failures.append("rayfronts_reset_evidence.after_query.has_active_query must be true")
        if after_query.get("has_map_state") is not True:
            failures.append("rayfronts_reset_evidence.after_query.has_map_state must be true")
        for field in ("query_count", "map_entry_count", "frontier_count"):
            _require_positive_int(
                after_query,
                field,
                failures,
                label=f"rayfronts_reset_evidence.after_query.{field}",
            )

    after_reset = evidence.get("after_reset")
    if not isinstance(after_reset, Mapping):
        failures.append("rayfronts_reset_evidence.after_reset must be an object")
    else:
        if after_reset.get("has_active_query") is not False:
            failures.append("rayfronts_reset_evidence.after_reset.has_active_query must be false")
        if after_reset.get("has_map_state") is not False:
            failures.append("rayfronts_reset_evidence.after_reset.has_map_state must be false")
        for field in ("query_count", "hypothesis_count", "map_entry_count", "frontier_count", "map_update_count"):
            _require_zero_int(
                after_reset,
                field,
                failures,
                label=f"rayfronts_reset_evidence.after_reset.{field}",
            )

    return {
        "failures": failures,
        "status": "ok" if not failures else "failed",
    }


def _load_reset_stable_health_handshake_report(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(Path(path).expanduser().resolve(strict=True).read_text(encoding="utf-8"))
    report = validate_reset_stable_health_handshake_surface(value)
    return {
        "failures": list(report["issues"]),
        "sample_count": report["sample_count"],
        "stable_ready_count": report["stable_ready_count"],
        "status": report["status"],
    }


def _default_ros_distro_for_simulator(simulator_version: str) -> str:
    defaults = ISAAC_RUNTIME_DEFAULTS_BY_VERSION.get(
        simulator_version,
        ISAAC_RUNTIME_DEFAULTS_BY_VERSION[DEFAULT_ISAAC_SIMULATOR_VERSION],
    )
    return defaults["ros_distro"]


def _run(args: argparse.Namespace) -> int:
    manifest = load_episode_manifest(Path(args.episodes) if args.episodes else None)
    if args.mode == "contract":
        if not args.agent:
            raise RunError("--agent is required for contract mode")
        summary = run_contract(
            manifest,
            Path(args.output_dir),
            agent_entrypoint=args.agent,
            episode_ids=tuple(args.episode_id or ()),
            limit=args.limit,
            record_sensors=args.record_sensors,
            overwrite=args.overwrite,
        )
    elif args.mode == "isaac":
        if args.record_sensors:
            raise RunError("--record-sensors is not supported by isaac smoke mode")
        agent_entrypoint = args.agent or (
            "real://rayfronts-baseline"
            if args.rayfronts_baseline
            else "real://runtime-metrics-smoke"
        )
        if args.rayfronts_baseline and "rayfronts" not in agent_entrypoint.lower():
            raise RunError("--rayfronts-baseline requires --agent to identify RayFronts")
        ros_distro = args.ros_distro or _default_ros_distro_for_simulator(
            args.simulator_version
        )
        resource_guard_env = {
            "AIRGROUND_RESOURCE_GUARD": "0" if args.no_resource_guard else "1",
            "AIRGROUND_RESOURCE_GUARD_MAX_CONSECUTIVE_FAILURES": str(args.resource_guard_max_consecutive_failures),
            "AIRGROUND_RESOURCE_GUARD_MAX_GPU_MEMORY_FRACTION": str(args.resource_guard_max_gpu_memory_fraction),
            "AIRGROUND_RESOURCE_GUARD_MAX_SYSTEM_MEMORY_FRACTION": str(args.resource_guard_max_system_memory_fraction),
            "AIRGROUND_RESOURCE_GUARD_MIN_AVAILABLE_MEMORY_GB": str(args.resource_guard_min_available_memory_gb),
            "AIRGROUND_RESOURCE_GUARD_HOST_MEMORY_MAX_GB": str(args.resource_guard_host_memory_max_gb),
            "AIRGROUND_RESOURCE_GUARD_POLL_S": str(args.resource_guard_poll_s),
            RESOURCE_GUARD_PROFILE_ENV: str(args.resource_guard_profile),
        }
        runtime_env = dict(resource_guard_env)
        if args.rayfronts_device:
            runtime_env["AIRGROUND_RAYFRONTS_DEVICE"] = str(args.rayfronts_device)
        previous_resource_env = {key: os.environ.get(key) for key in runtime_env}
        os.environ.update(runtime_env)
        try:
            validate_isaac_resource_guard_configuration()
            with resource_guard_host_address_space_limit() as host_guard_report:
                summary = run_isaac_smoke(
                    manifest,
                    Path(args.output_dir),
                    agent_entrypoint=agent_entrypoint,
                    episode_ids=tuple(args.episode_id or ()),
                    limit=args.limit,
                    overwrite=args.overwrite,
                    repo_root=Path(args.repo_root),
                    container=args.isaac_container,
                    sample_count=args.isaac_sample_count,
                    timeout_s=args.isaac_timeout,
                    simulator_version=args.simulator_version,
                    ros_distro=ros_distro,
                    require_reset_sensor_payloads=not args.no_reset_sensor_payloads,
                    require_reset_airstack_trajectory_clear=not args.no_reset_airstack_trajectory_clear,
                    require_stable_reset_health_handshake=not args.no_reset_stable_health_handshake,
                    manage_reset_support_stack=not args.no_reset_support_stack,
                    require_reset_support_postflight_clean=not args.no_reset_support_postflight_check,
                    rayfronts_baseline=args.rayfronts_baseline,
                    rayfronts_baseline_mode=args.rayfronts_baseline_mode,
                    rayfronts_full_mission_runner=args.rayfronts_full_mission_runner,
                    rayfronts_confirmation_evidence_dir=(
                        Path(args.rayfronts_confirmation_evidence_dir)
                        if args.rayfronts_confirmation_evidence_dir
                        else None
                    ),
                    rayfronts_communication_evidence_dir=(
                        Path(args.rayfronts_communication_evidence_dir)
                        if args.rayfronts_communication_evidence_dir
                        else None
                    ),
                    rayfronts_uav_control_evidence_dir=(
                        Path(args.rayfronts_uav_control_evidence_dir)
                        if args.rayfronts_uav_control_evidence_dir
                        else None
                    ),
                    rayfronts_uav_control_adapter=args.rayfronts_uav_control_adapter,
                    rayfronts_uav_control_target_altitude_m=args.rayfronts_uav_control_target_altitude_m,
                    rayfronts_uav_control_hover_s=args.rayfronts_uav_control_hover_s,
                    rayfronts_uav_control_px4_params=args.rayfronts_uav_control_px4_param,
                    rayfronts_uav_control_bootstrap_hover_s=args.rayfronts_uav_control_bootstrap_hover_s,
                    rayfronts_uav_control_waypoint_max_distance_m=args.rayfronts_uav_control_waypoint_max_distance_m,
                    rayfronts_uav_control_search_sorties=args.rayfronts_uav_control_search_sorties,
                    rayfronts_uav_control_search_budget_s=args.rayfronts_uav_control_search_budget_s,
                    rayfronts_uav_control_mission_budget_s=(
                        args.rayfronts_uav_control_mission_budget_s
                    ),
                    rayfronts_uav_control_planner=args.rayfronts_uav_control_planner,
                    ugv_goal_standoff_m=args.ugv_goal_standoff_m,
                    ugv_goal_anchor_radius_m=args.ugv_goal_anchor_radius_m,
                    ugv_goal_adjust_max_m=args.ugv_goal_adjust_max_m,
                    ugv_goal_min_clearance_m=args.ugv_goal_min_clearance_m,
                    ugv_goal_plan_probe_max=args.ugv_goal_plan_probe_max,
                    ugv_goal_candidate_attempts=args.ugv_goal_candidate_attempts,
                    ugv_motion_trace=bool(args.ugv_motion_trace),
                    ugv_motion_trace_sample_hz=args.ugv_motion_trace_sample_hz,
                    ugv_goal_timeout_s=args.ugv_goal_timeout_s,
                    ugv_goal_first_timeout_s=args.ugv_goal_first_timeout_s,
                    ugv_fifo_max_targets=args.ugv_fifo_max_targets,
                    ugv_target_dedup_radius_m=args.ugv_target_dedup_radius_m,
                    ugv_inject_goal_position_m=args.ugv_inject_goal_position_m,
                    ugv_inject_via_position_m=args.ugv_inject_via_position_m,
                    ugv_inject_target_instance_ids=args.ugv_inject_target_instance_ids,
                    ugv_inject_goal_note=args.ugv_inject_goal_note,
                    rayfronts_target_annotations_path=(
                        Path(args.rayfronts_target_annotations)
                        if args.rayfronts_target_annotations
                        else None
                    ),
                    rayfronts_confirmation_sensor_trace_dir=(
                        Path(args.rayfronts_confirmation_sensor_trace_dir)
                        if args.rayfronts_confirmation_sensor_trace_dir
                        else None
                    ),
                    rayfronts_nav2_map_yaml=(
                        Path(args.rayfronts_nav2_map_yaml)
                        if args.rayfronts_nav2_map_yaml
                        else None
                    ),
                )
                summary["resource_guard_host_limit"] = host_guard_report
        finally:
            for key, value in previous_resource_env.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
        if args.require_rayfronts_physical_mission:
            if not args.rayfronts_baseline:
                raise RunError("--require-rayfronts-physical-mission requires --rayfronts-baseline")
            expected_episode_count = summary.get("episode_count")
            gate_report = validate_rayfronts_baseline_run_artifacts(
                Path(args.output_dir),
                expected_episode_count=(
                    expected_episode_count if isinstance(expected_episode_count, int) else None
                ),
                split=manifest.split,
                require_mapper_derived_hypothesis=(
                    args.rayfronts_baseline_mode in {"mapper", "vlfm"}
                ),
                require_selected_behavior_mode=(
                    "VLFM-based" if args.rayfronts_baseline_mode == "vlfm" else None
                ),
                require_physical_mission=True,
                min_time_to_confirmation_s=args.min_time_to_confirmation_s,
                min_detection_to_confirmation_s=args.min_detection_to_confirmation_s,
                min_uav_path_m=args.min_uav_path_m,
                min_ugv_path_m=args.min_ugv_path_m,
            )
            gate_path = Path(args.output_dir) / "rayfronts_full_mission_gate.json"
            gate_path.write_text(
                canonical_rayfronts_baseline_run_check_json(gate_report),
                encoding="utf-8",
            )
            summary["rayfronts_full_mission_gate"] = str(gate_path)
            if gate_report.get("status") != "ok":
                raise RunError(
                    "RayFronts full-mission gate failed; see "
                    f"{gate_path} ({len(gate_report.get('failures', []))} failures)"
                )
    else:
        raise RunError(f"unsupported run mode: {args.mode}")
    _write_json(summary)
    return 0


def _gt_traversability_schema(_: argparse.Namespace) -> int:
    sys.stdout.write(canonical_traversability_schema_json())
    return 0


def _gt_traversability_validate(args: argparse.Namespace) -> int:
    metadata = load_traversability_metadata(Path(args.metadata))
    summary = validate_traversability_npz(Path(args.npz), metadata)
    _write_json(summary)
    return 0


def _gt_traversability_export_nav2(args: argparse.Namespace) -> int:
    metadata = load_traversability_metadata(Path(args.metadata))
    grid = load_traversability_grid(Path(args.npz), metadata)
    export = write_nav2_occupancy_grid(
        grid,
        Path(args.output_dir),
        stem=args.stem,
        occupied_thresh=args.occupied_thresh,
        free_thresh=args.free_thresh,
    )
    _write_json(export.summary())
    return 0


def _gt_traversability_package(args: argparse.Namespace) -> int:
    metadata = load_traversability_metadata(Path(args.metadata))
    with np.load(Path(args.npz).expanduser().resolve(strict=True)) as data:
        arrays = {key: np.array(data[key], copy=True) for key in data.files}
    export = write_traversability_artifact(
        metadata,
        arrays,
        Path(args.output_dir),
        stem=args.stem,
        export_nav2=not args.no_nav2,
        occupied_thresh=args.occupied_thresh,
        free_thresh=args.free_thresh,
    )
    _write_json(export.summary())
    return 0


def _gt_traversability_reach_region(args: argparse.Namespace) -> int:
    """Recalibrate the reachable region with the 1.5x UGV-width corridor rule."""

    metadata = load_traversability_metadata(Path(args.metadata))
    npz_path = Path(args.npz).expanduser().resolve(strict=True)
    with np.load(npz_path) as data:
        arrays = {key: np.array(data[key], copy=True) for key in data.files}
    if "mask" not in arrays:
        raise GroundTruthError("traversability arrays must contain a 'mask' entry")

    result = build_reach_region(
        arrays["mask"],
        resolution_m=metadata.resolution_m,
        clearance_margin_m=args.clearance_margin_m,
        footprint_width_m=args.footprint_width_m,
    )
    if int(result.reach_mask.sum()) == 0:
        raise GroundTruthError(
            "reach-region calibration produced an empty region; "
            "check --clearance-margin-m against the source mask"
        )

    arrays["mask"] = result.reach_mask
    arrays["component"] = result.reach_component
    reach_metadata = metadata.model_copy(
        update={
            "generator": "airground-reach-region-v1",
            "generator_version": "p1-03d",
            "npz_sha256": None,
        }
    )
    output_dir = Path(args.output_dir).expanduser().resolve()
    export = write_traversability_artifact(
        reach_metadata,
        arrays,
        output_dir / "package",
        stem=args.stem,
        export_nav2=not args.no_nav2,
    )
    report = {
        "schema_version": metadata.schema_version,
        "scene_id": metadata.scene_id,
        "frame": metadata.frame,
        "resolution_m": float(metadata.resolution_m),
        "source_npz": str(npz_path),
        "source_npz_bytes_sha256": hashlib.sha256(npz_path.read_bytes()).hexdigest(),
        "reach_region": result.summary(),
        "component_sizes_desc": [
            {"component": int(component), "cells": int(cells)}
            for component, cells in result.component_sizes_desc()
        ],
        "package": export.summary(),
        "status": "ok",
    }
    report_path = output_dir / "reach_region_report.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    sys.stdout.write(
        json.dumps(
            {
                "component_count": int(result.component_count),
                "largest_component_cells": int(result.component_cell_counts and max(result.component_cell_counts)),
                "passable_cells": int(result.reach_mask.sum()),
                "report": str(report_path),
                "status": "ok",
            },
            sort_keys=True,
        )
        + "\n"
    )
    return 0


def _gt_traversability_sweep_footprint(args: argparse.Namespace) -> int:
    metadata = load_traversability_metadata(Path(args.metadata))
    footprint_evidence = None
    if args.footprint_report:
        estimate = load_jackal_footprint_estimate_from_asset_report(
            Path(args.footprint_report),
            padding_m=args.footprint_padding,
            robot_root=args.footprint_robot_root,
        )
        config = estimate.sweep_config(
            yaw_samples=args.yaw_samples,
            max_slope_rad=args.max_slope_rad,
            max_step_height_m=args.max_step_height,
            min_overhead_clearance_m=args.min_overhead_clearance,
            blocked_cost=args.blocked_cost,
        )
        footprint_evidence = estimate.as_dict()
    else:
        config = FootprintSweepConfig(
            footprint_length_m=args.footprint_length,
            footprint_width_m=args.footprint_width,
            yaw_samples=args.yaw_samples,
            max_slope_rad=args.max_slope_rad,
            max_step_height_m=args.max_step_height,
            min_overhead_clearance_m=args.min_overhead_clearance,
            blocked_cost=args.blocked_cost,
        )
    export = write_footprint_sweep_artifact(
        metadata,
        Path(args.npz),
        Path(args.output_dir),
        config=config,
        footprint_evidence=footprint_evidence,
        stem=args.stem,
        generator_version=args.generator_version,
        export_nav2=args.export_nav2,
        occupied_thresh=args.occupied_thresh,
        free_thresh=args.free_thresh,
    )
    _write_json(export.summary())
    return 0


def _gt_traversability_rollout_report(args: argparse.Namespace) -> int:
    records = _read_jsonl_records(Path(args.samples))
    report = build_traversability_rollout_report(
        records,
        min_samples=args.min_samples,
        min_consistency=args.min_consistency,
        max_mismatches=args.max_mismatches,
    )
    output = canonical_traversability_rollout_report_json(report)
    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
    else:
        sys.stdout.write(output)
    return 0 if report.summary()["status"] == "ok" else 2


def _gt_traversability_mismatch_review(args: argparse.Namespace) -> int:
    records = _read_jsonl_records(Path(args.samples))
    report = build_traversability_mismatch_review_report(
        records,
        screenshot_paths=(
            _read_string_mapping(Path(args.screenshot_manifest))
            if args.screenshot_manifest
            else None
        ),
        final_dispositions=(
            _read_string_mapping(Path(args.review_annotations))
            if args.review_annotations
            else None
        ),
        require_screenshots=not args.no_require_screenshots,
        require_final_dispositions=not args.no_require_final_dispositions,
    )
    output = canonical_traversability_mismatch_review_report_json(report)
    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
    else:
        sys.stdout.write(output)
    return 0 if report.summary()["status"] == "ok" else 2


def _gt_traversability_calibrate_thresholds(args: argparse.Namespace) -> int:
    report = build_jackal_ground_threshold_calibration_report(
        _read_jsonl_records(Path(args.trace)),
        robot_id=args.robot_id,
        testbed_version=args.testbed_version,
        max_tilt_rad=args.max_tilt_rad,
    )
    summary = report.summary()
    if args.output_config and summary["status"] == "ok":
        Path(args.output_config).write_text(
            jackal_ground_threshold_config_yaml(report),
            encoding="utf-8",
        )
    output = canonical_jackal_ground_threshold_calibration_json(report)
    if args.output_report:
        Path(args.output_report).write_text(output, encoding="utf-8")
    else:
        sys.stdout.write(output)
    return 0 if summary["status"] == "ok" else 2


def _gt_targets_schema(_: argparse.Namespace) -> int:
    sys.stdout.write(canonical_target_annotations_schema_json())
    return 0


def _gt_targets_validate(args: argparse.Namespace) -> int:
    manifest = (
        load_target_annotations(Path(args.annotations))
        if args.annotations
        else load_default_target_annotations()
    )
    reachability_counts = {
        "reachable": sum(1 for instance in manifest.instances if instance.ground_reachable == "reachable"),
        "unreachable": sum(
            1 for instance in manifest.instances if instance.ground_reachable == "unreachable"
        ),
        "unknown": sum(1 for instance in manifest.instances if instance.ground_reachable == "unknown"),
    }
    _write_json(
        {
            "confirmation_region_count": len(manifest.confirmation_regions),
            "instance_count": len(manifest.instances),
            "ground_reachability_counts": reachability_counts,
            "reachable_confirmation_region_count": sum(
                1 for region in manifest.confirmation_regions if region.reachable
            ),
            "schema_version": manifest.schema_version,
            "scene_id": manifest.scene_id,
            "sha256": target_annotations_sha256(manifest),
            "status": "ok",
        }
    )
    return 0


def _gt_targets_audit(args: argparse.Namespace) -> int:
    manifest = (
        load_target_annotations(Path(args.annotations))
        if args.annotations
        else load_default_target_annotations()
    )
    report = audit_target_annotations(
        manifest,
        require_source_path=args.require_source_path,
        require_usd_prim_path=args.require_usd_prim,
        require_verified=args.require_verified,
        require_review_version=args.require_review_version,
        max_issues=args.max_issues,
    )
    output = canonical_target_annotation_audit_report_json(report)
    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
    else:
        sys.stdout.write(output)
    return 0 if report.summary()["status"] == "ok" else 2


def _gt_targets_build_confirmation_regions(args: argparse.Namespace) -> int:
    manifest = (
        load_target_annotations(Path(args.annotations))
        if args.annotations
        else load_default_target_annotations()
    )
    metadata = load_traversability_metadata(Path(args.metadata))
    updated = build_confirmation_regions_from_traversability(
        manifest,
        metadata,
        Path(args.npz),
        min_distance_m=args.min_distance,
        max_distance_m=args.max_distance,
        radial_step_m=args.radial_step,
        angle_count=args.angle_count,
        max_poses_per_target=args.max_poses_per_target,
        proxy_visible_fraction=args.proxy_visible_fraction,
    )
    output = canonical_target_annotations_json(updated)
    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
    else:
        sys.stdout.write(output)
    return 0


def _gt_targets_visibility_occlusion(args: argparse.Namespace) -> int:
    manifest = (
        load_target_annotations(Path(args.annotations))
        if args.annotations
        else load_default_target_annotations()
    )
    metadata = load_traversability_metadata(Path(args.metadata))
    report = build_visibility_occlusion_report_from_traversability(
        manifest,
        metadata,
        Path(args.npz),
        uav_altitudes_m=tuple(args.uav_altitude) if args.uav_altitude else (2.0, 4.0, 6.0),
        min_range_m=args.min_range,
        max_range_m=args.max_range,
        horizontal_fov_rad=args.horizontal_fov,
        yaw_samples=args.yaw_samples,
        sample_stride_cells=args.sample_stride_cells,
        ray_step_m=args.ray_step,
    )
    output = canonical_visibility_occlusion_report_json(report)
    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
    else:
        sys.stdout.write(output)
    return 0


def _gt_targets_visibility_at_pose(args: argparse.Namespace) -> int:
    manifest = (
        load_target_annotations(Path(args.annotations))
        if args.annotations
        else load_default_target_annotations()
    )
    metadata = load_traversability_metadata(Path(args.metadata))
    report = evaluate_target_visibility_at_pose(
        manifest,
        metadata,
        Path(args.npz),
        observer_xy_m=(float(args.pose[0]), float(args.pose[1])),
        observer_heights_m=tuple(args.observer_height) if args.observer_height else (0.3, 0.45),
        min_range_m=args.min_range,
        max_range_m=args.max_range,
        ray_step_m=args.ray_step,
        instance_ids=tuple(args.instance) if args.instance else None,
    )
    output = canonical_pose_visibility_report_json(report)
    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
    else:
        sys.stdout.write(output)
    return 0


def _gt_targets_validate_confirmation_visibility(args: argparse.Namespace) -> int:
    manifest = (
        load_target_annotations(Path(args.annotations))
        if args.annotations
        else load_default_target_annotations()
    )
    metadata = load_traversability_metadata(Path(args.metadata))
    report = validate_confirmation_visibility_from_traversability(
        manifest,
        metadata,
        Path(args.npz),
        min_distance_m=args.min_distance,
        max_distance_m=args.max_distance,
        horizontal_fov_rad=args.horizontal_fov,
        min_visible_fraction=args.min_visible_fraction,
        required_consecutive_frames=args.required_consecutive_frames,
        ray_step_m=args.ray_step,
    )
    output = canonical_confirmation_visibility_report_json(report)
    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
    else:
        sys.stdout.write(output)
    return 0 if report.status == "ok" else 2


def _gt_targets_validate_confirmation_sensor_trace(args: argparse.Namespace) -> int:
    manifest = (
        load_target_annotations(Path(args.annotations))
        if args.annotations
        else load_default_target_annotations()
    )
    records = _read_jsonl_records(Path(args.trace))
    report = validate_confirmation_visibility_sensor_trace(
        manifest,
        records,
        min_distance_m=args.min_distance,
        max_distance_m=args.max_distance,
        horizontal_fov_rad=args.horizontal_fov,
        min_visible_fraction=args.min_visible_fraction,
        required_consecutive_frames=args.required_consecutive_frames,
        max_frame_gap_s=args.max_frame_gap,
        require_raycast_evidence=not args.no_require_raycast_evidence,
    )
    output = canonical_sensor_frame_confirmation_visibility_report_json(report)
    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
    else:
        sys.stdout.write(output)
    return 0 if report.status == "ok" else 2


def _gt_targets_build_confirmation_evidence(args: argparse.Namespace) -> int:
    manifest = (
        load_target_annotations(Path(args.annotations))
        if args.annotations
        else load_default_target_annotations()
    )
    records = _read_jsonl_records(Path(args.trace))
    try:
        evidence = build_confirmation_evidence_from_sensor_trace(
            manifest,
            records,
            target_id=args.target_id,
            report_id=args.report_id,
            nav2_goal_reached=args.nav2_goal_reached,
            min_distance_m=args.min_distance,
            max_distance_m=args.max_distance,
            horizontal_fov_rad=args.horizontal_fov,
            min_visible_fraction=args.min_visible_fraction,
            required_consecutive_frames=args.required_consecutive_frames,
            max_frame_gap_s=args.max_frame_gap,
            require_raycast_evidence=not args.no_require_raycast_evidence,
        )
    except FullMissionEvidenceError as error:
        if args.output:
            Path(args.output).write_text(
                json.dumps(
                    {
                        "error": str(error),
                        "generator": "airground-full-mission-confirmation-evidence-v1",
                        "schema_version": "1.0.0",
                        "status": "failed",
                    },
                    ensure_ascii=True,
                    sort_keys=True,
                    separators=(",", ":"),
                )
                + "\n",
                encoding="utf-8",
            )
        else:
            sys.stderr.write(str(error) + "\n")
        return 2
    output = canonical_confirmation_evidence_json(evidence)
    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
    else:
        sys.stdout.write(output)
    return 0


def _gt_targets_review(args: argparse.Namespace) -> int:
    manifest = (
        load_target_annotations(Path(args.annotations))
        if args.annotations
        else load_default_target_annotations()
    )
    camera_position = None
    if args.camera_x is not None or args.camera_y is not None or args.camera_z is not None:
        if args.camera_x is None or args.camera_y is None or args.camera_z is None:
            raise ValueError("--camera-x, --camera-y and --camera-z must be provided together")
        camera_position = (args.camera_x, args.camera_y, args.camera_z)
    summary = write_target_review_artifacts(
        manifest,
        Path(args.output_dir),
        max_targets=args.max_targets,
        canvas_width_px=args.width,
        canvas_height_px=args.height,
        camera_position_xyz_m=camera_position,
        camera_yaw_rad=args.camera_yaw,
        horizontal_fov_rad=args.horizontal_fov,
        vertical_fov_rad=args.vertical_fov,
        max_distance_m=args.max_distance,
    )
    _write_json(summary)
    return 0


def _gt_targets_review_ledger_template(args: argparse.Namespace) -> int:
    manifest = (
        load_target_annotations(Path(args.annotations))
        if args.annotations
        else load_default_target_annotations()
    )
    queue_path = Path(args.review_queue).expanduser().resolve(strict=True)
    queue_value = yaml.safe_load(queue_path.read_text(encoding="utf-8"))
    if not isinstance(queue_value, Mapping):
        raise GroundTruthError(f"target review queue must be a YAML/JSON mapping: {queue_path}")
    template = build_target_review_ledger_template(
        manifest,
        dict(queue_value),
        review_version=args.review_version,
        source_review_queue_sha256=hashlib.sha256(queue_path.read_bytes()).hexdigest(),
        source_review_media=args.source_review_media,
        generator_version=args.generator_version,
    )
    output = canonical_target_review_ledger_template_json(template)
    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
    else:
        sys.stdout.write(output)
    return 0


def _gt_targets_apply_review(args: argparse.Namespace) -> int:
    manifest = (
        load_target_annotations(Path(args.annotations))
        if args.annotations
        else load_default_target_annotations()
    )
    ledger = load_target_review_ledger(Path(args.ledger))
    updated, report = apply_target_review_ledger(
        manifest,
        ledger,
        require_source_checksum=not args.allow_missing_source_checksum,
        generator_version=args.generator_version,
    )
    output_annotations = canonical_target_annotations_json(updated)
    if args.output_annotations:
        Path(args.output_annotations).write_text(output_annotations, encoding="utf-8")
    else:
        sys.stdout.write(output_annotations)
    report_json = canonical_target_review_apply_report_json(report)
    if args.output_report:
        Path(args.output_report).write_text(report_json, encoding="utf-8")
    return 0


def _gt_targets_convert_rayfronts(args: argparse.Namespace) -> int:
    manifest = convert_rayfronts_bbox_annotations(
        Path(args.input),
        scene_id=args.scene,
        spawn_offset_xyz_m=(args.spawn_x, args.spawn_y, args.spawn_z),
        source_path=args.source_path,
    )
    output = canonical_target_annotations_json(manifest)
    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
    else:
        sys.stdout.write(output)
    return 0


def _gt_targets_bind_usd_prims(args: argparse.Namespace) -> int:
    manifest = (
        load_target_annotations(Path(args.annotations))
        if args.annotations
        else load_default_target_annotations()
    )
    prims = load_usd_prim_candidate_manifest(Path(args.prim_candidates))
    updated, report = bind_target_annotations_to_usd_prims(
        manifest,
        prims,
        max_center_distance_m=args.max_center_distance,
        max_size_l1_delta_m=args.max_size_l1_delta,
        ambiguity_margin_m=args.ambiguity_margin,
        require_unique=args.require_unique,
        fail_on_ambiguous=args.fail_on_ambiguous,
        only_unbound=args.only_unbound,
        generator_version=args.generator_version,
    )
    if args.output_annotations:
        Path(args.output_annotations).write_text(
            canonical_target_annotations_json(updated),
            encoding="utf-8",
        )
    report_json = canonical_target_prim_binding_report_json(report)
    if args.output_report:
        Path(args.output_report).write_text(report_json, encoding="utf-8")
    else:
        sys.stdout.write(report_json)
    return 0 if report.status == "ok" else 2


def _add_gt_commands(subparsers: argparse._SubParsersAction) -> None:
    gt = subparsers.add_parser("gt", help="inspect and validate ground-truth artifacts")
    gt_commands = gt.add_subparsers(dest="gt_command", required=True)

    traversability = gt_commands.add_parser(
        "traversability",
        help="validate traversability ground truth",
    )
    traversability_commands = traversability.add_subparsers(
        dest="traversability_command",
        required=True,
    )

    schema = traversability_commands.add_parser(
        "schema",
        help="write the traversability metadata JSON schema",
    )
    schema.set_defaults(handler=_gt_traversability_schema)

    validate = traversability_commands.add_parser(
        "validate",
        help="validate traversability metadata and NPZ arrays",
    )
    validate.add_argument("--metadata", required=True, help="traversability metadata YAML")
    validate.add_argument("--npz", required=True, help="traversability arrays NPZ")
    validate.set_defaults(handler=_gt_traversability_validate)

    export_nav2 = traversability_commands.add_parser(
        "export-nav2",
        help="export a Nav2 map_server YAML+PGM from traversability arrays",
    )
    export_nav2.add_argument("--metadata", required=True, help="traversability metadata YAML")
    export_nav2.add_argument("--npz", required=True, help="traversability arrays NPZ")
    export_nav2.add_argument("--output-dir", required=True, help="directory for YAML+PGM files")
    export_nav2.add_argument("--stem", default="traversability", help="output file stem")
    export_nav2.add_argument("--occupied-thresh", type=float, default=0.65)
    export_nav2.add_argument("--free-thresh", type=float, default=0.196)
    export_nav2.set_defaults(handler=_gt_traversability_export_nav2)

    package = traversability_commands.add_parser(
        "package",
        help="write deterministic metadata, NPZ, Nav2 map and checksum manifest",
    )
    package.add_argument("--metadata", required=True, help="source traversability metadata YAML")
    package.add_argument("--npz", required=True, help="source traversability arrays NPZ")
    package.add_argument("--output-dir", required=True, help="directory for packaged artifact")
    package.add_argument("--stem", default="traversability", help="output file stem")
    package.add_argument("--no-nav2", action="store_true", help="skip Nav2 YAML+PGM export")
    package.add_argument("--occupied-thresh", type=float, default=0.65)
    package.add_argument("--free-thresh", type=float, default=0.196)
    package.set_defaults(handler=_gt_traversability_package)

    reach_region = traversability_commands.add_parser(
        "reach-region",
        help="recalibrate the reachable region with the 1.5x UGV-width corridor rule",
    )
    reach_region.add_argument("--metadata", required=True, help="source traversability metadata YAML")
    reach_region.add_argument("--npz", required=True, help="source traversability arrays NPZ")
    reach_region.add_argument("--output-dir", required=True, help="directory for the reach-region artifact")
    reach_region.add_argument(
        "--stem",
        default="retro_p1_03_profiled_roi_0p05_band_1p5w",
        help="output file stem",
    )
    reach_region.add_argument(
        "--clearance-margin-m",
        type=float,
        default=DEFAULT_REACH_CLEARANCE_MARGIN_M,
        help="extra clearance to non-traversable cells (default 0.1075 m = 1.5x0.430 m corridor)",
    )
    reach_region.add_argument(
        "--footprint-width-m",
        type=float,
        default=DEFAULT_REACH_FOOTPRINT_WIDTH_M,
        help="UGV width used to derive the corridor rule (default 0.430 m)",
    )
    reach_region.add_argument("--no-nav2", action="store_true", help="skip Nav2 YAML+PGM export")
    reach_region.set_defaults(handler=_gt_traversability_reach_region)

    sweep_footprint = traversability_commands.add_parser(
        "sweep-footprint",
        help="run deterministic Jackal footprint sweep over raycast terrain arrays",
    )
    sweep_footprint.add_argument("--metadata", required=True, help="raycast traversability metadata YAML")
    sweep_footprint.add_argument("--npz", required=True, help="raycast terrain arrays NPZ")
    sweep_footprint.add_argument("--output-dir", required=True, help="directory for swept artifact files")
    sweep_footprint.add_argument("--stem", default="traversability_footprint", help="output file stem")
    sweep_footprint.add_argument("--footprint-length", type=float, default=0.508)
    sweep_footprint.add_argument("--footprint-width", type=float, default=0.430)
    sweep_footprint.add_argument(
        "--footprint-report",
        help="verified Jackal asset report JSON; when set, derive footprint length/width from collisions",
    )
    sweep_footprint.add_argument("--footprint-padding", type=float, default=0.025)
    sweep_footprint.add_argument("--footprint-robot-root", default="/jackal")
    sweep_footprint.add_argument("--yaw-samples", type=int, default=16)
    sweep_footprint.add_argument("--max-slope-rad", type=float, default=np.deg2rad(15.0))
    sweep_footprint.add_argument("--max-step-height", type=float, default=0.10)
    sweep_footprint.add_argument("--min-overhead-clearance", type=float, default=0.50)
    sweep_footprint.add_argument("--blocked-cost", type=float, default=1.0e6)
    sweep_footprint.add_argument("--generator-version", default="p1-02")
    sweep_footprint.add_argument("--export-nav2", action="store_true", help="also write Nav2 YAML+PGM")
    sweep_footprint.add_argument("--occupied-thresh", type=float, default=0.65)
    sweep_footprint.add_argument("--free-thresh", type=float, default=0.196)
    sweep_footprint.set_defaults(handler=_gt_traversability_sweep_footprint)

    rollout = traversability_commands.add_parser(
        "rollout-report",
        help="validate Jackal rollout sample outcomes against traversability labels",
    )
    rollout.add_argument("--samples", required=True, help="JSONL rollout samples")
    rollout.add_argument("--min-samples", type=int, default=200)
    rollout.add_argument("--min-consistency", type=float, default=0.98)
    rollout.add_argument("--max-mismatches", type=int, default=50)
    rollout.add_argument("--output", help="output report JSON; stdout if omitted")
    rollout.set_defaults(handler=_gt_traversability_rollout_report)

    mismatch_review = traversability_commands.add_parser(
        "mismatch-review",
        help="review static/dynamic traversability mismatches and required artifacts",
    )
    mismatch_review.add_argument("--samples", required=True, help="JSONL rollout samples")
    mismatch_review.add_argument(
        "--screenshot-manifest",
        help="JSON object mapping mismatched sample_id to screenshot path",
    )
    mismatch_review.add_argument(
        "--review-annotations",
        help="JSON object mapping mismatched sample_id to final disposition text",
    )
    mismatch_review.add_argument(
        "--no-require-screenshots",
        action="store_true",
        help="do not fail mismatches that lack screenshot paths",
    )
    mismatch_review.add_argument(
        "--no-require-final-dispositions",
        action="store_true",
        help="do not fail mismatches that lack final disposition text",
    )
    mismatch_review.add_argument("--output", help="output review JSON; stdout if omitted")
    mismatch_review.set_defaults(handler=_gt_traversability_mismatch_review)

    calibrate_thresholds = traversability_commands.add_parser(
        "calibrate-thresholds",
        help="derive Jackal slope/step thresholds from standard ground-testbed outcomes",
    )
    calibrate_thresholds.add_argument("--trace", required=True, help="JSONL testbed outcome trace")
    calibrate_thresholds.add_argument(
        "--robot-id",
        default="isaacsim.clearpath_jackal",
        help="robot identifier written into the versioned threshold config",
    )
    calibrate_thresholds.add_argument(
        "--testbed-version",
        default="airground-jackal-ground-testbed-v1",
        help="standard testbed version written into the report/config",
    )
    calibrate_thresholds.add_argument("--max-tilt-rad", type=float, default=0.7)
    calibrate_thresholds.add_argument(
        "--output-report",
        help="output calibration report JSON; stdout if omitted",
    )
    calibrate_thresholds.add_argument(
        "--output-config",
        help="write versioned threshold YAML when calibration status is ok",
    )
    calibrate_thresholds.set_defaults(handler=_gt_traversability_calibrate_thresholds)

    targets = gt_commands.add_parser("targets", help="validate target instance annotations")
    target_commands = targets.add_subparsers(dest="targets_command", required=True)

    target_schema = target_commands.add_parser(
        "schema",
        help="write the target annotation JSON schema",
    )
    target_schema.set_defaults(handler=_gt_targets_schema)

    target_validate = target_commands.add_parser(
        "validate",
        help="validate target annotations",
    )
    target_validate.add_argument(
        "--annotations",
        help="target annotation JSON/YAML; defaults to packaged RetroNeighborhood annotations",
    )
    target_validate.set_defaults(handler=_gt_targets_validate)

    target_audit = target_commands.add_parser(
        "audit",
        help="audit target annotation completeness for release gates",
    )
    target_audit.add_argument(
        "--annotations",
        help="target annotation JSON/YAML; defaults to packaged RetroNeighborhood annotations",
    )
    target_audit.add_argument("--require-source-path", action="store_true")
    target_audit.add_argument("--require-usd-prim", action="store_true")
    target_audit.add_argument("--require-verified", action="store_true")
    target_audit.add_argument("--require-review-version", action="store_true")
    target_audit.add_argument("--max-issues", type=int, default=100)
    target_audit.add_argument("--output", help="output audit report JSON; stdout if omitted")
    target_audit.set_defaults(handler=_gt_targets_audit)

    convert = target_commands.add_parser(
        "convert-rayfronts",
        help="convert RayFronts class+bbox JSON to target annotations",
    )
    convert.add_argument("--input", required=True, help="RayFronts annotation JSON")
    convert.add_argument("--output", help="output target annotation JSON; stdout if omitted")
    convert.add_argument(
        "--source-path",
        help="stable source path to store in output; defaults to the input argument text",
    )
    convert.add_argument("--scene", default="RetroNeighborhood", choices=SCENE_IDS)
    convert.add_argument("--spawn-x", type=float, default=0.0)
    convert.add_argument("--spawn-y", type=float, default=0.0)
    convert.add_argument("--spawn-z", type=float, default=0.0)
    convert.set_defaults(handler=_gt_targets_convert_rayfronts)

    bind_prims = target_commands.add_parser(
        "bind-usd-prims",
        help="bind target annotations to exported USD prim candidate paths",
    )
    bind_prims.add_argument(
        "--annotations",
        help="target annotation JSON/YAML; defaults to packaged RetroNeighborhood annotations",
    )
    bind_prims.add_argument(
        "--prim-candidates",
        required=True,
        help="USD prim candidate manifest from the Isaac/USD exporter",
    )
    bind_prims.add_argument(
        "--output-annotations",
        help="write updated target annotations with usd_prim_path fields",
    )
    bind_prims.add_argument(
        "--output-report",
        help="write binding report JSON; stdout if omitted",
    )
    bind_prims.add_argument("--max-center-distance", type=float, default=3.0)
    bind_prims.add_argument("--max-size-l1-delta", type=float)
    bind_prims.add_argument("--ambiguity-margin", type=float, default=0.25)
    bind_prims.add_argument(
        "--only-unbound",
        action="store_true",
        help="keep already-bound instances untouched and only bind instances without usd_prim_path",
    )
    bind_prims.add_argument("--require-unique", action="store_true")
    bind_prims.add_argument("--fail-on-ambiguous", action="store_true")
    bind_prims.add_argument("--generator-version", default="p1-05b")
    bind_prims.set_defaults(handler=_gt_targets_bind_usd_prims)

    build_regions = target_commands.add_parser(
        "build-confirmation-regions",
        help="attach traversability-filtered UGV confirmation candidates",
    )
    build_regions.add_argument(
        "--annotations",
        help="target annotation JSON/YAML; defaults to packaged RetroNeighborhood annotations",
    )
    build_regions.add_argument("--metadata", required=True, help="traversability metadata YAML")
    build_regions.add_argument("--npz", required=True, help="traversability arrays NPZ")
    build_regions.add_argument("--output", help="output target annotation JSON; stdout if omitted")
    build_regions.add_argument("--min-distance", type=float, default=1.5)
    build_regions.add_argument("--max-distance", type=float, default=8.0)
    build_regions.add_argument("--radial-step", type=float, default=0.5)
    build_regions.add_argument("--angle-count", type=int, default=32)
    build_regions.add_argument("--max-poses-per-target", type=int, default=128)
    build_regions.add_argument("--proxy-visible-fraction", type=float, default=1.0)
    build_regions.set_defaults(handler=_gt_targets_build_confirmation_regions)

    visibility = target_commands.add_parser(
        "visibility-occlusion",
        help="estimate target visibility and occlusion difficulty from a traversability grid",
    )
    visibility.add_argument(
        "--annotations",
        help="target annotation JSON/YAML; defaults to packaged RetroNeighborhood annotations",
    )
    visibility.add_argument("--metadata", required=True, help="traversability metadata YAML")
    visibility.add_argument("--npz", required=True, help="traversability arrays NPZ")
    visibility.add_argument("--output", help="output metrics JSON; stdout if omitted")
    visibility.add_argument(
        "--uav-altitude",
        type=float,
        action="append",
        help="UAV altitude above grid height to sample; repeatable",
    )
    visibility.add_argument("--min-range", type=float, default=1.0)
    visibility.add_argument("--max-range", type=float, default=35.0)
    visibility.add_argument("--horizontal-fov", type=float, default=1.5707963267948966)
    visibility.add_argument("--yaw-samples", type=int, default=8)
    visibility.add_argument("--sample-stride-cells", type=int, default=1)
    visibility.add_argument("--ray-step", type=float, help="2D raycast step in meters")
    visibility.set_defaults(handler=_gt_targets_visibility_occlusion)

    visibility_at_pose = target_commands.add_parser(
        "visibility-at-pose",
        help="check whether one observer pose can see the requested targets",
    )
    visibility_at_pose.add_argument(
        "--annotations",
        help="target annotation JSON/YAML; defaults to packaged RetroNeighborhood annotations",
    )
    visibility_at_pose.add_argument("--metadata", required=True, help="traversability metadata YAML")
    visibility_at_pose.add_argument("--npz", required=True, help="traversability arrays NPZ")
    visibility_at_pose.add_argument("--pose", nargs=2, type=float, required=True, metavar=("X", "Y"))
    visibility_at_pose.add_argument(
        "--observer-height",
        action="append",
        type=float,
        help="observer camera height above the local ground (default 0.3 and 0.45 m)",
    )
    visibility_at_pose.add_argument(
        "--instance",
        action="append",
        help="target instance id to check; repeatable (default: every instance)",
    )
    visibility_at_pose.add_argument("--min-range", type=float, default=1.0)
    visibility_at_pose.add_argument("--max-range", type=float, default=35.0)
    visibility_at_pose.add_argument("--ray-step", type=float, default=0.25)
    visibility_at_pose.add_argument("--output", help="output JSON; stdout if omitted")
    visibility_at_pose.set_defaults(handler=_gt_targets_visibility_at_pose)

    confirmation_visibility = target_commands.add_parser(
        "validate-confirmation-visibility",
        help="validate confirmation regions with a grid/OBB visibility proxy",
    )
    confirmation_visibility.add_argument(
        "--annotations",
        help="target annotation JSON/YAML; defaults to packaged RetroNeighborhood annotations",
    )
    confirmation_visibility.add_argument("--metadata", required=True, help="traversability metadata YAML")
    confirmation_visibility.add_argument("--npz", required=True, help="traversability arrays NPZ")
    confirmation_visibility.add_argument("--output", help="output report JSON; stdout if omitted")
    confirmation_visibility.add_argument("--min-distance", type=float, default=1.5)
    confirmation_visibility.add_argument("--max-distance", type=float, default=8.0)
    confirmation_visibility.add_argument("--horizontal-fov", type=float, default=1.5707963267948966)
    confirmation_visibility.add_argument("--min-visible-fraction", type=float, default=0.2)
    confirmation_visibility.add_argument("--required-consecutive-frames", type=int, default=5)
    confirmation_visibility.add_argument("--ray-step", type=float, help="2D raycast step in meters")
    confirmation_visibility.set_defaults(handler=_gt_targets_validate_confirmation_visibility)

    confirmation_sensor_trace = target_commands.add_parser(
        "validate-confirmation-sensor-trace",
        help="validate continuous real sensor-frame confirmation visibility JSONL evidence",
    )
    confirmation_sensor_trace.add_argument(
        "--annotations",
        help="target annotation JSON/YAML; defaults to packaged RetroNeighborhood annotations",
    )
    confirmation_sensor_trace.add_argument("--trace", required=True, help="sensor-frame trace JSONL")
    confirmation_sensor_trace.add_argument("--output", help="output report JSON; stdout if omitted")
    confirmation_sensor_trace.add_argument("--min-distance", type=float, default=1.5)
    confirmation_sensor_trace.add_argument("--max-distance", type=float, default=8.0)
    confirmation_sensor_trace.add_argument("--horizontal-fov", type=float, default=1.5707963267948966)
    confirmation_sensor_trace.add_argument("--min-visible-fraction", type=float, default=0.2)
    confirmation_sensor_trace.add_argument("--required-consecutive-frames", type=int, default=5)
    confirmation_sensor_trace.add_argument(
        "--max-frame-gap",
        type=float,
        default=0.15,
        help="maximum sim-time gap between consecutive visible frames",
    )
    confirmation_sensor_trace.add_argument(
        "--no-require-raycast-evidence",
        action="store_true",
        help="allow trace frames without ray_count evidence",
    )
    confirmation_sensor_trace.set_defaults(handler=_gt_targets_validate_confirmation_sensor_trace)

    confirmation_evidence = target_commands.add_parser(
        "build-confirmation-evidence",
        help="build RayFronts full-mission UGV confirmation evidence from sensor-frame trace",
    )
    confirmation_evidence.add_argument(
        "--annotations",
        help="target annotation JSON/YAML; defaults to packaged RetroNeighborhood annotations",
    )
    confirmation_evidence.add_argument("--trace", required=True, help="sensor-frame trace JSONL")
    confirmation_evidence.add_argument("--target-id", required=True, help="target instance id")
    confirmation_evidence.add_argument("--report-id", required=True, help="UAV detection report id to bind")
    confirmation_evidence.add_argument(
        "--nav2-goal-reached",
        action="store_true",
        help="assert evaluator observed a successful UGV Nav2 goal result",
    )
    confirmation_evidence.add_argument("--output", help="output evidence JSON; stdout if omitted")
    confirmation_evidence.add_argument("--min-distance", type=float, default=1.5)
    confirmation_evidence.add_argument("--max-distance", type=float, default=8.0)
    confirmation_evidence.add_argument("--horizontal-fov", type=float, default=1.5707963267948966)
    confirmation_evidence.add_argument("--min-visible-fraction", type=float, default=0.2)
    confirmation_evidence.add_argument("--required-consecutive-frames", type=int, default=5)
    confirmation_evidence.add_argument(
        "--max-frame-gap",
        type=float,
        default=0.15,
        help="maximum sim-time gap between consecutive visible frames",
    )
    confirmation_evidence.add_argument(
        "--no-require-raycast-evidence",
        action="store_true",
        help="allow trace frames without ray_count evidence",
    )
    confirmation_evidence.set_defaults(handler=_gt_targets_build_confirmation_evidence)

    review = target_commands.add_parser(
        "review",
        help="render top-down and first-person SVG review artifacts for target annotations",
    )
    review.add_argument(
        "--annotations",
        help="target annotation JSON/YAML; defaults to packaged RetroNeighborhood annotations",
    )
    review.add_argument("--output-dir", required=True, help="directory for SVG and manifest outputs")
    review.add_argument("--max-targets", type=int, help="render only the first N targets")
    review.add_argument("--width", type=int, default=1200, help="SVG canvas width in pixels")
    review.add_argument("--height", type=int, default=900, help="SVG canvas height in pixels")
    review.add_argument("--camera-x", type=float, help="first-person camera X in map frame")
    review.add_argument("--camera-y", type=float, help="first-person camera Y in map frame")
    review.add_argument("--camera-z", type=float, help="first-person camera Z in map frame")
    review.add_argument("--camera-yaw", type=float, help="first-person camera yaw in radians")
    review.add_argument("--horizontal-fov", type=float, default=1.5707963267948966)
    review.add_argument("--vertical-fov", type=float, default=1.0471975511965976)
    review.add_argument("--max-distance", type=float, default=120.0)
    review.set_defaults(handler=_gt_targets_review)


    review_template = target_commands.add_parser(
        "review-ledger-template",
        help="build a safe draft template for human target-review ledger authoring",
    )
    review_template.add_argument(
        "--annotations",
        help="target annotation JSON/YAML; defaults to packaged RetroNeighborhood annotations",
    )
    review_template.add_argument("--review-queue", required=True, help="target review queue JSON/YAML")
    review_template.add_argument("--review-version", required=True, help="review version to stamp into draft fields")
    review_template.add_argument(
        "--source-review-media",
        help="path to the MP4/contact-sheet review media humans should inspect",
    )
    review_template.add_argument("--output", help="output template JSON; stdout if omitted")
    review_template.add_argument("--generator-version", default="p1-05f")
    review_template.set_defaults(handler=_gt_targets_review_ledger_template)

    apply_review = target_commands.add_parser(
        "apply-review",
        help="apply a human target-review ledger to target annotations",
    )
    apply_review.add_argument(
        "--annotations",
        help="target annotation JSON/YAML; defaults to packaged RetroNeighborhood annotations",
    )
    apply_review.add_argument("--ledger", required=True, help="human review ledger JSON/YAML")
    apply_review.add_argument(
        "--output-annotations",
        help="write reviewed target annotations; stdout if omitted",
    )
    apply_review.add_argument(
        "--output-report",
        help="write review apply report JSON",
    )
    apply_review.add_argument(
        "--allow-missing-source-checksum",
        action="store_true",
        help="allow ledgers without source_annotations_sha256; mismatched checksums still fail",
    )
    apply_review.add_argument("--generator-version", default="p1-05e")
    apply_review.set_defaults(handler=_gt_targets_apply_review)


def _add_episode_commands(subparsers: argparse._SubParsersAction) -> None:
    episodes = subparsers.add_parser("episodes", help="validate episode manifests")
    episode_commands = episodes.add_subparsers(dest="episodes_command", required=True)

    validate = episode_commands.add_parser(
        "validate",
        help="validate the public episode manifest schema and counts",
    )
    validate.add_argument("--manifest", help="episode manifest YAML; defaults to packaged draft")
    validate.add_argument(
        "--output",
        choices=("summary", "canonical-json"),
        default="summary",
    )
    validate.set_defaults(handler=_episode_validate)

    schema = episode_commands.add_parser("schema", help="write the episode manifest JSON schema")
    schema.set_defaults(handler=_episode_schema)

    apply_timeouts = episode_commands.add_parser(
        "apply-timeouts",
        help="derive timeout_s from oracle completion times",
    )
    apply_timeouts.add_argument("--manifest", required=True, help="input episode manifest YAML/JSON")
    apply_timeouts.add_argument(
        "--oracle-times",
        required=True,
        help="YAML/JSON mapping from episode_id to oracle_time_s",
    )
    apply_timeouts.add_argument("--output", help="output manifest JSON; stdout if omitted")
    apply_timeouts.set_defaults(handler=_episode_apply_timeouts)

    hidden_summary = episode_commands.add_parser(
        "hidden-summary",
        help="write redacted hidden-test release metadata with a salted manifest checksum",
    )
    hidden_summary.add_argument("--manifest", required=True, help="hidden-test episode manifest")
    hidden_summary.add_argument("--output", help="output metadata JSON; stdout if omitted")
    salt = hidden_summary.add_mutually_exclusive_group(required=True)
    salt.add_argument("--salt", help="checksum salt value; not echoed in output")
    salt.add_argument("--salt-file", help="file containing checksum salt bytes")
    salt.add_argument("--salt-env", help="environment variable containing checksum salt")
    hidden_summary.set_defaults(handler=_episode_hidden_summary)

    generate = episode_commands.add_parser(
        "generate-from-candidates",
        help="sample a balanced public or hidden manifest from pre-filtered candidates",
    )
    generate.add_argument("--candidates", required=True, help="candidate pool YAML/JSON")
    generate.add_argument("--output", help="output manifest JSON; stdout if omitted")
    generate.add_argument("--split", required=True, choices=("public", "hidden_test"))
    generate.add_argument(
        "--exclude-manifest",
        action="append",
        help="manifest whose start/target signatures cannot be reused; repeatable",
    )
    generate.add_argument(
        "--seed-base",
        type=int,
        help="first generated episode seed; defaults to split-specific seed space",
    )
    generate.add_argument(
        "--status",
        choices=("draft", "released"),
        default="released",
        help="output manifest status; released requires the fixed 60 episode contract",
    )
    generate.add_argument(
        "--use-oracle-timeouts",
        action="store_true",
        help="derive timeout_s from candidate oracle estimated completion time",
    )
    generate.set_defaults(handler=_episode_generate_from_candidates)

    difficulty = episode_commands.add_parser(
        "difficulty-metadata",
        help="derive fixed tercile difficulty boundaries from a candidate pool",
    )
    difficulty.add_argument("--candidates", required=True, help="candidate pool YAML/JSON")
    difficulty.add_argument("--output", help="output metadata JSON; stdout if omitted")
    difficulty.add_argument(
        "--validate-labels",
        action="store_true",
        help="fail when candidate easy/medium/hard labels disagree with computed terciles",
    )
    difficulty.set_defaults(handler=_episode_difficulty_metadata)

    audit_difficulty = episode_commands.add_parser(
        "audit-difficulty",
        help="audit frozen difficulty metadata against a candidate pool",
    )
    audit_difficulty.add_argument("--candidates", required=True, help="candidate pool YAML/JSON")
    audit_difficulty.add_argument("--metadata", required=True, help="difficulty metadata YAML/JSON")
    audit_difficulty.add_argument("--output", help="output audit JSON; stdout if omitted")
    audit_difficulty.set_defaults(handler=_episode_audit_difficulty)

    audit_candidates = episode_commands.add_parser(
        "audit-candidates",
        help="audit candidate-pool readiness before manifest generation",
    )
    audit_candidates.add_argument("--candidates", required=True, help="candidate pool YAML/JSON")
    audit_candidates.add_argument("--output", help="output audit JSON; stdout if omitted")
    audit_candidates.add_argument(
        "--require-oracle",
        action="store_true",
        help="fail if any candidate lacks oracle/path evidence",
    )
    audit_candidates.add_argument("--max-issues", type=int, default=100)
    audit_candidates.set_defaults(handler=_episode_audit_candidates)

    attach_oracle = episode_commands.add_parser(
        "attach-oracle",
        help="attach oracle/path evidence to a candidate pool by candidate_id",
    )
    attach_oracle.add_argument("--candidates", required=True, help="candidate pool YAML/JSON")
    attach_oracle.add_argument("--oracle-evidence", required=True, help="oracle evidence YAML/JSON")
    attach_oracle.add_argument("--output", help="output candidate pool JSON; stdout if omitted")
    attach_oracle.add_argument(
        "--require-all",
        action="store_true",
        help="fail unless every candidate has existing or provided oracle evidence",
    )
    attach_oracle.add_argument(
        "--allow-extra",
        action="store_true",
        help="ignore oracle evidence records for candidate ids not in the pool",
    )
    attach_oracle.set_defaults(handler=_episode_attach_oracle)

    grid_oracle = episode_commands.add_parser(
        "grid-oracle-estimate",
        help="write deterministic candidate-level grid/path oracle estimates",
    )
    grid_oracle.add_argument("--candidates", required=True, help="candidate pool YAML/JSON")
    grid_oracle.add_argument(
        "--targets",
        required=True,
        help="reviewed target annotations with confirmation regions",
    )
    grid_oracle.add_argument("--output", help="oracle evidence JSON; stdout if omitted")
    grid_oracle.add_argument("--source", default="airground-grid-oracle-estimate-v1")
    grid_oracle.add_argument("--uav-speed", type=float, default=4.0)
    grid_oracle.add_argument("--ugv-speed", type=float, default=0.8)
    grid_oracle.add_argument("--detection-overhead-per-target", type=float, default=1.5)
    grid_oracle.add_argument("--confirmation-overhead-per-target", type=float, default=1.0)
    grid_oracle.set_defaults(handler=_episode_grid_oracle_estimate)

    build_candidates = episode_commands.add_parser(
        "build-candidates",
        help="assemble a candidate pool from paired starts, target GT, and difficulty metrics",
    )
    build_candidates.add_argument("--paired-starts", required=True, help="paired-starts JSON artifact")
    build_candidates.add_argument("--targets", required=True, help="target annotations with confirmation regions")
    build_candidates.add_argument("--visibility-occlusion", required=True, help="visibility/occlusion report JSON")
    build_candidates.add_argument("--metadata", required=True, help="traversability metadata YAML")
    build_candidates.add_argument("--npz", required=True, help="traversability arrays NPZ")
    build_candidates.add_argument("--output", help="output candidate pool JSON; stdout if omitted")
    build_candidates.add_argument("--difficulty-version", default="difficulty-retro-v1")
    build_candidates.add_argument("--source", default="airground-candidate-pool-builder-v1")
    build_candidates.add_argument("--seed-material", default="benchmark-v1.0-retro")
    build_candidates.add_argument("--max-single", type=int, default=120)
    build_candidates.add_argument("--max-unordered", type=int, default=120)
    build_candidates.add_argument("--max-sequential", type=int, default=120)
    build_candidates.add_argument("--multi-target-size", type=int, choices=(2, 3), default=2)
    build_candidates.add_argument("--min-start-confirmation-distance", type=float, default=1.5)
    build_candidates.add_argument("--gt-traversability", required=True)
    build_candidates.add_argument("--gt-targets", required=True)
    build_candidates.add_argument("--gt-confirmation-regions", required=True)
    build_candidates.add_argument("--gt-checksum", required=True)
    build_candidates.set_defaults(handler=_episode_build_candidates)

    paired_starts = episode_commands.add_parser(
        "paired-starts",
        help="generate UGV + docked-UAV paired start candidates from GT artifacts",
    )
    paired_starts.add_argument("--targets", required=True, help="target annotations with confirmation regions")
    paired_starts.add_argument("--metadata", required=True, help="traversability metadata YAML")
    paired_starts.add_argument("--npz", required=True, help="traversability arrays NPZ")
    paired_starts.add_argument("--output", help="output paired-starts JSON; stdout if omitted")
    paired_starts.add_argument("--ceiling-npz", help="optional NPZ containing ceiling height array")
    paired_starts.add_argument("--ceiling-key", default="ceiling_height", help="ceiling height array key")
    paired_starts.add_argument("--seed-material", default="benchmark-v1.0-retro")
    paired_starts.add_argument("--uav-parent-frame", choices=("ugv/base_link", "ugv/platform"), default="ugv/platform")
    paired_starts.add_argument("--uav-x", type=float, default=0.0)
    paired_starts.add_argument("--uav-y", type=float, default=0.0)
    paired_starts.add_argument("--uav-z", type=float, default=0.45)
    paired_starts.add_argument("--uav-yaw", type=float, default=0.0)
    paired_starts.add_argument("--min-takeoff-clearance", type=float, default=1.0)
    paired_starts.add_argument("--exclude-confirmation-radius", type=float, default=1.5)
    paired_starts.add_argument("--max-starts-per-component", type=int, default=16)
    paired_starts.set_defaults(handler=_episode_paired_starts)

    release_pair = episode_commands.add_parser(
        "release-pair",
        help="generate public and private hidden-test release artifacts together",
    )
    release_pair.add_argument("--candidates", required=True, help="candidate pool YAML/JSON")
    release_pair.add_argument("--output-dir", required=True, help="directory for release artifacts")
    release_pair.add_argument("--public-seed-base", type=int, help="first public episode seed")
    release_pair.add_argument("--hidden-seed-base", type=int, help="first hidden episode seed")
    release_pair.add_argument("--overwrite", action="store_true", help="allow writing into a non-empty output dir")
    release_pair.add_argument(
        "--use-oracle-timeouts",
        action="store_true",
        help="derive timeout_s from candidate oracle estimated completion time",
    )
    release_salt = release_pair.add_mutually_exclusive_group(required=True)
    release_salt.add_argument("--salt", help="hidden manifest checksum salt; not written to outputs")
    release_salt.add_argument("--salt-file", help="file containing hidden manifest checksum salt")
    release_salt.add_argument("--salt-env", help="environment variable containing hidden manifest checksum salt")
    release_pair.set_defaults(handler=_episode_release_pair)

    audit = episode_commands.add_parser(
        "audit-gt",
        help="cross-check a manifest against traversability and target GT artifacts",
    )
    audit.add_argument("--manifest", required=True, help="episode manifest YAML/JSON")
    audit.add_argument("--targets", required=True, help="target annotation JSON/YAML")
    audit.add_argument("--metadata", required=True, help="traversability metadata YAML")
    audit.add_argument("--npz", required=True, help="traversability arrays NPZ")
    audit.add_argument("--output", help="output audit report JSON; stdout if omitted")
    audit.add_argument(
        "--allow-immediate-confirmation",
        action="store_true",
        help="do not fail when UGV starts inside a target confirmation region",
    )
    audit.set_defaults(handler=_episode_audit_ground_truth)


def _add_evaluate_command(subparsers: argparse._SubParsersAction) -> None:
    evaluate = subparsers.add_parser("evaluate", help="summarize a run event trace")
    source = evaluate.add_mutually_exclusive_group(required=True)
    source.add_argument("--run", help="run directory containing events.jsonl")
    source.add_argument("--events", help="explicit events JSONL file")
    evaluate.add_argument("--output-dir", help="write summary.json and summary.csv")
    evaluate.add_argument(
        "--check-artifacts",
        action="store_true",
        help=(
            "validate run metric evidence and persisted artifacts; requires --run "
            "and writes a metrics_validation_report.json when --output-dir is set"
        ),
    )
    evaluate.add_argument(
        "--require-success",
        action="store_true",
        help="with --check-artifacts, require mission_success=true",
    )
    evaluate.set_defaults(handler=_evaluate)


def _add_tasks_commands(subparsers: argparse._SubParsersAction) -> None:
    tasks = subparsers.add_parser(
        "tasks",
        help="build and inspect the UGV-centric open-set object-goal task catalog",
    )
    task_commands = tasks.add_subparsers(dest="tasks_command", required=True)

    build_catalog = task_commands.add_parser(
        "build-catalog",
        help="resolve upstream RAVEN task word lists against reachable instances",
    )
    build_catalog.add_argument(
        "--targets",
        help="reviewed target annotation JSON with confirmation regions",
    )
    build_catalog.add_argument("--catalog-id", default=None)
    build_catalog.add_argument("--output", help="catalog JSON; stdout if omitted")
    build_catalog.add_argument(
        "--diagnostics-output",
        help="optional human-readable catalog status summary JSON",
    )
    build_catalog.set_defaults(handler=_tasks_build_catalog)


def _add_metrics_commands(subparsers: argparse._SubParsersAction) -> None:
    metrics = subparsers.add_parser(
        "metrics",
        help="compute UGV-centric Progress / PPL metrics from run traces",
    )
    metric_commands = metrics.add_subparsers(dest="metrics_command", required=True)

    ugv_progress = metric_commands.add_parser(
        "ugv-progress",
        help="compute the UGV-centric Progress / PPL / SR / SPL report for one episode",
    )
    ugv_progress.add_argument(
        "--trajectory",
        required=True,
        help="UGV pose trace: trajectory.parquet or events.jsonl",
    )
    ugv_progress.add_argument("--targets", required=True, help="target annotation JSON")
    ugv_progress.add_argument("--catalog", required=True, help="task catalog JSON")
    ugv_progress.add_argument("--task-id", required=True)
    ugv_progress.add_argument("--budget-s", required=True, type=float)
    ugv_progress.add_argument("--episode-id")
    ugv_progress.add_argument(
        "--traversability-npz",
        help="traversability NPZ used for the optimal-path (d_K) computation",
    )
    ugv_progress.add_argument(
        "--traversability-metadata",
        help="traversability metadata JSON paired with --traversability-npz",
    )
    ugv_progress.add_argument(
        "--arrival-regions",
        help=(
            "dense arrival-region raster NPZ (region_labels) used for the K predicate; "
            "K is rebuilt from the manifest OBBs and the traversability grid per instance "
            "whenever those are supplied, so overlapping bands are not lost to the raster's "
            "single label per cell"
        ),
    )
    ugv_progress.add_argument(
        "--arrival-region-index",
        help="region_index.json pairing region ids with the arrival-region labels",
    )
    ugv_progress.add_argument("--start-x", type=float)
    ugv_progress.add_argument("--start-y", type=float)
    ugv_progress.add_argument("--reach-tolerance-m", type=float, default=0.5)
    ugv_progress.add_argument(
        "--window-start-s",
        type=float,
        default=0.0,
        help=(
            "Start of the scored K window in simulated seconds (default 0 = "
            "episode start, the moment the simulation clock starts ticking).  "
            "The window ends at --window-start-s + --budget-s"
        ),
    )
    ugv_progress.add_argument("--output", help="report JSON; stdout if omitted")
    ugv_progress.add_argument("--output-dir", help="write report JSON plus sha256")
    ugv_progress.set_defaults(handler=_metrics_ugv_progress)

    aggregate = metric_commands.add_parser(
        "aggregate-progress",
        help="aggregate per-episode UGV progress reports into suite metrics",
    )
    aggregate.add_argument("--report", action="append", required=True)
    aggregate.add_argument("--output", help="aggregate JSON; stdout if omitted")
    aggregate.set_defaults(handler=_metrics_aggregate_progress)


def _add_run_command(subparsers: argparse._SubParsersAction) -> None:
    run = subparsers.add_parser(
        "run",
        help="run benchmark episodes and write run artifacts",
    )
    run.add_argument(
        "--episodes",
        help="episode manifest YAML; defaults to packaged benchmark-v1.0-retro draft",
    )
    run.add_argument("--agent", help="agent entrypoint or contract identifier")
    run.add_argument("--output-dir", required=True, help="directory for run artifacts")
    run.add_argument(
        "--mode",
        choices=("contract", "isaac"),
        default="contract",
        help="execution backend; isaac runs a real Docker/ROS smoke and never falls back to contract",
    )
    run.add_argument("--episode-id", action="append", help="episode id to run; repeatable")
    run.add_argument("--limit", type=int, help="run the first N selected episodes")
    run.add_argument(
        "--record-sensors",
        action="store_true",
        help="write optional MCAP sensor recording artifacts; disabled by default",
    )
    run.add_argument("--repo-root", default=".", help="repository root for isaac smoke runner lookup")
    run.add_argument("--isaac-container", default="isaac-sim", help="Docker container name for isaac mode")
    run.add_argument("--isaac-sample-count", type=int, default=6, help="real odometry sample count for isaac mode")
    run.add_argument("--isaac-timeout", type=float, default=60.0, help="real ROS sample timeout for isaac mode")
    run.add_argument(
        "--no-resource-guard",
        action="store_true",
        help="deprecated and rejected for isaac mode; host protection is mandatory",
    )
    run.add_argument(
        "--resource-guard-min-available-memory-gb",
        type=float,
        default=RESOURCE_GUARD_DEFAULT_MIN_AVAILABLE_MEMORY_GB,
        help="isaac mode only: fail before/during run when host available RAM drops below this GB floor",
    )
    run.add_argument(
        "--resource-guard-max-system-memory-fraction",
        type=float,
        default=RESOURCE_GUARD_DEFAULT_MAX_SYSTEM_MEMORY_FRACTION,
        help="isaac mode only: fail before/during run when host RAM used fraction exceeds this ceiling",
    )
    run.add_argument(
        "--resource-guard-max-gpu-memory-fraction",
        type=float,
        default=RESOURCE_GUARD_DEFAULT_MAX_GPU_MEMORY_FRACTION,
        help="isaac mode only: fail before/during run when any GPU memory used fraction exceeds this ceiling",
    )
    run.add_argument(
        "--resource-guard-max-consecutive-failures",
        type=int,
        default=RESOURCE_GUARD_DEFAULT_MAX_CONSECUTIVE_FAILURES,
        help="isaac mode only: terminate only after this many consecutive monitor samples exceed resource limits",
    )
    run.add_argument(
        "--resource-guard-poll-s",
        type=float,
        default=RESOURCE_GUARD_DEFAULT_POLL_S,
        help="isaac mode only: resource monitor poll interval in seconds",
    )
    run.add_argument(
        "--resource-guard-host-memory-max-gb",
        type=float,
        default=RESOURCE_GUARD_DEFAULT_HOST_MEMORY_MAX_GB,
        help="isaac mode only: hard RLIMIT_AS cap for the host CLI and its host child processes",
    )
    run.add_argument(
        "--resource-guard-profile",
        default=RESOURCE_GUARD_DEFAULT_PROFILE,
        help=(
            "isaac mode only: explicit guard profile; default keeps hard cgroup enforcement, "
            "lft-w02-rootless-no-cgroup accepts rootless Docker no-cgroup only with soft guard evidence"
        ),
    )
    run.add_argument(
        "--rayfronts-device",
        help="isaac RayFronts/VLFM mapper device override: auto, cpu, cuda, or cuda:<index>",
    )
    run.add_argument(
        "--rayfronts-baseline",
        action="store_true",
        help=(
            "isaac mode only: require live RayFronts public hypotheses and write "
            "RayFronts baseline policy evidence"
        ),
    )
    run.add_argument(
        "--rayfronts-baseline-mode",
        choices=("surface", "mapper", "vlfm"),
        default="surface",
        help=(
            "isaac mode only: 'surface' uses the public map-probe RayFronts health node; "
            "'mapper' starts the frontier mapper server; 'vlfm' starts the semantic VLFM mapper "
            "and requires mapper-derived evidence"
        ),
    )
    run.add_argument(
        "--require-rayfronts-physical-mission",
        action="store_true",
        help=(
            "isaac mode only: after a RayFronts run, require the full-mission physical gate "
            "to pass; rejects metrics smoke artifacts with millisecond confirmation, "
            "near-zero paths, or missing confirmation-region/Nav2/visibility evidence"
        ),
    )
    run.add_argument(
        "--rayfronts-full-mission-runner",
        action="store_true",
        help=(
            "isaac mode only: use AirStack run_rayfronts_full_mission.py instead of the "
            "metrics smoke collector; requires --rayfronts-baseline and fails unless the "
            "runner produces real Nav2/confirmation evidence"
        ),
    )
    run.add_argument(
        "--rayfronts-confirmation-evidence-dir",
        help="directory containing per-episode confirmation evidence JSON files",
    )
    run.add_argument(
        "--rayfronts-communication-evidence-dir",
        help="directory containing per-episode communication evidence JSON files",
    )
    run.add_argument(
        "--rayfronts-uav-control-evidence-dir",
        help="directory containing per-episode UAV control evidence JSON files",
    )
    run.add_argument(
        "--rayfronts-uav-control-adapter",
        action="store_true",
        help="run the RayFronts action to PX4 OFFBOARD UAV control adapter inside the full-mission runner",
    )
    run.add_argument(
        "--rayfronts-uav-control-target-altitude-m",
        type=float,
        default=1.45,
        help="PX4 OFFBOARD target altitude before the full-mission UAV search waypoint; default: 1.45",
    )
    run.add_argument(
        "--rayfronts-uav-control-px4-param",
        action="append",
        default=[],
        metavar="NAME=VALUE",
        help="PX4 parameter override applied by the UAV control runner before arming (repeatable)",
    )
    run.add_argument(
        "--rayfronts-uav-control-bootstrap-hover-s",
        type=float,
        default=0.0,
        help="Take off and hover this many seconds before the RayFronts hypothesis wait (0 disables)",
    )
    run.add_argument(
        "--rayfronts-uav-control-hover-s",
        type=float,
        default=2.0,
        help="stable PX4 hover duration before sending the full-mission UAV search waypoint; default: 2.0",
    )
    run.add_argument(
        "--rayfronts-uav-control-waypoint-max-distance-m",
        type=float,
        default=2.0,
        help="Maximum UAV search leg distance per sortie; default: 2.0",
    )
    run.add_argument(
        "--rayfronts-uav-control-search-sorties",
        type=int,
        default=1,
        help=(
            "Number of RayFronts frontier hops to fly before ending the UAV search "
            "(upstream-style continuous search); default: 1 (legacy single hop)"
        ),
    )
    run.add_argument(
        "--rayfronts-uav-control-search-budget-s",
        type=float,
        default=0.0,
        help="Simulated-time budget for the continuous UAV search loop; 0 disables the extra cap",
    )
    run.add_argument(
        "--rayfronts-uav-control-mission-budget-s",
        type=float,
        default=0.0,
        help=(
            "Total simulated mission budget measured from the episode start; also the K "
            "window.  0 disables the deadline.  When reached, the runner cancels the UAV "
            "search and the UGV lane, settles the artifacts and reports "
            "mission_budget_exhausted"
        ),
    )
    run.add_argument(
        "--rayfronts-uav-control-planner",
        choices=["offboard_direct", "droan"],
        default="offboard_direct",
        help=(
            "UAV search goal source: 'offboard_direct' streams the RayFronts hop to PX4 "
            "OFFBOARD (fork behaviour); 'droan' starts the upstream AirStack local chain "
            "(depth->disparity + droan_gl + trajectory_controller) and follows its "
            "collision-checked tracking point"
        ),
    )
    run.add_argument(
        "--ugv-goal-standoff-m",
        type=float,
        default=None,
        help=(
            "Standoff distance used for the *ideal* (report/visualisation only) UGV goal; "
            "the dispatched pose is the reachable cell closest to the structural anchor; "
            "runner default: 2.0"
        ),
    )
    run.add_argument(
        "--ugv-goal-anchor-radius-m",
        type=float,
        default=None,
        help=(
            "Radius around the communicated detection whose lethal costmap cells form the "
            "structural anchor (centroid); runner default: 3.0"
        ),
    )
    run.add_argument(
        "--ugv-goal-adjust-max-m",
        type=float,
        default=None,
        help=(
            "Maximum distance between the dispatched pose and the structural anchor; "
            "beyond it the detection is left undispatched; runner default: 3.0"
        ),
    )
    run.add_argument(
        "--ugv-goal-plan-probe-max",
        type=int,
        default=None,
        help=(
            "How many nearest reachable candidates are pre-checked with Nav2 "
            "compute_path_to_pose before dispatch; runner default: 4"
        ),
    )
    run.add_argument(
        "--ugv-goal-candidate-attempts",
        type=int,
        default=None,
        help=(
            "How many dispatch candidates to try per detection when the previous one "
            "did not reach; runner default: 1"
        ),
    )
    run.add_argument(
        "--ugv-goal-min-clearance-m",
        type=float,
        default=None,
        help=(
            "Minimum clearance from lethal cells required of the dispatched UGV pose. "
            "NavFn refuses to plan when its goal cell is INSCRIBED, and a UGV parked "
            "with less than ~0.5 m of clearance (0.215 m inscribed radius + ~0.3 m of "
            "manoeuvring room) cannot get out again; runner default: 0.0 (disabled)"
        ),
    )
    run.add_argument(
        "--ugv-motion-trace",
        action="store_true",
        help=(
            "Record ugv_motion_trace.jsonl for the whole episode (drivetrain stall/slip "
            "diagnostics); runner default: off"
        ),
    )
    run.add_argument(
        "--ugv-motion-trace-sample-hz",
        type=float,
        default=None,
        help="UGV motion trace sample rate in wall-clock hertz; runner default: 20.0",
    )
    run.add_argument(
        "--ugv-goal-timeout-s",
        type=float,
        default=None,
        help=(
            "Simulated-time budget for one UGV FIFO target (multi-target lane). "
            "On timeout the goal is cancelled, recorded unreachable and the next "
            "target is taken; runner default: 180.0"
        ),
    )
    run.add_argument(
        "--ugv-goal-first-timeout-s",
        type=float,
        default=None,
        help=(
            "Simulated-time budget for the *first* UGV FIFO target only "
            "(default: None = every target uses --ugv-goal-timeout-s). "
            "Injected-lane use: the first target only has to be touched while "
            "the second carries the long leg of the tour"
        ),
    )
    run.add_argument(
        "--ugv-fifo-max-targets",
        type=int,
        default=None,
        help="Maximum queued UGV detection targets; the runner default is 24",
    )
    run.add_argument(
        "--ugv-target-dedup-radius-m",
        type=float,
        default=None,
        help=(
            "Planar dedup radius between queued UGV targets, mirroring upstream's "
            "visited-cluster threshold; runner default: 10.0"
        ),
    )
    run.add_argument(
        "--ugv-inject-goal-position-m",
        default=None,
        help=(
            "DIAGNOSTIC ONLY: drive the UGV to this map-frame goal ('x,y[,z]') "
            "without waiting for a detection, to exercise Nav2 + the 3D obstacle "
            "layer in isolation.  Requires --rayfronts-full-mission-runner and "
            "--ugv-centric-lane; the run is marked ugv_injected_goal_diagnostic "
            "and is never a benchmark episode."
        ),
    )
    run.add_argument(
        "--ugv-inject-goal-note",
        default=None,
        help="free-form provenance note recorded with an injected UGV goal",
    )
    run.add_argument(
        "--ugv-inject-via-position-m",
        default=None,
        help=(
            "DIAGNOSTIC ONLY: one via waypoint per --ugv-inject-goal-position-m "
            "point ('x,y;x,y'; an empty entry means 'no via').  When the chosen "
            "plan probe's resampled worst cell is dirty the runner drives the via "
            "hop before the goal so the leg bypasses pinch corridors "
            "(2026-10-04 rule)."
        ),
    )
    run.add_argument(
        "--ugv-inject-target-instance-ids",
        default=None,
        help=(
            "DIAGNOSTIC ONLY: one reviewed instance id per "
            "--ugv-inject-goal-position-m point (';'-separated; an empty entry "
            "means 'match the point against every instance band').  The named "
            "instance's OBB defines the [1.5, 8.0] m goal band of the optimal "
            "route lane (2026-10-05 rule)."
        ),
    )
    run.add_argument(
        "--rayfronts-target-annotations",
        help="reviewed target annotations JSON/YAML for runner-side sensor confirmation evidence",
    )
    run.add_argument(
        "--rayfronts-confirmation-sensor-trace-dir",
        help="directory containing per-episode confirmation sensor trace JSONL files",
    )
    run.add_argument(
        "--rayfronts-nav2-map-yaml",
        help=(
            "Nav2 map_server YAML exported from traversability GT for the full-mission "
            "reset-support stack; if omitted, the runner tries to resolve it from the "
            "episode traversability reference"
        ),
    )
    run.add_argument(
        "--min-time-to-confirmation-s",
        type=float,
        default=5.0,
        help="minimum TTC for --require-rayfronts-physical-mission; default: 5.0",
    )
    run.add_argument(
        "--min-detection-to-confirmation-s",
        type=float,
        default=1.0,
        help="minimum D2C for --require-rayfronts-physical-mission; default: 1.0",
    )
    run.add_argument(
        "--min-uav-path-m",
        type=float,
        default=1.0,
        help="minimum UAV 3D path for --require-rayfronts-physical-mission; default: 1.0",
    )
    run.add_argument(
        "--min-ugv-path-m",
        type=float,
        default=1.0,
        help="minimum UGV planar path for --require-rayfronts-physical-mission; default: 1.0",
    )
    run.add_argument(
        "--no-reset-sensor-payloads",
        action="store_true",
        help=(
            "diagnostic only: do not require RGB/depth/LiDAR reset payload checksums "
            "from isaac mode"
        ),
    )
    run.add_argument(
        "--no-reset-airstack-trajectory-clear",
        action="store_true",
        help="diagnostic only: do not require AirStack trajectory buffer clear reset evidence in isaac mode",
    )
    run.add_argument(
        "--no-reset-stable-health-handshake",
        action="store_true",
        help="diagnostic only: do not require stable full-health reset handshake in isaac mode",
    )
    run.add_argument(
        "--no-reset-support-stack",
        action="store_true",
        help="diagnostic only: do not auto-start Nav2/RayFronts reset support stack in isaac mode",
    )
    run.add_argument(
        "--no-reset-support-postflight-check",
        action="store_true",
        help="diagnostic only: do not fail isaac mode on residual Nav2/RayFronts support processes",
    )
    run.add_argument(
        "--simulator-version",
        default=DEFAULT_ISAAC_SIMULATOR_VERSION,
        help=(
            "runtime simulator version recorded by isaac mode; "
            f"default: {DEFAULT_ISAAC_SIMULATOR_VERSION}"
        ),
    )
    run.add_argument(
        "--ros-distro",
        default=None,
        help="ROS distro recorded by isaac mode; default is inferred from --simulator-version",
    )
    run.add_argument("--overwrite", action="store_true", help="allow writing into a non-empty output dir")
    run.set_defaults(handler=_run)


def _replay_trajectory_video(args: argparse.Namespace) -> int:
    camera_specs = load_camera_specs(Path(args.camera_specs)) if args.camera_specs else None
    manifest = build_trajectory_video_manifest(
        Path(args.run_dir),
        Path(args.output_dir),
        scene_usd=Path(args.scene_usd) if args.scene_usd else None,
        fps=args.fps,
        width=args.width,
        height=args.height,
        review_window=args.review_window,
        review_k=args.review_k,
        review_pre_roll_s=args.review_pre_roll_s,
        review_tail_s=args.review_tail_s,
        ugv_progress_path=Path(args.ugv_progress) if args.ugv_progress else None,
        **({"camera_specs": camera_specs} if camera_specs is not None else {}),
    )
    replay_report = write_run_replay_manifest(Path(args.run_dir))
    if args.renderer_command:
        renderer_script = Path(args.renderer_script).expanduser().resolve(strict=True)
        command = [
            *args.renderer_command,
            str(renderer_script),
            "--video-manifest",
            str(Path(manifest["path"]).expanduser().resolve(strict=True)),
            "--output-dir",
            str(Path(args.output_dir).expanduser().resolve()),
        ]
        if args.scene_usd:
            command.extend(("--scene-usd", str(Path(args.scene_usd).expanduser().resolve(strict=True))))
        subprocess.run(command, check=True)
    result = {
        "manifest": manifest["path"],
        "replay_manifest_status": replay_report["status"],
        "render_window": manifest.get("render_window"),
        "renderer_executed": bool(args.renderer_command),
        "schema_version": "1.0.0",
        "status": "ok",
    }
    print(json.dumps(result, ensure_ascii=True, sort_keys=True, separators=(",", ":")) + "\n")
    return 0


def _add_replay_commands(subparsers: argparse._SubParsersAction) -> None:
    replay = subparsers.add_parser("replay", help="build local trajectory replay review media")
    replay_commands = replay.add_subparsers(dest="replay_command", required=True)
    trajectory_video = replay_commands.add_parser(
        "trajectory-video",
        help="build trajectory replay manifest and optionally render review videos",
    )
    trajectory_video.add_argument("--run-dir", required=True, help="run artifact directory containing trajectories")
    trajectory_video.add_argument("--output-dir", required=True, help="directory for local replay videos/manifests")
    trajectory_video.add_argument("--scene-usd", help="RetroNeighborhood USD path for Isaac rendering")
    trajectory_video.add_argument("--fps", type=float, default=30.0, help="review video frames per second")
    trajectory_video.add_argument("--width", type=int, default=1920, help="review video width")
    trajectory_video.add_argument("--height", type=int, default=1080, help="review video height")
    trajectory_video.add_argument(
        "--camera-specs",
        help="JSON list of sampled first-person cameras; defaults to the current UAV/UGV front stereo left surface",
    )
    trajectory_video.add_argument(
        "--review-window",
        choices=[REVIEW_WINDOW_FULL, REVIEW_WINDOW_TAKEOFF_TO_K],
        default=REVIEW_WINDOW_TAKEOFF_TO_K,
        help=(
            "review-video window: 'takeoff-to-k' (default) renders from just before UAV "
            "lift-off until the UGV reached --review-k ground-truth instances; 'full' "
            "renders the whole episode"
        ),
    )
    trajectory_video.add_argument(
        "--review-k",
        type=int,
        default=DEFAULT_REVIEW_K,
        help="number of reached GT instances that ends the takeoff-to-k window",
    )
    trajectory_video.add_argument(
        "--review-pre-roll-s",
        type=float,
        default=DEFAULT_REVIEW_PRE_ROLL_S,
        help="simulated seconds kept before UAV lift-off",
    )
    trajectory_video.add_argument(
        "--review-tail-s",
        type=float,
        default=DEFAULT_REVIEW_TAIL_S,
        help="simulated seconds kept after the k-th reach",
    )
    trajectory_video.add_argument(
        "--ugv-progress",
        help="ugv_progress.json with the reach times; defaults to <run-dir>/ugv_progress.json",
    )
    trajectory_video.add_argument(
        "--renderer-command",
        nargs="+",
        help="optional Isaac Python command prefix, for example /isaac-sim/python.sh",
    )
    trajectory_video.add_argument(
        "--renderer-script",
        default="AirStack/simulation/isaac-sim/tools/render_trajectory_replay_video.py",
        help="Isaac-side renderer script",
    )
    trajectory_video.set_defaults(handler=_replay_trajectory_video)


def _add_asset_common_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--manifest", help="asset manifest YAML")
    parser.add_argument(
        "--simulator-version",
        choices=sorted(PACKAGED_ASSET_MANIFESTS),
        default=DEFAULT_ASSET_SIMULATOR_VERSION,
        help="packaged Isaac Sim asset manifest version; ignored when --manifest is supplied",
    )
    parser.add_argument("--cache", default="assets/cache", help="asset cache directory")


def _add_assets_commands(subparsers: argparse._SubParsersAction) -> None:
    assets = subparsers.add_parser("assets", help="fetch and verify simulator assets")
    asset_commands = assets.add_subparsers(dest="assets_command", required=True)

    manifest = asset_commands.add_parser(
        "manifest",
        help="summarize the versioned Isaac asset manifest",
    )
    manifest.add_argument("--manifest", help="asset manifest YAML")
    manifest.add_argument(
        "--simulator-version",
        choices=sorted(PACKAGED_ASSET_MANIFESTS),
        default=DEFAULT_ASSET_SIMULATOR_VERSION,
        help="packaged Isaac Sim asset manifest version; ignored when --manifest is supplied",
    )
    manifest.set_defaults(handler=_asset_manifest_summary)

    fetch = asset_commands.add_parser("fetch", help="download or copy manifest assets")
    _add_asset_common_arguments(fetch)
    fetch.add_argument("--asset", action="append", help="asset id; repeat to select a subset")
    fetch.add_argument(
        "--source-root",
        help="local Isaac 5.1/ asset root; defaults to ISAAC_ASSET_ROOT",
    )
    fetch.add_argument("--offline", action="store_true", help="reject network downloads")
    fetch.set_defaults(handler=_asset_fetch)

    check = asset_commands.add_parser("check", help="verify cached manifest assets")
    _add_asset_common_arguments(check)
    check.set_defaults(handler=_asset_check)

    root = asset_commands.add_parser("root", help="resolve the configured Isaac asset root")
    root.add_argument("--manifest", help="asset manifest YAML")
    root.add_argument(
        "--simulator-version",
        choices=sorted(PACKAGED_ASSET_MANIFESTS),
        default=DEFAULT_ASSET_SIMULATOR_VERSION,
        help="packaged Isaac Sim asset manifest version; ignored when --manifest is supplied",
    )
    root.add_argument(
        "--source-root",
        help="local Isaac 5.1/ asset root; defaults to ISAAC_ASSET_ROOT",
    )
    root.set_defaults(handler=_asset_root)


def _add_release_commands(subparsers: argparse._SubParsersAction) -> None:
    release = subparsers.add_parser("release", help="audit release artifacts")
    release_commands = release.add_subparsers(dest="release_command", required=True)
    audit_pair = release_commands.add_parser(
        "audit-pair",
        help="audit files produced by episodes release-pair",
    )
    audit_pair.add_argument("--release-dir", required=True, help="release-pair output directory")
    audit_pair.add_argument("--output", help="output audit report JSON; stdout if omitted")
    audit_pair.set_defaults(handler=_release_audit_pair)

    checklist = release_commands.add_parser(
        "checklist",
        help="run machine-readable release checklist checks",
    )
    checklist.add_argument("--release-dir", required=True, help="release-pair output directory")
    checklist.add_argument("--repo-root", default=".", help="repository root for document checks")
    checklist.add_argument("--run-dir", help="optional run directory to check for run/evaluate artifacts")
    checklist.add_argument(
        "--release-manifest",
        help="release manifest JSON; defaults to <release-dir>/release_manifest.json",
    )
    checklist.add_argument(
        "--fresh-clone-report",
        help="optional fresh-clone reproducibility report JSON to validate",
    )
    checklist.add_argument(
        "--fresh-clone-plan",
        help="optional fresh-clone reproducibility plan JSON for checksum verification",
    )
    checklist.add_argument(
        "--fault-report",
        help="optional fault-injection suite report JSON to validate",
    )
    checklist.add_argument(
        "--performance-report",
        help="optional performance/long-stability report JSON to validate",
    )
    checklist.add_argument(
        "--reset-state-report",
        help="optional reset state long-run audit report JSON to validate",
    )
    checklist.add_argument(
        "--reset-state-run-dir",
        help=(
            "optional run directory used only to recompute --reset-state-report; "
            "defaults to --run-dir"
        ),
    )
    checklist.add_argument(
        "--soft-reset-full-action-report",
        help="optional soft reset full-action artifact check report JSON to validate",
    )
    checklist.add_argument(
        "--strict-clean",
        action="store_true",
        help="fail if release manifest reports dirty repo/submodule provenance",
    )
    checklist.add_argument(
        "--fail-on-warn",
        action="store_true",
        help="treat any release checklist warning as a failing release gate",
    )
    checklist.add_argument(
        "--strict-release",
        action="store_true",
        help=(
            "enable strict release gates: strict-clean, fail-on-warn, metrics evidence, "
            "fresh-clone evidence, fault report, performance report, reset state audit, "
            "soft reset full-action evidence, GT artifacts, target human review, release id, "
            f"and Isaac {DEFAULT_ISAAC_SIMULATOR_VERSION} assets"
        ),
    )
    checklist.add_argument(
        "--require-metrics-evidence",
        action="store_true",
        help="fail unless --run-dir passes strict metric evidence validation",
    )
    checklist.add_argument(
        "--require-fresh-clone",
        action="store_true",
        help="fail unless fresh-clone plan and report evidence are provided",
    )
    checklist.add_argument(
        "--require-fault-report",
        action="store_true",
        help="fail unless fault-injection report evidence is provided",
    )
    checklist.add_argument(
        "--require-performance-report",
        action="store_true",
        help="fail unless performance/long-stability report evidence is provided",
    )
    checklist.add_argument(
        "--require-reset-state-report",
        action="store_true",
        help="fail unless reset state long-run audit evidence is provided",
    )
    checklist.add_argument(
        "--require-soft-reset-full-action-report",
        action="store_true",
        help="fail unless soft reset full-action artifact evidence is provided",
    )
    checklist.add_argument(
        "--require-gt-artifacts",
        action="store_true",
        help="fail unless release manifest includes explicit GT artifact checksums",
    )
    checklist.add_argument(
        "--require-target-review",
        action="store_true",
        help=(
            "fail unless a target GT --gt-artifact passes USD prim, verified, "
            "and review_version audit gates"
        ),
    )
    checklist.add_argument(
        "--require-simulator-version",
        choices=sorted(PACKAGED_ASSET_MANIFESTS),
        help="fail unless the release manifest asset manifest uses this simulator version",
    )
    checklist.add_argument(
        "--require-release-id",
        default="benchmark-v1.0-retro",
        help="fail unless release manifest uses this benchmark release id",
    )
    checklist.add_argument(
        "--gt-artifact",
        action="append",
        help=(
            "GT artifact file to recompute and compare against release manifest "
            "checksums, as name=path; repeatable"
        ),
    )
    checklist.add_argument("--output", help="output checklist JSON; stdout if omitted")
    checklist.set_defaults(handler=_release_checklist)

    repro_plan = release_commands.add_parser(
        "repro-plan",
        help="write a fresh-clone reproducibility command plan",
    )
    repro_plan.add_argument("--repo-url", required=True, help="repository URL to clone")
    repro_plan.add_argument(
        "--target-dir",
        default="RAVEN-AirGround-fresh",
        help="relative fresh-clone target directory name",
    )
    repro_plan.add_argument(
        "--contract-only",
        action="store_true",
        help="omit the final real Isaac/ROS episode smoke step",
    )
    repro_plan.add_argument(
        "--real-episode-manifest",
        default="benchmark/airground_benchmark/episode_manifests/benchmark-v1.0-retro.yaml",
        help="episode manifest path used by the real Isaac/ROS smoke step",
    )
    repro_plan.add_argument("--real-episode-id", help="optional episode id for the real smoke step")
    repro_plan.add_argument(
        "--real-episode-output-dir",
        default="runs/fresh_clone_smoke",
        help="fresh-clone relative output directory for the real smoke run",
    )
    repro_plan.add_argument(
        "--real-episode-repo-root",
        default=".",
        help="repo root argument passed to airground run --mode isaac in the fresh clone",
    )
    repro_plan.add_argument(
        "--real-episode-container",
        default="isaac-sim",
        help="Docker container name used by the real smoke step",
    )
    repro_plan.add_argument("--output", help="output plan JSON; stdout if omitted")
    repro_plan.set_defaults(handler=_release_repro_plan)

    repro_report = release_commands.add_parser(
        "repro-report",
        help="validate fresh-clone command results against a reproducibility plan",
    )
    repro_report.add_argument("--plan", required=True, help="fresh-clone repro plan JSON")
    repro_report.add_argument(
        "--results",
        required=True,
        help="JSON list or object containing fresh-clone step results",
    )
    repro_report.add_argument(
        "--artifact-root",
        help=(
            "fresh-clone root directory used to compute SHA-256 for each reported "
            "artifact path"
        ),
    )
    repro_report.add_argument(
        "--repo-root",
        help=(
            "fresh-clone git checkout root used to record the reproduced commit; "
            "defaults to --artifact-root when available"
        ),
    )
    repro_report.add_argument(
        "--repo-commit",
        help="explicit 40-hex commit reproduced by the fresh-clone run",
    )
    repro_report.add_argument("--output", help="output report JSON; stdout if omitted")
    repro_report.set_defaults(handler=_release_repro_report)

    performance = release_commands.add_parser(
        "performance-report",
        help="build a performance/long-stability report from real run artifacts",
    )
    performance.add_argument("--run-dir", required=True, help="real run artifact directory")
    performance.add_argument(
        "--resource-trace",
        required=True,
        help="JSONL resource trace with timestamp_s, memory, GPU, and OOM fields",
    )
    performance.add_argument(
        "--min-episodes",
        type=int,
        default=60,
        help="minimum completed episode count required for the report",
    )
    performance.add_argument(
        "--min-resource-samples",
        type=int,
        default=2,
        help="minimum resource samples required in the JSONL trace",
    )
    performance.add_argument(
        "--max-system-memory-growth-mb",
        type=float,
        help="maximum allowed last-minus-first system memory growth in MB",
    )
    performance.add_argument(
        "--max-gpu-memory-fraction",
        type=float,
        default=0.95,
        help="maximum allowed peak GPU memory used / total fraction",
    )
    performance.add_argument(
        "--max-gpu-memory-growth-mb",
        type=float,
        help="maximum allowed last-minus-first GPU memory growth in MB",
    )
    performance.add_argument(
        "--max-gpu-memory-used-mb",
        type=float,
        help="maximum allowed peak GPU memory used in MB",
    )
    performance.add_argument(
        "--allow-contract-backend",
        action="store_true",
        help="allow non-Isaac backend evidence; for tests only, not release",
    )
    performance.add_argument(
        "--allow-failed-episodes",
        action="store_true",
        help="allow mission failures in the report; for diagnostics only",
    )
    performance.add_argument(
        "--allow-missing-energy-evidence",
        action="store_true",
        help="allow missing real energy evidence; for diagnostics only",
    )
    performance.add_argument("--output", help="output report JSON; stdout if omitted")
    performance.set_defaults(handler=_release_performance_report)

    manifest = release_commands.add_parser(
        "manifest",
        help=(
            "write a release manifest with assets, evaluator checksums, "
            "run artifacts, containers, and commits"
        ),
    )
    manifest.add_argument("--release-dir", required=True, help="release-pair output directory")
    manifest.add_argument("--repo-root", default=".", help="repository root for git commit capture")
    manifest.add_argument(
        "--release-id",
        default="benchmark-v1.0-retro",
        help="benchmark release id recorded in release manifest",
    )
    manifest.add_argument("--asset-manifest", help="asset manifest YAML; defaults to packaged manifest")
    manifest.add_argument(
        "--simulator-version",
        choices=sorted(PACKAGED_ASSET_MANIFESTS),
        default=DEFAULT_ASSET_SIMULATOR_VERSION,
        help="packaged Isaac Sim asset manifest version; ignored when --asset-manifest is supplied",
    )
    manifest.add_argument(
        "--gt-artifact",
        action="append",
        help="additional GT artifact checksum entry as name=path; repeatable",
    )
    manifest.add_argument(
        "--container-tag",
        action="append",
        help="container image tag or digest included in release provenance; repeatable",
    )
    manifest.add_argument(
        "--run-dir",
        help="optional run artifact directory to index in release provenance",
    )
    manifest.add_argument("--output", help="output release manifest JSON; stdout if omitted")
    manifest.set_defaults(handler=_release_manifest)


def _add_reset_commands(subparsers: argparse._SubParsersAction) -> None:
    reset = subparsers.add_parser("reset", help="inspect reset and health contracts")
    reset_commands = reset.add_subparsers(dest="reset_command", required=True)

    plan = reset_commands.add_parser("plan", help="write the ordered reset plan")
    plan.add_argument("--mode", choices=("soft", "hard"), default="soft")
    plan.set_defaults(handler=_reset_plan)

    check_trace = reset_commands.add_parser(
        "check-trace",
        help="validate an adapter reset trace against the reset contract",
    )
    check_trace.add_argument("--mode", choices=("soft", "hard"), default="soft")
    check_trace.add_argument("--trace", required=True, help="YAML/JSON list of reset step ids")
    check_trace.add_argument(
        "--allow-extra-steps",
        action="store_true",
        help="ignore adapter-specific extra steps in the trace",
    )
    check_trace.add_argument(
        "--require-sensor-payloads",
        action="store_true",
        help="require RGB, depth, and point-cloud payload checksum metadata in reset trace",
    )
    check_trace.add_argument(
        "--require-adapter-state-clear",
        action="store_true",
        help="require adapter-owned communication queue and metric accumulator clear evidence",
    )
    check_trace.add_argument(
        "--require-ros-queue-clear",
        action="store_true",
        help="require adapter-owned ROS subscription queue clear evidence",
    )
    check_trace.add_argument(
        "--require-airstack-trajectory-clear",
        action="store_true",
        help="require adapter-facing AirStack trajectory buffer clear evidence",
    )
    check_trace.add_argument(
        "--require-nav2-cancel",
        action="store_true",
        help="require live UGV Nav2 NavigateToPose cancel evidence",
    )
    check_trace.add_argument(
        "--require-uav-px4-cancel",
        action="store_true",
        help="require safe UAV PX4 OFFBOARD-to-LOITER cancel evidence",
    )
    check_trace.add_argument(
        "--require-control-hold",
        action="store_true",
        help="require live UGV dirty command followed by zero-hold command evidence",
    )
    check_trace.add_argument(
        "--require-rayfronts-reset",
        action="store_true",
        help="require RayFronts map/query/hypothesis reset evidence",
    )
    check_trace.add_argument(
        "--health",
        help="optional YAML/JSON component health mapping to validate with reset trace",
    )
    check_trace.add_argument(
        "--require-healthy-components",
        action="store_true",
        help="require simulator, PX4, AirStack, Nav2, RayFronts, sensors, and adapter health",
    )
    check_trace.add_argument(
        "--require-stable-health-handshake",
        action="store_true",
        help="require consecutive full-health handshake evidence in reset trace",
    )
    check_trace.add_argument("--previous-infra-retries", type=int, default=0)
    check_trace.add_argument("--max-infra-retries", type=int, default=1)
    check_trace.set_defaults(handler=_reset_check_trace)

    check_run = reset_commands.add_parser(
        "check-run",
        help="validate per-episode reset traces and health evidence in a run artifact",
    )
    check_run.add_argument("--run-dir", required=True, help="run artifact directory")
    check_run.add_argument("--mode", choices=("soft", "hard"), default="soft")
    check_run.add_argument("--expected-episodes", type=int)
    check_run.add_argument(
        "--allow-extra-steps",
        action="store_true",
        help="ignore adapter-specific extra reset steps in each trace",
    )
    check_run.add_argument(
        "--require-sensor-payloads",
        action="store_true",
        help="require per-episode RGB/depth/LiDAR payload checksum metadata",
    )
    check_run.add_argument(
        "--no-require-healthy-components",
        action="store_true",
        help="do not require per-episode component health artifacts",
    )
    check_run.add_argument(
        "--require-reset-support",
        action="store_true",
        help="require managed Nav2/RayFronts reset support readiness and clean postflight evidence",
    )
    check_run.add_argument(
        "--require-stable-health-handshake",
        action="store_true",
        help="require per-episode stable full-health reset handshake evidence",
    )
    check_run.add_argument(
        "--require-airstack-trajectory-clear",
        action="store_true",
        help="require per-episode AirStack trajectory buffer clear evidence",
    )
    check_run.add_argument("--output", help="output validation report JSON")
    check_run.set_defaults(handler=_reset_check_run)

    audit_state_run = reset_commands.add_parser(
        "audit-state-run",
        help="audit residue-sensitive reset state surfaces across a long run artifact",
    )
    audit_state_run.add_argument("--run-dir", required=True, help="run artifact directory")
    audit_state_run.add_argument("--mode", choices=("soft", "hard"), default="soft")
    audit_state_run.add_argument("--expected-episodes", type=int, default=60)
    audit_state_run.add_argument(
        "--no-require-reset-support",
        action="store_true",
        help="do not require managed Nav2/RayFronts reset support readiness and postflight evidence",
    )
    audit_state_run.add_argument(
        "--no-require-reset-run-validation",
        action="store_true",
        help="do not require the integrated reset_run_validation_report.json surface",
    )
    audit_state_run.add_argument(
        "--allow-mission-failures",
        action="store_true",
        help="allow run_summary mission_success_rate below 1.0 for diagnostics",
    )
    audit_state_run.add_argument(
        "--allow-multi-attempt",
        action="store_true",
        help="allow per-episode attempt_count other than 1 for diagnostics",
    )
    audit_state_run.add_argument("--output", help="output audit report JSON")
    audit_state_run.set_defaults(handler=_reset_audit_state_run)

    check_hard_restart = reset_commands.add_parser(
        "check-hard-restart-run",
        help="validate a hard-restart full-health smoke artifact",
    )
    check_hard_restart.add_argument("--run-dir", required=True, help="hard restart smoke artifact directory")
    check_hard_restart.add_argument(
        "--require-clock-epoch-reset",
        action="store_true",
        help="require clock_epoch_evidence.json to prove /clock epoch reset after hard restart",
    )
    check_hard_restart.add_argument("--output", help="output validation report JSON")
    check_hard_restart.set_defaults(handler=_reset_check_hard_restart_run)

    check_soft_full_action = reset_commands.add_parser(
        "check-soft-full-action-run",
        help="validate a soft-reset full-action smoke artifact",
    )
    check_soft_full_action.add_argument(
        "--run-dir",
        required=True,
        help="soft reset full-action smoke artifact directory",
    )
    check_soft_full_action.add_argument("--output", help="output validation report JSON")
    check_soft_full_action.set_defaults(handler=_reset_check_soft_full_action_run)

    check_recovery = reset_commands.add_parser(
        "check-recovery-run",
        help="validate a reset recovery orchestration artifact",
    )
    check_recovery.add_argument("--run-dir", required=True, help="reset recovery artifact directory")
    check_recovery.add_argument(
        "--require-clock-epoch-reset",
        action="store_true",
        help="require delegated hard restart evidence to prove /clock epoch reset",
    )
    check_recovery.add_argument("--output", help="output validation report JSON")
    check_recovery.set_defaults(handler=_reset_check_recovery_run)

    check_production_orchestrator = reset_commands.add_parser(
        "check-production-orchestrator",
        help="validate the production reset-orchestrator evidence bundle",
    )
    check_production_orchestrator.add_argument(
        "--soft-full-action-run-dir",
        required=True,
        help="soft reset full-action smoke artifact directory",
    )
    check_production_orchestrator.add_argument(
        "--recovery-run-dir",
        required=True,
        help="reset recovery artifact directory",
    )
    check_production_orchestrator.add_argument(
        "--hard-restart-run-dir",
        required=True,
        help="hard restart full-health smoke artifact directory",
    )
    check_production_orchestrator.add_argument(
        "--reset-state-run-dir",
        required=True,
        help="multi-episode reset-state run artifact directory",
    )
    check_production_orchestrator.add_argument(
        "--dock-reset-pose-report",
        required=True,
        help="dock reset pose gate report JSON",
    )
    check_production_orchestrator.add_argument(
        "--dock-reset-sequence-report",
        required=True,
        help="dock reset sequence gate report JSON",
    )
    check_production_orchestrator.add_argument("--expected-episodes", type=int, default=60)
    check_production_orchestrator.add_argument(
        "--require-clock-epoch-reset",
        action="store_true",
        help="require hard restart /clock epoch reset evidence",
    )
    check_production_orchestrator.add_argument("--output", help="output validation report JSON")
    check_production_orchestrator.set_defaults(handler=_reset_check_production_orchestrator)

    run_hard_restart = reset_commands.add_parser(
        "run-hard-restart-full-health",
        help="run the host-side hard-restart full-health smoke runner and validate its artifact",
    )
    run_hard_restart.add_argument("--artifact-dir", required=True, help="output artifact directory")
    run_hard_restart.add_argument("--container", default="isaac-sim")
    run_hard_restart.add_argument("--container-artifact-dir")
    run_hard_restart.add_argument("--python", default=sys.executable)
    run_hard_restart.add_argument(
        "--runner",
        default="tools/run_hard_restart_full_health_smoke.py",
        help="path to the host-side hard restart full-health runner",
    )
    run_hard_restart.add_argument("--airground-cli", default=".venv/bin/airground")
    run_hard_restart.add_argument("--docker-health-timeout-s", type=float, default=90.0)
    run_hard_restart.add_argument("--docker-health-poll-s", type=float, default=5.0)
    run_hard_restart.add_argument("--post-restart-settle-s", type=float, default=10.0)
    run_hard_restart.add_argument("--require-clock-epoch-reset", action="store_true")
    run_hard_restart.add_argument("--clock-sample-timeout-s", type=float, default=10.0)
    run_hard_restart.add_argument("--pre-restart-clock-min-s", type=float, default=20.0)
    run_hard_restart.add_argument("--pre-restart-clock-wait-timeout-s", type=float, default=45.0)
    run_hard_restart.add_argument("--post-restart-clock-max-s", type=float, default=30.0)
    run_hard_restart.add_argument("--post-restart-clock-delta-s", type=float, default=0.25)
    run_hard_restart.add_argument("--post-restart-clock-wait-timeout-s", type=float, default=90.0)
    run_hard_restart.add_argument("--rayfronts-duration-s", type=float, default=90.0)
    run_hard_restart.add_argument("--nav2-tf-startup-timeout-s", type=float, default=90.0)
    run_hard_restart.add_argument("--nav2-hold-after-success-s", type=float, default=60.0)
    run_hard_restart.add_argument("--postflight-wait-s", type=float, default=120.0)
    run_hard_restart.add_argument("--dry-run", action="store_true")
    run_hard_restart.add_argument("--output", help="output command and artifact gate JSON")
    run_hard_restart.set_defaults(handler=_reset_run_hard_restart_full_health)

    run_recovery = reset_commands.add_parser(
        "run-recovery",
        help="run reset recovery decision plus soft-component or hard-stack smoke validation",
    )
    run_recovery.add_argument("--artifact-dir", required=True, help="output artifact directory")
    run_recovery.add_argument("--health", required=True, help="pre-recovery component health JSON/YAML")
    run_recovery.add_argument("--container", default="isaac-sim")
    run_recovery.add_argument("--container-artifact-dir")
    run_recovery.add_argument("--python", default=sys.executable)
    run_recovery.add_argument(
        "--runner",
        default="tools/run_reset_recovery_smoke.py",
        help="path to the host-side reset recovery runner",
    )
    run_recovery.add_argument(
        "--soft-runner",
        default="tools/run_soft_reset_full_action_smoke.py",
        help="path to the host-side soft reset full-action runner module/script",
    )
    run_recovery.add_argument(
        "--hard-runner",
        default="tools/run_hard_restart_full_health_smoke.py",
        help="path to the host-side hard restart full-health runner",
    )
    run_recovery.add_argument("--airground-cli", default=".venv/bin/airground")
    run_recovery.add_argument("--previous-infra-retries", type=int, default=0)
    run_recovery.add_argument("--max-infra-retries", type=int, default=1)
    run_recovery.add_argument("--rayfronts-duration-s", type=float, default=300.0)
    run_recovery.add_argument("--rayfronts-ready-timeout-s", type=float, default=45.0)
    run_recovery.add_argument("--nav2-tf-startup-timeout-s", type=float, default=90.0)
    run_recovery.add_argument("--nav2-hold-after-success-s", type=float, default=240.0)
    run_recovery.add_argument("--nav2-ready-timeout-s", type=float, default=150.0)
    run_recovery.add_argument("--reset-trace-timeout-s", type=float, default=60.0)
    run_recovery.add_argument("--stable-health-samples", type=int, default=3)
    run_recovery.add_argument("--stable-health-period-s", type=float, default=0.5)
    run_recovery.add_argument("--stable-health-timeout-s", type=float, default=10.0)
    run_recovery.add_argument("--docker-health-timeout-s", type=float, default=90.0)
    run_recovery.add_argument("--docker-health-poll-s", type=float, default=5.0)
    run_recovery.add_argument("--post-restart-settle-s", type=float, default=10.0)
    run_recovery.add_argument("--require-clock-epoch-reset", action="store_true")
    run_recovery.add_argument("--postflight-wait-s", type=float, default=2.0)
    run_recovery.add_argument("--dry-run", action="store_true")
    run_recovery.add_argument("--output", help="output command and artifact gate JSON")
    run_recovery.set_defaults(handler=_reset_run_recovery)

    run_soft_full_action = reset_commands.add_parser(
        "run-soft-full-action",
        help="run the host-side soft-reset full-action smoke runner and validate its artifact",
    )
    run_soft_full_action.add_argument("--artifact-dir", required=True, help="output artifact directory")
    run_soft_full_action.add_argument("--container", default="isaac-sim")
    run_soft_full_action.add_argument("--container-artifact-dir")
    run_soft_full_action.add_argument("--python", default=sys.executable)
    run_soft_full_action.add_argument(
        "--runner",
        default="tools/run_soft_reset_full_action_smoke.py",
        help="path to the host-side soft reset full-action runner",
    )
    run_soft_full_action.add_argument("--airground-cli", default=".venv/bin/airground")
    run_soft_full_action.add_argument("--rayfronts-duration-s", type=float, default=300.0)
    run_soft_full_action.add_argument("--rayfronts-ready-timeout-s", type=float, default=45.0)
    run_soft_full_action.add_argument("--nav2-tf-startup-timeout-s", type=float, default=90.0)
    run_soft_full_action.add_argument("--nav2-hold-after-success-s", type=float, default=240.0)
    run_soft_full_action.add_argument("--nav2-ready-timeout-s", type=float, default=150.0)
    run_soft_full_action.add_argument("--reset-trace-timeout-s", type=float, default=60.0)
    run_soft_full_action.add_argument("--stable-health-samples", type=int, default=3)
    run_soft_full_action.add_argument("--stable-health-period-s", type=float, default=0.5)
    run_soft_full_action.add_argument("--stable-health-timeout-s", type=float, default=10.0)
    run_soft_full_action.add_argument("--postflight-wait-s", type=float, default=2.0)
    run_soft_full_action.add_argument("--dry-run", action="store_true")
    run_soft_full_action.add_argument("--output", help="output command and artifact gate JSON")
    run_soft_full_action.set_defaults(handler=_reset_run_soft_full_action)

    recovery = reset_commands.add_parser(
        "decide-recovery",
        help="decide soft retry vs. hard reset from component health",
    )
    recovery.add_argument("--health", required=True, help="YAML/JSON component health mapping")
    recovery.add_argument("--previous-infra-retries", type=int, default=0)
    recovery.add_argument("--max-infra-retries", type=int, default=1)
    recovery.set_defaults(handler=_reset_decide_recovery)


def _add_faults_commands(subparsers: argparse._SubParsersAction) -> None:
    faults = subparsers.add_parser("faults", help="run contract fault-injection checks")
    fault_commands = faults.add_subparsers(dest="faults_command", required=True)

    catalog = fault_commands.add_parser("catalog", help="write predefined fault scenarios")
    catalog.set_defaults(handler=_faults_catalog)

    run_contract_faults = fault_commands.add_parser(
        "run-contract",
        help="run fault scenarios against the contract environment",
    )
    selector = run_contract_faults.add_mutually_exclusive_group(required=True)
    selector.add_argument("--scenario", action="append", help="scenario id; repeatable")
    selector.add_argument("--all", action="store_true", help="run all predefined scenarios")
    run_contract_faults.add_argument("--max-cycles", type=int, default=10)
    run_contract_faults.add_argument("--output", help="output report JSON; stdout if omitted")
    run_contract_faults.set_defaults(handler=_faults_run_contract)


def _add_smoke_commands(subparsers: argparse._SubParsersAction) -> None:
    smoke = subparsers.add_parser("smoke", help="validate backend smoke-run evidence")
    smoke_commands = smoke.add_subparsers(dest="smoke_command", required=True)

    check_uav = smoke_commands.add_parser(
        "check-uav",
        help="validate UAV arm/takeoff/hover/waypoint/cancel/e-stop smoke trace",
    )
    check_uav.add_argument("--trace", required=True, help="JSONL run/event trace to validate")
    check_uav.add_argument("--output", help="output report JSON; stdout if omitted")
    check_uav.add_argument(
        "--min-hover-s",
        type=float,
        help="require the hover step to report at least this many stable seconds",
    )
    check_uav.add_argument(
        "--max-hover-drift-m",
        type=float,
        help="require the hover step drift_m to stay at or below this threshold",
    )
    check_uav.add_argument(
        "--min-waypoint-x-m",
        type=float,
        help="require the waypoint target_x_m to be at least this value",
    )
    check_uav.add_argument(
        "--max-waypoint-error-m",
        type=float,
        help="require the waypoint endpoint_error_m to stay at or below this threshold",
    )
    check_uav.set_defaults(handler=_smoke_check_uav)

    check_ugv_topics = smoke_commands.add_parser(
        "check-ugv-topics",
        help="validate Jackal /ugv topic, sensor, and TF smoke trace",
    )
    check_ugv_topics.add_argument("--trace", required=True, help="JSONL topic audit trace")
    check_ugv_topics.add_argument("--output", help="output report JSON; stdout if omitted")
    check_ugv_topics.set_defaults(handler=_smoke_check_ugv_topics)

    check_nav2 = smoke_commands.add_parser(
        "check-nav2",
        help="validate UGV Nav2 lifecycle/map/goal/cancel/recovery smoke trace",
    )
    check_nav2.add_argument("--trace", required=True, help="JSONL Nav2 smoke trace")
    check_nav2.add_argument("--output", help="output report JSON; stdout if omitted")
    check_nav2.set_defaults(handler=_smoke_check_nav2)

    check_dock_takeoff = smoke_commands.add_parser(
        "check-dock-takeoff",
        help="validate repeated reset/dock/takeoff loop evidence",
    )
    check_dock_takeoff.add_argument("--trace", required=True, help="JSONL loop trace")
    check_dock_takeoff.add_argument("--expected-cycles", type=int, default=100)
    check_dock_takeoff.add_argument("--min-clearance-m", type=float, default=1.0)
    check_dock_takeoff.add_argument("--require-docked-clearance", action="store_true")
    check_dock_takeoff.add_argument("--min-docked-clearance-m", type=float, default=-0.02)
    check_dock_takeoff.add_argument("--require-fresh-reset", action="store_true")
    check_dock_takeoff.add_argument("--require-pose-trace", action="store_true")
    check_dock_takeoff.add_argument("--pose-trace-root", help="host directory for resolving pose_trace files")
    check_dock_takeoff.add_argument("--require-reset-sequence", action="store_true")
    check_dock_takeoff.add_argument("--output", help="output report JSON; stdout if omitted")
    check_dock_takeoff.set_defaults(handler=_smoke_check_dock_takeoff)

    check_dock_contact_impulse = smoke_commands.add_parser(
        "check-dock-contact-impulse",
        help="validate dock/takeoff contact impulse safety evidence",
    )
    check_dock_contact_impulse.add_argument("--trace", required=True, help="JSONL contact impulse trace")
    check_dock_contact_impulse.add_argument("--expected-cycles", type=int, default=100)
    check_dock_contact_impulse.add_argument(
        "--max-unexpected-collision-impulse-n-s",
        type=float,
        default=0.0,
    )
    check_dock_contact_impulse.add_argument("--output", help="output report JSON; stdout if omitted")
    check_dock_contact_impulse.set_defaults(handler=_smoke_check_dock_contact_impulse)

    check_jackal_routes = smoke_commands.add_parser(
        "check-jackal-routes",
        help="validate Jackal ground-route physical safety evidence",
    )
    check_jackal_routes.add_argument("--trace", required=True, help="JSONL route trace")
    check_jackal_routes.add_argument("--expected-routes", type=int, default=10)
    check_jackal_routes.add_argument("--max-tilt-rad", type=float, default=0.7)
    check_jackal_routes.add_argument("--output", help="output report JSON; stdout if omitted")
    check_jackal_routes.set_defaults(handler=_smoke_check_jackal_routes)


    check_ugv_precision = smoke_commands.add_parser(
        "check-ugv-precision",
        help="validate Jackal static and 10m straight-line precision evidence",
    )
    check_ugv_precision.add_argument("--trace", required=True, help="JSONL precision trace")
    check_ugv_precision.add_argument("--min-static-s", type=float, default=60.0)
    check_ugv_precision.add_argument("--max-static-drift-m", type=float, default=0.02)
    check_ugv_precision.add_argument("--min-straight-distance-m", type=float, default=10.0)
    check_ugv_precision.add_argument("--max-straight-endpoint-error-m", type=float, default=0.25)
    check_ugv_precision.add_argument("--max-tilt-rad", type=float, default=0.7)
    check_ugv_precision.add_argument("--output", help="output report JSON; stdout if omitted")
    check_ugv_precision.set_defaults(handler=_smoke_check_ugv_precision)

    check_headless_integration = smoke_commands.add_parser(
        "check-headless-integration",
        help=(
            "validate unified Isaac headless integration evidence across "
            "headless runtime, UAV dock, Jackal, confirmation, and reset"
        ),
    )
    check_headless_integration.add_argument(
        "--headless-artifact-dir",
        required=True,
        help="directory containing headless Docker/env/ROS topic evidence",
    )
    check_headless_integration.add_argument(
        "--headless-run-dir",
        required=True,
        help="real Isaac/ROS run artifact directory to recompute with check-oracle-run",
    )
    check_headless_integration.add_argument(
        "--expected-headless-episodes",
        type=int,
        default=1,
        help="required episode count in the headless run artifact",
    )
    check_headless_integration.add_argument(
        "--headless-split",
        choices=("public", "hidden_test"),
        default="public",
        help="required split in the headless run artifact",
    )
    check_headless_integration.add_argument(
        "--simulator-version",
        default=DEFAULT_ISAAC_SIMULATOR_VERSION,
        help="expected Isaac Sim runtime_backend simulator version",
    )
    check_headless_integration.add_argument(
        "--require-headless-render",
        action="store_true",
        help="require AIRGROUND_RENDER=true in container_env.txt",
    )
    check_headless_integration.add_argument(
        "--require-energy-evidence",
        action="store_true",
        help="require UAV/UGV energy evidence in the headless run artifact",
    )
    check_headless_integration.add_argument("--dock-trace", required=True, help="dock/takeoff JSONL trace")
    check_headless_integration.add_argument("--dock-expected-cycles", type=int, default=100)
    check_headless_integration.add_argument("--dock-min-clearance-m", type=float, default=1.0)
    check_headless_integration.add_argument(
        "--no-dock-require-docked-clearance",
        action="store_true",
        help="do not require docked clearance evidence in the dock/takeoff trace",
    )
    check_headless_integration.add_argument("--dock-min-docked-clearance-m", type=float, default=-0.02)
    check_headless_integration.add_argument("--jackal-trace", required=True, help="Jackal route JSONL trace")
    check_headless_integration.add_argument("--jackal-expected-routes", type=int, default=200)
    check_headless_integration.add_argument("--jackal-max-tilt-rad", type=float, default=0.7)
    check_headless_integration.add_argument(
        "--confirmation-annotations",
        required=True,
        help="reviewed target annotations with confirmation regions",
    )
    check_headless_integration.add_argument(
        "--confirmation-trace",
        required=True,
        help="sensor-frame confirmation visibility JSONL trace",
    )
    check_headless_integration.add_argument(
        "--confirmation-required-consecutive-frames",
        type=int,
        default=5,
        help="required consecutive valid frames per reachable confirmation region",
    )
    check_headless_integration.add_argument(
        "--reset-recovery-run-dir",
        required=True,
        help="reset recovery artifact directory",
    )
    check_headless_integration.add_argument("--output", help="output report JSON; stdout if omitted")
    check_headless_integration.set_defaults(handler=_smoke_check_headless_integration)

    check_clock_sync = smoke_commands.add_parser(
        "check-clock-sync",
        help="validate shared /clock and sensor/agent step alignment evidence",
    )
    check_clock_sync.add_argument("--trace", required=True, help="JSONL clock sync trace")
    check_clock_sync.add_argument("--expected-steps", type=int, default=25)
    check_clock_sync.add_argument("--agent-hz", type=float, default=5.0)
    check_clock_sync.add_argument("--sensor-hz", type=float, default=10.0)
    check_clock_sync.add_argument("--tolerance-s", type=float, default=0.005)
    check_clock_sync.add_argument("--output", help="output report JSON; stdout if omitted")
    check_clock_sync.set_defaults(handler=_smoke_check_clock_sync)

    check_runtime_barrier = smoke_commands.add_parser(
        "check-runtime-barrier",
        help="validate real runtime action/communication/physics/observation barrier evidence",
    )
    check_runtime_barrier.add_argument("--trace", required=True, help="JSONL runtime barrier trace")
    check_runtime_barrier.add_argument("--expected-steps", type=int, default=10)
    check_runtime_barrier.add_argument("--agent-hz", type=float, default=5.0)
    check_runtime_barrier.add_argument("--sensor-hz", type=float, default=10.0)
    check_runtime_barrier.add_argument("--physics-hz", type=float, default=250.0)
    check_runtime_barrier.add_argument("--tolerance-s", type=float, default=0.005)
    check_runtime_barrier.add_argument(
        "--no-require-communication",
        action="store_true",
        help="do not require at least one submitted and delivered communication message",
    )
    check_runtime_barrier.add_argument(
        "--require-sensor-payloads",
        action="store_true",
        help="require RGB, depth, and point-cloud payload checksum metadata per barrier step",
    )
    check_runtime_barrier.add_argument("--output", help="output report JSON; stdout if omitted")
    check_runtime_barrier.set_defaults(handler=_smoke_check_runtime_barrier)

    check_runtime_fault = smoke_commands.add_parser(
        "check-runtime-fault",
        help="validate real Isaac/ROS runtime fault termination artifacts",
    )
    check_runtime_fault.add_argument("--run-dir", required=True, help="run artifact directory")
    check_runtime_fault.add_argument(
        "--expected-reason-code",
        help="required termination reason code, e.g. action_timeout",
    )
    check_runtime_fault.add_argument(
        "--expected-category",
        help="required termination reason category, e.g. agent_failure",
    )
    check_runtime_fault.add_argument(
        "--require-sensor-payloads",
        action="store_true",
        help="require UAV/UGV RGB, depth, and point-cloud reset payload checksums",
    )
    check_runtime_fault.add_argument(
        "--require-watchdog-evidence",
        action="store_true",
        help="require /clock-driven action-timeout watchdog evidence",
    )
    check_runtime_fault.add_argument(
        "--require-crash-evidence",
        action="store_true",
        help="require agent process crash watchdog evidence",
    )
    check_runtime_fault.add_argument(
        "--require-action-validation-evidence",
        action="store_true",
        help="require pre-publish action validation rejection evidence",
    )
    check_runtime_fault.add_argument(
        "--require-safety-evidence",
        action="store_true",
        help="require physics safety watchdog evidence such as rollover or collision",
    )
    check_runtime_fault.add_argument(
        "--require-fault-injection-evidence",
        action="store_true",
        help="require Phase 15 adapter-level fault injection timeout evidence",
    )
    check_runtime_fault.add_argument("--output", help="output report JSON; stdout if omitted")
    check_runtime_fault.set_defaults(handler=_smoke_check_runtime_fault)

    check_runtime_fault_suite = smoke_commands.add_parser(
        "check-runtime-fault-suite",
        help="validate Phase 15 real Isaac/ROS runtime fault suite artifacts",
    )
    check_runtime_fault_suite.add_argument(
        "--suite-dir",
        required=True,
        help="directory containing one subdirectory per required Phase 15 fault scenario",
    )
    check_runtime_fault_suite.add_argument(
        "--require-sensor-payloads",
        action="store_true",
        help="require UAV/UGV RGB, depth, and point-cloud reset payload checksums in every scenario",
    )
    check_runtime_fault_suite.add_argument(
        "--forbid-manual-trigger",
        action="store_true",
        help="fail if any scenario was produced by a manual adapter-reported fault trigger",
    )
    check_runtime_fault_suite.add_argument(
        "--require-fault-injection-evidence",
        action="store_true",
        help="require phase15_fault_injector auto-trigger evidence in every scenario",
    )
    check_runtime_fault_suite.add_argument("--output", help="output report JSON; stdout if omitted")
    check_runtime_fault_suite.set_defaults(handler=_smoke_check_runtime_fault_suite)

    check_runtime_api = smoke_commands.add_parser(
        "check-runtime-api",
        help="validate real RuntimeApiBridge observation/action/status sample evidence",
    )
    check_runtime_api.add_argument("--sample", required=True, help="JSON runtime API sample")
    check_runtime_api.add_argument("--output", help="output report JSON; stdout if omitted")
    check_runtime_api.add_argument(
        "--require-full-surface",
        action="store_true",
        help=(
            "require mission, inbox, per-agent last_action_status, and public info "
            "surfaces in the runtime API sample"
        ),
    )
    check_runtime_api.add_argument(
        "--require-task-feedback",
        action="store_true",
        help=(
            "require public TaskGate feedback in public_infos; implies "
            "--require-full-surface"
        ),
    )
    check_runtime_api.add_argument(
        "--require-sensor-payloads",
        action="store_true",
        help="require RGB, depth, and point-cloud payload checksum metadata",
    )
    check_runtime_api.set_defaults(handler=_smoke_check_runtime_api)

    check_runtime_interface_bundle = smoke_commands.add_parser(
        "check-runtime-interface-bundle",
        help="validate combined runtime API and synchronized step-barrier evidence",
    )
    check_runtime_interface_bundle.add_argument(
        "--runtime-api-sample",
        required=True,
        help="JSON runtime API full-surface sample",
    )
    check_runtime_interface_bundle.add_argument(
        "--runtime-barrier-trace",
        required=True,
        help="JSONL runtime barrier trace",
    )
    check_runtime_interface_bundle.add_argument("--expected-steps", type=int, default=5)
    check_runtime_interface_bundle.add_argument("--agent-hz", type=float, default=5.0)
    check_runtime_interface_bundle.add_argument("--sensor-hz", type=float, default=10.0)
    check_runtime_interface_bundle.add_argument("--physics-hz", type=float, default=250.0)
    check_runtime_interface_bundle.add_argument("--tolerance-s", type=float, default=0.005)
    check_runtime_interface_bundle.add_argument(
        "--no-require-task-feedback",
        action="store_true",
        help="do not require public TaskGate feedback in runtime API sample",
    )
    check_runtime_interface_bundle.add_argument(
        "--no-require-sensor-payloads",
        action="store_true",
        help="do not require RGB/depth/LiDAR payload checksum metadata",
    )
    check_runtime_interface_bundle.add_argument(
        "--no-require-communication",
        action="store_true",
        help="do not require at least one submitted and delivered communication message",
    )
    check_runtime_interface_bundle.add_argument(
        "--output",
        help="output bundle validation report JSON; stdout if omitted",
    )
    check_runtime_interface_bundle.set_defaults(handler=_smoke_check_runtime_interface_bundle)

    check_rayfronts_baseline = smoke_commands.add_parser(
        "check-rayfronts-baseline",
        help="validate RayFronts UAV+UGV baseline smoke coverage evidence",
    )
    check_rayfronts_baseline.add_argument(
        "--trace",
        required=True,
        help="JSONL RayFronts baseline smoke trace",
    )
    check_rayfronts_baseline.add_argument("--output", help="output report JSON; stdout if omitted")
    check_rayfronts_baseline.set_defaults(handler=_smoke_check_rayfronts_baseline)

    check_rayfronts_baseline_run = smoke_commands.add_parser(
        "check-rayfronts-baseline-run",
        help="validate a real Isaac/ROS RayFronts baseline run artifact",
    )
    check_rayfronts_baseline_run.add_argument("--run-dir", required=True, help="run artifact directory")
    check_rayfronts_baseline_run.add_argument(
        "--expected-episodes",
        type=int,
        help="required episode count",
    )
    check_rayfronts_baseline_run.add_argument(
        "--split",
        choices=("public", "hidden_test"),
        default="public",
        help="required manifest split; default: public",
    )
    check_rayfronts_baseline_run.add_argument(
        "--no-require-success",
        action="store_true",
        help="do not require every episode to have mission_success=true",
    )
    check_rayfronts_baseline_run.add_argument(
        "--no-require-energy-evidence",
        action="store_true",
        help="do not require positive UAV and UGV energy events",
    )
    policy_evidence = check_rayfronts_baseline_run.add_mutually_exclusive_group()
    policy_evidence.add_argument(
        "--require-policy-evidence",
        dest="require_policy_evidence",
        action="store_true",
        default=True,
        help="require rayfronts_baseline policy isolation evidence in run_manifest or episode records (default)",
    )
    policy_evidence.add_argument(
        "--no-require-policy-evidence",
        dest="require_policy_evidence",
        action="store_false",
        help="do not require rayfronts_baseline policy isolation evidence",
    )
    reset_dependencies = check_rayfronts_baseline_run.add_mutually_exclusive_group()
    reset_dependencies.add_argument(
        "--require-reset-support-dependencies",
        dest="require_reset_support_dependencies",
        action="store_true",
        default=True,
        help="require reset support Nav2 dependency report evidence (default)",
    )
    reset_dependencies.add_argument(
        "--no-require-reset-support-dependencies",
        dest="require_reset_support_dependencies",
        action="store_false",
        help="do not require reset support Nav2 dependency report evidence",
    )
    check_rayfronts_baseline_run.add_argument(
        "--require-mapper-derived-hypothesis",
        action="store_true",
        help=(
            "require RayFronts hypothesis evidence to come from the mapper/encoder "
            "baseline instead of the public map-probe surface"
        ),
    )
    check_rayfronts_baseline_run.add_argument(
        "--require-selected-behavior-mode",
        help=(
            "require rayfronts_baseline_evidence.json selected_hypothesis.behavior_mode "
            "to match this exact value"
        ),
    )
    check_rayfronts_baseline_run.add_argument(
        "--require-physical-mission",
        action="store_true",
        help=(
            "require full-mission physical evidence: non-trivial TTC/D2C/path, "
            "UGV Nav2 goal reached, confirmation-region membership, sensor visibility, "
            "and occlusion-clear confirmation evidence"
        ),
    )
    check_rayfronts_baseline_run.add_argument(
        "--min-time-to-confirmation-s",
        type=float,
        default=5.0,
        help="minimum TTC allowed when --require-physical-mission is set; default: 5.0",
    )
    check_rayfronts_baseline_run.add_argument(
        "--min-detection-to-confirmation-s",
        type=float,
        default=1.0,
        help="minimum D2C allowed when --require-physical-mission is set; default: 1.0",
    )
    check_rayfronts_baseline_run.add_argument(
        "--min-uav-path-m",
        type=float,
        default=1.0,
        help="minimum UAV 3D path allowed when --require-physical-mission is set; default: 1.0",
    )
    check_rayfronts_baseline_run.add_argument(
        "--min-ugv-path-m",
        type=float,
        default=1.0,
        help="minimum UGV planar path allowed when --require-physical-mission is set; default: 1.0",
    )
    check_rayfronts_baseline_run.add_argument("--output", help="output report JSON; stdout if omitted")
    check_rayfronts_baseline_run.set_defaults(handler=_smoke_check_rayfronts_baseline_run)

    check_oracle_run = smoke_commands.add_parser(
        "check-oracle-run",
        help="validate public/hidden oracle run completion and evaluator artifact consistency",
    )
    check_oracle_run.add_argument("--run-dir", required=True, help="run artifact directory")
    check_oracle_run.add_argument("--expected-episodes", type=int, help="required episode count")
    check_oracle_run.add_argument("--split", choices=("public", "hidden_test"), help="required manifest split")
    check_oracle_run.add_argument(
        "--no-require-success",
        action="store_true",
        help="do not require every episode to have mission_success=true",
    )
    check_oracle_run.add_argument(
        "--require-energy-evidence",
        action="store_true",
        help="also require per-agent energy/control_effort events in each episode trace",
    )
    check_oracle_run.add_argument(
        "--redact-private",
        action="store_true",
        help="write a public-safe hidden_test/private aggregate summary",
    )
    check_oracle_run.add_argument("--salt", help="redaction salt; not echoed in output")
    check_oracle_run.add_argument("--salt-file", help="file containing redaction salt bytes")
    check_oracle_run.add_argument("--salt-env", help="environment variable containing redaction salt")
    check_oracle_run.add_argument("--output", help="output report JSON; stdout if omitted")
    check_oracle_run.set_defaults(handler=_smoke_check_oracle_run)

    check_system_run_bundle = smoke_commands.add_parser(
        "check-system-run-bundle",
        help="validate reset/run/record/fault/performance system-run evidence bundle",
    )
    check_system_run_bundle.add_argument(
        "--soft-full-action-run-dir",
        required=True,
        help="soft full-action reset run directory",
    )
    check_system_run_bundle.add_argument(
        "--recovery-run-dir",
        required=True,
        help="selective reset recovery artifact directory",
    )
    check_system_run_bundle.add_argument(
        "--hard-restart-run-dir",
        required=True,
        help="hard restart full-health artifact directory",
    )
    check_system_run_bundle.add_argument(
        "--reset-state-run-dir",
        required=True,
        help="60-episode reset-state run directory",
    )
    check_system_run_bundle.add_argument(
        "--dock-reset-pose-report",
        required=True,
        help="dock reset pose gate report JSON",
    )
    check_system_run_bundle.add_argument(
        "--dock-reset-sequence-report",
        required=True,
        help="dock reset sequence gate report JSON",
    )
    check_system_run_bundle.add_argument(
        "--public-run-dir",
        required=True,
        help="public 60-episode real run artifact directory",
    )
    check_system_run_bundle.add_argument(
        "--performance-report",
        required=True,
        help="performance/resource stability report JSON",
    )
    check_system_run_bundle.add_argument(
        "--fault-suite-dir",
        required=True,
        help="runtime fault suite directory",
    )
    check_system_run_bundle.add_argument("--expected-episodes", type=int, default=60)
    check_system_run_bundle.add_argument(
        "--require-clock-epoch-reset",
        action="store_true",
        help="require hard restart clock epoch reset evidence",
    )
    check_system_run_bundle.add_argument("--output", help="output report JSON; stdout if omitted")
    check_system_run_bundle.set_defaults(handler=_smoke_check_system_run_bundle)


    rayfronts_baseline_contract = smoke_commands.add_parser(
        "rayfronts-baseline-contract",
        help="run RayFronts UAV+UGV policy contract smoke against an episode manifest",
    )
    rayfronts_baseline_contract.add_argument("--manifest", required=True, help="released or draft episode manifest")
    rayfronts_baseline_contract.add_argument("--rayfronts-root", default="RayFronts", help="RayFronts repository root")
    rayfronts_baseline_contract.add_argument("--trace-output", required=True, help="output JSONL smoke trace")
    rayfronts_baseline_contract.add_argument("--output", help="output check report JSON; stdout if omitted")
    rayfronts_baseline_contract.set_defaults(handler=_smoke_rayfronts_baseline_contract)

    check_isaac_headless = smoke_commands.add_parser(
        "check-isaac-headless",
        help="validate Isaac headless RetroNeighborhood smoke evidence trace",
    )
    check_isaac_headless.add_argument(
        "--trace",
        required=True,
        help="JSONL Isaac headless smoke evidence trace",
    )
    check_isaac_headless.add_argument(
        "--simulator-version",
        default=DEFAULT_ISAAC_SIMULATOR_VERSION,
        help=f"expected Isaac Sim version; default: {DEFAULT_ISAAC_SIMULATOR_VERSION}",
    )
    check_isaac_headless.add_argument("--output", help="output report JSON; stdout if omitted")
    check_isaac_headless.set_defaults(handler=_smoke_check_isaac_headless)

    isaac_preflight = smoke_commands.add_parser(
        "isaac-preflight",
        help="inspect local prerequisites for Isaac headless RetroNeighborhood smoke",
    )
    isaac_preflight.add_argument("--isaac-python", help="path or command for Isaac python.sh")
    isaac_preflight.add_argument("--isaac-sim", help="path or command for isaac-sim launcher")
    isaac_preflight.add_argument("--asset-root", help="local Isaac/AirGround asset root")
    isaac_preflight.add_argument(
        "--isaac-version-file",
        help="path to Isaac Sim VERSION file, for example /isaac-sim/VERSION",
    )
    isaac_preflight.add_argument(
        "--simulator-version",
        default=DEFAULT_ISAAC_SIMULATOR_VERSION,
        help=(
            "expected Isaac Sim version prefix "
            f"(default: {DEFAULT_ISAAC_SIMULATOR_VERSION})"
        ),
    )
    isaac_preflight.add_argument(
        "--allow-missing-gpu",
        action="store_true",
        help="do not fail when nvidia-smi/GPU is unavailable",
    )
    isaac_preflight.add_argument(
        "--allow-missing-asset-root",
        action="store_true",
        help="do not fail when asset root is unavailable",
    )
    isaac_preflight.add_argument("--output", help="output report JSON; stdout if omitted")
    isaac_preflight.set_defaults(handler=_smoke_isaac_preflight)

    isaac_launch_plan = smoke_commands.add_parser(
        "isaac-launch-plan",
        help=f"write Docker/compose commands for Isaac {DEFAULT_ISAAC_SIMULATOR_VERSION} headless smoke",
    )
    isaac_launch_plan.add_argument(
        "--repo-root",
        default=".",
        help="RAVEN-AirGround repository root; default: current directory",
    )
    isaac_launch_plan.add_argument(
        "--asset-root",
        help="host asset cache root; default: <repo-root>/assets/cache/<simulator-version>",
    )
    isaac_launch_plan.add_argument(
        "--log-dir",
        help="host log directory; default: <repo-root>/runs/p0_02_headless",
    )
    isaac_launch_plan.add_argument(
        "--simulator-version",
        default=DEFAULT_ISAAC_SIMULATOR_VERSION,
        help=(
            "Isaac Sim version for asset root and container env; "
            f"default: {DEFAULT_ISAAC_SIMULATOR_VERSION}"
        ),
    )
    isaac_launch_plan.add_argument(
        "--allow-missing-docker",
        action="store_true",
        help="do not fail when Docker is unavailable",
    )
    isaac_launch_plan.add_argument(
        "--allow-missing-asset-root",
        action="store_true",
        help="do not fail when the host asset cache is unavailable",
    )
    isaac_launch_plan.add_argument("--output", help="output plan JSON; stdout if omitted")
    isaac_launch_plan.set_defaults(handler=_smoke_isaac_launch_plan)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="airground")
    subparsers = parser.add_subparsers(dest="command", required=True)

    doctor = subparsers.add_parser("doctor", help="validate the local benchmark package")
    doctor.add_argument("--config", action="append", help="YAML override layer")
    doctor.set_defaults(handler=_doctor)
    _add_assets_commands(subparsers)
    _add_gt_commands(subparsers)
    _add_episode_commands(subparsers)
    _add_tasks_commands(subparsers)
    _add_metrics_commands(subparsers)
    _add_run_command(subparsers)
    _add_evaluate_command(subparsers)
    _add_release_commands(subparsers)
    _add_replay_commands(subparsers)
    _add_reset_commands(subparsers)
    _add_faults_commands(subparsers)
    _add_smoke_commands(subparsers)

    config = subparsers.add_parser("config", help="inspect benchmark configuration")
    config_commands = config.add_subparsers(dest="config_command", required=True)

    validate = config_commands.add_parser("validate", help="validate merged YAML layers")
    validate.add_argument("--config", action="append", help="YAML override layer")
    validate.add_argument(
        "--output",
        choices=("summary", "canonical-json"),
        default="summary",
    )
    validate.set_defaults(handler=_validate_config)

    schema = config_commands.add_parser("schema", help="write the JSON schema")
    schema.set_defaults(handler=_write_schema)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI and return a process exit code."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.handler(args))
    except (
        AssetError,
        EpisodeAuditError,
        EpisodeGenerationError,
        EpisodeManifestError,
        GroundTruthError,
        MetricsError,
        ReleaseAuditError,
        ReleaseManifestError,
        RunError,
        TrajectoryReplayError,
        OSError,
        ValueError,
        ValidationError,
        yaml.YAMLError,
    ) as error:
        LOGGER.error("%s", error)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
