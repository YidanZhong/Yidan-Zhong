"""Deterministic episode sampling from pre-validated candidate pools.

This module does not infer physics, reachability, visibility, or occlusion from
raw Isaac assets. It consumes a candidate pool produced by those upstream GT
generators and turns it into a versioned public or hidden-test manifest with
stable split semantics and balanced marginal difficulty labels.
"""

from __future__ import annotations

from airground_benchmark.scenes import SceneCatalogId, validate_scene_catalog, SceneId, scene_slug

from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
import hashlib
from itertools import combinations
import json
import math
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
import yaml

from airground_benchmark.config.schema import SCHEMA_VERSION
from airground_benchmark.ground_truth import (
    ConfirmationPose,
    ConfirmationRegion,
    TargetAnnotationManifest,
    TargetInstance,
    TargetVisibilityOcclusionMetric,
    TraversabilityGrid,
    VisibilityOcclusionReport,
)
from airground_benchmark.episode_manifest import (
    DifficultyAxes,
    EpisodeManifest,
    EpisodeManifestError,
    EpisodeTarget,
    ExpectedCounts,
    GroundTruthRef,
    ManifestSplit,
    ReleaseChannel,
    StartPair,
    TaskType,
    episode_manifest_sha256,
    salted_episode_manifest_sha256,
    timeout_from_oracle_time_s,
)
from airground_benchmark.traversability import TraversabilityQuery


DifficultyAxis = Literal["visibility", "occlusion", "detour"]
DifficultyDirection = Literal["higher_is_easier", "lower_is_easier"]

AXIS_DIRECTIONS: dict[DifficultyAxis, DifficultyDirection] = {
    "visibility": "higher_is_easier",
    "occlusion": "lower_is_easier",
    "detour": "lower_is_easier",
}


class EpisodeGenerationError(ValueError):
    """Raised when an episode manifest cannot be generated from candidates."""


class StrictModel(BaseModel):
    """Base class for generation schemas."""

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)


class CandidateOracleSummary(StrictModel):
    """Oracle/path evidence attached to one upstream candidate episode."""

    source: str = Field(min_length=1)
    estimated_completion_time_s: float = Field(gt=0.0)
    detection_to_confirmation_time_s: float = Field(ge=0.0)
    uav_path_length_m: float = Field(ge=0.0)
    ugv_path_length_m: float = Field(ge=0.0)
    waypoint_count: int = Field(ge=2)
    checksum_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_timing(self) -> "CandidateOracleSummary":
        if self.detection_to_confirmation_time_s > self.estimated_completion_time_s:
            raise ValueError("detection_to_confirmation_time_s must be <= estimated_completion_time_s")
        return self


class CandidateOracleEvidenceRecord(StrictModel):
    """Oracle/path evidence keyed by candidate_id."""

    candidate_id: str = Field(pattern=r"^[A-Za-z0-9_.-]+$")
    oracle: CandidateOracleSummary


