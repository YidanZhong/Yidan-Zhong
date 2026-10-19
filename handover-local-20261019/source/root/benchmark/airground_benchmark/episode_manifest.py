"""Versioned episode manifest schema and validation helpers."""

from __future__ import annotations

from airground_benchmark.scenes import SceneCatalogId, validate_scene_catalog, SceneId

from collections import Counter
from collections.abc import Mapping
import hashlib
from importlib import resources
import json
import math
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
import yaml

from airground_benchmark.config.schema import SCHEMA_VERSION


class EpisodeManifestError(ValueError):
    """Raised when an episode manifest is structurally invalid."""


class StrictModel(BaseModel):
    """Base class that rejects undeclared manifest fields."""

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)


TaskType = Literal["single_target", "unordered_multi_target", "sequential_target"]
DifficultyLabel = Literal["easy", "medium", "hard"]
ManifestSplit = Literal["public", "hidden_test"]
ReleaseChannel = Literal["public", "private"]


class Pose2D(StrictModel):
    """Planar pose in the public map frame."""

    frame: Literal["map"]
    x_m: float
    y_m: float
    yaw_rad: float


class RelativePose3D(StrictModel):
    """Pose relative to another frame, used for docked UAV placement."""

    parent_frame: Literal["ugv/base_link", "ugv/platform"]
    x_m: float
    y_m: float
    z_m: float
    roll_rad: float = 0.0
    pitch_rad: float = 0.0
    yaw_rad: float = 0.0


class StartPair(StrictModel):
    """Coupled start state for UGV and docked UAV takeoff."""

    ugv: Pose2D
    uav_on_platform: RelativePose3D
    docked: Literal[True]


class GroundTruthRef(StrictModel):
    """Stable references to evaluator-only ground-truth artifacts."""

    traversability: str = Field(min_length=1)
    targets: str = Field(min_length=1)
    confirmation_regions: str = Field(min_length=1)
    checksum_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class EpisodeTarget(StrictModel):
    """One semantic target instance required by an episode."""

    query_id: str = Field(pattern=r"^[A-Za-z0-9_.-]+$")
    semantic_class: str = Field(min_length=1)
    instance_id: str = Field(pattern=r"^[A-Za-z0-9_.:/-]+$")
    confirmation_region_id: str = Field(pattern=r"^[A-Za-z0-9_.:/-]+$")
    sequence_index: int | None = Field(default=None, ge=0)


class DifficultyAxes(StrictModel):
    """Difficulty labels and raw values used for balanced sampling."""

    visibility_label: DifficultyLabel
    occlusion_label: DifficultyLabel
    detour_label: DifficultyLabel
    visibility: float = Field(ge=0.0, le=1.0)
    occlusion: float = Field(ge=0.0, le=1.0)
    detour: float = Field(ge=1.0)


class EpisodeSpec(StrictModel):
    """A single benchmark episode in a fixed public or hidden split."""

    episode_id: str = Field(pattern=r"^[A-Za-z0-9_.-]+$")
    seed: int = Field(ge=0)
    split: ManifestSplit
    release_channel: ReleaseChannel
    difficulty_version: str = Field(pattern=r"^[A-Za-z0-9_.-]+$")
    scene_id: SceneId
    task_type: TaskType
    query: str = Field(min_length=1)
    timeout_s: int = Field(ge=300, le=1200)
    starts: StartPair
    targets: tuple[EpisodeTarget, ...] = Field(min_length=1, max_length=3)
    difficulty: DifficultyAxes
    ground_truth: GroundTruthRef

    @model_validator(mode="after")
    def validate_task_contract(self) -> "EpisodeSpec":
        expected_channel: ReleaseChannel = (
            "public" if self.split == "public" else "private"
        )
        if self.release_channel != expected_channel:
            raise ValueError(
                f"{self.split} episodes must use release_channel={expected_channel!r}"
            )

        target_count = len(self.targets)
        if self.task_type == "single_target" and target_count != 1:
            raise ValueError("single_target episodes must contain exactly one target")
        if self.task_type in {"unordered_multi_target", "sequential_target"}:
            if not 2 <= target_count <= 3:
                raise ValueError(f"{self.task_type} episodes must contain 2-3 targets")

        query_ids = [target.query_id for target in self.targets]
        if len(set(query_ids)) != len(query_ids):
            raise ValueError("target query_id values must be unique within an episode")

        instance_ids = [target.instance_id for target in self.targets]
        if len(set(instance_ids)) != len(instance_ids):
            raise ValueError("target instance_id values must be unique within an episode")

        region_ids = [target.confirmation_region_id for target in self.targets]
        if len(set(region_ids)) != len(region_ids):
            raise ValueError("confirmation_region_id values must be unique within an episode")

        sequence = [target.sequence_index for target in self.targets]
        if self.task_type == "sequential_target":
            expected = tuple(range(target_count))
            if tuple(sequence) != expected:
                raise ValueError("sequential_target sequence_index must be 0..N-1 in target order")
        elif any(index is not None for index in sequence):
            raise ValueError("sequence_index is only valid for sequential_target episodes")
        return self


