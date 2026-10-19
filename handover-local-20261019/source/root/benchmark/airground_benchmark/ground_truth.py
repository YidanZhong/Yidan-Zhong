"""Ground-truth schemas and validators."""

from __future__ import annotations

from airground_benchmark.scenes import SceneId, EXTRA_USD_ALIASES

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import hashlib
import html
from importlib import resources
import json
import logging
import math
from pathlib import Path
import re
from typing import Any, Literal

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, model_validator
import yaml

from airground_benchmark.communication import RadioPose, RaycastFn
from airground_benchmark.config.schema import SCHEMA_VERSION

LOGGER = logging.getLogger(__name__)


class GroundTruthError(ValueError):
    """Raised when a ground-truth artifact is invalid."""


class StrictModel(BaseModel):
    """Base class that rejects undeclared fields."""

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)


class GridOrigin(StrictModel):
    """Origin of grid cell (0, 0) in the map frame."""

    x_m: float
    y_m: float
    z_m: float = 0.0


class TraversabilityArrays(StrictModel):
    """NPZ array keys used by the traversability schema."""

    height: str = "height"
    normal: str = "normal"
    cost: str = "cost"
    mask: str = "mask"
    component: str = "component"


class TraversabilityMetadata(StrictModel):
    """Traversability ground-truth metadata."""

    schema_version: Literal[SCHEMA_VERSION]
    scene_id: SceneId
    frame: Literal["map"]
    origin: GridOrigin
    resolution_m: float = Field(gt=0.0)
    shape: tuple[int, int]
    arrays: TraversabilityArrays = Field(default_factory=TraversabilityArrays)
    generator: str = Field(min_length=1)
    generator_version: str = Field(min_length=1)
    npz_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_shape(self) -> "TraversabilityMetadata":
        rows, cols = self.shape
        if rows <= 0 or cols <= 0:
            raise ValueError("traversability shape dimensions must be positive")
        return self


class OrientedBoundingBox(StrictModel):
    """Target oriented bounding box in the map frame."""

    frame: Literal["map"]
    center_xyz_m: tuple[float, float, float]
    size_xyz_m: tuple[float, float, float]
    orientation_rpy_rad: tuple[float, float, float] = (0.0, 0.0, 0.0)

    @model_validator(mode="after")
    def validate_size(self) -> "OrientedBoundingBox":
        if any(size <= 0.0 for size in self.size_xyz_m):
            raise ValueError("oriented bounding box size must be positive on all axes")
        return self


class TargetInstance(StrictModel):
    """One semantic target instance with evaluator-only geometry."""

    instance_id: str = Field(pattern=r"^[A-Za-z0-9_.:/-]+$")
    semantic_class: str = Field(min_length=1)
    source_class: str = Field(min_length=1)
    source_index: int = Field(ge=0)
    obb: OrientedBoundingBox
    usd_prim_path: str | None = Field(default=None, pattern=r"^/.*")
    verified: bool = False
    excluded_reason: str | None = None
    review_version: str | None = None
    ground_reachable: Literal["unknown", "reachable", "unreachable"] = "unknown"
    confirmation_region_id: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_.:/-]+$")


class UsdPrimCandidate(StrictModel):
    """One USD prim candidate exported from the Isaac scene for target binding."""

    prim_path: str = Field(pattern=r"^/.*")
    semantic_hints: tuple[str, ...] = ()
    center_xyz_m: tuple[float, float, float]
    size_xyz_m: tuple[float, float, float]
    #: 2026-09-24: the RetroNeighborhood container crates are ``SM_ShippingContainer*``
    #: meshes whose color lives in the bound material (``MI_ShippingContainer_Blue``
    #: / ``_Red`` / ...).  Exposing that lets the binder separate "blue container"
    #: from "red container" without rendering.
    material_path: str | None = None
    color_hint: str | None = None

    @model_validator(mode="after")
    def validate_size(self) -> "UsdPrimCandidate":
        if any(size < 0.0 for size in self.size_xyz_m):
            raise ValueError("USD prim candidate size must be non-negative on all axes")
        return self


class UsdPrimCandidateManifest(StrictModel):
    """Versioned USD prim candidate export used to bind target annotations."""

    schema_version: Literal[SCHEMA_VERSION]
    scene_id: SceneId
    frame: Literal["map"]
    generator: str = Field(min_length=1)
    generator_version: str = Field(min_length=1)
    source_usd_path: str | None = None
    candidates: tuple[UsdPrimCandidate, ...] = Field(min_length=1)


class TargetPrimBinding(StrictModel):
    """Binding result for one target instance."""

    instance_id: str = Field(pattern=r"^[A-Za-z0-9_.:/-]+$")
    semantic_class: str = Field(min_length=1)
    source_index: int = Field(ge=0)
    usd_prim_path: str | None = Field(default=None, pattern=r"^/.*")
    candidate_count: int = Field(ge=0)
    candidate_rank: int | None = Field(default=None, ge=0)
    center_distance_m: float | None = Field(default=None, ge=0.0)
    size_l1_delta_m: float | None = Field(default=None, ge=0.0)
    score: float | None = Field(default=None, ge=0.0)
    skipped_existing_binding: bool = False
    issues: tuple[str, ...] = ()


class TargetPrimBindingReport(StrictModel):
    """Deterministic report for automatic target-to-USD-prim binding."""

    schema_version: Literal[SCHEMA_VERSION]
    scene_id: SceneId
    frame: Literal["map"]
    generator: Literal["airground-target-prim-binder-v1"]
    generator_version: str
    source_usd_path: str | None = None
    max_center_distance_m: float = Field(gt=0.0)
    max_size_l1_delta_m: float | None = Field(default=None, gt=0.0)
    ambiguity_margin_m: float = Field(ge=0.0)
    require_unique: bool
    fail_on_ambiguous: bool
    instance_count: int = Field(ge=0)
    candidate_count: int = Field(ge=0)
    bound_count: int = Field(ge=0)
    unbound_count: int = Field(ge=0)
    ambiguous_count: int = Field(ge=0)
    duplicate_binding_count: int = Field(ge=0)
    issue_count: int = Field(ge=0)
    status: Literal["ok", "failed"]
    bindings: tuple[TargetPrimBinding, ...]


class ConfirmationPose(StrictModel):
    """One UGV pose candidate for confirming a target."""

    frame: Literal["map"]
    position_xyz_m: tuple[float, float, float]
    yaw_rad: float
    distance_to_target_m: float = Field(ge=0.0)
    visible_fraction: float = Field(ge=0.0, le=1.0)
    traversability_component: int | None = None


class ConfirmationRegion(StrictModel):
    """Merged UGV confirmation region for one target."""

    region_id: str = Field(pattern=r"^[A-Za-z0-9_.:/-]+$")
    instance_id: str = Field(pattern=r"^[A-Za-z0-9_.:/-]+$")
    reachable: bool
    poses: tuple[ConfirmationPose, ...] = ()
    yaw_range_rad: tuple[float, float] | None = None
    excluded_reason: str | None = None
    #: 2026-09-24 dense arrival region support.  ``poses`` stays the capped
    #: diagnostic sample; the authoritative set is the raster cell set stored in
    #: the companion ``arrival_regions.npz`` under ``region_label``.
    region_label: int | None = Field(default=None, ge=0)
    cell_count: int | None = Field(default=None, ge=0)
    distance_reference: Literal["obb_center", "obb_surface"] | None = None

    @model_validator(mode="after")
    def validate_reachability(self) -> "ConfirmationRegion":
        if self.reachable:
            if not self.poses:
                raise ValueError("reachable confirmation regions must contain at least one pose")
            low, high = self.yaw_range_rad if self.yaw_range_rad is not None else (0.0, 0.0)
            if high < low:
                raise ValueError("yaw_range_rad upper bound must be >= lower bound")
            for pose in self.poses:
                if not 1.5 <= pose.distance_to_target_m <= 8.0:
                    raise ValueError("confirmation pose distance must be within 1.5-8.0 m")
                if pose.visible_fraction < 0.2:
                    raise ValueError("confirmation pose visible_fraction must be >= 0.2")
        elif self.excluded_reason is None:
            raise ValueError("unreachable confirmation regions require excluded_reason")
        return self


class VisibilityOcclusionConfig(StrictModel):
    """Deterministic grid/OBB proxy settings for episode difficulty pre-screening."""

    uav_altitudes_m: tuple[float, ...] = (2.0, 4.0, 6.0)
    min_range_m: float = Field(default=1.0, ge=0.0)
    max_range_m: float = Field(default=35.0, gt=0.0)
    horizontal_fov_rad: float = Field(default=math.radians(90.0), gt=0.0, le=math.tau)
    yaw_samples: int = Field(default=8, ge=1)
    sample_stride_cells: int = Field(default=1, ge=1)
    ray_step_m: float | None = None

    @model_validator(mode="after")
    def validate_config(self) -> "VisibilityOcclusionConfig":
        if not self.uav_altitudes_m:
            raise ValueError("uav_altitudes_m must not be empty")
        if any(altitude <= 0.0 for altitude in self.uav_altitudes_m):
            raise ValueError("uav_altitudes_m values must be positive")
        if self.max_range_m < self.min_range_m:
            raise ValueError("max_range_m must be >= min_range_m")
        if self.ray_step_m is not None and self.ray_step_m <= 0.0:
            raise ValueError("ray_step_m must be positive when provided")
        return self


class TargetVisibilityOcclusionMetric(StrictModel):
    """Per-target visibility and occlusion difficulty proxy."""

    instance_id: str = Field(pattern=r"^[A-Za-z0-9_.:/-]+$")
    semantic_class: str = Field(min_length=1)
    visibility: float = Field(ge=0.0, le=1.0)
    occlusion: float = Field(ge=0.0, le=1.0)
    candidate_sample_count: int = Field(ge=0)
    visible_sample_count: int = Field(ge=0)
    ray_count: int = Field(ge=0)
    occluded_ray_count: int = Field(ge=0)


class VisibilityOcclusionReport(StrictModel):
    """Versioned visibility/occlusion metrics for target difficulty labeling."""

    schema_version: Literal[SCHEMA_VERSION]
    scene_id: SceneId
    frame: Literal["map"]
    generator: Literal["airground-grid-obb-visibility-occlusion-proxy-v1"]
    generator_version: str
    config: VisibilityOcclusionConfig
    target_count: int = Field(ge=0)
    metrics: tuple[TargetVisibilityOcclusionMetric, ...]


class ConfirmationVisibilityConfig(StrictModel):
    """Grid/OBB proxy settings for validating UGV confirmation regions."""

    min_distance_m: float = Field(default=1.5, ge=0.0)
    max_distance_m: float = Field(default=8.0, gt=0.0)
    horizontal_fov_rad: float = Field(default=math.radians(90.0), gt=0.0, le=math.tau)
    min_visible_fraction: float = Field(default=0.2, ge=0.0, le=1.0)
    required_consecutive_frames: int = Field(default=5, ge=1)
    ray_step_m: float | None = None

    @model_validator(mode="after")
    def validate_config(self) -> "ConfirmationVisibilityConfig":
        if self.max_distance_m < self.min_distance_m:
            raise ValueError("max_distance_m must be >= min_distance_m")
        if self.ray_step_m is not None and self.ray_step_m <= 0.0:
            raise ValueError("ray_step_m must be positive when provided")
        return self


class ConfirmationPoseVisibilityMetric(StrictModel):
    """Visibility proxy result for one confirmation pose."""

    pose_index: int = Field(ge=0)
    valid: bool
    in_range: bool
    in_fov: bool
    yaw_error_rad: float = Field(ge=0.0)
    stored_visible_fraction: float = Field(ge=0.0, le=1.0)
    ray_visible_fraction: float = Field(ge=0.0, le=1.0)
    effective_visible_fraction: float = Field(ge=0.0, le=1.0)
    ray_count: int = Field(ge=0)
    occluded_ray_count: int = Field(ge=0)
    consecutive_visible_frames: int = Field(ge=0)


class ConfirmationRegionVisibilityMetric(StrictModel):
    """Visibility proxy result for one confirmation region."""

    region_id: str = Field(pattern=r"^[A-Za-z0-9_.:/-]+$")
    instance_id: str = Field(pattern=r"^[A-Za-z0-9_.:/-]+$")
    reachable: bool
    valid: bool
    pose_count: int = Field(ge=0)
    valid_pose_count: int = Field(ge=0)
    issues: tuple[str, ...] = ()
    poses: tuple[ConfirmationPoseVisibilityMetric, ...] = ()


class ConfirmationVisibilityReport(StrictModel):
    """Versioned confirmation-region visibility proxy report."""

    schema_version: Literal[SCHEMA_VERSION]
    scene_id: SceneId
    frame: Literal["map"]
    generator: Literal["airground-grid-confirmation-visibility-proxy-v1"]
    generator_version: str
    config: ConfirmationVisibilityConfig
    region_count: int = Field(ge=0)
    valid_region_count: int = Field(ge=0)
    issue_count: int = Field(ge=0)
    status: Literal["ok", "failed"]
    metrics: tuple[ConfirmationRegionVisibilityMetric, ...]


class RaycastConfirmationVisibilityConfig(StrictModel):
    """Raycast-based confirmation visibility settings for real Isaac adapters."""

    camera_height_m: float = Field(gt=0.0)
    min_distance_m: float = Field(ge=0.0)
    max_distance_m: float = Field(gt=0.0)
    horizontal_fov_rad: float = Field(gt=0.0, lt=math.tau)
    min_visible_fraction: float = Field(ge=0.0, le=1.0)
    required_consecutive_frames: int = Field(ge=1)
    target_sample_count: Literal[1, 5, 9] = 5
    occlusion_epsilon_m: float = Field(ge=0.0)
    ignored_prim_prefixes: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_distances(self) -> "RaycastConfirmationVisibilityConfig":
        if self.max_distance_m < self.min_distance_m:
            raise ValueError("max_distance_m must be >= min_distance_m")
        return self


class RaycastConfirmationPoseMetric(StrictModel):
    """Visibility result for one confirmation pose using raycast evidence."""

    pose_index: int = Field(ge=0)
    valid: bool
    distance_to_target_m: float = Field(ge=0.0)
    yaw_error_rad: float = Field(ge=0.0)
    ray_count: int = Field(ge=0)
    clear_ray_count: int = Field(ge=0)
    blocked_ray_count: int = Field(ge=0)
    visible_fraction: float = Field(ge=0.0, le=1.0)
    consecutive_visible_frames: int = Field(ge=0)
    blocking_prim_paths: tuple[str, ...] = ()
    issues: tuple[str, ...] = ()


class RaycastConfirmationRegionMetric(StrictModel):
    """Raycast visibility result for one confirmation region."""

    region_id: str = Field(pattern=r"^[A-Za-z0-9_.:/-]+$")
    instance_id: str = Field(pattern=r"^[A-Za-z0-9_.:/-]+$")
    reachable: bool
    valid: bool
    pose_count: int = Field(ge=0)
    valid_pose_count: int = Field(ge=0)
    pose_metrics: tuple[RaycastConfirmationPoseMetric, ...] = ()
    issues: tuple[str, ...] = ()


class RaycastConfirmationVisibilityReport(StrictModel):
    """Versioned confirmation-region visibility report using raycast evidence."""

    schema_version: Literal[SCHEMA_VERSION]
    scene_id: SceneId
    frame: Literal["map"]
    generator: Literal["airground-raycast-confirmation-visibility-v1"]
    generator_version: str
    config: RaycastConfirmationVisibilityConfig
    region_count: int = Field(ge=0)
    valid_region_count: int = Field(ge=0)
    issue_count: int = Field(ge=0)
    status: Literal["ok", "failed"]
    metrics: tuple[RaycastConfirmationRegionMetric, ...]


class SensorFrameConfirmationVisibilityConfig(StrictModel):
    """Continuous sensor-frame confirmation visibility settings."""

    min_distance_m: float = Field(ge=0.0)
    max_distance_m: float = Field(gt=0.0)
    horizontal_fov_rad: float = Field(gt=0.0, lt=math.tau)
    min_visible_fraction: float = Field(ge=0.0, le=1.0)
    required_consecutive_frames: int = Field(ge=1)
    max_frame_gap_s: float = Field(gt=0.0)
    require_raycast_evidence: bool = True

    @model_validator(mode="after")
    def validate_distances(self) -> "SensorFrameConfirmationVisibilityConfig":
        if self.max_distance_m < self.min_distance_m:
            raise ValueError("max_distance_m must be >= min_distance_m")
        return self


class SensorFrameConfirmationVisibilityTraceFrame(StrictModel):
    """One real sensor-frame sample for a confirmation pose."""

    event: Literal["confirmation_visibility_sensor_frame"] = "confirmation_visibility_sensor_frame"
    sim_time_s: float = Field(ge=0.0)
    region_id: str = Field(pattern=r"^[A-Za-z0-9_.:/-]+$")
    instance_id: str = Field(pattern=r"^[A-Za-z0-9_.:/-]+$")
    pose_index: int = Field(ge=0)
    distance_to_target_m: float = Field(ge=0.0)
    yaw_error_rad: float = Field(ge=0.0)
    visible_fraction: float = Field(ge=0.0, le=1.0)
    ray_count: int = Field(default=0, ge=0)
    clear_ray_count: int = Field(default=0, ge=0)
    blocked_ray_count: int = Field(default=0, ge=0)
    camera_frame: str | None = None
    blocking_prim_paths: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_ray_counts(self) -> "SensorFrameConfirmationVisibilityTraceFrame":
        if self.clear_ray_count + self.blocked_ray_count > self.ray_count:
            raise ValueError("clear_ray_count + blocked_ray_count must be <= ray_count")
        return self