class CandidateOracleEvidenceBundle(StrictModel):
    """Versioned oracle/path evidence bundle for candidate pools."""

    schema_version: Literal[SCHEMA_VERSION]
    generator: str = Field(default="airground-candidate-oracle-evidence-v1", min_length=1)
    records: tuple[CandidateOracleEvidenceRecord, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_unique_candidate_ids(self) -> "CandidateOracleEvidenceBundle":
        candidate_ids = [record.candidate_id for record in self.records]
        if len(set(candidate_ids)) != len(candidate_ids):
            raise ValueError("oracle evidence candidate_id values must be unique")
        return self


class CandidateEpisode(StrictModel):
    """One candidate that has already passed upstream GT and reachability filters."""

    candidate_id: str = Field(pattern=r"^[A-Za-z0-9_.-]+$")
    eligible_splits: tuple[ManifestSplit, ...] = ("public", "hidden_test")
    task_type: TaskType
    query: str = Field(min_length=1)
    starts: StartPair
    targets: tuple[EpisodeTarget, ...] = Field(min_length=1, max_length=3)
    difficulty: DifficultyAxes
    ground_truth: GroundTruthRef
    oracle: CandidateOracleSummary | None = None

    @model_validator(mode="after")
    def validate_candidate_contract(self) -> "CandidateEpisode":
        if len(set(self.eligible_splits)) != len(self.eligible_splits):
            raise ValueError("eligible_splits values must be unique")
        if not self.eligible_splits:
            raise ValueError("eligible_splits must not be empty")

        target_count = len(self.targets)
        if self.task_type == "single_target" and target_count != 1:
            raise ValueError("single_target candidates must contain exactly one target")
        if self.task_type in {"unordered_multi_target", "sequential_target"}:
            if not 2 <= target_count <= 3:
                raise ValueError(f"{self.task_type} candidates must contain 2-3 targets")

        sequence = [target.sequence_index for target in self.targets]
        if self.task_type == "sequential_target":
            if tuple(sequence) != tuple(range(target_count)):
                raise ValueError("sequential_target sequence_index must be 0..N-1")
        elif any(index is not None for index in sequence):
            raise ValueError("sequence_index is only valid for sequential_target candidates")
        return self


class CandidatePool(StrictModel):
    """Candidate episode pool for one scene and difficulty version."""

    schema_version: Literal[SCHEMA_VERSION]
    catalog_id: SceneCatalogId
    scene_id: SceneId
    difficulty_version: str = Field(pattern=r"^[A-Za-z0-9_.-]+$")
    source: str = Field(min_length=1)
    source_checksum_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    candidates: tuple[CandidateEpisode, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_unique_candidates(self) -> "CandidatePool":
        validate_scene_catalog(self.scene_id, self.catalog_id)
        candidate_ids = [candidate.candidate_id for candidate in self.candidates]
        if len(set(candidate_ids)) != len(candidate_ids):
            raise ValueError("candidate_id values must be unique")
        signatures = [_candidate_signature(candidate) for candidate in self.candidates]
        if len(set(signatures)) != len(signatures):
            raise ValueError("candidate start/target signatures must be unique")
        return self


class CandidatePoolBuildConfig(StrictModel):
    """Settings for assembling candidate pools from upstream GT artifacts."""

    difficulty_version: str = Field(default="difficulty-retro-v1", pattern=r"^[A-Za-z0-9_.-]+$")
    source: str = "airground-candidate-pool-builder-v1"
    max_single_target_candidates: int = Field(default=120, ge=0)
    max_unordered_multi_target_candidates: int = Field(default=120, ge=0)
    max_sequential_target_candidates: int = Field(default=120, ge=0)
    multi_target_size: Literal[2, 3] = 2
    min_start_confirmation_distance_m: float = Field(default=1.5, ge=0.0)
    seed_material: str = "benchmark-v1.0-retro"


class DifficultyAxisMetadata(StrictModel):
    """Tercile boundaries for one difficulty axis."""

    direction: DifficultyDirection
    low_cut: float
    high_cut: float
    label_counts: dict[str, int]

    @model_validator(mode="after")
    def validate_cuts(self) -> "DifficultyAxisMetadata":
        if self.high_cut < self.low_cut:
            raise ValueError("high_cut must be >= low_cut")
        return self


class DifficultyMetadata(StrictModel):
    """Versioned difficulty boundary metadata derived from a candidate pool."""

    schema_version: Literal[SCHEMA_VERSION]
    catalog_id: SceneCatalogId
    scene_id: SceneId
    difficulty_version: str = Field(pattern=r"^[A-Za-z0-9_.-]+$")
    source: str
    source_checksum_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    candidate_count: int = Field(ge=1)
    axes: dict[DifficultyAxis, DifficultyAxisMetadata]
    label_mismatch_count: int = Field(ge=0)
    label_mismatches: tuple[dict[str, Any], ...] = ()


class DifficultyMetadataAuditIssue(StrictModel):
    """One difficulty-metadata release audit issue."""

    code: str
    message: str


class DifficultyMetadataAuditReport(StrictModel):
    """Machine-readable audit report for frozen difficulty metadata."""

    schema_version: Literal[SCHEMA_VERSION]
    catalog_id: SceneCatalogId
    scene_id: SceneId
    difficulty_version: str = Field(pattern=r"^[A-Za-z0-9_.-]+$")
    generator: Literal["airground-difficulty-metadata-audit-v1"]
    candidate_count: int = Field(ge=0)
    metadata_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    expected_metadata_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    issue_count: int = Field(ge=0)
    status: Literal["ok", "failed"]
    issues: tuple[DifficultyMetadataAuditIssue, ...] = ()


class ReleasePairReport(StrictModel):
    """Redacted report for a deterministic public/hidden release pair."""

    schema_version: Literal[SCHEMA_VERSION]
    catalog_id: SceneCatalogId
    scene_id: SceneId
    difficulty_version: str = Field(pattern=r"^[A-Za-z0-9_.-]+$")
    status: Literal["ok"]
    public_manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    hidden_manifest_salted_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    difficulty_metadata_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    public_episode_count: int = Field(ge=0)
    hidden_episode_count: int = Field(ge=0)
    public_task_counts: dict[str, int]
    hidden_task_counts: dict[str, int]
    public_difficulty_distribution: dict[str, dict[str, int]]
    hidden_difficulty_distribution: dict[str, dict[str, int]]
    reused_start_target_signature_count: int = Field(ge=0)


class CandidatePoolAuditIssue(StrictModel):
    """One candidate-pool readiness issue."""

    code: str
    message: str
    candidate_id: str | None = None


class CandidatePoolAuditReport(StrictModel):
    """Machine-readable audit report for candidate-pool readiness."""

    schema_version: Literal[SCHEMA_VERSION]
    catalog_id: SceneCatalogId
    scene_id: SceneId
    difficulty_version: str = Field(pattern=r"^[A-Za-z0-9_.-]+$")
    generator: Literal["airground-candidate-pool-audit-v1"]
    candidate_count: int = Field(ge=0)
    task_counts: dict[str, int]
    oracle_available_count: int = Field(ge=0)
    requirements: dict[str, bool]
    issue_count: int = Field(ge=0)
    status: Literal["ok", "failed"]
    issues: tuple[CandidatePoolAuditIssue, ...] = ()


class PairedStartConfig(StrictModel):
    """Config for generating coupled UGV + docked-UAV start candidates."""

    uav_parent_frame: Literal["ugv/base_link", "ugv/platform"] = "ugv/platform"
    uav_x_m: float = 0.0
    uav_y_m: float = 0.0
    uav_z_m: float = Field(default=0.45, gt=0.0)
    uav_yaw_rad: float = 0.0
    min_takeoff_clearance_m: float = Field(default=1.0, ge=0.0)
    exclude_confirmation_radius_m: float = Field(default=1.5, ge=0.0)
    max_starts_per_component: int = Field(default=16, ge=1)


class PairedStartCandidate(StrictModel):
    """One deterministic paired start candidate for later episode generation."""

    candidate_id: str = Field(pattern=r"^[A-Za-z0-9_.-]+$")
    starts: StartPair
    traversability_component: int = Field(ge=0)
    grid_cell: tuple[int, int]
    reachable_region_ids: tuple[str, ...] = Field(min_length=1)
    takeoff_clearance_m: float | None = Field(default=None, ge=0.0)


def load_candidate_pool(path: Path) -> CandidatePool:
    """Load a candidate pool from YAML or JSON."""
    resolved = Path(path).expanduser().resolve(strict=True)
    value = yaml.safe_load(resolved.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise EpisodeGenerationError(f"candidate pool {resolved} must be a YAML mapping")
    return CandidatePool.model_validate(dict(value))


def load_difficulty_metadata(path: Path) -> DifficultyMetadata:
    """Load frozen difficulty metadata from YAML or JSON."""
    resolved = Path(path).expanduser().resolve(strict=True)
    value = yaml.safe_load(resolved.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise EpisodeGenerationError(f"difficulty metadata {resolved} must be a YAML/JSON mapping")
    return DifficultyMetadata.model_validate(dict(value))


def load_candidate_oracle_evidence(path: Path) -> tuple[CandidateOracleEvidenceRecord, ...]:
    """Load candidate oracle/path evidence from a bundle or candidate-id mapping."""
    resolved = Path(path).expanduser().resolve(strict=True)
    value = yaml.safe_load(resolved.read_text(encoding="utf-8"))
    if isinstance(value, Mapping) and "records" in value:
        return CandidateOracleEvidenceBundle.model_validate(dict(value)).records
    if not isinstance(value, Mapping):
        raise EpisodeGenerationError(f"oracle evidence {resolved} must be a YAML/JSON mapping")
    records = []
    for candidate_id, oracle in sorted(value.items()):
        if not isinstance(candidate_id, str):
            raise EpisodeGenerationError("oracle evidence mapping keys must be candidate_id strings")
        if not isinstance(oracle, Mapping):
            raise EpisodeGenerationError(f"oracle evidence for {candidate_id} must be a mapping")
        records.append(
            CandidateOracleEvidenceRecord.model_validate(
                {"candidate_id": candidate_id, "oracle": dict(oracle)}
            )
        )
    if not records:
        raise EpisodeGenerationError("oracle evidence mapping must not be empty")
    return tuple(records)


def load_paired_start_candidates(path: Path) -> tuple[PairedStartCandidate, ...]:
    """Load paired-start candidates from the deterministic JSON artifact."""
    resolved = Path(path).expanduser().resolve(strict=True)
    value = yaml.safe_load(resolved.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise EpisodeGenerationError(f"paired starts {resolved} must be a YAML/JSON mapping")
    raw_candidates = value.get("candidates")
    if not isinstance(raw_candidates, Sequence) or isinstance(raw_candidates, (str, bytes)):
        raise EpisodeGenerationError("paired starts artifact must contain a candidates array")
    candidates = tuple(PairedStartCandidate.model_validate(candidate) for candidate in raw_candidates)
    if not candidates:
        raise EpisodeGenerationError("paired starts artifact must contain at least one candidate")
    return candidates


def attach_oracle_evidence_to_candidate_pool(
    pool: CandidatePool,
    records: Sequence[CandidateOracleEvidenceRecord],
    *,
    require_all: bool = False,
    allow_extra: bool = False,
) -> CandidatePool:
    """Return a candidate pool with oracle/path evidence attached by candidate_id."""
    evidence_by_id: dict[str, CandidateOracleSummary] = {}
    duplicates: list[str] = []
    for record in records:
        if record.candidate_id in evidence_by_id:
            duplicates.append(record.candidate_id)
        evidence_by_id[record.candidate_id] = record.oracle
    if duplicates:
        raise EpisodeGenerationError(
            f"duplicate oracle evidence candidate ids: {', '.join(sorted(set(duplicates))[:5])}"
        )
    candidate_ids = {candidate.candidate_id for candidate in pool.candidates}
    extra_ids = sorted(set(evidence_by_id) - candidate_ids)
    if extra_ids and not allow_extra:
        raise EpisodeGenerationError(
            f"oracle evidence contains unknown candidate ids: {', '.join(extra_ids[:5])}"
        )
    missing = [
        candidate.candidate_id
        for candidate in pool.candidates
        if candidate.candidate_id not in evidence_by_id and candidate.oracle is None
    ]
    if require_all and missing:
        raise EpisodeGenerationError(
            f"oracle evidence missing for {len(missing)} candidates: {', '.join(missing[:5])}"
        )
    payload = pool.model_dump(mode="json")
    updated_candidates = []
    for candidate in pool.candidates:
        candidate_payload = candidate.model_dump(mode="json")
        oracle = evidence_by_id.get(candidate.candidate_id)
        if oracle is not None:
            candidate_payload["oracle"] = oracle.model_dump(mode="json")
        updated_candidates.append(candidate_payload)
    payload["candidates"] = updated_candidates
    return CandidatePool.model_validate(payload)


def estimate_candidate_grid_oracle_evidence(
    pool: CandidatePool,
    target_manifest: TargetAnnotationManifest,
    *,
    source: str = "airground-grid-oracle-estimate-v1",
    uav_speed_mps: float = 4.0,
    ugv_speed_mps: float = 0.8,
    detection_overhead_s_per_target: float = 1.5,
    confirmation_overhead_s_per_target: float = 1.0,
) -> CandidateOracleEvidenceBundle:
    """Build deterministic candidate-level grid/path oracle estimates.

    This is a reproducible upper-bound estimator for release sampling and timeout
    derivation when a real Isaac/ROS oracle batch has not yet been rerun for a
    regenerated candidate pool. It only consumes reviewed target GT and candidate
    metadata; it does not claim sensor, Nav2, or controller success.
    """
    if uav_speed_mps <= 0.0 or not math.isfinite(uav_speed_mps):
        raise EpisodeGenerationError("uav_speed_mps must be finite and positive")
    if ugv_speed_mps <= 0.0 or not math.isfinite(ugv_speed_mps):
        raise EpisodeGenerationError("ugv_speed_mps must be finite and positive")
    if detection_overhead_s_per_target < 0.0 or not math.isfinite(
        detection_overhead_s_per_target
    ):
        raise EpisodeGenerationError("detection_overhead_s_per_target must be finite and non-negative")
    if confirmation_overhead_s_per_target < 0.0 or not math.isfinite(
        confirmation_overhead_s_per_target
    ):
        raise EpisodeGenerationError(
            "confirmation_overhead_s_per_target must be finite and non-negative"
        )

    targets_by_id = {instance.instance_id: instance for instance in target_manifest.instances}
    regions_by_id = {
        region.region_id: region for region in target_manifest.confirmation_regions
    }
    records: list[CandidateOracleEvidenceRecord] = []
    for candidate in pool.candidates:
        ordered_targets = _candidate_targets_for_grid_oracle(candidate, regions_by_id)
        ugv_x = candidate.starts.ugv.x_m
        ugv_y = candidate.starts.ugv.y_m
        uav_x = candidate.starts.ugv.x_m
        uav_y = candidate.starts.ugv.y_m
        ugv_direct_path_m = 0.0
        uav_path_m = 0.0
        path_payload: list[dict[str, Any]] = []
        for target in ordered_targets:
            target_instance = targets_by_id.get(target.instance_id)
            if target_instance is None:
                raise EpisodeGenerationError(
                    f"candidate {candidate.candidate_id} references unknown target "
                    f"{target.instance_id}"
            )
            target_x, target_y, _ = target_instance.obb.center_xyz_m
            uav_direct_leg_m = math.hypot(target_x - uav_x, target_y - uav_y)
            uav_path_m += uav_direct_leg_m
            uav_x, uav_y = target_x, target_y

            region = regions_by_id.get(target.confirmation_region_id)
            if region is None:
                raise EpisodeGenerationError(
                    f"candidate {candidate.candidate_id} references unknown "
                    f"confirmation region {target.confirmation_region_id}"
                )
            pose = _nearest_confirmation_pose(ugv_x, ugv_y, region)
            pose_x, pose_y, _ = pose.position_xyz_m
            direct_leg_m = math.hypot(pose_x - ugv_x, pose_y - ugv_y)
            ugv_direct_path_m += direct_leg_m
            ugv_x, ugv_y = pose_x, pose_y
            path_payload.append(
                {
                    "instance_id": target.instance_id,
                    "confirmation_region_id": target.confirmation_region_id,
                    "confirmation_pose_xyz_m": pose.position_xyz_m,
                    "ugv_direct_leg_m": direct_leg_m,
                    "uav_direct_leg_m": uav_direct_leg_m,
                }
            )

        target_count = len(ordered_targets)
        ugv_path_m = ugv_direct_path_m * max(1.0, float(candidate.difficulty.detour))
        detection_time_s = max(
            2.0,
            (uav_path_m / uav_speed_mps) + detection_overhead_s_per_target * target_count,
        )
        detection_to_confirmation_time_s = max(
            2.0,
            (ugv_path_m / ugv_speed_mps)
            + confirmation_overhead_s_per_target * target_count,
        )
        estimated_completion_time_s = max(
            detection_time_s + detection_to_confirmation_time_s,
            detection_to_confirmation_time_s + 4.0,
        )
        checksum_payload = {
            "candidate_id": candidate.candidate_id,
            "difficulty_detour": candidate.difficulty.detour,
            "source": source,
            "targets": path_payload,
            "timing": {
                "uav_speed_mps": uav_speed_mps,
                "ugv_speed_mps": ugv_speed_mps,
                "detection_overhead_s_per_target": detection_overhead_s_per_target,
                "confirmation_overhead_s_per_target": confirmation_overhead_s_per_target,
            },
        }
        records.append(
            CandidateOracleEvidenceRecord(
                candidate_id=candidate.candidate_id,
                oracle=CandidateOracleSummary(
                    source=source,
                    estimated_completion_time_s=estimated_completion_time_s,
                    detection_to_confirmation_time_s=detection_to_confirmation_time_s,
                    uav_path_length_m=uav_path_m,
                    ugv_path_length_m=ugv_path_m,
                    waypoint_count=max(2, target_count + 1),
                    checksum_sha256=hashlib.sha256(
                        json.dumps(
                            checksum_payload,
                            ensure_ascii=True,
                            sort_keys=True,
                            separators=(",", ":"),
                        ).encode("utf-8")
                    ).hexdigest(),
                ),
            )
        )
    return CandidateOracleEvidenceBundle(
        schema_version=pool.schema_version,
        generator=source,
        records=tuple(records),
    )


def build_paired_start_candidates(
    grid: TraversabilityGrid,
    confirmation_regions: Sequence[ConfirmationRegion],
    *,
    config: PairedStartConfig | None = None,
    ceiling_height: Any | None = None,
    seed_material: str = "benchmark-v1.0-retro",
) -> tuple[PairedStartCandidate, ...]:
    """Generate deterministic UAV-on-UGV paired starts from traversability GT.

    The generator only consumes already validated traversability and confirmation
    region artifacts. It does not infer physics or target visibility. Each start
    places the UGV on a traversable cell in the same connected component as at
    least one reachable confirmation pose and places the UAV at an editable
    relative pose on the UGV platform.
    """
    resolved = config or PairedStartConfig()
    ceiling = _validate_ceiling_height(ceiling_height, grid)
    regions_by_component = _reachable_regions_by_component(confirmation_regions)
    rows, cols = grid.metadata.shape
    selected: list[PairedStartCandidate] = []
    for component, regions in sorted(regions_by_component.items()):
        cell_rows: list[tuple[str, int, int, float | None]] = []
        for row in range(rows):
            for col in range(cols):
                pose = grid.traversable_pose_at_cell(row, col)
                if pose is None:
                    continue
                x_m, y_m, z_m, cell_component = pose
                if cell_component != component:
                    continue
                clearance_m = _takeoff_clearance_m(
                    ceiling,
                    row,
                    col,
                    z_m,
                    uav_platform_z_m=resolved.uav_z_m,
                )
                if ceiling is not None and (
                    clearance_m is None
                    or clearance_m < resolved.min_takeoff_clearance_m
                ):
                    continue
                if _inside_excluded_region_radius(
                    x_m,
                    y_m,
                    regions,
                    radius_m=resolved.exclude_confirmation_radius_m,
                ):
                    continue
                order_key = _stable_start_order_key(seed_material, component, row, col)
                cell_rows.append((order_key, row, col, clearance_m))
        if not cell_rows:
            continue
        for _, row, col, clearance_m in sorted(cell_rows)[: resolved.max_starts_per_component]:
            x_m, y_m, _, _ = grid.traversable_pose_at_cell(row, col)  # type: ignore[misc]
            yaw_rad = _yaw_toward_nearest_region(x_m, y_m, regions)
            selected.append(
                PairedStartCandidate.model_validate(
                    {
                        "candidate_id": f"paired-start-c{component}-r{row}-c{col}",
                        "starts": {
                            "ugv": {
                                "frame": "map",
                                "x_m": x_m,
                                "y_m": y_m,
                                "yaw_rad": yaw_rad,
                            },
                            "uav_on_platform": {
                                "parent_frame": resolved.uav_parent_frame,
                                "x_m": resolved.uav_x_m,
                                "y_m": resolved.uav_y_m,
                                "z_m": resolved.uav_z_m,
                                "yaw_rad": resolved.uav_yaw_rad,
                            },
                            "docked": True,
                        },
                        "traversability_component": component,
                        "grid_cell": (row, col),
                        "reachable_region_ids": tuple(region.region_id for region in regions),
                        "takeoff_clearance_m": clearance_m,
                    }
                )
            )
    if not selected:
        raise EpisodeGenerationError("no valid paired starts found")
    return tuple(selected)


def build_candidate_pool_from_artifacts(
    paired_starts: Sequence[PairedStartCandidate],
    target_manifest: TargetAnnotationManifest,
    visibility_report: VisibilityOcclusionReport,
    grid: TraversabilityGrid,
    *,
    ground_truth: GroundTruthRef | Mapping[str, Any],
    config: CandidatePoolBuildConfig | None = None,
) -> CandidatePool:
    """Assemble a deterministic candidate pool from upstream GT artifacts.

    This builder consumes already generated paired starts, target annotations,
    visibility/occlusion metrics, and traversability GT. It does not run Isaac,
    oracle policies, or hidden split sampling; it prepares candidate episodes
    with raw difficulty values for later audit, difficulty metadata, and release
    sampling steps.
    """
    if not (target_manifest.scene_id == visibility_report.scene_id == grid.metadata.scene_id):
        raise EpisodeGenerationError("targets, visibility and traversability must share a scene")
    resolved = config or CandidatePoolBuildConfig(
        difficulty_version=f"difficulty-{scene_slug(target_manifest.scene_id)}-v1",
        seed_material=f"benchmark-v1.0-{scene_slug(target_manifest.scene_id)}",
    )
    ground_truth_ref = GroundTruthRef.model_validate(ground_truth)
    if not paired_starts:
        raise EpisodeGenerationError("candidate pool builder requires paired starts")
    target_options = _candidate_target_options(target_manifest, visibility_report)
    if not target_options:
        raise EpisodeGenerationError("candidate pool builder found no reachable targets with metrics")
    query = TraversabilityQuery(grid)
    raw_candidates: list[dict[str, Any]] = []
    feasible_by_start: dict[str, list[dict[str, Any]]] = {}
    for start in paired_starts:
        feasible_targets = []
        for option in target_options:
            detour = query.detour_ratio_to_confirmation_region(
                (start.starts.ugv.x_m, start.starts.ugv.y_m),
                option["region"],
            )
            if detour is None:
                continue
            if _start_too_close_to_region(
                start,
                option["region"],
                min_distance_m=resolved.min_start_confirmation_distance_m,
            ):
                continue
            feasible_targets.append({**option, "detour": detour})
            raw_candidates.append(
                _raw_candidate_payload(
                    "single_target",
                    start,
                    (feasible_targets[-1],),
                    ground_truth=ground_truth_ref,
                    seed_material=resolved.seed_material,
                )
            )
        feasible_by_start[start.candidate_id] = feasible_targets

    for start in paired_starts:
        feasible_targets = feasible_by_start.get(start.candidate_id, [])
        for target_group in combinations(feasible_targets, resolved.multi_target_size):
            raw_candidates.append(
                _raw_candidate_payload(
                    "unordered_multi_target",
                    start,
                    target_group,
                    ground_truth=ground_truth_ref,
                    seed_material=resolved.seed_material,
                )
            )
            raw_candidates.append(
                _raw_candidate_payload(
                    "sequential_target",
                    start,
                    target_group,
                    ground_truth=ground_truth_ref,
                    seed_material=resolved.seed_material,
                )
            )

    limited = [
        *_limit_raw_candidates(raw_candidates, "single_target", resolved.max_single_target_candidates),
        *_limit_raw_candidates(
            raw_candidates,
            "unordered_multi_target",
            resolved.max_unordered_multi_target_candidates,
        ),
        *_limit_raw_candidates(raw_candidates, "sequential_target", resolved.max_sequential_target_candidates),
    ]
    if not limited:
        raise EpisodeGenerationError("candidate pool builder produced no feasible candidates")
    labeled = _label_raw_candidates(limited)
    return CandidatePool.model_validate(
        {
            "schema_version": SCHEMA_VERSION,
            "catalog_id": f"benchmark-v1.0-{scene_slug(target_manifest.scene_id)}",
            "scene_id": target_manifest.scene_id,
            "difficulty_version": resolved.difficulty_version,
            "source": resolved.source,
            "candidates": labeled,
        }
    )


def build_manifest_from_candidates(
    pool: CandidatePool,
    *,
    split: ManifestSplit,
    exclude_manifests: Sequence[EpisodeManifest] = (),
    expected_counts: ExpectedCounts | None = None,
    seed_base: int | None = None,
    status: Literal["draft", "released"] = "released",
    use_oracle_timeouts: bool = False,
) -> EpisodeManifest:
    """Select a deterministic, difficulty-balanced manifest from a candidate pool."""
    counts = expected_counts or ExpectedCounts(
        total=60,
        single_target=30,
        unordered_multi_target=15,
        sequential_target=15,
    )
    if status == "released" and counts.total != 60:
        raise EpisodeGenerationError("released manifests must use the 60 episode contract")

    excluded_signatures = {
        _episode_signature(episode)
        for manifest in exclude_manifests
        for episode in manifest.episodes
    }
    release_channel: ReleaseChannel = "public" if split == "public" else "private"
    public = split == "public"
    base_seed = seed_base if seed_base is not None else _default_seed_base(split)
    selected: list[CandidateEpisode] = []

    task_plan: tuple[tuple[TaskType, int], ...] = (
        ("single_target", counts.single_target),
        ("unordered_multi_target", counts.unordered_multi_target),
        ("sequential_target", counts.sequential_target),
    )
    for task_type, required_count in task_plan:
        task_candidates = [
            candidate
            for candidate in pool.candidates
            if task_type == candidate.task_type
            and split in candidate.eligible_splits
            and _candidate_signature(candidate) not in excluded_signatures
        ]
        selected_for_task = _balanced_select(
            task_candidates,
            required_count,
            seed_material=f"{pool.catalog_id}:{pool.difficulty_version}:{split}:{task_type}",
        )
        selected.extend(selected_for_task)
        excluded_signatures.update(
            _candidate_signature(candidate) for candidate in selected_for_task
        )

    episodes = []
    for index, candidate in enumerate(selected):
        episode = {
            "episode_id": f"retro-{split.replace('_', '-')}-{index:03d}",
            "seed": base_seed + index,
            "split": split,
            "release_channel": release_channel,
            "difficulty_version": pool.difficulty_version,
            "scene_id": pool.scene_id,
            "task_type": candidate.task_type,
            "query": candidate.query,
            "timeout_s": _candidate_timeout_s(candidate, use_oracle_timeouts=use_oracle_timeouts),
            "starts": candidate.starts.model_dump(mode="json"),
            "targets": [
                _target_for_task(candidate.task_type, target, target_index)
                for target_index, target in enumerate(candidate.targets)
            ],
            "difficulty": candidate.difficulty.model_dump(mode="json"),
            "ground_truth": candidate.ground_truth.model_dump(mode="json"),
        }
        episodes.append(episode)

    return EpisodeManifest.model_validate(
        {
            "schema_version": SCHEMA_VERSION,
            "catalog_id": pool.catalog_id,
            "scene_id": pool.scene_id,
            "split": split,
            "release_channel": release_channel,
            "difficulty_version": pool.difficulty_version,
            "public": public,
            "zero_shot": True,
            "status": status,
            "expected_counts": counts.model_dump(mode="json"),
            "episodes": episodes,
        }
    )


def difficulty_metadata_from_candidates(pool: CandidatePool) -> DifficultyMetadata:
    """Compute fixed tercile boundaries and label consistency metadata."""
    axes: dict[DifficultyAxis, DifficultyAxisMetadata] = {}
    mismatches: list[dict[str, Any]] = []
    for axis, direction in AXIS_DIRECTIONS.items():
        values = sorted(_candidate_axis_value(candidate, axis) for candidate in pool.candidates)
        low_cut, high_cut = _tercile_cuts(values)
        expected_labels = _rank_tercile_labels(
            (
                (candidate.candidate_id, _candidate_axis_value(candidate, axis))
                for candidate in pool.candidates
            ),
            direction,
        )
        counts = Counter()
        for candidate in pool.candidates:
            value = _candidate_axis_value(candidate, axis)
            expected = expected_labels[candidate.candidate_id]
            actual = _candidate_axis_label(candidate, axis)
            counts[actual] += 1
            if expected != actual:
                mismatches.append(
                    {
                        "axis": axis,
                        "candidate_id": candidate.candidate_id,
                        "actual_label": actual,
                        "expected_label": expected,
                        "value": value,
                    }
                )
        axes[axis] = DifficultyAxisMetadata.model_validate(
            {
                "direction": direction,
                "low_cut": low_cut,
                "high_cut": high_cut,
                "label_counts": {label: counts[label] for label in ("easy", "medium", "hard")},
            }
        )
    return DifficultyMetadata.model_validate(
        {
            "schema_version": pool.schema_version,
            "catalog_id": pool.catalog_id,
            "scene_id": pool.scene_id,
            "difficulty_version": pool.difficulty_version,
            "source": pool.source,
            "source_checksum_sha256": pool.source_checksum_sha256,
            "candidate_count": len(pool.candidates),
            "axes": {axis: metadata.model_dump(mode="json") for axis, metadata in axes.items()},
            "label_mismatch_count": len(mismatches),
            "label_mismatches": tuple(mismatches[:100]),
        }
    )


def canonical_difficulty_metadata_json(metadata: DifficultyMetadata) -> str:
    """Serialize difficulty metadata deterministically."""
    return (
        json.dumps(
            metadata.model_dump(mode="json"),
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    )


def difficulty_metadata_sha256(metadata: DifficultyMetadata) -> str:
    """Return SHA-256 of canonical difficulty metadata JSON."""
    return hashlib.sha256(canonical_difficulty_metadata_json(metadata).encode("utf-8")).hexdigest()


def canonical_difficulty_metadata_audit_json(report: DifficultyMetadataAuditReport) -> str:
    """Serialize a difficulty metadata audit report deterministically."""
    return (
        json.dumps(
            report.model_dump(mode="json"),
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    )


def canonical_release_pair_report_json(report: ReleasePairReport) -> str:
    """Serialize a release-pair report deterministically."""
    return (
        json.dumps(
            report.model_dump(mode="json"),
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    )


def canonical_candidate_pool_audit_json(report: CandidatePoolAuditReport) -> str:
    """Serialize a candidate-pool audit report deterministically."""
    return (
        json.dumps(
            report.model_dump(mode="json"),
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    )


def canonical_candidate_pool_json(pool: CandidatePool) -> str:
    """Serialize a candidate pool deterministically."""
    return (
        json.dumps(
            pool.model_dump(mode="json"),
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    )


def canonical_candidate_oracle_evidence_json(
    bundle: CandidateOracleEvidenceBundle,
) -> str:
    """Serialize candidate oracle/path evidence deterministically."""
    return (
        json.dumps(
            bundle.model_dump(mode="json"),
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    )


def canonical_paired_start_candidates_json(
    candidates: Sequence[PairedStartCandidate],
) -> str:
    """Serialize paired start candidates as a deterministic artifact."""
    return (
        json.dumps(
            {
                "candidate_count": len(candidates),
                "candidates": [
                    candidate.model_dump(mode="json") for candidate in candidates
                ],
                "generator": "airground-paired-start-generator-v1",
                "schema_version": SCHEMA_VERSION,
                "status": "ok",
            },
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    )


def build_release_pair_from_candidates(
    pool: CandidatePool,
    *,
    hidden_salt: bytes | str,
    public_seed_base: int | None = None,
    hidden_seed_base: int | None = None,
    use_oracle_timeouts: bool = False,
) -> tuple[EpisodeManifest, EpisodeManifest, DifficultyMetadata, ReleasePairReport]:
    """Generate public and hidden manifests together from one candidate pool.

    The hidden manifest is returned to the caller for private scoring storage,
    but the report only contains redacted aggregate metadata and a salted hidden
    manifest commitment.
    """
    difficulty_metadata = difficulty_metadata_from_candidates(pool)
    validate_candidate_labels_against_metadata(difficulty_metadata)
    public_manifest = build_manifest_from_candidates(
        pool,
        split="public",
        seed_base=public_seed_base,
        status="released",
        use_oracle_timeouts=use_oracle_timeouts,
    )
    hidden_manifest = build_manifest_from_candidates(
        pool,
        split="hidden_test",
        exclude_manifests=(public_manifest,),
        seed_base=hidden_seed_base,
        status="released",
        use_oracle_timeouts=use_oracle_timeouts,
    )
    public_signatures = {_episode_signature(episode) for episode in public_manifest.episodes}
    hidden_signatures = {_episode_signature(episode) for episode in hidden_manifest.episodes}
    reused = len(public_signatures & hidden_signatures)
    if reused:
        raise EpisodeGenerationError(
            f"public and hidden manifests reuse {reused} start/target signatures"
        )
    report = ReleasePairReport(
        schema_version=pool.schema_version,
        catalog_id=pool.catalog_id,
        scene_id=pool.scene_id,
        difficulty_version=pool.difficulty_version,
        status="ok",
        public_manifest_sha256=episode_manifest_sha256(public_manifest),
        hidden_manifest_salted_sha256=salted_episode_manifest_sha256(
            hidden_manifest,
            hidden_salt,
        ),
        difficulty_metadata_sha256=hashlib.sha256(
            canonical_difficulty_metadata_json(difficulty_metadata).encode("utf-8")
        ).hexdigest(),
        public_episode_count=len(public_manifest.episodes),
        hidden_episode_count=len(hidden_manifest.episodes),
        public_task_counts=public_manifest.task_counts,
        hidden_task_counts=hidden_manifest.task_counts,
        public_difficulty_distribution=_manifest_difficulty_distribution(public_manifest),
        hidden_difficulty_distribution=_manifest_difficulty_distribution(hidden_manifest),
        reused_start_target_signature_count=reused,
    )
    return public_manifest, hidden_manifest, difficulty_metadata, report


def audit_candidate_pool(
    pool: CandidatePool,
    *,
    require_oracle: bool = False,
    max_issues: int = 100,
) -> CandidatePoolAuditReport:
    """Audit candidate-pool readiness before manifest generation."""
    if max_issues < 0:
        raise EpisodeGenerationError("max_issues must be non-negative")
    issues: list[CandidatePoolAuditIssue] = []
    task_counts = Counter(candidate.task_type for candidate in pool.candidates)
    oracle_available_count = 0
    for candidate in pool.candidates:
        if candidate.oracle is None:
            if require_oracle:
                issues.append(
                    CandidatePoolAuditIssue(
                        code="missing_oracle_evidence",
                        candidate_id=candidate.candidate_id,
                        message="candidate must include oracle/path evidence",
                    )
                )
            continue
        oracle_available_count += 1
    status: Literal["ok", "failed"] = "ok" if not issues else "failed"
    return CandidatePoolAuditReport(
        schema_version=pool.schema_version,
        catalog_id=pool.catalog_id,
        scene_id=pool.scene_id,
        difficulty_version=pool.difficulty_version,
        generator="airground-candidate-pool-audit-v1",
        candidate_count=len(pool.candidates),
        task_counts={
            "single_target": task_counts["single_target"],
            "unordered_multi_target": task_counts["unordered_multi_target"],
            "sequential_target": task_counts["sequential_target"],
        },
        oracle_available_count=oracle_available_count,
        requirements={"require_oracle": require_oracle},
        issue_count=len(issues),
        status=status,
        issues=tuple(issues[:max_issues]),
    )


def audit_difficulty_metadata(
    pool: CandidatePool,
    metadata: DifficultyMetadata,
) -> DifficultyMetadataAuditReport:
    """Audit frozen difficulty metadata against the current candidate pool."""
    expected = difficulty_metadata_from_candidates(pool)
    issues: list[DifficultyMetadataAuditIssue] = []
    metadata_json = canonical_difficulty_metadata_json(metadata)
    expected_json = canonical_difficulty_metadata_json(expected)
    if metadata_json != expected_json:
        issues.append(
            DifficultyMetadataAuditIssue(
                code="difficulty_metadata_mismatch",
                message="metadata does not match boundaries recomputed from candidate pool",
            )
        )
    if expected.label_mismatch_count:
        issues.append(
            DifficultyMetadataAuditIssue(
                code="candidate_label_mismatch",
                message=f"{expected.label_mismatch_count} candidate labels disagree with recomputed boundaries",
            )
        )
    status: Literal["ok", "failed"] = "ok" if not issues else "failed"
    return DifficultyMetadataAuditReport(
        schema_version=pool.schema_version,
        catalog_id=pool.catalog_id,
        scene_id=pool.scene_id,
        difficulty_version=pool.difficulty_version,
        generator="airground-difficulty-metadata-audit-v1",
        candidate_count=len(pool.candidates),
        metadata_sha256=hashlib.sha256(metadata_json.encode("utf-8")).hexdigest(),
        expected_metadata_sha256=hashlib.sha256(expected_json.encode("utf-8")).hexdigest(),
        issue_count=len(issues),
        status=status,
        issues=tuple(issues),
    )


def validate_candidate_labels_against_metadata(metadata: DifficultyMetadata) -> None:
    """Raise if candidate labels disagree with computed metadata."""
    if metadata.label_mismatch_count:
        raise EpisodeGenerationError(
            f"candidate difficulty labels do not match tercile metadata: "
            f"{metadata.label_mismatch_count} mismatches"
        )


def _validate_ceiling_height(ceiling_height: Any | None, grid: TraversabilityGrid) -> Any | None:
    if ceiling_height is None:
        return None
    if getattr(ceiling_height, "shape", None) != tuple(grid.metadata.shape):
        raise EpisodeGenerationError("ceiling_height shape must match traversability grid")
    return ceiling_height


def _reachable_regions_by_component(
    confirmation_regions: Sequence[ConfirmationRegion],
) -> dict[int, tuple[ConfirmationRegion, ...]]:
    grouped: dict[int, list[ConfirmationRegion]] = {}
    for region in confirmation_regions:
        if not region.reachable:
            continue
        components = {
            int(pose.traversability_component)
            for pose in region.poses
            if pose.traversability_component is not None
            and int(pose.traversability_component) >= 0
        }
        for component in sorted(components):
            grouped.setdefault(component, []).append(region)
    if not grouped:
        raise EpisodeGenerationError("no reachable confirmation regions with components")
    return {component: tuple(regions) for component, regions in grouped.items()}


def _takeoff_clearance_m(
    ceiling_height: Any | None,
    row: int,
    col: int,
    ground_z_m: float,
    *,
    uav_platform_z_m: float,
) -> float | None:
    if ceiling_height is None:
        return None
    clearance_m = float(ceiling_height[row, col]) - ground_z_m - uav_platform_z_m
    if not math.isfinite(clearance_m):
        return None
    return max(0.0, clearance_m)


def _inside_excluded_region_radius(
    x_m: float,
    y_m: float,
    regions: Sequence[ConfirmationRegion],
    *,
    radius_m: float,
) -> bool:
    if radius_m <= 0.0:
        return False
    for region in regions:
        for pose in region.poses:
            px, py, _ = pose.position_xyz_m
            if math.hypot(x_m - px, y_m - py) < radius_m:
                return True
    return False


def _stable_start_order_key(
    seed_material: str,
    component: int,
    row: int,
    col: int,
) -> str:
    return hashlib.sha256(
        f"{seed_material}:{component}:{row}:{col}".encode("utf-8")
    ).hexdigest()


def _yaw_toward_nearest_region(
    x_m: float,
    y_m: float,
    regions: Sequence[ConfirmationRegion],
) -> float:
    nearest_pose = min(
        (pose for region in regions for pose in region.poses),
        key=lambda pose: math.hypot(x_m - pose.position_xyz_m[0], y_m - pose.position_xyz_m[1]),
    )
    px, py, _ = nearest_pose.position_xyz_m
    return math.atan2(py - y_m, px - x_m)


def _target_for_task(
    task_type: TaskType,
    target: EpisodeTarget,
    target_index: int,
) -> dict[str, Any]:
    value = target.model_dump(mode="json")
    if task_type == "sequential_target":
        value["sequence_index"] = target_index
    else:
        value["sequence_index"] = None
    return value


def _candidate_targets_for_grid_oracle(
    candidate: CandidateEpisode,
    regions_by_id: Mapping[str, ConfirmationRegion],
) -> tuple[EpisodeTarget, ...]:
    if candidate.task_type != "unordered_multi_target":
        return tuple(candidate.targets)

    remaining = list(candidate.targets)
    ordered: list[EpisodeTarget] = []
    ugv_x = candidate.starts.ugv.x_m
    ugv_y = candidate.starts.ugv.y_m
    while remaining:
        next_target = min(
            remaining,
            key=lambda target: (
                _distance_to_nearest_confirmation_pose(
                    ugv_x,
                    ugv_y,
                    _region_for_grid_oracle(target, regions_by_id),
                ),
                target.instance_id,
            ),
        )
        pose = _nearest_confirmation_pose(
            ugv_x,
            ugv_y,
            _region_for_grid_oracle(next_target, regions_by_id),
        )
        pose_x, pose_y, _ = pose.position_xyz_m
        ugv_x, ugv_y = pose_x, pose_y
        ordered.append(next_target)
        remaining.remove(next_target)
    return tuple(ordered)


def _region_for_grid_oracle(
    target: EpisodeTarget,
    regions_by_id: Mapping[str, ConfirmationRegion],
) -> ConfirmationRegion:
    region = regions_by_id.get(target.confirmation_region_id)
    if region is None:
        raise EpisodeGenerationError(
            f"target {target.instance_id} references unknown confirmation region "
            f"{target.confirmation_region_id}"
        )
    return region


def _distance_to_nearest_confirmation_pose(
    x_m: float,
    y_m: float,
    region: ConfirmationRegion,
) -> float:
    pose = _nearest_confirmation_pose(x_m, y_m, region)
    pose_x, pose_y, _ = pose.position_xyz_m
    return math.hypot(pose_x - x_m, pose_y - y_m)


def _nearest_confirmation_pose(
    x_m: float,
    y_m: float,
    region: ConfirmationRegion,
) -> ConfirmationPose:
    if not region.reachable or not region.poses:
        raise EpisodeGenerationError(
            f"confirmation region {region.region_id} is not reachable for oracle estimate"
        )
    return min(
        region.poses,
        key=lambda pose: (
            math.hypot(pose.position_xyz_m[0] - x_m, pose.position_xyz_m[1] - y_m),
            pose.position_xyz_m,
            pose.yaw_rad,
        ),
    )


def _candidate_timeout_s(
    candidate: CandidateEpisode,
    *,
    use_oracle_timeouts: bool,
) -> int:
    if not use_oracle_timeouts:
        return 300
    if candidate.oracle is None:
        raise EpisodeGenerationError(
            f"candidate {candidate.candidate_id} is missing oracle evidence for timeout derivation"
        )
    return timeout_from_oracle_time_s(candidate.oracle.estimated_completion_time_s)


def _tercile_cuts(values: Sequence[float]) -> tuple[float, float]:
    if not values:
        raise EpisodeGenerationError("difficulty metadata requires at least one value")
    low_index = max(0, min(len(values) - 1, (len(values) + 2) // 3 - 1))
    high_index = max(0, min(len(values) - 1, (2 * len(values) + 2) // 3 - 1))
    return float(values[low_index]), float(values[high_index])


def _label_for_value(
    value: float,
    low_cut: float,
    high_cut: float,
    direction: DifficultyDirection,
) -> str:
    if direction == "lower_is_easier":
        if value <= low_cut:
            return "easy"
        if value <= high_cut:
            return "medium"
        return "hard"
    if value <= low_cut:
        return "hard"
    if value <= high_cut:
        return "medium"
    return "easy"


def _rank_tercile_labels(
    items: Iterable[tuple[str, float]],
    direction: DifficultyDirection,
) -> dict[str, str]:
    ranked = sorted(
        ((candidate_id, float(value)) for candidate_id, value in items),
        key=lambda item: ((-item[1] if direction == "higher_is_easier" else item[1]), item[0]),
    )
    targets = _ideal_label_counts(len(ranked))
    labels: dict[str, str] = {}
    offset = 0
    for label in ("easy", "medium", "hard"):
        for candidate_id, _ in ranked[offset : offset + targets[label]]:
            labels[candidate_id] = label
        offset += targets[label]
    return labels


def _candidate_axis_value(candidate: CandidateEpisode, axis: DifficultyAxis) -> float:
    return float(getattr(candidate.difficulty, axis))


def _candidate_axis_label(candidate: CandidateEpisode, axis: DifficultyAxis) -> str:
    return str(getattr(candidate.difficulty, f"{axis}_label"))


def _manifest_difficulty_distribution(manifest: EpisodeManifest) -> dict[str, dict[str, int]]:
    return {
        axis: {
            label: Counter(
                getattr(episode.difficulty, f"{axis}_label")
                for episode in manifest.episodes
            )[label]
            for label in ("easy", "medium", "hard")
        }
        for axis in ("visibility", "occlusion", "detour")
    }


def _balanced_select(
    candidates: Sequence[CandidateEpisode],
    count: int,
    *,
    seed_material: str,
) -> tuple[CandidateEpisode, ...]:
    if count < 0:
        raise EpisodeGenerationError("episode count must be non-negative")
    if len(candidates) < count:
        raise EpisodeGenerationError(
            f"insufficient candidates for balanced selection: need {count}, "
            f"have {len(candidates)}"
        )
    remaining = sorted(
        candidates,
        key=lambda candidate: _stable_sort_key(seed_material, candidate.candidate_id),
    )
    selected: list[CandidateEpisode] = []
    label_counts = {
        "visibility": Counter(),
        "occlusion": Counter(),
        "detour": Counter(),
    }
    targets = _ideal_label_counts(count)
    for _ in range(count):
        best = min(
            remaining,
            key=lambda candidate: (
                _balance_score(candidate, label_counts, targets),
                _stable_sort_key(seed_material, candidate.candidate_id),
            ),
        )
        remaining.remove(best)
        selected.append(best)
        _increment_label_counts(best, label_counts)
    return _locally_rebalance_selection(
        selected,
        remaining,
        targets=targets,
        seed_material=seed_material,
    )


def _ideal_label_counts(count: int) -> dict[str, int]:
    labels = ("easy", "medium", "hard")
    base, remainder = divmod(count, len(labels))
    return {
        label: base + (1 if index < remainder else 0)
        for index, label in enumerate(labels)
    }


def _balance_score(
    candidate: CandidateEpisode,
    label_counts: Mapping[str, Counter[str]],
    targets: Mapping[str, int],
) -> tuple[int, int]:
    labels = _candidate_labels(candidate)
    score = 0
    overfill = 0
    for axis, label in labels.items():
        after_counts = Counter(label_counts[axis])
        after_counts[label] += 1
        for expected_label, target in targets.items():
            delta = after_counts[expected_label] - target
            score += delta * delta
            if delta > 0:
                overfill += delta
    return overfill, score


def _selection_balance_score(
    candidates: Sequence[CandidateEpisode],
    targets: Mapping[str, int],
) -> tuple[int, int]:
    label_counts = {
        "visibility": Counter(),
        "occlusion": Counter(),
        "detour": Counter(),
    }
    for candidate in candidates:
        _increment_label_counts(candidate, label_counts)
    overfill = 0
    score = 0
    for axis_counts in label_counts.values():
        for label, target in targets.items():
            delta = axis_counts[label] - target
            score += delta * delta
            if delta > 0:
                overfill += delta
    return overfill, score


def _locally_rebalance_selection(
    selected: Sequence[CandidateEpisode],
    remaining: Sequence[CandidateEpisode],
    *,
    targets: Mapping[str, int],
    seed_material: str,
) -> tuple[CandidateEpisode, ...]:
    selected_list = list(selected)
    remaining_list = list(remaining)
    while True:
        current_score = _selection_balance_score(selected_list, targets)
        best_swap: tuple[tuple[int, int], str, int, int] | None = None
        for selected_index, outgoing in enumerate(selected_list):
            for remaining_index, incoming in enumerate(remaining_list):
                trial = list(selected_list)
                trial[selected_index] = incoming
                trial_score = _selection_balance_score(trial, targets)
                if trial_score >= current_score:
                    continue
                swap_key = (
                    trial_score,
                    _stable_sort_key(seed_material, incoming.candidate_id + ":" + outgoing.candidate_id),
                    selected_index,
                    remaining_index,
                )
                if best_swap is None or swap_key < best_swap:
                    best_swap = swap_key
        if best_swap is None:
            return tuple(selected_list)
        _, _, selected_index, remaining_index = best_swap
        selected_list[selected_index], remaining_list[remaining_index] = (
            remaining_list[remaining_index],
            selected_list[selected_index],
        )


def _increment_label_counts(
    candidate: CandidateEpisode,
    label_counts: dict[str, Counter[str]],
) -> None:
    for axis, label in _candidate_labels(candidate).items():
        label_counts[axis][label] += 1


def _candidate_labels(candidate: CandidateEpisode) -> dict[str, str]:
    return {
        "visibility": candidate.difficulty.visibility_label,
        "occlusion": candidate.difficulty.occlusion_label,
        "detour": candidate.difficulty.detour_label,
    }


def _stable_sort_key(seed_material: str, candidate_id: str) -> str:
    return hashlib.sha256(f"{seed_material}:{candidate_id}".encode("utf-8")).hexdigest()


def _default_seed_base(split: ManifestSplit) -> int:
    return 1_000_000 if split == "public" else 2_000_000


def _candidate_signature(candidate: CandidateEpisode) -> str:
    return _signature_payload(
        task_type=candidate.task_type,
        starts=candidate.starts,
        targets=candidate.targets,
    )


def _episode_signature(episode: Any) -> str:
    return _signature_payload(
        task_type=episode.task_type,
        starts=episode.starts,
        targets=episode.targets,
    )


def _candidate_target_options(
    target_manifest: TargetAnnotationManifest,
    visibility_report: VisibilityOcclusionReport,
) -> tuple[dict[str, Any], ...]:
    regions_by_id = {
        region.region_id: region
        for region in target_manifest.confirmation_regions
        if region.reachable
    }
    metrics_by_instance = {
        metric.instance_id: metric
        for metric in visibility_report.metrics
    }
    options: list[dict[str, Any]] = []
    for instance in target_manifest.instances:
        if instance.ground_reachable != "reachable" or instance.confirmation_region_id is None:
            continue
        region = regions_by_id.get(instance.confirmation_region_id)
        metric = metrics_by_instance.get(instance.instance_id)
        if region is None or metric is None:
            continue
        options.append({"instance": instance, "region": region, "metric": metric})
    return tuple(
        sorted(
            options,
            key=lambda option: option["instance"].instance_id,
        )
    )


def _start_too_close_to_region(
    start: PairedStartCandidate,
    region: ConfirmationRegion,
    *,
    min_distance_m: float,
) -> bool:
    if min_distance_m <= 0.0:
        return False
    sx = start.starts.ugv.x_m
    sy = start.starts.ugv.y_m
    return any(
        math.hypot(sx - pose.position_xyz_m[0], sy - pose.position_xyz_m[1]) < min_distance_m
        for pose in region.poses
    )


def _raw_candidate_payload(
    task_type: TaskType,
    start: PairedStartCandidate,
    target_options: Sequence[dict[str, Any]],
    *,
    ground_truth: GroundTruthRef,
    seed_material: str,
) -> dict[str, Any]:
    targets = [
        _episode_target_from_option(option, index if task_type == "sequential_target" else None)
        for index, option in enumerate(target_options)
    ]
    visibility = min(float(option["metric"].visibility) for option in target_options)
    occlusion = max(float(option["metric"].occlusion) for option in target_options)
    detour = max(float(option["detour"]) for option in target_options)
    instance_ids = [option["instance"].instance_id for option in target_options]
    candidate_id = _candidate_pool_builder_id(task_type, start.candidate_id, instance_ids, seed_material)
    return {
        "candidate_id": candidate_id,
        "eligible_splits": ["public", "hidden_test"],
        "task_type": task_type,
        "query": _query_for_target_options(task_type, target_options),
        "starts": start.starts.model_dump(mode="json"),
        "targets": targets,
        "difficulty_raw": {
            "visibility": visibility,
            "occlusion": occlusion,
            "detour": detour,
        },
        "ground_truth": ground_truth.model_dump(mode="json"),
    }


def _episode_target_from_option(option: Mapping[str, Any], sequence_index: int | None) -> dict[str, Any]:
    instance: TargetInstance = option["instance"]
    return {
        "query_id": _safe_query_id(
            f"q{sequence_index if sequence_index is not None else 0}-{instance.instance_id}"
        ),
        "semantic_class": instance.semantic_class,
        "instance_id": instance.instance_id,
        "confirmation_region_id": instance.confirmation_region_id,
        "sequence_index": sequence_index,
    }


def _query_for_target_options(task_type: TaskType, target_options: Sequence[dict[str, Any]]) -> str:
    classes = [str(option["instance"].semantic_class) for option in target_options]
    if task_type == "single_target":
        return classes[0]
    if task_type == "sequential_target":
        return " then ".join(classes)
    return " and ".join(sorted(classes))


def _candidate_pool_builder_id(
    task_type: str,
    start_id: str,
    instance_ids: Sequence[str],
    seed_material: str,
) -> str:
    digest = hashlib.sha256(
        json.dumps(
            {
                "instances": list(instance_ids),
                "seed_material": seed_material,
                "start_id": start_id,
                "task_type": task_type,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()[:16]
    return f"candidate-{task_type.replace('_', '-')}-{digest}"


def _safe_query_id(value: str) -> str:
    sanitized = "".join(char if char.isalnum() or char in {"_", ".", "-"} else "_" for char in value)
    return sanitized.strip("_.-") or "q0"


def _limit_raw_candidates(
    raw_candidates: Sequence[dict[str, Any]],
    task_type: TaskType,
    limit: int,
) -> tuple[dict[str, Any], ...]:
    if limit == 0:
        return ()
    task_candidates = [
        candidate
        for candidate in raw_candidates
        if candidate["task_type"] == task_type
    ]
    return tuple(
        sorted(
            task_candidates,
            key=lambda candidate: candidate["candidate_id"],
        )[:limit]
    )


def _label_raw_candidates(raw_candidates: Sequence[dict[str, Any]]) -> tuple[dict[str, Any], ...]:
    cuts = {}
    labels_by_axis: dict[str, dict[str, str]] = {}
    for axis, direction in AXIS_DIRECTIONS.items():
        values = sorted(float(candidate["difficulty_raw"][axis]) for candidate in raw_candidates)
        low_cut, high_cut = _tercile_cuts(values)
        cuts[axis] = (low_cut, high_cut, direction)
        labels_by_axis[axis] = _rank_tercile_labels(
            (
                (str(candidate["candidate_id"]), float(candidate["difficulty_raw"][axis]))
                for candidate in raw_candidates
            ),
            direction,
        )
    labeled = []
    for candidate in raw_candidates:
        raw = candidate["difficulty_raw"]
        difficulty = {
            axis: float(raw[axis])
            for axis in ("visibility", "occlusion", "detour")
        }
        for axis in cuts:
            difficulty[f"{axis}_label"] = labels_by_axis[axis][str(candidate["candidate_id"])]
        payload = dict(candidate)
        payload.pop("difficulty_raw")
        payload["difficulty"] = difficulty
        labeled.append(payload)
    return tuple(labeled)


def _signature_payload(
    *,
    task_type: str,
    starts: StartPair,
    targets: Iterable[EpisodeTarget],
) -> str:
    ugv = starts.ugv
    target_ids = sorted(target.instance_id for target in targets)
    payload = {
        "task_type": task_type,
        "ugv_start": [
            round(ugv.x_m, 3),
            round(ugv.y_m, 3),
            round(ugv.yaw_rad, 6),
        ],
        "target_ids": target_ids,
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))