class ExpectedCounts(StrictModel):
    """Expected benchmark task counts for one split.

    2026-10-05: the fields are plain non-negative integers instead of the fixed
    60/30/15/15 literals so a *draft* protocol manifest can declare its own
    shape honestly -- the upstream-paper single-scene evaluation set is the 10
    Table A.3 tasks x 3 starting poses = 30 episodes.  The release contract is
    unchanged and stays enforced where it belongs: generated ``released``
    manifests must total 60 (``episode_generation``) and the release audit
    re-checks 30/15/15 (``release_checklist``).
    """

    total: int = Field(ge=1)
    single_target: int = Field(ge=0)
    unordered_multi_target: int = Field(ge=0)
    sequential_target: int = Field(ge=0)

    @model_validator(mode="after")
    def _parts_sum_to_total(self) -> "ExpectedCounts":
        if (
            self.single_target + self.unordered_multi_target + self.sequential_target
            != self.total
        ):
            raise ValueError("expected_counts parts must sum to total")
        return self


class EpisodeManifest(StrictModel):
    """Episode manifest with draft/released validation modes."""

    schema_version: Literal[SCHEMA_VERSION]
    catalog_id: SceneCatalogId
    scene_id: SceneId
    split: ManifestSplit
    release_channel: ReleaseChannel
    difficulty_version: str = Field(pattern=r"^[A-Za-z0-9_.-]+$")
    public: bool
    zero_shot: Literal[True]
    status: Literal["draft", "released"]
    expected_counts: ExpectedCounts
    episodes: tuple[EpisodeSpec, ...] = Field(default_factory=tuple)

    @model_validator(mode="after")
    def validate_catalog_contract(self) -> "EpisodeManifest":
        validate_scene_catalog(self.scene_id, self.catalog_id)
        expected_public = self.split == "public"
        if self.public != expected_public:
            raise ValueError(
                f"manifest public flag must be {expected_public} for split={self.split!r}"
            )

        expected_channel: ReleaseChannel = (
            "public" if self.split == "public" else "private"
        )
        if self.release_channel != expected_channel:
            raise ValueError(
                f"manifest split={self.split!r} must use release_channel={expected_channel!r}"
            )

        episode_ids = [episode.episode_id for episode in self.episodes]
        if len(set(episode_ids)) != len(episode_ids):
            raise ValueError("episode_id values must be unique")

        seeds = [episode.seed for episode in self.episodes]
        if len(set(seeds)) != len(seeds):
            raise ValueError("episode seeds must be unique")

        wrong_scene = [
            episode.episode_id
            for episode in self.episodes
            if episode.scene_id != self.scene_id
        ]
        if wrong_scene:
            raise ValueError(f"episodes reference a different scene: {wrong_scene}")

        wrong_split = [
            episode.episode_id
            for episode in self.episodes
            if episode.split != self.split
        ]
        if wrong_split:
            raise ValueError(f"episodes reference a different split: {wrong_split}")

        wrong_release_channel = [
            episode.episode_id
            for episode in self.episodes
            if episode.release_channel != self.release_channel
        ]
        if wrong_release_channel:
            raise ValueError(
                f"episodes reference a different release_channel: {wrong_release_channel}"
            )

        wrong_difficulty_version = [
            episode.episode_id
            for episode in self.episodes
            if episode.difficulty_version != self.difficulty_version
        ]
        if wrong_difficulty_version:
            raise ValueError(
                f"episodes reference a different difficulty_version: {wrong_difficulty_version}"
            )

        if len(self.episodes) > self.expected_counts.total:
            raise ValueError("manifest contains more episodes than the expected total")

        counts = Counter(episode.task_type for episode in self.episodes)
        if counts["single_target"] > self.expected_counts.single_target:
            raise ValueError("too many single_target episodes")
        if counts["unordered_multi_target"] > self.expected_counts.unordered_multi_target:
            raise ValueError("too many unordered_multi_target episodes")
        if counts["sequential_target"] > self.expected_counts.sequential_target:
            raise ValueError("too many sequential_target episodes")

        if self.status == "released":
            if len(self.episodes) != self.expected_counts.total:
                raise ValueError("released manifest must contain exactly 60 episodes")
            expected = {
                "single_target": self.expected_counts.single_target,
                "unordered_multi_target": self.expected_counts.unordered_multi_target,
                "sequential_target": self.expected_counts.sequential_target,
            }
            for task_type, expected_count in expected.items():
                if counts[task_type] != expected_count:
                    raise ValueError(
                        f"released manifest has {counts[task_type]} {task_type} "
                        f"episodes; expected {expected_count}"
                    )
        return self

    @property
    def task_counts(self) -> dict[str, int]:
        """Return deterministic counts by task type."""
        counts = Counter(episode.task_type for episode in self.episodes)
        return {
            "single_target": counts["single_target"],
            "unordered_multi_target": counts["unordered_multi_target"],
            "sequential_target": counts["sequential_target"],
        }