class SensorFrameConfirmationPoseTraceMetric(StrictModel):
    """Continuous-frame visibility result for one traced confirmation pose."""

    pose_index: int = Field(ge=0)
    valid: bool
    frame_count: int = Field(ge=0)
    valid_frame_count: int = Field(ge=0)
    max_consecutive_visible_frames: int = Field(ge=0)
    first_valid_time_s: float | None = Field(default=None, ge=0.0)
    last_valid_time_s: float | None = Field(default=None, ge=0.0)
    min_distance_to_target_m: float | None = Field(default=None, ge=0.0)
    max_distance_to_target_m: float | None = Field(default=None, ge=0.0)
    max_yaw_error_rad: float | None = Field(default=None, ge=0.0)
    min_visible_fraction: float | None = Field(default=None, ge=0.0, le=1.0)
    ray_count: int = Field(ge=0)
    clear_ray_count: int = Field(ge=0)
    blocked_ray_count: int = Field(ge=0)
    blocking_prim_paths: tuple[str, ...] = ()
    issues: tuple[str, ...] = ()


class SensorFrameConfirmationRegionTraceMetric(StrictModel):
    """Continuous sensor-frame validation result for one confirmation region."""

    region_id: str = Field(pattern=r"^[A-Za-z0-9_.:/-]+$")
    instance_id: str = Field(pattern=r"^[A-Za-z0-9_.:/-]+$")
    reachable: bool
    valid: bool
    pose_count: int = Field(ge=0)
    traced_pose_count: int = Field(ge=0)
    valid_pose_count: int = Field(ge=0)
    frame_count: int = Field(ge=0)
    valid_frame_count: int = Field(ge=0)
    pose_metrics: tuple[SensorFrameConfirmationPoseTraceMetric, ...] = ()
    issues: tuple[str, ...] = ()


class SensorFrameConfirmationVisibilityReport(StrictModel):
    """Versioned confirmation visibility report using real sensor-frame traces."""

    schema_version: Literal[SCHEMA_VERSION]
    scene_id: SceneId
    frame: Literal["map"]
    generator: Literal["airground-sensor-frame-confirmation-visibility-v1"]
    generator_version: str
    config: SensorFrameConfirmationVisibilityConfig
    region_count: int = Field(ge=0)
    valid_region_count: int = Field(ge=0)
    issue_count: int = Field(ge=0)
    trace_frame_count: int = Field(ge=0)
    status: Literal["ok", "failed"]
    metrics: tuple[SensorFrameConfirmationRegionTraceMetric, ...]


class TargetAnnotationManifest(StrictModel):
    """Versioned target instance and confirmation-region annotations."""

    schema_version: Literal[SCHEMA_VERSION]
    scene_id: SceneId
    frame: Literal["map"]
    source_format: str = Field(min_length=1)
    source_path: str | None = None
    spawn_offset_xyz_m: tuple[float, float, float] = (0.0, 0.0, 0.0)
    instances: tuple[TargetInstance, ...] = Field(min_length=1)
    confirmation_regions: tuple[ConfirmationRegion, ...] = ()

    @model_validator(mode="after")
    def validate_references(self) -> "TargetAnnotationManifest":
        instance_ids = [instance.instance_id for instance in self.instances]
        if len(set(instance_ids)) != len(instance_ids):
            raise ValueError("target instance_id values must be unique")
        region_ids = [region.region_id for region in self.confirmation_regions]
        if len(set(region_ids)) != len(region_ids):
            raise ValueError("confirmation region_id values must be unique")
        instance_set = set(instance_ids)
        for region in self.confirmation_regions:
            if region.instance_id not in instance_set:
                raise ValueError(f"confirmation region references unknown instance: {region.instance_id}")
        region_set = set(region_ids)
        for instance in self.instances:
            if instance.confirmation_region_id is not None and instance.confirmation_region_id not in region_set:
                raise ValueError(
                    f"target references unknown confirmation region: {instance.confirmation_region_id}"
                )
        return self


class TargetReviewDecision(StrictModel):
    """One human review decision for a target annotation row."""

    instance_id: str = Field(pattern=r"^[A-Za-z0-9_.:/-]+$")
    action: Literal["verify", "exclude"]
    usd_prim_path: str | None = Field(default=None, pattern=r"^/.*")
    semantic_class: str | None = Field(default=None, min_length=1)
    source_class: str | None = Field(default=None, min_length=1)
    obb: OrientedBoundingBox | None = None
    excluded_reason: str | None = Field(default=None, min_length=1)
    review_version: str | None = Field(default=None, min_length=1)
    notes: str | None = None

    @model_validator(mode="after")
    def validate_decision(self) -> "TargetReviewDecision":
        if self.action == "verify":
            if not self.usd_prim_path:
                raise ValueError("verify decisions require usd_prim_path")
            if self.excluded_reason is not None:
                raise ValueError("verify decisions must not include excluded_reason")
        elif not self.excluded_reason:
            raise ValueError("exclude decisions require excluded_reason")
        if self.semantic_class is not None and self.semantic_class != self.semantic_class.strip().lower():
            raise ValueError("semantic_class corrections must be lowercase and trimmed")
        return self


class TargetReviewLedger(StrictModel):
    """Versioned human-review ledger applied to target annotations."""

    schema_version: Literal[SCHEMA_VERSION]
    scene_id: SceneId
    frame: Literal["map"]
    generator: Literal["airground-target-human-review-ledger-v1"]
    generator_version: str = Field(min_length=1)
    review_version: str = Field(min_length=1)
    reviewer: str | None = None
    source_annotations_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    source_review_media: str | None = None
    decisions: tuple[TargetReviewDecision, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_unique_decisions(self) -> "TargetReviewLedger":
        instance_ids = [decision.instance_id for decision in self.decisions]
        if len(set(instance_ids)) != len(instance_ids):
            raise ValueError("review ledger decision instance_id values must be unique")
        return self


class TargetReviewApplyReport(StrictModel):
    """Machine-readable report for applying a target human-review ledger."""

    schema_version: Literal[SCHEMA_VERSION]
    scene_id: SceneId
    frame: Literal["map"]
    generator: Literal["airground-target-human-review-apply-v1"]
    generator_version: str
    review_version: str
    source_annotations_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    output_annotations_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    instance_count: int = Field(ge=0)
    decision_count: int = Field(ge=0)
    verify_decision_count: int = Field(ge=0)
    exclude_decision_count: int = Field(ge=0)
    untouched_count: int = Field(ge=0)
    changed_instance_ids: tuple[str, ...]
    excluded_instance_ids: tuple[str, ...]
    status: Literal["ok"]


class TargetReviewLedgerTemplateRow(StrictModel):
    """One safe draft row for human target-review ledger creation."""

    instance_id: str = Field(pattern=r"^[A-Za-z0-9_.:/-]+$")
    semantic_class: str = Field(min_length=1)
    source_index: int = Field(ge=0)
    priority: int | None = Field(default=None, ge=0)
    review_frame_index: int | None = Field(default=None, ge=0)
    issues: tuple[str, ...] = ()
    current_usd_prim_path: str | None = Field(default=None, pattern=r"^/.*")
    current_obb: OrientedBoundingBox
    decision_required: bool
    suggested_next_step: Literal[
        "confirm_or_correct_candidate",
        "choose_usd_prim_path_or_exclude",
        "optional_noop",
    ]
    final_decision_fields: Mapping[str, Any]


class TargetReviewLedgerTemplate(StrictModel):
    """A non-applicable draft used by humans to author a final review ledger."""

    schema_version: Literal[SCHEMA_VERSION]
    scene_id: SceneId
    frame: Literal["map"]
    generator: Literal["airground-target-human-review-ledger-template-v1"]
    generator_version: str = Field(min_length=1)
    review_version: str = Field(min_length=1)
    source_annotations_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_review_queue_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    source_review_media: str | None = None
    human_review_required: bool
    row_count: int = Field(ge=0)
    review_required_count: int = Field(ge=0)
    instructions: tuple[str, ...] = Field(min_length=1)
    rows: tuple[TargetReviewLedgerTemplateRow, ...]


@dataclass(frozen=True)
class TargetAnnotationAuditIssue:
    """One target annotation completeness issue."""

    code: str
    message: str
    instance_id: str | None = None
    severity: Literal["error", "warning"] = "error"

    def as_dict(self) -> dict[str, Any]:
        """Return deterministic JSON-compatible issue data."""
        return {
            "code": self.code,
            "instance_id": self.instance_id,
            "message": self.message,
            "severity": self.severity,
        }


@dataclass(frozen=True)
class TargetAnnotationAuditReport:
    """Completeness report for target annotations before release."""

    manifest: TargetAnnotationManifest
    requirements: Mapping[str, bool]
    issues: tuple[TargetAnnotationAuditIssue, ...]
    max_issues: int = 100

    def summary(self) -> dict[str, Any]:
        """Return stable aggregate target annotation audit statistics."""
        issue_counts: dict[str, int] = {}
        for issue in self.issues:
            issue_counts[issue.code] = issue_counts.get(issue.code, 0) + 1
        semantic_class_counts: dict[str, int] = {}
        for instance in self.manifest.instances:
            semantic_class_counts[instance.semantic_class] = (
                semantic_class_counts.get(instance.semantic_class, 0) + 1
            )
        return {
            "frame": self.manifest.frame,
            "generator": "airground-target-annotation-audit-v1",
            "instance_count": len(self.manifest.instances),
            "issue_counts": dict(sorted(issue_counts.items())),
            "issue_count": len(self.issues),
            "issues": [issue.as_dict() for issue in self.issues[: self.max_issues]],
            "max_issues_reported": self.max_issues,
            "requirements": dict(sorted(self.requirements.items())),
            "scene_id": self.manifest.scene_id,
            "schema_version": self.manifest.schema_version,
            "semantic_class_counts": dict(sorted(semantic_class_counts.items())),
            "source_format": self.manifest.source_format,
            "source_path": self.manifest.source_path,
            "status": "ok" if not self.issues else "failed",
        }


@dataclass(frozen=True)
class TraversabilityGrid:
    """Validated traversability arrays with map-frame cell helpers."""

    metadata: TraversabilityMetadata
    height: np.ndarray
    mask: np.ndarray
    component: np.ndarray
    cost: np.ndarray | None = None

    def cell_for_xy(self, x_m: float, y_m: float) -> tuple[int, int] | None:
        """Return the containing grid cell for a map-frame XY point."""
        resolution = self.metadata.resolution_m
        col = math.floor((x_m - self.metadata.origin.x_m) / resolution)
        row = math.floor((y_m - self.metadata.origin.y_m) / resolution)
        rows, cols = self.metadata.shape
        if row < 0 or col < 0 or row >= rows or col >= cols:
            return None
        return row, col

    def traversable_pose_at_cell(
        self,
        row: int,
        col: int,
    ) -> tuple[float, float, float, int] | None:
        """Return map-frame cell-center pose data when the cell is traversable."""
        if not bool(self.mask[row, col]):
            return None
        traversability_component = int(self.component[row, col])
        if traversability_component < 0:
            return None
        resolution = self.metadata.resolution_m
        x_m = self.metadata.origin.x_m + (col + 0.5) * resolution
        y_m = self.metadata.origin.y_m + (row + 0.5) * resolution
        z_m = float(self.height[row, col])
        return x_m, y_m, z_m, traversability_component


def _default_target_annotations_text() -> str:
    resource = resources.files("airground_benchmark").joinpath(
        "gt/targets/retro_neighborhood.targets.json"
    )
    return resource.read_text(encoding="utf-8")


def canonical_traversability_metadata_json(metadata: TraversabilityMetadata) -> str:
    """Serialize traversability metadata into checksum-stable JSON."""
    return (
        json.dumps(
            metadata.model_dump(mode="json"),
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    )


def canonical_target_annotations_json(manifest: TargetAnnotationManifest) -> str:
    """Serialize target annotations into checksum-stable JSON."""
    return (
        json.dumps(
            manifest.model_dump(mode="json"),
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    )


def canonical_usd_prim_candidate_manifest_json(manifest: UsdPrimCandidateManifest) -> str:
    """Serialize USD prim candidates into checksum-stable JSON."""
    return (
        json.dumps(
            manifest.model_dump(mode="json"),
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    )


def canonical_target_prim_binding_report_json(report: TargetPrimBindingReport) -> str:
    """Serialize target-to-USD-prim binding results deterministically."""
    return (
        json.dumps(
            report.model_dump(mode="json"),
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    )


def canonical_visibility_occlusion_report_json(report: VisibilityOcclusionReport) -> str:
    """Serialize visibility/occlusion metrics deterministically."""
    return (
        json.dumps(
            report.model_dump(mode="json"),
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    )


def canonical_confirmation_visibility_report_json(report: ConfirmationVisibilityReport) -> str:
    """Serialize confirmation-region visibility proxy metrics deterministically."""
    return (
        json.dumps(
            report.model_dump(mode="json"),
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    )


def canonical_raycast_confirmation_visibility_report_json(
    report: RaycastConfirmationVisibilityReport,
) -> str:
    """Serialize raycast confirmation visibility metrics deterministically."""
    return (
        json.dumps(
            report.model_dump(mode="json"),
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    )


def canonical_sensor_frame_confirmation_visibility_report_json(
    report: SensorFrameConfirmationVisibilityReport,
) -> str:
    """Serialize sensor-frame confirmation visibility metrics deterministically."""
    return (
        json.dumps(
            report.model_dump(mode="json"),
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    )


def canonical_target_annotation_audit_report_json(report: TargetAnnotationAuditReport) -> str:
    """Serialize a target annotation audit report deterministically."""
    return json.dumps(report.summary(), ensure_ascii=True, sort_keys=True, separators=(",", ":")) + "\n"


def canonical_target_review_apply_report_json(report: TargetReviewApplyReport) -> str:
    """Serialize a target review application report deterministically."""
    return (
        json.dumps(
            report.model_dump(mode="json"),
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    )


def canonical_target_review_ledger_template_json(template: TargetReviewLedgerTemplate) -> str:
    """Serialize a target review ledger template deterministically."""
    return (
        json.dumps(
            template.model_dump(mode="json"),
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    )


def canonical_traversability_schema_json() -> str:
    """Serialize the traversability JSON schema deterministically."""
    return (
        json.dumps(
            TraversabilityMetadata.model_json_schema(),
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    )


def canonical_target_annotations_schema_json() -> str:
    """Serialize the target annotation JSON schema deterministically."""
    return (
        json.dumps(
            TargetAnnotationManifest.model_json_schema(),
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    )


def _load_yaml_or_json_text(resolved: Path) -> Any:
    """Parse a YAML-or-JSON file; ``.json`` files take the C JSON parser.

    Every JSON document is also YAML, but PyYAML's pure-Python parser takes ~8 s on the 4 MB
    reviewed target manifest (json: ~0.05 s, same mapping), and that load runs on the Kit main
    thread for each confirmation request.  A ``.json`` file that is not valid JSON falls back to
    YAML with a warning, so the accepted inputs are unchanged.
    """
    text = resolved.read_text(encoding="utf-8")
    if resolved.suffix.lower() == ".json":
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            LOGGER.warning("%s is not strict JSON (%s); parsing it as YAML", resolved, exc)
    return yaml.safe_load(text)


def load_traversability_metadata(path: Path) -> TraversabilityMetadata:
    """Load traversability metadata YAML."""
    resolved = Path(path).expanduser().resolve(strict=True)
    value = yaml.safe_load(resolved.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise GroundTruthError(f"traversability metadata must be a YAML mapping: {resolved}")
    return TraversabilityMetadata.model_validate(dict(value))


def load_target_annotations(path: Path) -> TargetAnnotationManifest:
    """Load target annotations from YAML or JSON."""
    resolved = Path(path).expanduser().resolve(strict=True)
    value = _load_yaml_or_json_text(resolved)
    if not isinstance(value, Mapping):
        raise GroundTruthError(f"target annotations must be a YAML/JSON mapping: {resolved}")
    return TargetAnnotationManifest.model_validate(dict(value))


def load_usd_prim_candidate_manifest(path: Path) -> UsdPrimCandidateManifest:
    """Load USD prim candidate export from YAML or JSON."""
    resolved = Path(path).expanduser().resolve(strict=True)
    value = _load_yaml_or_json_text(resolved)
    if not isinstance(value, Mapping):
        raise GroundTruthError(f"USD prim candidate file must be a YAML/JSON mapping: {resolved}")
    return UsdPrimCandidateManifest.model_validate(dict(value))


def load_target_review_ledger(path: Path) -> TargetReviewLedger:
    """Load a human target-review ledger from YAML or JSON."""
    resolved = Path(path).expanduser().resolve(strict=True)
    value = _load_yaml_or_json_text(resolved)
    if not isinstance(value, Mapping):
        raise GroundTruthError(f"target review ledger must be a YAML/JSON mapping: {resolved}")
    return TargetReviewLedger.model_validate(dict(value))


def load_default_target_annotations() -> TargetAnnotationManifest:
    """Load packaged RetroNeighborhood target annotations."""
    value = yaml.safe_load(_default_target_annotations_text())
    if not isinstance(value, Mapping):
        raise GroundTruthError("packaged target annotations must be a YAML/JSON mapping")
    return TargetAnnotationManifest.model_validate(dict(value))


def load_traversability_grid(npz_path: Path, metadata: TraversabilityMetadata) -> TraversabilityGrid:
    """Load and validate traversability arrays for deterministic GT generation."""
    _, arrays = _read_traversability_npz(npz_path, metadata)
    return TraversabilityGrid(
        metadata=metadata,
        height=arrays["height"],
        mask=arrays["mask"],
        component=arrays["component"],
        cost=arrays["cost"],
    )


def target_annotations_sha256(manifest: TargetAnnotationManifest) -> str:
    """Return the SHA-256 checksum of canonical target annotations."""
    return hashlib.sha256(canonical_target_annotations_json(manifest).encode("utf-8")).hexdigest()


def apply_target_review_ledger(
    manifest: TargetAnnotationManifest,
    ledger: TargetReviewLedger,
    *,
    require_source_checksum: bool = True,
    generator_version: str = "p1-05e",
) -> tuple[TargetAnnotationManifest, TargetReviewApplyReport]:
    """Apply audited human-review decisions to target annotations.

    The ledger is the handoff format for P1-05: humans review the generated
    video/frames, write one decision per target row, and this function applies
    those decisions without manual JSON editing.  It verifies scene/frame
    compatibility, optionally requires the source annotation checksum, and only
    mutates rows explicitly listed in the ledger.
    """
    if manifest.scene_id != ledger.scene_id:
        raise GroundTruthError(
            f"target scene_id {manifest.scene_id!r} does not match review ledger scene_id {ledger.scene_id!r}"
        )
    if manifest.frame != ledger.frame:
        raise GroundTruthError(
            f"target frame {manifest.frame!r} does not match review ledger frame {ledger.frame!r}"
        )
    source_sha256 = target_annotations_sha256(manifest)
    if ledger.source_annotations_sha256 is None:
        if require_source_checksum:
            raise GroundTruthError("target review ledger must include source_annotations_sha256")
    elif ledger.source_annotations_sha256 != source_sha256:
        raise GroundTruthError(
            "target review ledger source_annotations_sha256 does not match input annotations"
        )

    instances_by_id = {instance.instance_id: instance for instance in manifest.instances}
    unknown_ids = sorted(
        decision.instance_id
        for decision in ledger.decisions
        if decision.instance_id not in instances_by_id
    )
    if unknown_ids:
        raise GroundTruthError(
            "target review ledger references unknown instance_id values: "
            + ", ".join(unknown_ids[:10])
        )

    decisions = {decision.instance_id: decision for decision in ledger.decisions}
    updated_instances: list[TargetInstance] = []
    changed_instance_ids: list[str] = []
    excluded_instance_ids: list[str] = []
    verify_decision_count = 0
    exclude_decision_count = 0

    for instance in manifest.instances:
        decision = decisions.get(instance.instance_id)
        if decision is None:
            updated_instances.append(instance)
            continue
        review_version = decision.review_version or ledger.review_version
        updates: dict[str, Any] = {
            "review_version": review_version,
            "verified": True,
        }
        if decision.usd_prim_path is not None:
            updates["usd_prim_path"] = decision.usd_prim_path
        if decision.semantic_class is not None:
            updates["semantic_class"] = decision.semantic_class
        if decision.source_class is not None:
            updates["source_class"] = decision.source_class
        if decision.obb is not None:
            updates["obb"] = decision.obb
        if decision.action == "verify":
            updates["excluded_reason"] = None
            verify_decision_count += 1
        else:
            updates["excluded_reason"] = decision.excluded_reason
            exclude_decision_count += 1
            excluded_instance_ids.append(instance.instance_id)
        updated_instances.append(instance.model_copy(update=updates))
        changed_instance_ids.append(instance.instance_id)

    updated = TargetAnnotationManifest(
        schema_version=manifest.schema_version,
        scene_id=manifest.scene_id,
        frame=manifest.frame,
        source_format=manifest.source_format,
        source_path=manifest.source_path,
        spawn_offset_xyz_m=manifest.spawn_offset_xyz_m,
        instances=tuple(updated_instances),
        confirmation_regions=manifest.confirmation_regions,
    )
    report = TargetReviewApplyReport(
        schema_version=manifest.schema_version,
        scene_id=manifest.scene_id,
        frame=manifest.frame,
        generator="airground-target-human-review-apply-v1",
        generator_version=generator_version,
        review_version=ledger.review_version,
        source_annotations_sha256=source_sha256,
        output_annotations_sha256=target_annotations_sha256(updated),
        instance_count=len(manifest.instances),
        decision_count=len(ledger.decisions),
        verify_decision_count=verify_decision_count,
        exclude_decision_count=exclude_decision_count,
        untouched_count=len(manifest.instances) - len(ledger.decisions),
        changed_instance_ids=tuple(changed_instance_ids),
        excluded_instance_ids=tuple(excluded_instance_ids),
        status="ok",
    )
    return updated, report


def build_target_review_ledger_template(
    manifest: TargetAnnotationManifest,
    review_queue: Mapping[str, Any],
    *,
    review_version: str,
    source_review_queue_sha256: str | None = None,
    source_review_media: str | None = None,
    generator_version: str = "p1-05f",
) -> TargetReviewLedgerTemplate:
    """Build a safe draft template for human target review.

    The result intentionally uses ``airground-target-human-review-ledger-template-v1``
    rather than the final ledger generator name. Passing it directly to
    ``apply-review`` fails schema validation; a human must copy/author final
    ``airground-target-human-review-ledger-v1`` decisions after inspecting the
    review video.
    """
    if not review_version:
        raise GroundTruthError("review_version must be non-empty")
    if review_queue.get("scene_id") not in (None, manifest.scene_id):
        raise GroundTruthError("review queue scene_id does not match target annotations")
    rows_value = review_queue.get("rows")
    if not isinstance(rows_value, Sequence) or isinstance(rows_value, (str, bytes)):
        raise GroundTruthError("target review queue must contain a rows array")
    instances_by_id = {instance.instance_id: instance for instance in manifest.instances}
    template_rows: list[TargetReviewLedgerTemplateRow] = []
    for row_value in rows_value:
        if not isinstance(row_value, Mapping):
            raise GroundTruthError("target review queue rows must be mappings")
        instance_id = str(row_value.get("instance_id", ""))
        instance = instances_by_id.get(instance_id)
        if instance is None:
            raise GroundTruthError(f"review queue references unknown instance_id: {instance_id}")
        issues = _review_queue_issues(row_value.get("issues"))
        priority = _optional_nonnegative_int(row_value.get("priority"))
        row_usd_prim_path = _optional_review_prim_path(row_value.get("usd_prim_path"))
        current_usd_prim_path = row_usd_prim_path or instance.usd_prim_path
        decision_required = bool(issues)
        if not current_usd_prim_path:
            suggested_next_step: Literal[
                "confirm_or_correct_candidate",
                "choose_usd_prim_path_or_exclude",
                "optional_noop",
            ] = "choose_usd_prim_path_or_exclude"
        elif decision_required:
            suggested_next_step = "confirm_or_correct_candidate"
        else:
            suggested_next_step = "optional_noop"
        final_decision_fields = {
            "action": "verify_or_exclude",
            "excluded_reason": "required only when action=exclude",
            "instance_id": instance.instance_id,
            "notes": "optional human review note",
            "obb": "optional corrected OBB object",
            "review_version": review_version,
            "semantic_class": "optional corrected lowercase class",
            "source_class": "optional corrected source class",
            "usd_prim_path": current_usd_prim_path or "required when action=verify",
        }
        template_rows.append(
            TargetReviewLedgerTemplateRow(
                instance_id=instance.instance_id,
                semantic_class=instance.semantic_class,
                source_index=instance.source_index,
                priority=priority,
                review_frame_index=(priority + 1) if priority is not None else None,
                issues=issues,
                current_usd_prim_path=current_usd_prim_path,
                current_obb=instance.obb,
                decision_required=decision_required,
                suggested_next_step=suggested_next_step,
                final_decision_fields=final_decision_fields,
            )
        )
    template_rows.sort(
        key=lambda row: (
            not row.decision_required,
            row.priority if row.priority is not None else 10**9,
            row.instance_id,
        )
    )
    review_required_count = sum(1 for row in template_rows if row.decision_required)
    return TargetReviewLedgerTemplate(
        schema_version=manifest.schema_version,
        scene_id=manifest.scene_id,
        frame=manifest.frame,
        generator="airground-target-human-review-ledger-template-v1",
        generator_version=generator_version,
        review_version=review_version,
        source_annotations_sha256=target_annotations_sha256(manifest),
        source_review_queue_sha256=source_review_queue_sha256,
        source_review_media=source_review_media,
        human_review_required=review_required_count > 0,
        row_count=len(template_rows),
        review_required_count=review_required_count,
        instructions=(
            "Inspect the referenced review video/contact sheet before authoring final decisions.",
            "Do not pass this template to apply-review; it is intentionally not a final ledger.",
            "Create an airground-target-human-review-ledger-v1 file with one verify/exclude decision per reviewed row.",
            "Keep source_annotations_sha256 unchanged so stale annotations are rejected.",
        ),
        rows=tuple(template_rows),
    )


def _review_queue_issues(value: Any) -> tuple[str, ...]:
    """Normalize a review queue issues field into stable issue tokens."""
    if value is None:
        return ()
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return ()
        separators = ";" if ";" in stripped else ","
        return tuple(part.strip() for part in stripped.split(separators) if part.strip())
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
        return tuple(str(part).strip() for part in value if str(part).strip())
    stripped = str(value).strip()
    return (stripped,) if stripped else ()


def _optional_nonnegative_int(value: Any) -> int | None:
    """Parse an optional non-negative integer from review queue metadata."""
    if value is None or value == "":
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise GroundTruthError(f"review queue priority must be an integer: {value!r}") from exc
    if parsed < 0:
        raise GroundTruthError("review queue priority must be non-negative")
    return parsed


def _optional_review_prim_path(value: Any) -> str | None:
    """Parse an optional USD prim path from a review queue row."""
    if value is None:
        return None
    path = str(value).strip()
    if not path:
        return None
    if not path.startswith("/"):
        raise GroundTruthError(f"review queue usd_prim_path must be absolute when provided: {path!r}")
    return path


def audit_target_annotations(
    manifest: TargetAnnotationManifest,
    *,
    require_source_path: bool = False,
    require_usd_prim_path: bool = False,
    require_verified: bool = False,
    require_review_version: bool = False,
    max_issues: int = 100,
) -> TargetAnnotationAuditReport:
    """Audit target annotation completeness before release.

    The base schema validates type and reference integrity. This audit adds the
    release-facing completeness gates needed by the UAV+UGV benchmark: stable
    instance ids, source provenance, optional USD prim binding, optional human
    review status and optional review version. It does not verify that a USD
    prim exists in a live Isaac stage.
    """
    if max_issues < 0:
        raise GroundTruthError("max_issues must be non-negative")
    requirements = {
        "require_review_version": require_review_version,
        "require_source_path": require_source_path,
        "require_usd_prim_path": require_usd_prim_path,
        "require_verified": require_verified,
    }
    issues: list[TargetAnnotationAuditIssue] = []
    if require_source_path and not manifest.source_path:
        issues.append(
            TargetAnnotationAuditIssue(
                code="missing_source_path",
                message="target annotation manifest must include source_path",
                instance_id=None,
            )
        )

    source_indexes: dict[int, str] = {}
    for instance in manifest.instances:
        if not instance.instance_id.startswith(f"{manifest.scene_id}."):
            issues.append(
                TargetAnnotationAuditIssue(
                    code="unstable_instance_id",
                    instance_id=instance.instance_id,
                    message=f"instance_id must start with {manifest.scene_id}.",
                )
            )
        if instance.source_index in source_indexes:
            issues.append(
                TargetAnnotationAuditIssue(
                    code="duplicate_source_index",
                    instance_id=instance.instance_id,
                    message=f"source_index duplicates {source_indexes[instance.source_index]}",
                )
            )
        else:
            source_indexes[instance.source_index] = instance.instance_id
        if instance.semantic_class != instance.semantic_class.strip().lower():
            issues.append(
                TargetAnnotationAuditIssue(
                    code="noncanonical_semantic_class",
                    instance_id=instance.instance_id,
                    message="semantic_class should be lowercase and trimmed",
                    severity="warning",
                )
            )
        if require_usd_prim_path and not instance.usd_prim_path and not instance.excluded_reason:
            issues.append(
                TargetAnnotationAuditIssue(
                    code="missing_usd_prim_path",
                    instance_id=instance.instance_id,
                    message="target instance must be bound to a USD prim path unless excluded by human review",
                )
            )
        if require_verified and not instance.verified:
            issues.append(
                TargetAnnotationAuditIssue(
                    code="unverified_target",
                    instance_id=instance.instance_id,
                    message="target instance must be marked verified",
                )
            )
        if require_review_version and not instance.review_version:
            issues.append(
                TargetAnnotationAuditIssue(
                    code="missing_review_version",
                    instance_id=instance.instance_id,
                    message="target instance must include review_version",
                )
            )
    return TargetAnnotationAuditReport(
        manifest=manifest,
        requirements=requirements,
        issues=tuple(issues),
        max_issues=max_issues,
    )


_TARGET_USD_ALIAS_TOKENS: dict[str, tuple[str, ...]] = {
    "billboard": ("billboard",),
    "blue container": (
        "blue_container",
        "container",
        "garbage_container",
        "shipping_container",
        "shippingcontainer",
    ),
    "bus stop": ("bus_stop", "busstop"),
    "chimney": ("chimney",),
    "fountain": ("fountain",),
    "house": ("house",),
    "porch": ("porch",),
    "red car": ("red_car", "hovercar", "car"),
    "red container": (
        "red_container",
        "container",
        "garbage_container",
        "shipping_container",
        "shippingcontainer",
    ),
    "tree": ("tree",),
    "tunnel": ("tunnel",),
    "yellow car": ("yellow_car", "car"),
}

_TARGET_USD_ALIAS_TOKENS.update(EXTRA_USD_ALIASES)

#: Color words the binder understands, both in the queried class name and in the
#: exported ``color_hint``.  ``gray``/``grey`` are normalised to ``grey``.
_QUERY_COLOR_TOKENS: tuple[str, ...] = (
    "blue",
    "red",
    "green",
    "yellow",
    "white",
    "black",
    "grey",
    "gray",
    "orange",
)


def _query_color(semantic_class: str) -> str | None:
    """Return the color word requested by a semantic class, if any."""

    tokens = set(_semantic_key(semantic_class).split("_"))
    for color in _QUERY_COLOR_TOKENS:
        if color in tokens:
            return "grey" if color == "gray" else color
    return None


def bind_target_annotations_to_usd_prims(
    manifest: TargetAnnotationManifest,
    prims: UsdPrimCandidateManifest,
    *,
    max_center_distance_m: float = 3.0,
    max_size_l1_delta_m: float | None = None,
    ambiguity_margin_m: float = 0.25,
    require_unique: bool = False,
    fail_on_ambiguous: bool = False,
    only_unbound: bool = False,
    generator_version: str = "p1-05b",
) -> tuple[TargetAnnotationManifest, TargetPrimBindingReport]:
    """Bind target annotations to exported USD prim candidates.

    This is an automatic, review-aid stage for P1 target annotation work.  It
    assigns stable USD prim paths when the exported prim candidate has a
    compatible semantic hint/path token and a nearby world-space bounding box.
    It deliberately leaves ``verified`` and ``review_version`` untouched; human
    review remains a separate release gate.

    ``only_unbound`` keeps every already-bound instance exactly as reviewed and
    only fills in the instances that have no ``usd_prim_path`` yet (used by the
    2026-09-24 container re-anchor so the reviewed 161 rows cannot drift).
    """
    if manifest.scene_id != prims.scene_id:
        raise GroundTruthError(
            f"target scene_id {manifest.scene_id!r} does not match USD candidate scene_id {prims.scene_id!r}"
        )
    if manifest.frame != prims.frame:
        raise GroundTruthError(
            f"target frame {manifest.frame!r} does not match USD candidate frame {prims.frame!r}"
        )
    if max_center_distance_m <= 0.0:
        raise GroundTruthError("max_center_distance_m must be positive")
    if max_size_l1_delta_m is not None and max_size_l1_delta_m <= 0.0:
        raise GroundTruthError("max_size_l1_delta_m must be positive when provided")
    if ambiguity_margin_m < 0.0:
        raise GroundTruthError("ambiguity_margin_m must be non-negative")

    candidate_rows = sorted(
        prims.candidates,
        key=lambda candidate: (
            _prim_candidate_sort_key(candidate),
            candidate.prim_path,
        ),
    )
    chosen_paths: dict[str, list[str]] = {}
    updated_instances: list[TargetInstance] = []
    binding_rows: list[TargetPrimBinding] = []

    for instance in manifest.instances:
        if only_unbound and instance.usd_prim_path:
            binding_rows.append(
                TargetPrimBinding(
                    instance_id=instance.instance_id,
                    semantic_class=instance.semantic_class,
                    source_index=instance.source_index,
                    usd_prim_path=instance.usd_prim_path,
                    candidate_count=0,
                    skipped_existing_binding=True,
                    issues=("existing_binding_kept",),
                )
            )
            updated_instances.append(instance)
            continue
        ranked = _rank_prim_candidates_for_target(
            instance,
            candidate_rows,
            max_center_distance_m=max_center_distance_m,
            max_size_l1_delta_m=max_size_l1_delta_m,
        )
        issues: list[str] = []
        chosen = ranked[0] if ranked else None
        candidate_count = len(ranked)
        if chosen is None:
            issues.append("no_semantic_candidate_within_threshold")
            updated_instances.append(instance)
            binding_rows.append(
                TargetPrimBinding(
                    instance_id=instance.instance_id,
                    semantic_class=instance.semantic_class,
                    source_index=instance.source_index,
                    candidate_count=candidate_count,
                    issues=tuple(issues),
                )
            )
            continue

        _, center_distance_m, size_l1_delta_m, candidate = chosen
        ambiguous = (
            len(ranked) > 1
            and ranked[1][0] <= chosen[0] + ambiguity_margin_m
            and ranked[1][3].prim_path != candidate.prim_path
        )
        if ambiguous:
            issues.append("ambiguous_match")
        chosen_paths.setdefault(candidate.prim_path, []).append(instance.instance_id)
        updated_instances.append(instance.model_copy(update={"usd_prim_path": candidate.prim_path}))
        binding_rows.append(
            TargetPrimBinding(
                instance_id=instance.instance_id,
                semantic_class=instance.semantic_class,
                source_index=instance.source_index,
                usd_prim_path=candidate.prim_path,
                candidate_count=candidate_count,
                candidate_rank=0,
                center_distance_m=center_distance_m,
                size_l1_delta_m=size_l1_delta_m,
                score=chosen[0],
                issues=tuple(issues),
            )
        )

    duplicate_paths = {
        path: instance_ids for path, instance_ids in chosen_paths.items() if len(instance_ids) > 1
    }
    if duplicate_paths:
        binding_rows = [
            _binding_with_duplicate_issue(row, duplicate_paths)
            for row in binding_rows
        ]

    unbound_count = sum(1 for row in binding_rows if row.usd_prim_path is None)
    ambiguous_count = sum(1 for row in binding_rows if "ambiguous_match" in row.issues)
    duplicate_binding_count = sum(1 for row in binding_rows if "duplicate_usd_prim_path" in row.issues)
    issue_count = sum(len(row.issues) for row in binding_rows)
    failed = (
        unbound_count > 0
        or (require_unique and duplicate_binding_count > 0)
        or (fail_on_ambiguous and ambiguous_count > 0)
    )
    updated = TargetAnnotationManifest(
        schema_version=manifest.schema_version,
        scene_id=manifest.scene_id,
        frame=manifest.frame,
        source_format=manifest.source_format,
        source_path=manifest.source_path,
        spawn_offset_xyz_m=manifest.spawn_offset_xyz_m,
        instances=tuple(updated_instances),
        confirmation_regions=manifest.confirmation_regions,
    )
    report = TargetPrimBindingReport(
        schema_version=manifest.schema_version,
        scene_id=manifest.scene_id,
        frame=manifest.frame,
        generator="airground-target-prim-binder-v1",
        generator_version=generator_version,
        source_usd_path=prims.source_usd_path,
        max_center_distance_m=max_center_distance_m,
        max_size_l1_delta_m=max_size_l1_delta_m,
        ambiguity_margin_m=ambiguity_margin_m,
        require_unique=require_unique,
        fail_on_ambiguous=fail_on_ambiguous,
        instance_count=len(manifest.instances),
        candidate_count=len(prims.candidates),
        bound_count=len(manifest.instances) - unbound_count,
        unbound_count=unbound_count,
        ambiguous_count=ambiguous_count,
        duplicate_binding_count=duplicate_binding_count,
        issue_count=issue_count,
        status="failed" if failed else "ok",
        bindings=tuple(binding_rows),
    )
    return updated, report


def _binding_with_duplicate_issue(
    row: TargetPrimBinding,
    duplicate_paths: Mapping[str, Sequence[str]],
) -> TargetPrimBinding:
    if row.usd_prim_path is None or row.usd_prim_path not in duplicate_paths:
        return row
    issues = tuple(dict.fromkeys((*row.issues, "duplicate_usd_prim_path")))
    return row.model_copy(update={"issues": issues})


def _rank_prim_candidates_for_target(
    instance: TargetInstance,
    candidates: Sequence[UsdPrimCandidate],
    *,
    max_center_distance_m: float,
    max_size_l1_delta_m: float | None,
) -> list[tuple[float, float, float, UsdPrimCandidate]]:
    ranked: list[tuple[float, float, float, UsdPrimCandidate]] = []
    target_center = instance.obb.center_xyz_m
    target_size = instance.obb.size_xyz_m
    query_color = _query_color(instance.semantic_class)
    for candidate in candidates:
        if not _candidate_matches_semantic_class(candidate, instance.semantic_class):
            continue
        if (
            query_color is not None
            and candidate.color_hint is not None
            and candidate.color_hint != query_color
        ):
            # "blue container" must not bind to the red crate that happens to sit
            # closer to the annotation.
            continue
        center_distance_m = _euclidean_distance(target_center, candidate.center_xyz_m)
        if center_distance_m > max_center_distance_m:
            continue
        size_l1_delta_m = sum(
            abs(float(target_value) - float(candidate_value))
            for target_value, candidate_value in zip(target_size, candidate.size_xyz_m, strict=True)
        )
        if max_size_l1_delta_m is not None and size_l1_delta_m > max_size_l1_delta_m:
            continue
        color_penalty = 0.0
        if query_color is not None and candidate.color_hint is None:
            # Unknown color still bindable, but ranked behind a confirmed match.
            color_penalty = 0.5
        score = center_distance_m + 0.05 * size_l1_delta_m + color_penalty
        ranked.append((score, center_distance_m, size_l1_delta_m, candidate))
    return sorted(ranked, key=lambda item: (item[0], item[1], item[2], item[3].prim_path))


def _candidate_matches_semantic_class(candidate: UsdPrimCandidate, semantic_class: str) -> bool:
    aliases = _semantic_class_aliases(semantic_class)
    hint_tokens = {
        token
        for hint in candidate.semantic_hints
        for token in _semantic_tokens(hint)
    }
    path_tokens = _semantic_tokens(candidate.prim_path)
    if (hint_tokens | path_tokens) & aliases:
        return True
    # Compact substring match keeps older exports (no semantic hints) working for
    # names such as ``SM_ShippingContainer3`` / ``SM_Garbage_Container_1``.
    compact = re.sub(r"[^a-z0-9]+", "", candidate.prim_path.lower())
    return any(alias.replace("_", "") in compact for alias in aliases)


def _semantic_class_aliases(semantic_class: str) -> set[str]:
    canonical = _semantic_key(semantic_class)
    aliases = set(_TARGET_USD_ALIAS_TOKENS.get(semantic_class.strip().lower(), ()))
    aliases.add(canonical)
    return aliases


def _semantic_tokens(value: str) -> set[str]:
    normalized = _semantic_key(value)
    tokens = {token for token in normalized.split("_") if token}
    tokens.add(normalized)
    # Keep compound phrases used by Unreal/Isaac prim names.
    for compound in ("bus_stop", "blue_container", "red_container", "red_car", "yellow_car"):
        if compound in normalized:
            tokens.add(compound)
    # Avoid the common false-positive where "street" contains "tree".
    if "street" in tokens:
        tokens.discard("tree")
    return tokens


def _semantic_key(value: str) -> str:
    return re.sub(r"_+", "_", re.sub(r"[^a-z0-9]+", "_", value.strip().lower())).strip("_")


def _prim_candidate_sort_key(candidate: UsdPrimCandidate) -> tuple[float, float, str]:
    size = candidate.size_xyz_m
    volume = float(size[0]) * float(size[1]) * float(size[2])
    return (-volume, _euclidean_distance((0.0, 0.0, 0.0), candidate.center_xyz_m), candidate.prim_path)


def _euclidean_distance(
    a: tuple[float, float, float],
    b: tuple[float, float, float],
) -> float:
    return math.sqrt(sum((float(x) - float(y)) ** 2 for x, y in zip(a, b, strict=True)))


def write_target_review_artifacts(
    manifest: TargetAnnotationManifest,
    output_dir: Path,
    *,
    max_targets: int | None = None,
    canvas_width_px: int = 1200,
    canvas_height_px: int = 900,
    camera_position_xyz_m: tuple[float, float, float] | None = None,
    camera_yaw_rad: float | None = None,
    horizontal_fov_rad: float = math.radians(90.0),
    vertical_fov_rad: float = math.radians(60.0),
    max_distance_m: float = 120.0,
) -> dict[str, Any]:
    """Write deterministic SVG review artifacts for target annotations.

    The review packet is intentionally simulator-independent: it renders the
    current target OBBs, labels, and optional USD prim paths into a top-down SVG
    and a simple first-person pinhole-camera SVG. It is a review aid for human
    annotation cleanup; it does not replace later Isaac camera-frustum or mesh
    raycast validation.
    """
    if max_targets is not None and max_targets <= 0:
        raise GroundTruthError("max_targets must be positive when provided")
    if canvas_width_px < 200 or canvas_height_px < 200:
        raise GroundTruthError("review canvas dimensions must be at least 200 px")
    if horizontal_fov_rad <= 0.0 or vertical_fov_rad <= 0.0:
        raise GroundTruthError("review camera FOV values must be positive")
    if horizontal_fov_rad >= math.pi or vertical_fov_rad >= math.pi:
        raise GroundTruthError("review camera FOV values must be < pi radians")
    if max_distance_m <= 0.0:
        raise GroundTruthError("max_distance_m must be positive")

    instances = tuple(manifest.instances[:max_targets] if max_targets is not None else manifest.instances)
    if not instances:
        raise GroundTruthError("target review requires at least one rendered target")

    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)
    camera_position, camera_yaw = _target_review_camera(instances, camera_position_xyz_m, camera_yaw_rad)
    topdown_svg = _render_target_topdown_svg(
        manifest,
        instances,
        width_px=canvas_width_px,
        height_px=canvas_height_px,
    )
    first_person_svg, visible_ids = _render_target_first_person_svg(
        manifest,
        instances,
        camera_position_xyz_m=camera_position,
        camera_yaw_rad=camera_yaw,
        horizontal_fov_rad=horizontal_fov_rad,
        vertical_fov_rad=vertical_fov_rad,
        max_distance_m=max_distance_m,
        width_px=canvas_width_px,
        height_px=canvas_height_px,
    )

    topdown_path = output_root / "targets_topdown.svg"
    first_person_path = output_root / "targets_first_person.svg"
    manifest_path = output_root / "review_manifest.json"
    topdown_path.write_text(topdown_svg, encoding="utf-8")
    first_person_path.write_text(first_person_svg, encoding="utf-8")

    visible_set = set(visible_ids)
    summary: dict[str, Any] = {
        "artifacts": {
            "first_person_svg": {
                "path": first_person_path.name,
                "sha256": _file_sha256(first_person_path),
            },
            "topdown_svg": {
                "path": topdown_path.name,
                "sha256": _file_sha256(topdown_path),
            },
        },
        "camera": {
            "horizontal_fov_rad": horizontal_fov_rad,
            "max_distance_m": max_distance_m,
            "position_xyz_m": list(camera_position),
            "vertical_fov_rad": vertical_fov_rad,
            "yaw_rad": camera_yaw,
        },
        "first_person_visible_count": len(visible_ids),
        "frame": manifest.frame,
        "instance_count": len(manifest.instances),
        "rendered_instance_count": len(instances),
        "scene_id": manifest.scene_id,
        "schema_version": manifest.schema_version,
        "source_sha256": target_annotations_sha256(manifest),
        "status": "ok",
        "targets": [
            {
                "first_person_visible": instance.instance_id in visible_set,
                "instance_id": instance.instance_id,
                "semantic_class": instance.semantic_class,
                "source_index": instance.source_index,
                "usd_prim_path": instance.usd_prim_path,
            }
            for instance in instances
        ],
    }
    manifest_path.write_text(
        json.dumps(summary, ensure_ascii=True, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    summary["artifacts"]["review_manifest"] = {
        "path": manifest_path.name,
        "sha256": _file_sha256(manifest_path),
    }
    manifest_path.write_text(
        json.dumps(summary, ensure_ascii=True, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    return summary


def build_confirmation_regions_from_traversability(
    manifest: TargetAnnotationManifest,
    metadata: TraversabilityMetadata,
    npz_path: Path,
    *,
    min_distance_m: float = 1.5,
    max_distance_m: float = 8.0,
    radial_step_m: float = 0.5,
    angle_count: int = 32,
    max_poses_per_target: int = 128,
    proxy_visible_fraction: float = 1.0,
) -> TargetAnnotationManifest:
    """Attach deterministic traversability-filtered UGV confirmation candidates.

    This generator is a ground-reachability pass. It samples UGV poses around
    each OBB and filters them against traversability components. It deliberately
    uses a proxy visible fraction; Isaac camera-frustum and occlusion raycast
    gates remain a later GT generation stage.
    """
    _validate_confirmation_sampling_config(
        min_distance_m=min_distance_m,
        max_distance_m=max_distance_m,
        radial_step_m=radial_step_m,
        angle_count=angle_count,
        max_poses_per_target=max_poses_per_target,
        proxy_visible_fraction=proxy_visible_fraction,
    )
    if manifest.scene_id != metadata.scene_id or manifest.frame != metadata.frame:
        raise GroundTruthError(
            "target annotations and traversability metadata must share scene_id and frame"
        )

    grid = load_traversability_grid(npz_path, metadata)
    updated_instances: list[TargetInstance] = []
    regions: list[ConfirmationRegion] = []
    for instance in manifest.instances:
        region_id = f"confirm/{instance.instance_id}"
        if instance.excluded_reason:
            reason = instance.excluded_reason
            poses: tuple[ConfirmationPose, ...] = ()
        else:
            poses = tuple(
                _sample_confirmation_poses(
                    instance,
                    grid,
                    min_distance_m=min_distance_m,
                    max_distance_m=max_distance_m,
                    radial_step_m=radial_step_m,
                    angle_count=angle_count,
                    max_poses_per_target=max_poses_per_target,
                    proxy_visible_fraction=proxy_visible_fraction,
                )
            )
            reason = "no_traversable_pose_within_confirmation_radius"

        if poses:
            regions.append(
                ConfirmationRegion(
                    region_id=region_id,
                    instance_id=instance.instance_id,
                    reachable=True,
                    poses=poses,
                    yaw_range_rad=_yaw_range_rad(poses),
                )
            )
            updated_instances.append(
                instance.model_copy(
                    update={
                        "ground_reachable": "reachable",
                        "confirmation_region_id": region_id,
                    }
                )
            )
        else:
            regions.append(
                ConfirmationRegion(
                    region_id=region_id,
                    instance_id=instance.instance_id,
                    reachable=False,
                    excluded_reason=reason,
                )
            )
            updated_instances.append(
                instance.model_copy(
                    update={
                        "ground_reachable": "unreachable",
                        "confirmation_region_id": region_id,
                        "excluded_reason": instance.excluded_reason or reason,
                    }
                )
            )

    return TargetAnnotationManifest(
        schema_version=manifest.schema_version,
        scene_id=manifest.scene_id,
        frame=manifest.frame,
        source_format=manifest.source_format,
        source_path=manifest.source_path,
        spawn_offset_xyz_m=manifest.spawn_offset_xyz_m,
        instances=tuple(updated_instances),
        confirmation_regions=tuple(regions),
    )


def build_visibility_occlusion_report_from_traversability(
    manifest: TargetAnnotationManifest,
    metadata: TraversabilityMetadata,
    npz_path: Path,
    *,
    uav_altitudes_m: tuple[float, ...] = (2.0, 4.0, 6.0),
    min_range_m: float = 1.0,
    max_range_m: float = 35.0,
    horizontal_fov_rad: float = math.radians(90.0),
    yaw_samples: int = 8,
    sample_stride_cells: int = 1,
    ray_step_m: float | None = None,
) -> VisibilityOcclusionReport:
    """Estimate target visibility and occlusion from a traversability footprint.

    This is a deterministic pre-screening proxy for Phase 9 candidate pools. It
    samples UAV positions over the traversability grid footprint, checks whether
    each target center falls inside a yaw-binned horizontal camera frustum and
    range gate, then estimates occlusion by casting 2D rays through blocked grid
    cells to OBB surface samples. It is not a substitute for the later Isaac
    mesh raycast, but it gives stable values for difficulty balancing before the
    full simulator GT pass exists.
    """
    if manifest.scene_id != metadata.scene_id or manifest.frame != metadata.frame:
        raise GroundTruthError(
            "target annotations and traversability metadata must share scene_id and frame"
        )
    config = VisibilityOcclusionConfig(
        uav_altitudes_m=uav_altitudes_m,
        min_range_m=min_range_m,
        max_range_m=max_range_m,
        horizontal_fov_rad=horizontal_fov_rad,
        yaw_samples=yaw_samples,
        sample_stride_cells=sample_stride_cells,
        ray_step_m=ray_step_m,
    )
    grid = load_traversability_grid(npz_path, metadata)
    samples = tuple(_uav_search_samples(grid, config))
    candidate_count = len(samples) * config.yaw_samples
    metrics = tuple(
        _target_visibility_occlusion_metric(instance, grid, samples, candidate_count, config)
        for instance in manifest.instances
    )
    return VisibilityOcclusionReport(
        schema_version=manifest.schema_version,
        scene_id=manifest.scene_id,
        frame=manifest.frame,
        generator="airground-grid-obb-visibility-occlusion-proxy-v1",
        generator_version="1.0.0",
        config=config,
        target_count=len(metrics),
        metrics=metrics,
    )


def validate_confirmation_visibility_from_traversability(
    manifest: TargetAnnotationManifest,
    metadata: TraversabilityMetadata,
    npz_path: Path,
    *,
    min_distance_m: float = 1.5,
    max_distance_m: float = 8.0,
    horizontal_fov_rad: float = math.radians(90.0),
    min_visible_fraction: float = 0.2,
    required_consecutive_frames: int = 5,
    ray_step_m: float | None = None,
    generator_version: str = "0",
) -> ConfirmationVisibilityReport:
    """Validate confirmation regions with a deterministic grid/OBB proxy.

    This fixes an adapter-facing report surface for P1-07. It checks distance,
    pose yaw/FOV, stored visible fraction, 2D traversability-grid occlusion, and
    the continuous-frame gate. It does not replace later Isaac camera frustum or
    mesh raycast validation.
    """
    if manifest.scene_id != metadata.scene_id or manifest.frame != metadata.frame:
        raise GroundTruthError(
            "target annotations and traversability metadata must share scene_id and frame"
        )
    config = ConfirmationVisibilityConfig(
        min_distance_m=min_distance_m,
        max_distance_m=max_distance_m,
        horizontal_fov_rad=horizontal_fov_rad,
        min_visible_fraction=min_visible_fraction,
        required_consecutive_frames=required_consecutive_frames,
        ray_step_m=ray_step_m,
    )
    grid = load_traversability_grid(npz_path, metadata)
    instances_by_id = {instance.instance_id: instance for instance in manifest.instances}
    metrics: list[ConfirmationRegionVisibilityMetric] = []
    for region in manifest.confirmation_regions:
        instance = instances_by_id.get(region.instance_id)
        if instance is None:
            metrics.append(
                ConfirmationRegionVisibilityMetric(
                    region_id=region.region_id,
                    instance_id=region.instance_id,
                    reachable=region.reachable,
                    valid=False,
                    pose_count=len(region.poses),
                    valid_pose_count=0,
                    issues=("unknown_instance",),
                )
            )
            continue
        metrics.append(_confirmation_region_visibility_metric(region, instance, grid, config))

    reachable_target_region_ids = {
        instance.confirmation_region_id
        for instance in manifest.instances
        if instance.ground_reachable == "reachable" and instance.confirmation_region_id
    }
    reported_region_ids = {metric.region_id for metric in metrics}
    for missing_region_id in sorted(reachable_target_region_ids - reported_region_ids):
        instance = next(
            target
            for target in manifest.instances
            if target.confirmation_region_id == missing_region_id
        )
        metrics.append(
            ConfirmationRegionVisibilityMetric(
                region_id=missing_region_id,
                instance_id=instance.instance_id,
                reachable=True,
                valid=False,
                pose_count=0,
                valid_pose_count=0,
                issues=("missing_confirmation_region",),
            )
        )

    issue_count = sum(len(metric.issues) for metric in metrics)
    reachable_region_count = sum(1 for metric in metrics if metric.reachable)
    valid_region_count = sum(1 for metric in metrics if metric.reachable and metric.valid)
    status: Literal["ok", "failed"] = (
        "ok" if issue_count == 0 and valid_region_count == reachable_region_count else "failed"
    )
    return ConfirmationVisibilityReport(
        schema_version=manifest.schema_version,
        scene_id=manifest.scene_id,
        frame=manifest.frame,
        generator="airground-grid-confirmation-visibility-proxy-v1",
        generator_version=generator_version,
        config=config,
        region_count=len(metrics),
        valid_region_count=valid_region_count,
        issue_count=issue_count,
        status=status,
        metrics=tuple(metrics),
    )


def validate_confirmation_visibility_with_raycast(
    manifest: TargetAnnotationManifest,
    raycast: RaycastFn,
    *,
    camera_height_m: float = 1.2,
    min_distance_m: float = 1.5,
    max_distance_m: float = 8.0,
    horizontal_fov_rad: float = math.radians(90.0),
    min_visible_fraction: float = 0.2,
    required_consecutive_frames: int = 5,
    target_sample_count: Literal[1, 5, 9] = 5,
    occlusion_epsilon_m: float = 1e-3,
    ignored_prim_prefixes: Sequence[str] = (),
    generator_version: str = "p1-07b",
) -> RaycastConfirmationVisibilityReport:
    """Validate confirmation regions with a real/static-scene raycast callback.

    Real Isaac adapters can pass a PhysX scene-query backed raycast function.
    The validator checks distance, yaw/FOV, target surface samples, mesh
    occlusion and the continuous-frame gate surface. It still consumes explicit
    confirmation poses from the target manifest; it does not generate regions.
    """
    config = RaycastConfirmationVisibilityConfig(
        camera_height_m=camera_height_m,
        min_distance_m=min_distance_m,
        max_distance_m=max_distance_m,
        horizontal_fov_rad=horizontal_fov_rad,
        min_visible_fraction=min_visible_fraction,
        required_consecutive_frames=required_consecutive_frames,
        target_sample_count=target_sample_count,
        occlusion_epsilon_m=occlusion_epsilon_m,
        ignored_prim_prefixes=tuple(ignored_prim_prefixes),
    )
    instances_by_id = {instance.instance_id: instance for instance in manifest.instances}
    metrics: list[RaycastConfirmationRegionMetric] = []
    for region in manifest.confirmation_regions:
        instance = instances_by_id.get(region.instance_id)
        if instance is None:
            metrics.append(
                RaycastConfirmationRegionMetric(
                    region_id=region.region_id,
                    instance_id=region.instance_id,
                    reachable=region.reachable,
                    valid=False,
                    pose_count=len(region.poses),
                    valid_pose_count=0,
                    issues=("unknown_instance",),
                )
            )
            continue
        metrics.append(_raycast_confirmation_region_metric(region, instance, raycast, config))

    reachable_target_region_ids = {
        instance.confirmation_region_id
        for instance in manifest.instances
        if instance.ground_reachable == "reachable" and instance.confirmation_region_id
    }
    reported_region_ids = {metric.region_id for metric in metrics}
    for missing_region_id in sorted(reachable_target_region_ids - reported_region_ids):
        instance = next(
            target
            for target in manifest.instances
            if target.confirmation_region_id == missing_region_id
        )
        metrics.append(
            RaycastConfirmationRegionMetric(
                region_id=missing_region_id,
                instance_id=instance.instance_id,
                reachable=True,
                valid=False,
                pose_count=0,
                valid_pose_count=0,
                issues=("missing_confirmation_region",),
            )
        )

    issue_count = sum(len(metric.issues) for metric in metrics)
    reachable_region_count = sum(1 for metric in metrics if metric.reachable)
    valid_region_count = sum(1 for metric in metrics if metric.reachable and metric.valid)
    status: Literal["ok", "failed"] = (
        "ok" if issue_count == 0 and valid_region_count == reachable_region_count else "failed"
    )
    return RaycastConfirmationVisibilityReport(
        schema_version=manifest.schema_version,
        scene_id=manifest.scene_id,
        frame=manifest.frame,
        generator="airground-raycast-confirmation-visibility-v1",
        generator_version=generator_version,
        config=config,
        region_count=len(metrics),
        valid_region_count=valid_region_count,
        issue_count=issue_count,
        status=status,
        metrics=tuple(metrics),
    )


def confirmation_sensor_frame_records_from_pose(
    manifest: TargetAnnotationManifest,
    raycast: RaycastFn,
    *,
    camera_position_xyz_m: tuple[float, float, float],
    camera_yaw_rad: float,
    sim_time_s: float,
    camera_frame: str | None = None,
    target_id: str | None = None,
    camera_height_m: float = 1.2,
    min_distance_m: float = 1.5,
    max_distance_m: float = 8.0,
    horizontal_fov_rad: float = math.radians(90.0),
    min_visible_fraction: float = 0.2,
    required_consecutive_frames: int = 5,
    target_sample_count: Literal[1, 5, 9] = 5,
    occlusion_epsilon_m: float = 1.0e-3,
    ignored_prim_prefixes: Sequence[str] = (),
) -> tuple[dict[str, Any], ...]:
    """Build live UGV confirmation sensor-frame records from a camera pose.

    Real Isaac/ROS adapters use this to publish
    ``confirmation_visibility_sensor_frame`` records from the current UGV camera
    pose.  Unlike ``validate_confirmation_visibility_with_raycast``, this helper
    does not consume stored candidate poses as the camera pose; it computes
    distance, FOV and PhysX raycast visibility from the provided live pose.
    """
    if sim_time_s < 0.0 or not math.isfinite(sim_time_s):
        raise GroundTruthError("sim_time_s must be finite and non-negative")
    if camera_height_m <= 0.0 or not math.isfinite(camera_height_m):
        raise GroundTruthError("camera_height_m must be finite and positive")
    camera_x, camera_y, camera_z = (float(value) for value in camera_position_xyz_m)
    if not all(math.isfinite(value) for value in (camera_x, camera_y, camera_z, camera_yaw_rad)):
        raise GroundTruthError("camera position and yaw must be finite")

    config = RaycastConfirmationVisibilityConfig(
        camera_height_m=camera_height_m,
        min_distance_m=min_distance_m,
        max_distance_m=max_distance_m,
        horizontal_fov_rad=horizontal_fov_rad,
        min_visible_fraction=min_visible_fraction,
        required_consecutive_frames=required_consecutive_frames,
        target_sample_count=target_sample_count,
        occlusion_epsilon_m=occlusion_epsilon_m,
        ignored_prim_prefixes=tuple(ignored_prim_prefixes),
    )
    instances_by_id = {instance.instance_id: instance for instance in manifest.instances}
    live_pose = ConfirmationPose(
        frame="map",
        position_xyz_m=(camera_x, camera_y, camera_z - camera_height_m),
        yaw_rad=_normalize_angle(camera_yaw_rad),
        distance_to_target_m=0.0,
        visible_fraction=1.0,
    )
    records: list[dict[str, Any]] = []
    for region in manifest.confirmation_regions:
        if target_id is not None and region.instance_id != target_id:
            continue
        if not region.reachable:
            continue
        instance = instances_by_id.get(region.instance_id)
        if instance is None:
            continue
        metric = _raycast_confirmation_pose_metric(
            0,
            live_pose,
            instance,
            raycast,
            config,
        )
        records.append(
            {
                "blocked_ray_count": metric.blocked_ray_count,
                "blocking_prim_paths": list(metric.blocking_prim_paths),
                "camera_frame": camera_frame,
                "clear_ray_count": metric.clear_ray_count,
                "distance_to_target_m": metric.distance_to_target_m,
                "event": "confirmation_visibility_sensor_frame",
                "instance_id": region.instance_id,
                "pose_index": 0,
                "ray_count": metric.ray_count,
                "region_id": region.region_id,
                "sim_time_s": sim_time_s,
                "visible_fraction": metric.visible_fraction,
                "yaw_error_rad": metric.yaw_error_rad,
            }
        )
    return tuple(records)


def validate_confirmation_visibility_sensor_trace(
    manifest: TargetAnnotationManifest,
    trace_frames: Sequence[Mapping[str, Any] | SensorFrameConfirmationVisibilityTraceFrame],
    *,
    min_distance_m: float = 1.5,
    max_distance_m: float = 8.0,
    horizontal_fov_rad: float = math.radians(90.0),
    min_visible_fraction: float = 0.2,
    required_consecutive_frames: int = 5,
    max_frame_gap_s: float = 0.15,
    require_raycast_evidence: bool = True,
    generator_version: str = "p1-07d",
) -> SensorFrameConfirmationVisibilityReport:
    """Validate confirmation visibility from real continuous sensor-frame samples.

    This is the adapter-facing evidence checker for the final P1-07 gate.  A
    real Isaac/ROS run should emit one ``confirmation_visibility_sensor_frame``
    JSONL record for each sampled UGV camera frame and confirmation pose.  The
    checker requires each reachable confirmation region to contain at least one
    traced pose with ``required_consecutive_frames`` valid frames under the
    distance, yaw/FOV, visible-fraction and optional raycast-evidence gates.
    """
    config = SensorFrameConfirmationVisibilityConfig(
        min_distance_m=min_distance_m,
        max_distance_m=max_distance_m,
        horizontal_fov_rad=horizontal_fov_rad,
        min_visible_fraction=min_visible_fraction,
        required_consecutive_frames=required_consecutive_frames,
        max_frame_gap_s=max_frame_gap_s,
        require_raycast_evidence=require_raycast_evidence,
    )
    frames = tuple(
        frame
        if isinstance(frame, SensorFrameConfirmationVisibilityTraceFrame)
        else SensorFrameConfirmationVisibilityTraceFrame.model_validate(dict(frame))
        for frame in trace_frames
    )
    frames_by_region: dict[str, list[SensorFrameConfirmationVisibilityTraceFrame]] = {}
    for frame in frames:
        frames_by_region.setdefault(frame.region_id, []).append(frame)

    instances_by_id = {instance.instance_id: instance for instance in manifest.instances}
    metrics: list[SensorFrameConfirmationRegionTraceMetric] = []
    expected_region_ids: set[str] = set()
    for region in manifest.confirmation_regions:
        expected_region_ids.add(region.region_id)
        instance = instances_by_id.get(region.instance_id)
        region_frames = tuple(frames_by_region.get(region.region_id, ()))
        if instance is None:
            metrics.append(
                SensorFrameConfirmationRegionTraceMetric(
                    region_id=region.region_id,
                    instance_id=region.instance_id,
                    reachable=region.reachable,
                    valid=False,
                    pose_count=len(region.poses),
                    traced_pose_count=len({frame.pose_index for frame in region_frames}),
                    valid_pose_count=0,
                    frame_count=len(region_frames),
                    valid_frame_count=0,
                    issues=("unknown_instance",),
                )
            )
            continue
        metrics.append(
            _sensor_frame_confirmation_region_metric(
                region,
                instance,
                region_frames,
                config,
            )
        )

    for unknown_region_id in sorted(set(frames_by_region) - expected_region_ids):
        unknown_frames = tuple(frames_by_region[unknown_region_id])
        instance_ids = tuple(sorted({frame.instance_id for frame in unknown_frames}))
        metrics.append(
            SensorFrameConfirmationRegionTraceMetric(
                region_id=unknown_region_id,
                instance_id=instance_ids[0] if instance_ids else "unknown",
                reachable=False,
                valid=False,
                pose_count=0,
                traced_pose_count=len({frame.pose_index for frame in unknown_frames}),
                valid_pose_count=0,
                frame_count=len(unknown_frames),
                valid_frame_count=0,
                issues=("unknown_region_in_trace",),
            )
        )

    reachable_target_region_ids = {
        instance.confirmation_region_id
        for instance in manifest.instances
        if instance.ground_reachable == "reachable" and instance.confirmation_region_id
    }
    reported_region_ids = {metric.region_id for metric in metrics}
    for missing_region_id in sorted(reachable_target_region_ids - reported_region_ids):
        instance = next(
            target
            for target in manifest.instances
            if target.confirmation_region_id == missing_region_id
        )
        metrics.append(
            SensorFrameConfirmationRegionTraceMetric(
                region_id=missing_region_id,
                instance_id=instance.instance_id,
                reachable=True,
                valid=False,
                pose_count=0,
                traced_pose_count=0,
                valid_pose_count=0,
                frame_count=0,
                valid_frame_count=0,
                issues=("missing_confirmation_region",),
            )
        )

    issue_count = sum(len(metric.issues) for metric in metrics)
    reachable_region_count = sum(1 for metric in metrics if metric.reachable)
    valid_region_count = sum(1 for metric in metrics if metric.reachable and metric.valid)
    status: Literal["ok", "failed"] = (
        "ok" if issue_count == 0 and valid_region_count == reachable_region_count else "failed"
    )
    return SensorFrameConfirmationVisibilityReport(
        schema_version=manifest.schema_version,
        scene_id=manifest.scene_id,
        frame=manifest.frame,
        generator="airground-sensor-frame-confirmation-visibility-v1",
        generator_version=generator_version,
        config=config,
        region_count=len(metrics),
        valid_region_count=valid_region_count,
        issue_count=issue_count,
        trace_frame_count=len(frames),
        status=status,
        metrics=tuple(metrics),
    )


def convert_rayfronts_bbox_annotations(
    path: Path,
    *,
    scene_id: SceneId = "RetroNeighborhood",
    spawn_offset_xyz_m: tuple[float, float, float] = (0.0, 0.0, 0.0),
    source_path: str | None = None,
) -> TargetAnnotationManifest:
    """Convert RayFronts ``class`` + ``bbox_world`` JSON into target annotations."""
    resolved = Path(path).expanduser().resolve(strict=True)
    data = json.loads(resolved.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise GroundTruthError(f"RayFronts annotation file must be a JSON list: {resolved}")

    class_counts: dict[str, int] = {}
    instances: list[TargetInstance] = []
    sx, sy, sz = spawn_offset_xyz_m
    for index, item in enumerate(data):
        if not isinstance(item, Mapping):
            raise GroundTruthError(f"RayFronts annotation item {index} is not an object")
        source_class = item.get("class")
        bbox = item.get("bbox_world")
        if not isinstance(source_class, str) or not source_class.strip():
            raise GroundTruthError(f"RayFronts annotation item {index} has invalid class")
        if not isinstance(bbox, Mapping):
            raise GroundTruthError(f"RayFronts annotation item {index} has invalid bbox_world")
        center = _legacy_vec3(bbox, "center_xyz_m", index)
        size = _legacy_vec3(bbox, "size_xyz_m", index)
        orientation_deg = bbox.get("orientation_deg", [0.0, 0.0, 0.0])
        if not isinstance(orientation_deg, list | tuple) or len(orientation_deg) != 3:
            raise GroundTruthError(f"RayFronts annotation item {index} has invalid orientation_deg")

        semantic_class = source_class.strip().lower()
        count = class_counts.get(semantic_class, 0)
        class_counts[semantic_class] = count + 1
        instance_id = f"{scene_id}.{_slugify(semantic_class)}.{count:04d}"
        instances.append(
            TargetInstance(
                instance_id=instance_id,
                semantic_class=semantic_class,
                source_class=source_class,
                source_index=index,
                obb=OrientedBoundingBox(
                    frame="map",
                    center_xyz_m=(center[0] - sx, center[1] - sy, center[2] - sz),
                    size_xyz_m=size,
                    orientation_rpy_rad=tuple(
                        math.radians(float(value)) for value in orientation_deg
                    ),
                ),
            )
        )

    return TargetAnnotationManifest(
        schema_version=SCHEMA_VERSION,
        scene_id=scene_id,
        frame="map",
        source_format="rayfronts_bbox_world_v1",
        source_path=source_path if source_path is not None else str(path),
        spawn_offset_xyz_m=spawn_offset_xyz_m,
        instances=tuple(instances),
    )


def traversability_npz_sha256(path: Path) -> str:
    """Return the SHA-256 checksum for a traversability NPZ file."""
    resolved = Path(path).expanduser().resolve(strict=True)
    digest = hashlib.sha256()
    with resolved.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def validate_traversability_npz(
    npz_path: Path,
    metadata: TraversabilityMetadata,
) -> dict[str, Any]:
    """Validate a traversability NPZ against metadata and return a summary."""
    checksum, arrays = _read_traversability_npz(npz_path, metadata)
    mask = arrays["mask"]
    component = arrays["component"]

    rows, cols = metadata.shape
    return {
        "checksum_sha256": checksum,
        "component_count": int(len(set(int(value) for value in component[mask.astype(bool)]))),
        "frame": metadata.frame,
        "resolution_m": metadata.resolution_m,
        "scene_id": metadata.scene_id,
        "shape": [rows, cols],
        "status": "ok",
        "traversable_cells": int(mask.astype(bool).sum()),
    }


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _target_review_camera(
    instances: tuple[TargetInstance, ...],
    camera_position_xyz_m: tuple[float, float, float] | None,
    camera_yaw_rad: float | None,
) -> tuple[tuple[float, float, float], float]:
    if camera_position_xyz_m is not None and camera_yaw_rad is not None:
        return camera_position_xyz_m, _normalize_angle(camera_yaw_rad)

    bounds = _target_xy_bounds(instances)
    min_x, min_y, max_x, max_y = bounds
    center_x = (min_x + max_x) / 2.0
    center_y = (min_y + max_y) / 2.0
    span = max(max_x - min_x, max_y - min_y, 1.0)
    position = camera_position_xyz_m
    if position is None:
        position = (center_x - 0.65 * span, center_y - 0.55 * span, 2.0)
    yaw = camera_yaw_rad
    if yaw is None:
        yaw = math.atan2(center_y - position[1], center_x - position[0])
    return position, _normalize_angle(yaw)


def _render_target_topdown_svg(
    manifest: TargetAnnotationManifest,
    instances: tuple[TargetInstance, ...],
    *,
    width_px: int,
    height_px: int,
) -> str:
    bounds = _target_xy_bounds(instances)
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width_px}" '
            f'height="{height_px}" viewBox="0 0 {width_px} {height_px}">'
        ),
        "<style>"
        ".bg{fill:#111827}.grid{stroke:#374151;stroke-width:1;opacity:.35}"
        ".obb{fill-opacity:.18;stroke-width:2}.label{font:12px monospace;fill:#f9fafb}"
        ".title{font:18px sans-serif;font-weight:700;fill:#f9fafb}"
        ".meta{font:12px sans-serif;fill:#d1d5db}"
        "</style>",
        f'<rect class="bg" x="0" y="0" width="{width_px}" height="{height_px}"/>',
        (
            f'<text class="title" x="18" y="28">Target OBB Review · '
            f'{html.escape(manifest.scene_id)} · top-down map frame</text>'
        ),
        (
            f'<text class="meta" x="18" y="48">instances={len(instances)} · '
            f'frame={html.escape(manifest.frame)} · source={html.escape(manifest.source_format)}</text>'
        ),
    ]
    lines.extend(_target_review_grid(bounds, width_px, height_px))
    for instance in instances:
        color = _target_color(instance.instance_id)
        points = [
            _map_xy_to_canvas(x_m, y_m, bounds, width_px, height_px)
            for x_m, y_m in _obb_xy_corners(instance)
        ]
        point_text = " ".join(f"{x_px:.1f},{y_px:.1f}" for x_px, y_px in points)
        label_x, label_y = _map_xy_to_canvas(
            instance.obb.center_xyz_m[0],
            instance.obb.center_xyz_m[1],
            bounds,
            width_px,
            height_px,
        )
        title = _target_review_label(instance)
        lines.append(
            f'<polygon class="obb" points="{point_text}" fill="{color}" stroke="{color}">'
            f"<title>{html.escape(title)}</title></polygon>"
        )
        lines.append(
            f'<text class="label" x="{label_x + 4:.1f}" y="{label_y - 4:.1f}">'
            f"{html.escape(instance.instance_id)}</text>"
        )
    lines.append("</svg>")
    return "\n".join(lines) + "\n"


def _render_target_first_person_svg(
    manifest: TargetAnnotationManifest,
    instances: tuple[TargetInstance, ...],
    *,
    camera_position_xyz_m: tuple[float, float, float],
    camera_yaw_rad: float,
    horizontal_fov_rad: float,
    vertical_fov_rad: float,
    max_distance_m: float,
    width_px: int,
    height_px: int,
) -> tuple[str, tuple[str, ...]]:
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width_px}" '
            f'height="{height_px}" viewBox="0 0 {width_px} {height_px}">'
        ),
        "<style>"
        ".sky{fill:#1f2937}.ground{fill:#111827}.horizon{stroke:#6b7280;stroke-width:2}"
        ".obb{fill-opacity:.16;stroke-width:2}.label{font:12px monospace;fill:#f9fafb}"
        ".title{font:18px sans-serif;font-weight:700;fill:#f9fafb}"
        ".meta{font:12px sans-serif;fill:#d1d5db}"
        "</style>",
        f'<rect class="sky" x="0" y="0" width="{width_px}" height="{height_px / 2:.1f}"/>',
        (
            f'<rect class="ground" x="0" y="{height_px / 2:.1f}" '
            f'width="{width_px}" height="{height_px / 2:.1f}"/>'
        ),
        f'<line class="horizon" x1="0" y1="{height_px / 2:.1f}" x2="{width_px}" y2="{height_px / 2:.1f}"/>',
        (
            f'<text class="title" x="18" y="28">Target OBB Review · '
            f'{html.escape(manifest.scene_id)} · first-person proxy</text>'
        ),
        (
            f'<text class="meta" x="18" y="48">camera=({camera_position_xyz_m[0]:.2f},'
            f'{camera_position_xyz_m[1]:.2f},{camera_position_xyz_m[2]:.2f}) '
            f'yaw={camera_yaw_rad:.3f} rad · max_distance={max_distance_m:.1f} m</text>'
        ),
    ]
    visible_ids: list[str] = []
    projections: list[tuple[float, str, TargetInstance, tuple[float, float, float, float]]] = []
    for instance in instances:
        projection = _project_target_obb(
            instance,
            camera_position_xyz_m=camera_position_xyz_m,
            camera_yaw_rad=camera_yaw_rad,
            horizontal_fov_rad=horizontal_fov_rad,
            vertical_fov_rad=vertical_fov_rad,
            max_distance_m=max_distance_m,
            width_px=width_px,
            height_px=height_px,
        )
        if projection is None:
            continue
        distance_m, box = projection
        projections.append((distance_m, instance.instance_id, instance, box))
    for _, _, instance, (x0, y0, x1, y1) in sorted(projections, reverse=True):
        visible_ids.append(instance.instance_id)
        color = _target_color(instance.instance_id)
        label = _target_review_label(instance)
        lines.append(
            f'<rect class="obb" x="{x0:.1f}" y="{y0:.1f}" width="{x1 - x0:.1f}" '
            f'height="{y1 - y0:.1f}" fill="{color}" stroke="{color}">'
            f"<title>{html.escape(label)}</title></rect>"
        )
        lines.append(
            f'<text class="label" x="{x0 + 4:.1f}" y="{max(14.0, y0 - 4):.1f}">'
            f"{html.escape(instance.instance_id)}</text>"
        )
    lines.append("</svg>")
    return "\n".join(lines) + "\n", tuple(sorted(visible_ids))


def _target_review_label(instance: TargetInstance) -> str:
    prim = instance.usd_prim_path or "prim:null"
    return f"{instance.instance_id} · {instance.semantic_class} · {prim}"


def _target_xy_bounds(instances: tuple[TargetInstance, ...]) -> tuple[float, float, float, float]:
    xs: list[float] = []
    ys: list[float] = []
    for instance in instances:
        for x_m, y_m in _obb_xy_corners(instance):
            xs.append(x_m)
            ys.append(y_m)
    min_x = min(xs)
    max_x = max(xs)
    min_y = min(ys)
    max_y = max(ys)
    margin = max(max_x - min_x, max_y - min_y, 1.0) * 0.08
    return min_x - margin, min_y - margin, max_x + margin, max_y + margin


def _target_review_grid(
    bounds: tuple[float, float, float, float],
    width_px: int,
    height_px: int,
) -> list[str]:
    min_x, min_y, max_x, max_y = bounds
    lines: list[str] = []
    step = _nice_grid_step(max(max_x - min_x, max_y - min_y) / 8.0)
    start_x = math.floor(min_x / step) * step
    value = start_x
    while value <= max_x + 1e-9:
        x_px, _ = _map_xy_to_canvas(value, min_y, bounds, width_px, height_px)
        lines.append(f'<line class="grid" x1="{x_px:.1f}" y1="64" x2="{x_px:.1f}" y2="{height_px - 24}"/>')
        value += step
    start_y = math.floor(min_y / step) * step
    value = start_y
    while value <= max_y + 1e-9:
        _, y_px = _map_xy_to_canvas(min_x, value, bounds, width_px, height_px)
        lines.append(f'<line class="grid" x1="24" y1="{y_px:.1f}" x2="{width_px - 24}" y2="{y_px:.1f}"/>')
        value += step
    return lines


def _nice_grid_step(raw_step: float) -> float:
    if raw_step <= 0.0:
        return 1.0
    power = 10 ** math.floor(math.log10(raw_step))
    for multiplier in (1.0, 2.0, 5.0, 10.0):
        step = multiplier * power
        if step >= raw_step:
            return step
    return 10.0 * power


def _map_xy_to_canvas(
    x_m: float,
    y_m: float,
    bounds: tuple[float, float, float, float],
    width_px: int,
    height_px: int,
) -> tuple[float, float]:
    min_x, min_y, max_x, max_y = bounds
    pad_left = 24.0
    pad_right = 24.0
    pad_top = 64.0
    pad_bottom = 24.0
    plot_width = max(1.0, width_px - pad_left - pad_right)
    plot_height = max(1.0, height_px - pad_top - pad_bottom)
    x_px = pad_left + (x_m - min_x) / max(max_x - min_x, 1e-9) * plot_width
    y_px = pad_top + (max_y - y_m) / max(max_y - min_y, 1e-9) * plot_height
    return x_px, y_px


def _obb_xy_corners(instance: TargetInstance) -> tuple[tuple[float, float], ...]:
    center_x, center_y, _ = instance.obb.center_xyz_m
    size_x, size_y, _ = instance.obb.size_xyz_m
    yaw = instance.obb.orientation_rpy_rad[2]
    cos_yaw = math.cos(yaw)
    sin_yaw = math.sin(yaw)
    corners: list[tuple[float, float]] = []
    for dx, dy in (
        (-size_x / 2.0, -size_y / 2.0),
        (size_x / 2.0, -size_y / 2.0),
        (size_x / 2.0, size_y / 2.0),
        (-size_x / 2.0, size_y / 2.0),
    ):
        corners.append(
            (
                center_x + dx * cos_yaw - dy * sin_yaw,
                center_y + dx * sin_yaw + dy * cos_yaw,
            )
        )
    return tuple(corners)


def _obb_corners_xyz(instance: TargetInstance) -> tuple[tuple[float, float, float], ...]:
    center_x, center_y, center_z = instance.obb.center_xyz_m
    size_x, size_y, size_z = instance.obb.size_xyz_m
    yaw = instance.obb.orientation_rpy_rad[2]
    cos_yaw = math.cos(yaw)
    sin_yaw = math.sin(yaw)
    corners: list[tuple[float, float, float]] = []
    for dx in (-size_x / 2.0, size_x / 2.0):
        for dy in (-size_y / 2.0, size_y / 2.0):
            for dz in (-size_z / 2.0, size_z / 2.0):
                corners.append(
                    (
                        center_x + dx * cos_yaw - dy * sin_yaw,
                        center_y + dx * sin_yaw + dy * cos_yaw,
                        center_z + dz,
                    )
                )
    return tuple(corners)


def _project_target_obb(
    instance: TargetInstance,
    *,
    camera_position_xyz_m: tuple[float, float, float],
    camera_yaw_rad: float,
    horizontal_fov_rad: float,
    vertical_fov_rad: float,
    max_distance_m: float,
    width_px: int,
    height_px: int,
) -> tuple[float, tuple[float, float, float, float]] | None:
    center_x, center_y, center_z = instance.obb.center_xyz_m
    cam_x, cam_y, cam_z = camera_position_xyz_m
    center_distance = math.sqrt(
        (center_x - cam_x) ** 2 + (center_y - cam_y) ** 2 + (center_z - cam_z) ** 2
    )
    if center_distance > max_distance_m:
        return None

    forward_x = math.cos(camera_yaw_rad)
    forward_y = math.sin(camera_yaw_rad)
    right_x = -math.sin(camera_yaw_rad)
    right_y = math.cos(camera_yaw_rad)
    tan_h = math.tan(horizontal_fov_rad / 2.0)
    tan_v = math.tan(vertical_fov_rad / 2.0)
    projected: list[tuple[float, float]] = []
    for x_m, y_m, z_m in _obb_corners_xyz(instance):
        dx = x_m - cam_x
        dy = y_m - cam_y
        dz = z_m - cam_z
        forward = dx * forward_x + dy * forward_y
        if forward <= 0.05:
            continue
        right = dx * right_x + dy * right_y
        u = 0.5 + (right / forward) / (2.0 * tan_h)
        v = 0.5 - (dz / forward) / (2.0 * tan_v)
        projected.append((u * width_px, v * height_px))
    if len(projected) < 2:
        return None
    x0 = min(point[0] for point in projected)
    x1 = max(point[0] for point in projected)
    y0 = min(point[1] for point in projected)
    y1 = max(point[1] for point in projected)
    if x1 < 0.0 or x0 > width_px or y1 < 0.0 or y0 > height_px:
        return None
    return center_distance, (
        max(0.0, x0),
        max(0.0, y0),
        min(float(width_px), x1),
        min(float(height_px), y1),
    )


def _target_color(value: str) -> str:
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
    hue = int(digest[:6], 16) % 360
    return _hsl_to_hex(hue / 360.0, 0.72, 0.58)


def _hsl_to_hex(hue: float, saturation: float, lightness: float) -> str:
    def channel(offset: float) -> int:
        k = (offset + hue * 12.0) % 12.0
        a = saturation * min(lightness, 1.0 - lightness)
        value = lightness - a * max(-1.0, min(k - 3.0, 9.0 - k, 1.0))
        return round(255.0 * value)

    return f"#{channel(0):02x}{channel(8):02x}{channel(4):02x}"


def _read_traversability_npz(
    npz_path: Path,
    metadata: TraversabilityMetadata,
) -> tuple[str, dict[str, np.ndarray]]:
    resolved = Path(npz_path).expanduser().resolve(strict=True)
    checksum = traversability_npz_sha256(resolved)
    if metadata.npz_sha256 is not None and metadata.npz_sha256 != checksum:
        raise GroundTruthError(
            f"traversability checksum mismatch: expected {metadata.npz_sha256}, got {checksum}"
        )

    keys = metadata.arrays
    with np.load(resolved) as data:
        present = set(data.files)
        required = {keys.height, keys.normal, keys.cost, keys.mask, keys.component}
        missing = sorted(required - present)
        if missing:
            raise GroundTruthError(f"traversability NPZ missing arrays: {missing}")
        arrays = {
            "height": np.array(data[keys.height], copy=True),
            "normal": np.array(data[keys.normal], copy=True),
            "cost": np.array(data[keys.cost], copy=True),
            "mask": np.array(data[keys.mask], copy=True),
            "component": np.array(data[keys.component], copy=True),
        }
    _validate_traversability_arrays(arrays, metadata)
    return checksum, arrays


def _validate_traversability_arrays(
    arrays: Mapping[str, np.ndarray],
    metadata: TraversabilityMetadata,
) -> None:
    rows, cols = metadata.shape
    keys = metadata.arrays
    height = arrays["height"]
    normal = arrays["normal"]
    cost = arrays["cost"]
    mask = arrays["mask"]
    component = arrays["component"]
    _require_shape(keys.height, height, (rows, cols))
    _require_shape(keys.normal, normal, (rows, cols, 3))
    _require_shape(keys.cost, cost, (rows, cols))
    _require_shape(keys.mask, mask, (rows, cols))
    _require_shape(keys.component, component, (rows, cols))

    _require_float(keys.height, height)
    _require_float(keys.normal, normal)
    _require_float(keys.cost, cost)
    if mask.dtype.kind not in {"b", "u", "i"}:
        raise GroundTruthError(f"{keys.mask} must be boolean or integer, got {mask.dtype}")
    if component.dtype.kind not in {"u", "i"}:
        raise GroundTruthError(f"{keys.component} must be integer, got {component.dtype}")
    if not np.isin(mask, [0, 1, False, True]).all():
        raise GroundTruthError(f"{keys.mask} must contain only 0/1 values")


def _require_shape(name: str, value: np.ndarray, expected: tuple[int, ...]) -> None:
    if value.shape != expected:
        raise GroundTruthError(f"{name} shape {value.shape} does not match expected {expected}")


def _require_float(name: str, value: np.ndarray) -> None:
    if value.dtype.kind != "f":
        raise GroundTruthError(f"{name} must be floating-point, got {value.dtype}")
    if not np.isfinite(value).all():
        raise GroundTruthError(f"{name} contains non-finite values")


def _legacy_vec3(bbox: Mapping[str, Any], key: str, index: int) -> tuple[float, float, float]:
    value = bbox.get(key)
    if not isinstance(value, list | tuple) or len(value) != 3:
        raise GroundTruthError(f"RayFronts annotation item {index} has invalid {key}")
    return tuple(float(component) for component in value)


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    return slug or "target"


def _validate_confirmation_sampling_config(
    *,
    min_distance_m: float,
    max_distance_m: float,
    radial_step_m: float,
    angle_count: int,
    max_poses_per_target: int,
    proxy_visible_fraction: float,
) -> None:
    if min_distance_m < 0.0:
        raise GroundTruthError("min_distance_m must be non-negative")
    if max_distance_m < min_distance_m:
        raise GroundTruthError("max_distance_m must be >= min_distance_m")
    if radial_step_m <= 0.0:
        raise GroundTruthError("radial_step_m must be positive")
    if angle_count < 4:
        raise GroundTruthError("angle_count must be at least 4")
    if max_poses_per_target <= 0:
        raise GroundTruthError("max_poses_per_target must be positive")
    if not 0.2 <= proxy_visible_fraction <= 1.0:
        raise GroundTruthError("proxy_visible_fraction must be in [0.2, 1.0]")


def _sample_confirmation_poses(
    instance: TargetInstance,
    grid: TraversabilityGrid,
    *,
    min_distance_m: float,
    max_distance_m: float,
    radial_step_m: float,
    angle_count: int,
    max_poses_per_target: int,
    proxy_visible_fraction: float,
) -> list[ConfirmationPose]:
    target_x, target_y, _ = instance.obb.center_xyz_m
    poses: list[ConfirmationPose] = []
    seen_cells: set[tuple[int, int]] = set()
    for radius_m in _radius_samples(min_distance_m, max_distance_m, radial_step_m):
        for angle_index in range(angle_count):
            theta = 2.0 * math.pi * angle_index / angle_count
            cell = grid.cell_for_xy(
                target_x + math.cos(theta) * radius_m,
                target_y + math.sin(theta) * radius_m,
            )
            if cell is None or cell in seen_cells:
                continue
            seen_cells.add(cell)
            traversable = grid.traversable_pose_at_cell(*cell)
            if traversable is None:
                continue
            x_m, y_m, z_m, component = traversable
            distance_to_target_m = math.hypot(x_m - target_x, y_m - target_y)
            if not min_distance_m <= distance_to_target_m <= max_distance_m:
                continue
            poses.append(
                ConfirmationPose(
                    frame="map",
                    position_xyz_m=(x_m, y_m, z_m),
                    yaw_rad=_normalize_angle(math.atan2(target_y - y_m, target_x - x_m)),
                    distance_to_target_m=distance_to_target_m,
                    visible_fraction=proxy_visible_fraction,
                    traversability_component=component,
                )
            )
            if len(poses) >= max_poses_per_target:
                return poses
    return poses


ArrivalDistanceReference = Literal["obb_center", "obb_surface"]


def _obb_surface_distance_2d(x_m: float, y_m: float, obb: OrientedBoundingBox) -> float:
    """Planar distance from ``(x_m, y_m)`` to the OBB box (0.0 when inside)."""

    center_x, center_y, _ = obb.center_xyz_m
    size_x, size_y, _ = obb.size_xyz_m
    yaw = float(obb.orientation_rpy_rad[2]) if obb.orientation_rpy_rad else 0.0
    dx, dy = x_m - center_x, y_m - center_y
    cos_yaw, sin_yaw = math.cos(-yaw), math.sin(-yaw)
    local_x = cos_yaw * dx - sin_yaw * dy
    local_y = sin_yaw * dx + cos_yaw * dy
    outside_x = max(abs(local_x) - float(size_x) / 2.0, 0.0)
    outside_y = max(abs(local_y) - float(size_y) / 2.0, 0.0)
    return math.hypot(outside_x, outside_y)


@dataclass(frozen=True)
class ArrivalRegionBundle:
    """Dense arrival-cell raster plus its per-region index.

    ``region_labels`` uses ``0`` for "not part of any arrival region" and
    ``1..N`` for the reachable regions in manifest order; the mapping lives in
    ``region_index``.
    """

    region_labels: np.ndarray
    region_index: tuple[Mapping[str, Any], ...]
    distance_reference: str
    restrict_components: tuple[int, ...] | None = None

    def summary(self) -> dict[str, Any]:
        return {
            "distance_reference": self.distance_reference,
            "region_count": len(self.region_index),
            "restrict_components": list(self.restrict_components) if self.restrict_components else None,
            "shape": list(self.region_labels.shape),
            "total_cells": int((self.region_labels > 0).sum()),
        }


def build_arrival_regions_from_traversability(
    manifest: TargetAnnotationManifest,
    metadata: TraversabilityMetadata,
    npz_path: Path,
    *,
    min_distance_m: float = 1.5,
    max_distance_m: float = 8.0,
    distance_reference: ArrivalDistanceReference = "obb_surface",
    restrict_components: Sequence[int] | None = None,
    max_poses_per_target: int = 128,
) -> tuple[TargetAnnotationManifest, ArrivalRegionBundle]:
    """Rebuild confirmation/arrival regions as dense traversable cell sets.

    2026-09-24: the legacy ring sampler stopped after 128 poses, which truncated
    the declared ``[1.5, 8.0] m`` window to roughly ``[1.5, 3.5] m`` for every
    target with a large free area, and it measured the window from the OBB
    *centre* (so for a 21x11 m house 85 % of the "ring" fell inside the box).
    This builder enumerates every traversable cell whose distance to the
    instance's OBB *surface* lies in the window, optionally restricted to a set
    of reachable components, and keeps a capped deterministic pose sample for
    diagnostics/runtime goal candidates.
    """

    if manifest.scene_id != metadata.scene_id or manifest.frame != metadata.frame:
        raise GroundTruthError(
            "target annotations and traversability metadata must share scene_id and frame"
        )
    if min_distance_m < 0.0 or max_distance_m <= min_distance_m:
        raise GroundTruthError("arrival window must satisfy 0 <= min < max")
    if max_poses_per_target < 1:
        raise GroundTruthError("max_poses_per_target must be >= 1")
    if distance_reference not in ("obb_center", "obb_surface"):
        raise GroundTruthError(f"unsupported distance_reference {distance_reference!r}")

    grid = load_traversability_grid(npz_path, metadata)
    rows, cols = metadata.shape
    resolution = float(metadata.resolution_m)
    origin = metadata.origin
    allowed_components = (
        {int(value) for value in restrict_components} if restrict_components is not None else None
    )
    region_labels = np.zeros((rows, cols), dtype=np.int32)
    region_index: list[Mapping[str, Any]] = []
    updated_instances: list[TargetInstance] = []
    regions: list[ConfirmationRegion] = []
    height = np.asarray(grid.height, dtype=np.float64)

    for instance in manifest.instances:
        region_id = f"confirm/{instance.instance_id}"
        unbound = instance.usd_prim_path is None or (
            instance.excluded_reason or ""
        ).startswith("no reliable USD prim path")
        cells: list[tuple[int, int, float]] = []
        skipped_by_component = 0
        if not unbound:
            center_x, center_y, _ = instance.obb.center_xyz_m
            half_diagonal = 0.5 * math.hypot(*instance.obb.size_xyz_m[:2])
            window = half_diagonal + max_distance_m + 2.0 * resolution
            row_start = max(0, int(math.floor((center_y - window - origin.y_m) / resolution)))
            row_stop = min(rows, int(math.ceil((center_y + window - origin.y_m) / resolution)) + 1)
            col_start = max(0, int(math.floor((center_x - window - origin.x_m) / resolution)))
            col_stop = min(cols, int(math.ceil((center_x + window - origin.x_m) / resolution)) + 1)
            for row in range(row_start, row_stop):
                for col in range(col_start, col_stop):
                    if not grid.mask[row, col]:
                        continue
                    x_m = origin.x_m + (col + 0.5) * resolution
                    y_m = origin.y_m + (row + 0.5) * resolution
                    if distance_reference == "obb_surface":
                        distance_m = _obb_surface_distance_2d(x_m, y_m, instance.obb)
                    else:
                        distance_m = math.hypot(x_m - center_x, y_m - center_y)
                    if distance_m < min_distance_m or distance_m > max_distance_m:
                        continue
                    component = int(grid.component[row, col])
                    if allowed_components is not None and component not in allowed_components:
                        skipped_by_component += 1
                        continue
                    cells.append((row, col, distance_m))

        if cells:
            label = len(region_index) + 1
            rows_array = np.fromiter((cell[0] for cell in cells), dtype=np.int64, count=len(cells))
            cols_array = np.fromiter((cell[1] for cell in cells), dtype=np.int64, count=len(cells))
            region_labels[rows_array, cols_array] = label
            step = max(1, math.ceil(len(cells) / float(max_poses_per_target)))
            poses = []
            for row, col, distance_m in cells[::step][:max_poses_per_target]:
                x_m = origin.x_m + (col + 0.5) * resolution
                y_m = origin.y_m + (row + 0.5) * resolution
                poses.append(
                    ConfirmationPose(
                        frame="map",
                        position_xyz_m=(x_m, y_m, float(height[row, col])),
                        yaw_rad=_normalize_angle(
                            math.atan2(
                                instance.obb.center_xyz_m[1] - y_m,
                                instance.obb.center_xyz_m[0] - x_m,
                            )
                        ),
                        distance_to_target_m=distance_m,
                        visible_fraction=1.0,
                        traversability_component=int(grid.component[row, col]),
                    )
                )
            region_index.append(
                {
                    "cell_count": len(cells),
                    "components": sorted({int(grid.component[row, col]) for row, col, _ in cells}),
                    "distance_reference": distance_reference,
                    "instance_id": instance.instance_id,
                    "label": label,
                    "region_id": region_id,
                }
            )
            regions.append(
                ConfirmationRegion(
                    region_id=region_id,
                    instance_id=instance.instance_id,
                    reachable=True,
                    poses=tuple(poses),
                    yaw_range_rad=_yaw_range_rad(tuple(poses)),
                    region_label=label,
                    cell_count=len(cells),
                    distance_reference=distance_reference,
                )
            )
            updated_instances.append(
                instance.model_copy(
                    update={
                        "ground_reachable": "reachable",
                        "confirmation_region_id": region_id,
                        "excluded_reason": None,
                    }
                )
            )
            continue

        reason = (
            "outside_selected_reach_region"
            if skipped_by_component > 0
            else "no_arrival_cell_on_traversable_grid"
            if not unbound
            else instance.excluded_reason
        )
        regions.append(
            ConfirmationRegion(
                region_id=region_id,
                instance_id=instance.instance_id,
                reachable=False,
                excluded_reason=reason,
                cell_count=0,
                distance_reference=distance_reference,
            )
        )
        updated_instances.append(
            instance.model_copy(
                update={
                    "ground_reachable": "unreachable",
                    "confirmation_region_id": region_id,
                    "excluded_reason": instance.excluded_reason or reason,
                }
            )
        )

    updated = TargetAnnotationManifest(
        schema_version=manifest.schema_version,
        scene_id=manifest.scene_id,
        frame=manifest.frame,
        source_format=manifest.source_format,
        source_path=manifest.source_path,
        spawn_offset_xyz_m=manifest.spawn_offset_xyz_m,
        instances=tuple(updated_instances),
        confirmation_regions=tuple(regions),
    )
    bundle = ArrivalRegionBundle(
        region_labels=region_labels,
        region_index=tuple(region_index),
        distance_reference=distance_reference,
        restrict_components=tuple(sorted(allowed_components)) if allowed_components else None,
    )
    return updated, bundle


def write_arrival_regions_npz(path: Path, bundle: ArrivalRegionBundle) -> str:
    """Write the deterministic arrival-region raster and return its SHA-256."""

    import io
    import zipfile

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_STORED) as archive:
        array_buffer = io.BytesIO()
        np.lib.format.write_array(
            array_buffer,
            np.asarray(bundle.region_labels, dtype=np.int32),
            allow_pickle=False,
        )
        info = zipfile.ZipInfo("region_labels.npy")
        info.date_time = (1980, 1, 1, 0, 0, 0)
        info.compress_type = zipfile.ZIP_STORED
        info.external_attr = 0o644 << 16
        archive.writestr(info, array_buffer.getvalue())
    payload = buffer.getvalue()
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(payload)
    return hashlib.sha256(payload).hexdigest()


def load_arrival_region_labels(path: Path) -> np.ndarray:
    """Load the arrival-region label raster written by :func:`write_arrival_regions_npz`."""

    with np.load(Path(path)) as data:
        if "region_labels" not in data.files:
            raise GroundTruthError("arrival-region npz must contain 'region_labels'")
        return np.asarray(data["region_labels"], dtype=np.int32)


def _uav_search_samples(
    grid: TraversabilityGrid,
    config: VisibilityOcclusionConfig,
) -> list[tuple[float, float, float]]:
    rows, cols = grid.metadata.shape
    resolution = grid.metadata.resolution_m
    samples: list[tuple[float, float, float]] = []
    for row in range(0, rows, config.sample_stride_cells):
        for col in range(0, cols, config.sample_stride_cells):
            x_m = grid.metadata.origin.x_m + (col + 0.5) * resolution
            y_m = grid.metadata.origin.y_m + (row + 0.5) * resolution
            base_z_m = float(grid.height[row, col])
            for altitude_m in config.uav_altitudes_m:
                samples.append((x_m, y_m, base_z_m + altitude_m))
    return samples


class PoseTargetVisibility(StrictModel):
    """Visibility of one target instance from one observer pose."""

    instance_id: str = Field(pattern=r"^[A-Za-z0-9_.:/-]+$")
    semantic_class: str = Field(min_length=1)
    visible: bool
    visible_point_count: int = Field(ge=0)
    sampled_point_count: int = Field(ge=0)
    min_distance_m: float | None = Field(default=None, ge=0.0)


class PoseVisibilityReport(StrictModel):
    """Deterministic start-pose visibility report for an episode's targets."""

    schema_version: Literal[SCHEMA_VERSION]
    scene_id: str = Field(min_length=1)
    frame: Literal["map"]
    observer_xy_m: tuple[float, float]
    observer_heights_m: tuple[float, ...]
    min_range_m: float = Field(ge=0.0)
    max_range_m: float = Field(gt=0.0)
    ray_step_m: float = Field(gt=0.0)
    all_invisible: bool
    results: tuple[PoseTargetVisibility, ...]


def canonical_pose_visibility_report_json(report: PoseVisibilityReport) -> str:
    """Return deterministic JSON for a pose visibility report."""

    return (
        json.dumps(
            report.model_dump(mode="json"),
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    )


def evaluate_target_visibility_at_pose(
    manifest: TargetAnnotationManifest,
    metadata: TraversabilityMetadata,
    npz_path: Path,
    *,
    observer_xy_m: tuple[float, float],
    observer_heights_m: Sequence[float] = (0.3, 0.45),
    min_range_m: float = 1.0,
    max_range_m: float = 35.0,
    ray_step_m: float = 0.25,
    instance_ids: Sequence[str] | None = None,
) -> PoseVisibilityReport:
    """Check whether an observer at one pose can see each requested target.

    2026-09-24 start-selection gate: a start is only valid when neither the UGV
    camera (0.3 m) nor the docked UAV camera (0.45 m) has line of sight to any
    of the episode's queried targets.  Occlusion reuses the same 2D ray-through-
    non-traversable-cells proxy as ``visibility-occlusion`` so both surfaces stay
    comparable.
    """

    if manifest.scene_id != metadata.scene_id or manifest.frame != metadata.frame:
        raise GroundTruthError(
            "target annotations and traversability metadata must share scene_id and frame"
        )
    if max_range_m <= min_range_m:
        raise GroundTruthError("max_range_m must be greater than min_range_m")
    if ray_step_m <= 0.0:
        raise GroundTruthError("ray_step_m must be positive")
    heights = tuple(float(value) for value in observer_heights_m)
    if not heights:
        raise GroundTruthError("observer_heights_m must not be empty")

    grid = load_traversability_grid(npz_path, metadata)
    wanted = set(instance_ids) if instance_ids is not None else None
    cell = grid.cell_for_xy(float(observer_xy_m[0]), float(observer_xy_m[1]))
    observer_z = float(grid.height[cell]) if cell is not None else 0.0
    results: list[PoseTargetVisibility] = []
    for instance in manifest.instances:
        if wanted is not None and instance.instance_id not in wanted:
            continue
        points = _target_surface_proxy_points(instance)
        visible_points = 0
        min_distance: float | None = None
        for height_m in heights:
            for point in points:
                dx = float(point[0]) - float(observer_xy_m[0])
                dy = float(point[1]) - float(observer_xy_m[1])
                dz = float(point[2]) - (observer_z + float(height_m))
                distance_m = math.sqrt(dx * dx + dy * dy + dz * dz)
                if distance_m < min_range_m or distance_m > max_range_m:
                    continue
                if min_distance is None or distance_m < min_distance:
                    min_distance = distance_m
                if _ray_occluded_by_traversability(
                    grid,
                    start_xy_m=(float(observer_xy_m[0]), float(observer_xy_m[1])),
                    target_xy_m=(float(point[0]), float(point[1])),
                    step_m=ray_step_m,
                ):
                    continue
                visible_points += 1
        results.append(
            PoseTargetVisibility(
                instance_id=instance.instance_id,
                semantic_class=instance.semantic_class,
                visible=visible_points > 0,
                visible_point_count=visible_points,
                sampled_point_count=len(points) * len(heights),
                min_distance_m=min_distance,
            )
        )
    if not results:
        raise GroundTruthError("no target instances selected for pose visibility")
    return PoseVisibilityReport(
        schema_version=manifest.schema_version,
        scene_id=manifest.scene_id,
        frame=manifest.frame,
        observer_xy_m=(float(observer_xy_m[0]), float(observer_xy_m[1])),
        observer_heights_m=heights,
        min_range_m=float(min_range_m),
        max_range_m=float(max_range_m),
        ray_step_m=float(ray_step_m),
        all_invisible=all(not row.visible for row in results),
        results=tuple(results),
    )


def _target_visibility_occlusion_metric(
    instance: TargetInstance,
    grid: TraversabilityGrid,
    samples: tuple[tuple[float, float, float], ...],
    candidate_count: int,
    config: VisibilityOcclusionConfig,
) -> TargetVisibilityOcclusionMetric:
    target_x, target_y, target_z = instance.obb.center_xyz_m
    target_points = _target_surface_proxy_points(instance)
    visible_count = 0
    ray_count = 0
    occluded_count = 0
    fov_half = config.horizontal_fov_rad / 2.0
    for sample_x, sample_y, sample_z in samples:
        dx = target_x - sample_x
        dy = target_y - sample_y
        dz = target_z - sample_z
        distance_m = math.sqrt(dx * dx + dy * dy + dz * dz)
        if distance_m < config.min_range_m or distance_m > config.max_range_m:
            continue
        target_bearing = math.atan2(dy, dx)
        for yaw_index in range(config.yaw_samples):
            yaw_rad = -math.pi + math.tau * yaw_index / config.yaw_samples
            if abs(_normalize_angle(target_bearing - yaw_rad)) > fov_half:
                continue
            visible_count += 1
            for target_point in target_points:
                ray_count += 1
                if _ray_occluded_by_traversability(
                    grid,
                    start_xy_m=(sample_x, sample_y),
                    target_xy_m=(target_point[0], target_point[1]),
                    step_m=config.ray_step_m or grid.metadata.resolution_m / 2.0,
                ):
                    occluded_count += 1
    visibility = visible_count / candidate_count if candidate_count else 0.0
    occlusion = occluded_count / ray_count if ray_count else 1.0
    return TargetVisibilityOcclusionMetric(
        instance_id=instance.instance_id,
        semantic_class=instance.semantic_class,
        visibility=visibility,
        occlusion=occlusion,
        candidate_sample_count=candidate_count,
        visible_sample_count=visible_count,
        ray_count=ray_count,
        occluded_ray_count=occluded_count,
    )


def _confirmation_region_visibility_metric(
    region: ConfirmationRegion,
    instance: TargetInstance,
    grid: TraversabilityGrid,
    config: ConfirmationVisibilityConfig,
) -> ConfirmationRegionVisibilityMetric:
    if not region.reachable:
        return ConfirmationRegionVisibilityMetric(
            region_id=region.region_id,
            instance_id=region.instance_id,
            reachable=False,
            valid=True,
            pose_count=len(region.poses),
            valid_pose_count=0,
            issues=(),
        )

    pose_metrics = tuple(
        _confirmation_pose_visibility_metric(index, pose, instance, grid, config)
        for index, pose in enumerate(region.poses)
    )
    valid_pose_count = sum(1 for metric in pose_metrics if metric.valid)
    issues: list[str] = []
    if not region.poses:
        issues.append("reachable_region_has_no_poses")
    if valid_pose_count == 0:
        issues.append("no_pose_passes_visibility_proxy")
    return ConfirmationRegionVisibilityMetric(
        region_id=region.region_id,
        instance_id=region.instance_id,
        reachable=True,
        valid=valid_pose_count > 0,
        pose_count=len(region.poses),
        valid_pose_count=valid_pose_count,
        issues=tuple(issues),
        poses=pose_metrics,
    )


def _confirmation_pose_visibility_metric(
    pose_index: int,
    pose: ConfirmationPose,
    instance: TargetInstance,
    grid: TraversabilityGrid,
    config: ConfirmationVisibilityConfig,
) -> ConfirmationPoseVisibilityMetric:
    pose_x, pose_y, _ = pose.position_xyz_m
    target_x, target_y, _ = instance.obb.center_xyz_m
    distance_m = math.hypot(target_x - pose_x, target_y - pose_y)
    in_range = config.min_distance_m <= distance_m <= config.max_distance_m
    target_bearing = math.atan2(target_y - pose_y, target_x - pose_x)
    yaw_error = abs(_normalize_angle(target_bearing - pose.yaw_rad))
    in_fov = yaw_error <= config.horizontal_fov_rad / 2.0

    ray_count = 0
    occluded_count = 0
    for target_point in _target_surface_proxy_points(instance):
        ray_count += 1
        if _ray_occluded_by_traversability(
            grid,
            start_xy_m=(pose_x, pose_y),
            target_xy_m=(target_point[0], target_point[1]),
            step_m=config.ray_step_m or grid.metadata.resolution_m / 2.0,
        ):
            occluded_count += 1
    ray_visible_fraction = (ray_count - occluded_count) / ray_count if ray_count else 0.0
    effective_visible_fraction = min(pose.visible_fraction, ray_visible_fraction)
    visible_enough = effective_visible_fraction >= config.min_visible_fraction
    valid = in_range and in_fov and visible_enough
    return ConfirmationPoseVisibilityMetric(
        pose_index=pose_index,
        valid=valid,
        in_range=in_range,
        in_fov=in_fov,
        yaw_error_rad=yaw_error,
        stored_visible_fraction=pose.visible_fraction,
        ray_visible_fraction=ray_visible_fraction,
        effective_visible_fraction=effective_visible_fraction,
        ray_count=ray_count,
        occluded_ray_count=occluded_count,
        consecutive_visible_frames=config.required_consecutive_frames if valid else 0,
    )


def _raycast_confirmation_region_metric(
    region: ConfirmationRegion,
    instance: TargetInstance,
    raycast: RaycastFn,
    config: RaycastConfirmationVisibilityConfig,
) -> RaycastConfirmationRegionMetric:
    if not region.reachable:
        return RaycastConfirmationRegionMetric(
            region_id=region.region_id,
            instance_id=region.instance_id,
            reachable=False,
            valid=True,
            pose_count=len(region.poses),
            valid_pose_count=0,
            issues=(),
        )

    pose_metrics = tuple(
        _raycast_confirmation_pose_metric(index, pose, instance, raycast, config)
        for index, pose in enumerate(region.poses)
    )
    valid_pose_count = sum(1 for metric in pose_metrics if metric.valid)
    issues: list[str] = []
    if not region.poses:
        issues.append("reachable_region_has_no_poses")
    if valid_pose_count == 0:
        issues.append("no_pose_passes_raycast_visibility")
    return RaycastConfirmationRegionMetric(
        region_id=region.region_id,
        instance_id=region.instance_id,
        reachable=True,
        valid=valid_pose_count > 0,
        pose_count=len(region.poses),
        valid_pose_count=valid_pose_count,
        pose_metrics=pose_metrics,
        issues=tuple(issues),
    )


def _raycast_confirmation_pose_metric(
    pose_index: int,
    pose: ConfirmationPose,
    instance: TargetInstance,
    raycast: RaycastFn,
    config: RaycastConfirmationVisibilityConfig,
) -> RaycastConfirmationPoseMetric:
    pose_x, pose_y, pose_z = pose.position_xyz_m
    target_x, target_y, _target_z = instance.obb.center_xyz_m
    distance_m = math.hypot(target_x - pose_x, target_y - pose_y)
    issues: list[str] = []
    if not config.min_distance_m <= distance_m <= config.max_distance_m:
        issues.append("distance_out_of_range")
    target_bearing = math.atan2(target_y - pose_y, target_x - pose_x)
    yaw_error = abs(_normalize_angle(target_bearing - pose.yaw_rad))
    if yaw_error > config.horizontal_fov_rad / 2.0:
        issues.append("outside_horizontal_fov")

    origin = RadioPose(pose_x, pose_y, pose_z + config.camera_height_m)
    clear_ray_count = 0
    blocked_ray_count = 0
    blocking_paths: set[str] = set()
    target_points = _target_surface_raycast_points(instance, config.target_sample_count)
    for target_point in target_points:
        endpoint = RadioPose(*target_point)
        target_distance_m = origin.distance_to(endpoint)
        blocked, path = _raycast_segment_blocked(
            raycast,
            origin,
            endpoint,
            target_distance_m=target_distance_m,
            target_prim_path=instance.usd_prim_path,
            ignored_prim_prefixes=config.ignored_prim_prefixes,
            occlusion_epsilon_m=config.occlusion_epsilon_m,
        )
        if blocked:
            blocked_ray_count += 1
            if path:
                blocking_paths.add(path)
        else:
            clear_ray_count += 1

    ray_count = clear_ray_count + blocked_ray_count
    visible_fraction = clear_ray_count / ray_count if ray_count else 0.0
    if visible_fraction < config.min_visible_fraction:
        issues.append("visible_fraction_below_threshold")
    valid = not issues
    return RaycastConfirmationPoseMetric(
        pose_index=pose_index,
        valid=valid,
        distance_to_target_m=distance_m,
        yaw_error_rad=yaw_error,
        ray_count=ray_count,
        clear_ray_count=clear_ray_count,
        blocked_ray_count=blocked_ray_count,
        visible_fraction=visible_fraction,
        consecutive_visible_frames=config.required_consecutive_frames if valid else 0,
        blocking_prim_paths=tuple(sorted(blocking_paths)),
        issues=tuple(issues),
    )


def _sensor_frame_confirmation_region_metric(
    region: ConfirmationRegion,
    instance: TargetInstance,
    frames: Sequence[SensorFrameConfirmationVisibilityTraceFrame],
    config: SensorFrameConfirmationVisibilityConfig,
) -> SensorFrameConfirmationRegionTraceMetric:
    if not region.reachable:
        issues = ("unreachable_region_has_sensor_frames",) if frames else ()
        return SensorFrameConfirmationRegionTraceMetric(
            region_id=region.region_id,
            instance_id=region.instance_id,
            reachable=False,
            valid=not issues,
            pose_count=len(region.poses),
            traced_pose_count=len({frame.pose_index for frame in frames}),
            valid_pose_count=0,
            frame_count=len(frames),
            valid_frame_count=0,
            issues=issues,
        )

    frames_by_pose: dict[int, list[SensorFrameConfirmationVisibilityTraceFrame]] = {}
    for frame in frames:
        frames_by_pose.setdefault(frame.pose_index, []).append(frame)
    pose_metrics = tuple(
        _sensor_frame_confirmation_pose_metric(
            pose_index,
            tuple(frames_by_pose[pose_index]),
            expected_instance_id=region.instance_id,
            expected_pose_count=len(region.poses),
            config=config,
        )
        for pose_index in sorted(frames_by_pose)
    )
    valid_pose_count = sum(1 for metric in pose_metrics if metric.valid)
    issues: list[str] = []
    if not region.poses:
        issues.append("reachable_region_has_no_manifest_poses")
    if not frames:
        issues.append("missing_sensor_frames")
    if valid_pose_count == 0:
        issues.append("no_pose_has_required_consecutive_visible_frames")
    return SensorFrameConfirmationRegionTraceMetric(
        region_id=region.region_id,
        instance_id=region.instance_id,
        reachable=True,
        valid=valid_pose_count > 0,
        pose_count=len(region.poses),
        traced_pose_count=len(pose_metrics),
        valid_pose_count=valid_pose_count,
        frame_count=sum(metric.frame_count for metric in pose_metrics),
        valid_frame_count=sum(metric.valid_frame_count for metric in pose_metrics),
        pose_metrics=pose_metrics,
        issues=tuple(issues),
    )


def _sensor_frame_confirmation_pose_metric(
    pose_index: int,
    frames: Sequence[SensorFrameConfirmationVisibilityTraceFrame],
    *,
    expected_instance_id: str,
    expected_pose_count: int,
    config: SensorFrameConfirmationVisibilityConfig,
) -> SensorFrameConfirmationPoseTraceMetric:
    sorted_frames = tuple(sorted(frames, key=lambda frame: frame.sim_time_s))
    issues: set[str] = set()
    if pose_index >= expected_pose_count:
        issues.add("unknown_pose_index")
    if any(frame.instance_id != expected_instance_id for frame in sorted_frames):
        issues.add("instance_id_mismatch")

    valid_frame_count = 0
    max_consecutive = 0
    current_consecutive = 0
    previous_valid_time_s: float | None = None
    first_valid_time_s: float | None = None
    last_valid_time_s: float | None = None
    total_ray_count = 0
    total_clear_ray_count = 0
    total_blocked_ray_count = 0
    blocking_paths: set[str] = set()
    distances: list[float] = []
    yaw_errors: list[float] = []
    visible_fractions: list[float] = []
    invalid_reasons: set[str] = set()

    for frame in sorted_frames:
        distances.append(frame.distance_to_target_m)
        yaw_errors.append(frame.yaw_error_rad)
        visible_fractions.append(frame.visible_fraction)
        total_ray_count += frame.ray_count
        total_clear_ray_count += frame.clear_ray_count
        total_blocked_ray_count += frame.blocked_ray_count
        blocking_paths.update(frame.blocking_prim_paths)
        frame_valid, frame_reasons = _sensor_frame_confirmation_frame_is_valid(frame, config)
        invalid_reasons.update(frame_reasons)
        if frame_valid:
            valid_frame_count += 1
            if previous_valid_time_s is None:
                current_consecutive = 1
                first_valid_time_s = frame.sim_time_s if first_valid_time_s is None else first_valid_time_s
            elif frame.sim_time_s - previous_valid_time_s <= config.max_frame_gap_s:
                current_consecutive += 1
            else:
                current_consecutive = 1
            previous_valid_time_s = frame.sim_time_s
            last_valid_time_s = frame.sim_time_s
            max_consecutive = max(max_consecutive, current_consecutive)

    valid = (
        bool(sorted_frames)
        and not ({"unknown_pose_index", "instance_id_mismatch"} & issues)
        and max_consecutive >= config.required_consecutive_frames
    )
    if not sorted_frames:
        issues.add("no_sensor_frames")
    if sorted_frames and valid_frame_count == 0:
        issues.update(sorted(invalid_reasons))
    elif sorted_frames and max_consecutive < config.required_consecutive_frames:
        issues.add("insufficient_consecutive_visible_frames")
    if valid:
        issues.clear()

    return SensorFrameConfirmationPoseTraceMetric(
        pose_index=pose_index,
        valid=valid,
        frame_count=len(sorted_frames),
        valid_frame_count=valid_frame_count,
        max_consecutive_visible_frames=max_consecutive,
        first_valid_time_s=first_valid_time_s,
        last_valid_time_s=last_valid_time_s,
        min_distance_to_target_m=min(distances) if distances else None,
        max_distance_to_target_m=max(distances) if distances else None,
        max_yaw_error_rad=max(yaw_errors) if yaw_errors else None,
        min_visible_fraction=min(visible_fractions) if visible_fractions else None,
        ray_count=total_ray_count,
        clear_ray_count=total_clear_ray_count,
        blocked_ray_count=total_blocked_ray_count,
        blocking_prim_paths=tuple(sorted(blocking_paths)),
        issues=tuple(sorted(issues)),
    )


def _sensor_frame_confirmation_frame_is_valid(
    frame: SensorFrameConfirmationVisibilityTraceFrame,
    config: SensorFrameConfirmationVisibilityConfig,
) -> tuple[bool, tuple[str, ...]]:
    issues: list[str] = []
    if not config.min_distance_m <= frame.distance_to_target_m <= config.max_distance_m:
        issues.append("distance_out_of_range")
    if frame.yaw_error_rad > config.horizontal_fov_rad / 2.0:
        issues.append("outside_horizontal_fov")
    if frame.visible_fraction < config.min_visible_fraction:
        issues.append("visible_fraction_below_threshold")
    if config.require_raycast_evidence and frame.ray_count <= 0:
        issues.append("missing_raycast_evidence")
    if frame.ray_count > 0 and frame.clear_ray_count <= 0:
        issues.append("no_clear_raycast_samples")
    return (not issues, tuple(issues))


def _raycast_segment_blocked(
    raycast: RaycastFn,
    origin: RadioPose,
    endpoint: RadioPose,
    *,
    target_distance_m: float,
    target_prim_path: str | None,
    ignored_prim_prefixes: Sequence[str],
    occlusion_epsilon_m: float,
) -> tuple[bool, str | None]:
    ignored_prefixes = (
        *ignored_prim_prefixes,
        *((target_prim_path,) if target_prim_path else ()),
    )
    for hit in raycast(origin, endpoint):
        prim_path = hit.prim_path
        if prim_path is not None and _prim_path_is_ignored(prim_path, ignored_prefixes):
            continue
        if hit.distance_m < target_distance_m - occlusion_epsilon_m:
            return True, prim_path
    return False, None


def _prim_path_is_ignored(prim_path: str, prefixes: Sequence[str]) -> bool:
    return any(prim_path == prefix or prim_path.startswith(f"{prefix}/") for prefix in prefixes)


def _target_surface_raycast_points(
    instance: TargetInstance,
    target_sample_count: Literal[1, 5, 9],
) -> tuple[tuple[float, float, float], ...]:
    if target_sample_count == 1:
        return (instance.obb.center_xyz_m,)
    if target_sample_count == 5:
        return _target_surface_proxy_points(instance)
    return (instance.obb.center_xyz_m, *_obb_corners_xyz(instance))


def _target_surface_proxy_points(instance: TargetInstance) -> tuple[tuple[float, float, float], ...]:
    center_x, center_y, center_z = instance.obb.center_xyz_m
    size_x, size_y, _ = instance.obb.size_xyz_m
    yaw = instance.obb.orientation_rpy_rad[2]
    offsets = (
        (0.0, 0.0),
        (size_x / 2.0, 0.0),
        (-size_x / 2.0, 0.0),
        (0.0, size_y / 2.0),
        (0.0, -size_y / 2.0),
    )
    cos_yaw = math.cos(yaw)
    sin_yaw = math.sin(yaw)
    points = []
    for local_x, local_y in offsets:
        world_x = center_x + local_x * cos_yaw - local_y * sin_yaw
        world_y = center_y + local_x * sin_yaw + local_y * cos_yaw
        points.append((world_x, world_y, center_z))
    return tuple(points)


def _ray_occluded_by_traversability(
    grid: TraversabilityGrid,
    *,
    start_xy_m: tuple[float, float],
    target_xy_m: tuple[float, float],
    step_m: float,
) -> bool:
    distance_m = math.hypot(target_xy_m[0] - start_xy_m[0], target_xy_m[1] - start_xy_m[1])
    if distance_m <= 1e-9:
        return False
    step_count = max(1, math.ceil(distance_m / step_m))
    start_cell = grid.cell_for_xy(*start_xy_m)
    target_cell = grid.cell_for_xy(*target_xy_m)
    for step_index in range(1, step_count):
        fraction = step_index / step_count
        x_m = start_xy_m[0] + (target_xy_m[0] - start_xy_m[0]) * fraction
        y_m = start_xy_m[1] + (target_xy_m[1] - start_xy_m[1]) * fraction
        cell = grid.cell_for_xy(x_m, y_m)
        if cell is None:
            return True
        if cell == start_cell or cell == target_cell:
            continue
        if not bool(grid.mask[cell]):
            return True
    return False


def _radius_samples(
    min_distance_m: float,
    max_distance_m: float,
    radial_step_m: float,
) -> list[float]:
    radii: list[float] = []
    radius_m = min_distance_m
    while radius_m <= max_distance_m + 1e-9:
        radii.append(radius_m)
        radius_m += radial_step_m
    return radii


def _yaw_range_rad(poses: tuple[ConfirmationPose, ...]) -> tuple[float, float]:
    yaws = [pose.yaw_rad for pose in poses]
    return min(yaws), max(yaws)


def _normalize_angle(angle_rad: float) -> float:
    return (angle_rad + math.pi) % (2.0 * math.pi) - math.pi