def _read_yaml(text: str, source: str) -> dict[str, Any]:
    value = yaml.safe_load(text)
    if not isinstance(value, Mapping):
        raise EpisodeManifestError(f"episode manifest {source} must be a YAML mapping")
    manifest = dict(value)
    version = manifest.get("schema_version")
    if version != SCHEMA_VERSION:
        raise EpisodeManifestError(
            f"episode manifest {source} has schema_version={version!r}; "
            f"expected {SCHEMA_VERSION!r}"
        )
    return manifest


def _default_manifest_layer() -> dict[str, Any]:
    resource = resources.files("airground_benchmark").joinpath(
        "episode_manifests/benchmark-v1.0-retro.yaml"
    )
    return _read_yaml(resource.read_text(encoding="utf-8"), str(resource))


def load_episode_manifest(path: Path | None = None) -> EpisodeManifest:
    """Load and validate an episode manifest YAML file."""
    if path is None:
        return EpisodeManifest.model_validate(_default_manifest_layer())
    resolved = Path(path).expanduser().resolve(strict=True)
    return EpisodeManifest.model_validate(
        _read_yaml(resolved.read_text(encoding="utf-8"), str(resolved))
    )


def canonical_episode_manifest_json(manifest: EpisodeManifest) -> str:
    """Serialize a manifest into checksum-stable JSON."""
    return (
        json.dumps(
            manifest.model_dump(mode="json"),
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    )


def canonical_episode_schema_json() -> str:
    """Serialize the episode manifest JSON schema deterministically."""
    return (
        json.dumps(
            EpisodeManifest.model_json_schema(),
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    )


def episode_manifest_sha256(manifest: EpisodeManifest) -> str:
    """Return the SHA-256 of the canonical manifest JSON."""
    return hashlib.sha256(
        canonical_episode_manifest_json(manifest).encode("utf-8")
    ).hexdigest()


def salted_episode_manifest_sha256(manifest: EpisodeManifest, salt: bytes | str) -> str:
    """Return a salted SHA-256 commitment for a non-public manifest.

    The salt is intentionally not returned by metadata helpers. Release notes can
    publish this commitment without exposing hidden episode seeds, starts, target
    ids, ordering, or oracle traces.
    """
    salt_bytes = salt.encode("utf-8") if isinstance(salt, str) else bytes(salt)
    if not salt_bytes:
        raise EpisodeManifestError("manifest checksum salt must be non-empty")
    digest = hashlib.sha256()
    digest.update(b"raven-airground-manifest-v1\0")
    digest.update(salt_bytes)
    digest.update(b"\0")
    digest.update(canonical_episode_manifest_json(manifest).encode("utf-8"))
    return digest.hexdigest()


def hidden_release_metadata(manifest: EpisodeManifest, salt: bytes | str) -> dict[str, Any]:
    """Build the publishable metadata surface for a hidden-test manifest.

    The returned structure deliberately excludes episode ids, seeds, starts,
    target references, target order, queries, timeouts, and oracle data. It is
    limited to split metadata, task counts, difficulty distributions, evaluator
    GT checksums, and a salted manifest commitment.
    """
    if manifest.split != "hidden_test":
        raise EpisodeManifestError("hidden release metadata requires split='hidden_test'")
    if manifest.public:
        raise EpisodeManifestError("hidden release metadata requires public=false")
    if manifest.release_channel != "private":
        raise EpisodeManifestError(
            "hidden release metadata requires release_channel='private'"
        )

    difficulty_distribution = {
        "visibility": _difficulty_counts(
            episode.difficulty.visibility_label for episode in manifest.episodes
        ),
        "occlusion": _difficulty_counts(
            episode.difficulty.occlusion_label for episode in manifest.episodes
        ),
        "detour": _difficulty_counts(
            episode.difficulty.detour_label for episode in manifest.episodes
        ),
    }
    ground_truth_checksums = sorted(
        {episode.ground_truth.checksum_sha256 for episode in manifest.episodes}
    )
    return {
        "schema_version": manifest.schema_version,
        "catalog_id": manifest.catalog_id,
        "scene_id": manifest.scene_id,
        "split": manifest.split,
        "release_channel": manifest.release_channel,
        "public": manifest.public,
        "zero_shot": manifest.zero_shot,
        "status": manifest.status,
        "difficulty_version": manifest.difficulty_version,
        "episode_count": len(manifest.episodes),
        "expected_counts": manifest.expected_counts.model_dump(mode="json"),
        "task_counts": manifest.task_counts,
        "difficulty_distribution": difficulty_distribution,
        "ground_truth_checksum_count": len(ground_truth_checksums),
        "ground_truth_checksums_sha256": ground_truth_checksums,
        "salted_manifest_sha256": salted_episode_manifest_sha256(manifest, salt),
        "salted_checksum_algorithm": (
            "sha256('raven-airground-manifest-v1\\0' || salt || "
            "'\\0' || canonical_manifest_json)"
        ),
        "redaction_policy": {
            "episode_ids": "redacted",
            "seeds": "redacted",
            "starts": "redacted",
            "targets": "redacted",
            "target_order": "redacted",
            "queries": "redacted",
            "timeouts": "redacted",
            "oracle_traces": "redacted",
        },
    }


def _difficulty_counts(labels: object) -> dict[str, int]:
    counts = Counter(labels)
    return {
        "easy": counts["easy"],
        "medium": counts["medium"],
        "hard": counts["hard"],
    }


def timeout_from_oracle_time_s(oracle_time_s: float) -> int:
    """Derive a benchmark timeout from oracle completion time.

    The public rule is ``clip(ceil(4 * oracle_time_s), 300, 1200)`` seconds.
    Ceil keeps the integer timeout from falling below the four-times-oracle
    lower bound when oracle time has fractional seconds.
    """
    if not math.isfinite(oracle_time_s) or oracle_time_s <= 0.0:
        raise EpisodeManifestError("oracle_time_s must be a finite positive number")
    return min(1200, max(300, int(math.ceil(4.0 * oracle_time_s))))


def apply_oracle_timeouts(
    manifest: EpisodeManifest,
    oracle_times_s: Mapping[str, float],
) -> EpisodeManifest:
    """Return a manifest with timeout_s derived from oracle episode times."""
    expected_ids = {episode.episode_id for episode in manifest.episodes}
    provided_ids = set(oracle_times_s)
    missing = sorted(expected_ids - provided_ids)
    unknown = sorted(provided_ids - expected_ids)
    if missing:
        raise EpisodeManifestError(f"missing oracle times for episodes: {missing}")
    if unknown:
        raise EpisodeManifestError(f"oracle times reference unknown episodes: {unknown}")

    updated = manifest.model_dump(mode="json")
    episodes = updated["episodes"]
    if not isinstance(episodes, list):
        raise EpisodeManifestError("manifest episodes must serialize to a list")
    for episode in episodes:
        episode_id = episode["episode_id"]
        episode["timeout_s"] = timeout_from_oracle_time_s(
            float(oracle_times_s[episode_id])
        )
    return EpisodeManifest.model_validate(updated)
