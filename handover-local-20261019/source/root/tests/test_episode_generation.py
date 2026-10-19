"""Episode candidate sampling tests."""

from __future__ import annotations

from collections import Counter

import numpy as np
import pytest

from airground_benchmark.episode_generation import (
    CandidatePool,
    CandidatePoolBuildConfig,
    CandidateOracleEvidenceRecord,
    DifficultyMetadata,
    EpisodeGenerationError,
    attach_oracle_evidence_to_candidate_pool,
    audit_candidate_pool,
    audit_difficulty_metadata,
    build_candidate_pool_from_artifacts,
    build_manifest_from_candidates,
    build_release_pair_from_candidates,
    canonical_candidate_oracle_evidence_json,
    canonical_candidate_pool_audit_json,
    canonical_candidate_pool_json,
    canonical_difficulty_metadata_audit_json,
    canonical_difficulty_metadata_json,
    canonical_release_pair_report_json,
    difficulty_metadata_from_candidates,
    estimate_candidate_grid_oracle_evidence,
    PairedStartConfig,
    PairedStartCandidate,
    build_paired_start_candidates,
    validate_candidate_labels_against_metadata,
)
from airground_benchmark.episode_manifest import canonical_episode_manifest_json
from airground_benchmark.ground_truth import (
    ConfirmationPose,
    ConfirmationRegion,
    TargetAnnotationManifest,
    TraversabilityGrid,
    TraversabilityMetadata,
    VisibilityOcclusionReport,
)


GT_CHECKSUM = "2" * 64
LABELS = ("easy", "medium", "hard")


def test_balanced_sampler_builds_public_and_hidden_manifests_without_reuse() -> None:
    pool = CandidatePool.model_validate(_candidate_pool())

    public_manifest = build_manifest_from_candidates(
        pool,
        split="public",
        seed_base=1_000_000,
    )
    hidden_manifest = build_manifest_from_candidates(
        pool,
        split="hidden_test",
        exclude_manifests=(public_manifest,),
        seed_base=2_000_000,
    )
    repeated_public = build_manifest_from_candidates(
        pool,
        split="public",
        seed_base=1_000_000,
    )

    assert canonical_episode_manifest_json(public_manifest) == canonical_episode_manifest_json(
        repeated_public
    )
    assert public_manifest.status == "released"
    assert public_manifest.split == "public"
    assert public_manifest.release_channel == "public"
    assert public_manifest.public is True
    assert public_manifest.task_counts == {
        "single_target": 30,
        "unordered_multi_target": 15,
        "sequential_target": 15,
    }
    assert [episode.seed for episode in public_manifest.episodes] == list(
        range(1_000_000, 1_000_060)
    )
    assert hidden_manifest.split == "hidden_test"
    assert hidden_manifest.release_channel == "private"
    assert hidden_manifest.public is False
    assert [episode.seed for episode in hidden_manifest.episodes] == list(
        range(2_000_000, 2_000_060)
    )
    assert _manifest_signatures(public_manifest).isdisjoint(
        _manifest_signatures(hidden_manifest)
    )
    assert _difficulty_counts(public_manifest, "visibility") == {
        "easy": 20,
        "medium": 20,
        "hard": 20,
    }
    assert _difficulty_counts(public_manifest, "occlusion") == {
        "easy": 20,
        "medium": 20,
        "hard": 20,
    }
    assert _difficulty_counts(public_manifest, "detour") == {
        "easy": 20,
        "medium": 20,
        "hard": 20,
    }



def test_release_pair_generation_writes_redacted_public_hidden_report() -> None:
    pool = CandidatePool.model_validate(_candidate_pool())

    public_manifest, hidden_manifest, metadata, report = build_release_pair_from_candidates(
        pool,
        hidden_salt="unit-test-salt",
        public_seed_base=1_000_000,
        hidden_seed_base=2_000_000,
    )

    assert public_manifest.split == "public"
    assert hidden_manifest.split == "hidden_test"
    assert len(public_manifest.episodes) == 60
    assert len(hidden_manifest.episodes) == 60
    assert metadata.candidate_count == 120
    assert report.status == "ok"
    assert report.public_episode_count == 60
    assert report.hidden_episode_count == 60
    assert report.reused_start_target_signature_count == 0
    assert report.public_task_counts == {
        "single_target": 30,
        "unordered_multi_target": 15,
        "sequential_target": 15,
    }
    assert report.hidden_task_counts == report.public_task_counts
    assert report.public_difficulty_distribution["visibility"] == {
        "easy": 20,
        "medium": 20,
        "hard": 20,
    }
    assert report.hidden_difficulty_distribution["detour"] == {
        "easy": 20,
        "medium": 20,
        "hard": 20,
    }
    assert "unit-test-salt" not in canonical_release_pair_report_json(report)
    assert "hidden-test" not in canonical_release_pair_report_json(report)


def test_paired_start_generator_places_uav_on_ugv_platform_and_same_component() -> None:
    grid = _start_grid()
    regions = (_confirmation_region("region-a", component=1, pose=(4.5, 4.5, 0.0)),)

    starts = build_paired_start_candidates(
        grid,
        regions,
        config=PairedStartConfig(max_starts_per_component=4, exclude_confirmation_radius_m=0.0),
        ceiling_height=np.full((5, 5), 3.0, dtype=np.float32),
        seed_material="unit-test",
    )

    assert len(starts) == 4
    assert starts == build_paired_start_candidates(
        grid,
        regions,
        config=PairedStartConfig(max_starts_per_component=4, exclude_confirmation_radius_m=0.0),
        ceiling_height=np.full((5, 5), 3.0, dtype=np.float32),
        seed_material="unit-test",
    )
    first = starts[0]
    assert first.starts.docked is True
    assert first.starts.ugv.frame == "map"
    assert first.starts.uav_on_platform.parent_frame == "ugv/platform"
    assert first.starts.uav_on_platform.z_m == 0.45
    assert first.traversability_component == 1
    assert first.reachable_region_ids == ("region-a",)
    assert first.takeoff_clearance_m == pytest.approx(2.55)
    row, col = first.grid_cell
    assert grid.traversable_pose_at_cell(row, col) is not None


def test_paired_start_generator_filters_blocked_components_and_low_clearance() -> None:
    grid = _start_grid(blocked=(1, 1))
    regions = (_confirmation_region("region-a", component=1, pose=(4.5, 4.5, 0.0)),)
    ceiling = np.full((5, 5), 3.0, dtype=np.float32)
    ceiling[0:4, :] = 1.0

    starts = build_paired_start_candidates(
        grid,
        regions,
        config=PairedStartConfig(max_starts_per_component=8, exclude_confirmation_radius_m=0.0),
        ceiling_height=ceiling,
        seed_material="unit-test",
    )

    assert starts
    assert all(candidate.grid_cell[0] == 4 for candidate in starts)
    assert all(candidate.grid_cell != (1, 1) for candidate in starts)
    assert all(candidate.takeoff_clearance_m == pytest.approx(2.55) for candidate in starts)


def test_paired_start_generator_rejects_missing_reachable_regions_or_bad_ceiling() -> None:
    grid = _start_grid()
    unreachable = ConfirmationRegion(
        region_id="region-unreachable",
        instance_id="target-a",
        reachable=False,
        excluded_reason="blocked",
    )

    with pytest.raises(EpisodeGenerationError, match="reachable confirmation regions"):
        build_paired_start_candidates(grid, (unreachable,))
    with pytest.raises(EpisodeGenerationError, match="ceiling_height shape"):
        build_paired_start_candidates(
            grid,
            (_confirmation_region("region-a", component=1, pose=(4.5, 4.5, 0.0)),),
            ceiling_height=np.ones((2, 2), dtype=np.float32),
        )

def test_sampler_rejects_insufficient_candidates() -> None:
    pool_data = _candidate_pool()
    pool_data["candidates"] = [
        candidate
        for candidate in pool_data["candidates"]
        if candidate["task_type"] != "sequential_target"
    ]
    pool = CandidatePool.model_validate(pool_data)

    with pytest.raises(EpisodeGenerationError, match="insufficient candidates"):
        build_manifest_from_candidates(pool, split="public")


def test_manifest_generation_can_use_candidate_oracle_timeouts() -> None:
    pool = CandidatePool.model_validate(_candidate_pool(include_oracle=True))

    default_manifest = build_manifest_from_candidates(pool, split="public")
    oracle_manifest = build_manifest_from_candidates(
        pool,
        split="public",
        use_oracle_timeouts=True,
    )

    assert {episode.timeout_s for episode in default_manifest.episodes} == {300}
    assert all(480 <= episode.timeout_s <= 516 for episode in oracle_manifest.episodes)
    with pytest.raises(EpisodeGenerationError, match="missing oracle evidence"):
        build_manifest_from_candidates(
            CandidatePool.model_validate(_candidate_pool()),
            split="public",
            use_oracle_timeouts=True,
        )


def test_difficulty_metadata_fixes_tercile_boundaries_and_validates_labels() -> None:
    pool = CandidatePool.model_validate(_candidate_pool())

    metadata = difficulty_metadata_from_candidates(pool)
    serialized = canonical_difficulty_metadata_json(metadata)

    assert metadata.candidate_count == 120
    assert metadata.label_mismatch_count == 0
    assert metadata.axes["visibility"].direction == "higher_is_easier"
    assert metadata.axes["visibility"].low_cut == 0.15
    assert metadata.axes["visibility"].high_cut == 0.5
    assert metadata.axes["occlusion"].direction == "lower_is_easier"
    assert metadata.axes["occlusion"].low_cut == 0.1
    assert metadata.axes["occlusion"].high_cut == 0.5
    assert metadata.axes["detour"].low_cut == 1.1
    assert metadata.axes["detour"].high_cut == 1.6
    assert metadata.axes["visibility"].label_counts == {
        "easy": 40,
        "medium": 40,
        "hard": 40,
    }
    assert serialized == canonical_difficulty_metadata_json(metadata)
    validate_candidate_labels_against_metadata(metadata)


def test_difficulty_metadata_allows_rank_balanced_tied_values() -> None:
    pool_data = _candidate_pool()
    for index, candidate in enumerate(sorted(pool_data["candidates"], key=lambda item: item["candidate_id"])):
        candidate["difficulty"]["occlusion"] = 1.0
        candidate["difficulty"]["occlusion_label"] = LABELS[index // 40]
    pool = CandidatePool.model_validate(pool_data)

    metadata = difficulty_metadata_from_candidates(pool)

    assert metadata.axes["occlusion"].low_cut == 1.0
    assert metadata.axes["occlusion"].high_cut == 1.0
    assert metadata.axes["occlusion"].label_counts == {
        "easy": 40,
        "medium": 40,
        "hard": 40,
    }
    assert metadata.label_mismatch_count == 0


def test_difficulty_metadata_audit_detects_tampering() -> None:
    pool = CandidatePool.model_validate(_candidate_pool())
    metadata = difficulty_metadata_from_candidates(pool)

    report = audit_difficulty_metadata(pool, metadata)

    assert report.status == "ok"
    assert report.metadata_sha256 == report.expected_metadata_sha256
    assert canonical_difficulty_metadata_audit_json(report) == canonical_difficulty_metadata_audit_json(report)

    tampered_payload = metadata.model_dump(mode="json")
    tampered_payload["axes"]["visibility"]["low_cut"] = 0.2
    tampered = DifficultyMetadata.model_validate(tampered_payload)
    tampered_report = audit_difficulty_metadata(pool, tampered)

    assert tampered_report.status == "failed"
    assert tampered_report.issue_count == 1
    assert tampered_report.issues[0].code == "difficulty_metadata_mismatch"
    assert tampered_report.metadata_sha256 != tampered_report.expected_metadata_sha256


def test_difficulty_metadata_detects_label_mismatches() -> None:
    pool_data = _candidate_pool()
    first = pool_data["candidates"][0]
    first["difficulty"]["visibility_label"] = "hard"
    pool = CandidatePool.model_validate(pool_data)

    metadata = difficulty_metadata_from_candidates(pool)

    assert metadata.label_mismatch_count == 1
    assert metadata.label_mismatches[0]["candidate_id"] == "candidate-0000"
    assert metadata.label_mismatches[0]["axis"] == "visibility"
    with pytest.raises(EpisodeGenerationError, match="difficulty labels"):
        validate_candidate_labels_against_metadata(metadata)


def test_candidate_pool_audit_requires_oracle_evidence() -> None:
    pool = CandidatePool.model_validate(_candidate_pool())

    report = audit_candidate_pool(pool, require_oracle=True, max_issues=3)

    assert report.status == "failed"
    assert report.issue_count == 120
    assert len(report.issues) == 3
    assert report.issues[0].code == "missing_oracle_evidence"
    assert canonical_candidate_pool_audit_json(report) == canonical_candidate_pool_audit_json(report)


def test_candidate_pool_audit_accepts_oracle_evidence() -> None:
    pool_data = _candidate_pool(include_oracle=True)
    pool = CandidatePool.model_validate(pool_data)

    report = audit_candidate_pool(pool, require_oracle=True)

    assert report.status == "ok"
    assert report.issue_count == 0
    assert report.oracle_available_count == 120
    assert report.task_counts == {
        "single_target": 60,
        "unordered_multi_target": 30,
        "sequential_target": 30,
    }


def test_attach_oracle_evidence_updates_pool_and_requires_completeness() -> None:
    pool = CandidatePool.model_validate(_candidate_pool())
    first_id = pool.candidates[0].candidate_id
    record = CandidateOracleEvidenceRecord.model_validate(
        {
            "candidate_id": first_id,
            "oracle": _oracle_summary_payload(first_id),
        }
    )

    updated = attach_oracle_evidence_to_candidate_pool(pool, (record,))

    assert updated.candidates[0].oracle is not None
    assert updated.candidates[0].oracle.source == f"oracle/path/{first_id}.json"
    assert updated.candidates[1].oracle is None
    with pytest.raises(EpisodeGenerationError, match="oracle evidence missing"):
        attach_oracle_evidence_to_candidate_pool(pool, (record,), require_all=True)
    with pytest.raises(EpisodeGenerationError, match="unknown candidate ids"):
        attach_oracle_evidence_to_candidate_pool(
            pool,
            (
                CandidateOracleEvidenceRecord.model_validate(
                    {"candidate_id": "unknown-candidate", "oracle": _oracle_summary_payload("unknown")}
                ),
            ),
        )


def test_grid_oracle_estimate_builds_deterministic_candidate_records() -> None:
    pool = CandidatePool.model_validate(
        {
            "schema_version": "1.0.0",
            "catalog_id": "benchmark-v1.0-retro",
            "scene_id": "RetroNeighborhood",
            "difficulty_version": "retro-v1",
            "source": "unit-test-candidate-pool",
            "candidates": [
                {
                    "candidate_id": "candidate-single",
                    "eligible_splits": ["public", "hidden_test"],
                    "task_type": "single_target",
                    "query": "find target",
                    "starts": {
                        "ugv": {"frame": "map", "x_m": 0.0, "y_m": 0.0, "yaw_rad": 0.0},
                        "uav_on_platform": {
                            "parent_frame": "ugv/platform",
                            "x_m": 0.0,
                            "y_m": 0.0,
                            "z_m": 0.45,
                            "yaw_rad": 0.0,
                        },
                        "docked": True,
                    },
                    "targets": [
                        {
                            "query_id": "q-0",
                            "semantic_class": "target",
                            "instance_id": "target-a",
                            "confirmation_region_id": "region-a",
                        }
                    ],
                    "difficulty": {
                        "visibility_label": "easy",
                        "occlusion_label": "easy",
                        "detour_label": "easy",
                        "visibility": 0.9,
                        "occlusion": 0.1,
                        "detour": 1.0,
                    },
                    "ground_truth": {
                        "traversability": "gt/retro/traversability.npz",
                        "targets": "gt/retro/targets.yaml",
                        "confirmation_regions": "gt/retro/targets.yaml",
                        "checksum_sha256": GT_CHECKSUM,
                    },
                }
            ],
        }
    )
    targets = TargetAnnotationManifest.model_validate(
        {
            "schema_version": "1.0.0",
            "scene_id": "RetroNeighborhood",
            "frame": "map",
            "source_format": "unit-test",
            "instances": [_target_instance("target-a", "region-a", [4.0, 0.0, 1.0])],
            "confirmation_regions": [
                _region_payload("region-a", "target-a", [3.0, 0.0, 0.0])
            ],
        }
    )

    bundle = estimate_candidate_grid_oracle_evidence(
        pool,
        targets,
        uav_speed_mps=2.0,
        ugv_speed_mps=1.0,
        detection_overhead_s_per_target=0.0,
        confirmation_overhead_s_per_target=0.0,
    )

    assert bundle.generator == "airground-grid-oracle-estimate-v1"
    assert len(bundle.records) == 1
    oracle = bundle.records[0].oracle
    assert oracle.source == "airground-grid-oracle-estimate-v1"
    assert oracle.uav_path_length_m == 4.0
    assert oracle.ugv_path_length_m == 3.0
    assert oracle.detection_to_confirmation_time_s == 3.0
    assert oracle.estimated_completion_time_s == 7.0
    assert oracle.waypoint_count == 2
    assert oracle.checksum_sha256 is not None and len(oracle.checksum_sha256) == 64
    assert canonical_candidate_oracle_evidence_json(bundle) == canonical_candidate_oracle_evidence_json(
        bundle
    )


@pytest.mark.parametrize("scene_id", ["RetroNeighborhood", "ConstructionSite", "MilitaryBase"])
def test_candidate_pool_builder_assembles_task_types_and_raw_difficulty(scene_id) -> None:
    starts, targets, visibility, grid = _candidate_pool_builder_inputs()
    targets = targets.model_copy(update={"scene_id": scene_id})
    visibility = visibility.model_copy(update={"scene_id": scene_id})
    grid = TraversabilityGrid(metadata=grid.metadata.model_copy(update={"scene_id": scene_id}),
        height=grid.height, mask=grid.mask, component=grid.component)

    pool = build_candidate_pool_from_artifacts(
        starts,
        targets,
        visibility,
        grid,
        ground_truth={
            "traversability": "gt/traversability/retro.npz",
            "targets": "gt/targets/retro.targets.json",
            "confirmation_regions": "gt/targets/retro.targets.json",
            "checksum_sha256": GT_CHECKSUM,
        },
        config=CandidatePoolBuildConfig(
            difficulty_version="difficulty-unit",
            source="unit-test-builder",
            max_single_target_candidates=3,
            max_unordered_multi_target_candidates=2,
            max_sequential_target_candidates=2,
        ),
    )

    task_counts = Counter(candidate.task_type for candidate in pool.candidates)
    assert pool.scene_id == scene_id
    assert task_counts == {
        "single_target": 3,
        "unordered_multi_target": 2,
        "sequential_target": 2,
    }
    assert pool.source == "unit-test-builder"
    assert all(candidate.oracle is None for candidate in pool.candidates)
    assert all(candidate.difficulty.detour >= 1.0 for candidate in pool.candidates)
    assert {candidate.difficulty.visibility_label for candidate in pool.candidates} <= set(LABELS)
    assert canonical_candidate_pool_json(pool) == canonical_candidate_pool_json(pool)


def _manifest_signatures(manifest) -> set[tuple[object, ...]]:
    signatures = set()
    for episode in manifest.episodes:
        ugv = episode.starts.ugv
        signatures.add(
            (
                episode.task_type,
                round(ugv.x_m, 3),
                round(ugv.y_m, 3),
                round(ugv.yaw_rad, 6),
                tuple(sorted(target.instance_id for target in episode.targets)),
            )
        )
    return signatures


def _difficulty_counts(manifest, axis: str) -> dict[str, int]:
    counts = Counter(getattr(episode.difficulty, f"{axis}_label") for episode in manifest.episodes)
    return {label: counts[label] for label in LABELS}


def _candidate_pool(*, include_oracle: bool = False) -> dict[str, object]:
    candidates: list[dict[str, object]] = []
    offset = 0
    for task_type, count in (
        ("single_target", 60),
        ("unordered_multi_target", 30),
        ("sequential_target", 30),
    ):
        for index in range(count):
            candidates.append(
                _candidate(
                    offset + index,
                    task_type,
                    LABELS[index % 3],
                    include_oracle=include_oracle,
                )
            )
        offset += count
    return {
        "schema_version": "1.0.0",
        "catalog_id": "benchmark-v1.0-retro",
        "scene_id": "RetroNeighborhood",
        "difficulty_version": "retro-v1",
        "source": "unit-test-candidate-pool",
        "source_checksum_sha256": GT_CHECKSUM,
        "candidates": candidates,
    }


def _candidate(index: int, task_type: str, label: str, *, include_oracle: bool = False) -> dict[str, object]:
    target_count = 1 if task_type == "single_target" else 2
    targets = []
    for target_index in range(target_count):
        target = {
            "query_id": f"q-{index}-{target_index}",
            "semantic_class": "target",
            "instance_id": f"RetroNeighborhood.target.{index:04d}.{target_index}",
            "confirmation_region_id": (
                f"RetroNeighborhood.region.{index:04d}.{target_index}"
            ),
        }
        if task_type == "sequential_target":
            target["sequence_index"] = target_index
        targets.append(target)
    candidate = {
        "candidate_id": f"candidate-{index:04d}",
        "eligible_splits": ["public", "hidden_test"],
        "task_type": task_type,
        "query": f"find target {index}",
        "starts": {
            "ugv": {
                "frame": "map",
                "x_m": float(index),
                "y_m": float(index % 7),
                "yaw_rad": 0.1 * (index % 5),
            },
            "uav_on_platform": {
                "parent_frame": "ugv/platform",
                "x_m": 0.0,
                "y_m": 0.0,
                "z_m": 0.4,
            },
            "docked": True,
        },
        "targets": targets,
        "difficulty": {
            "visibility_label": label,
            "occlusion_label": label,
            "detour_label": label,
            "visibility": {"easy": 0.85, "medium": 0.5, "hard": 0.15}[label],
            "occlusion": {"easy": 0.1, "medium": 0.5, "hard": 0.85}[label],
            "detour": {"easy": 1.1, "medium": 1.6, "hard": 2.4}[label],
        },
        "ground_truth": {
            "traversability": "gt/retro/traversability.npz",
            "targets": "gt/retro/targets.yaml",
            "confirmation_regions": "gt/retro/confirmation_regions.yaml",
            "checksum_sha256": GT_CHECKSUM,
        },
    }
    if include_oracle:
        candidate["oracle"] = _oracle_summary_payload(f"candidate-{index:04d}", offset=index)
    return candidate


def _oracle_summary_payload(candidate_id: str, *, offset: int = 0) -> dict[str, object]:
    return {
        "source": f"oracle/path/{candidate_id}.json",
        "estimated_completion_time_s": 120.0 + float(offset % 10),
        "detection_to_confirmation_time_s": 30.0 + float(offset % 5),
        "uav_path_length_m": 40.0 + float(offset),
        "ugv_path_length_m": 25.0 + float(offset),
        "waypoint_count": 4 + (offset % 3),
        "checksum_sha256": GT_CHECKSUM,
    }


def _start_grid(*, blocked: tuple[int, int] | None = None) -> TraversabilityGrid:
    metadata = TraversabilityMetadata.model_validate(
        {
            "schema_version": "1.0.0",
            "scene_id": "RetroNeighborhood",
            "frame": "map",
            "origin": {"x_m": 0.0, "y_m": 0.0, "z_m": 0.0},
            "resolution_m": 1.0,
            "shape": [5, 5],
            "generator": "unit-test",
            "generator_version": "0",
        }
    )
    height = np.zeros((5, 5), dtype=np.float32)
    mask = np.ones((5, 5), dtype=np.uint8)
    if blocked is not None:
        mask[blocked] = 0
    component = np.ones((5, 5), dtype=np.int32)
    return TraversabilityGrid(metadata=metadata, height=height, mask=mask, component=component)


def _confirmation_region(
    region_id: str,
    *,
    component: int,
    pose: tuple[float, float, float],
) -> ConfirmationRegion:
    return ConfirmationRegion(
        region_id=region_id,
        instance_id=f"target-{region_id}",
        reachable=True,
        yaw_range_rad=(-3.14, 3.14),
        poses=(
            ConfirmationPose(
                frame="map",
                position_xyz_m=pose,
                yaw_rad=0.0,
                distance_to_target_m=2.0,
                visible_fraction=0.5,
                traversability_component=component,
            ),
        ),
    )


def _candidate_pool_builder_inputs() -> tuple[
    tuple[PairedStartCandidate, ...],
    TargetAnnotationManifest,
    VisibilityOcclusionReport,
    TraversabilityGrid,
]:
    grid = _start_grid()
    starts = (
        PairedStartCandidate.model_validate(
            {
                "candidate_id": "start-0",
                "starts": {
                    "ugv": {"frame": "map", "x_m": 0.0, "y_m": 0.0, "yaw_rad": 0.0},
                    "uav_on_platform": {
                        "parent_frame": "ugv/platform",
                        "x_m": 0.0,
                        "y_m": 0.0,
                        "z_m": 0.45,
                        "yaw_rad": 0.0,
                    },
                    "docked": True,
                },
                "traversability_component": 1,
                "grid_cell": [0, 0],
                "reachable_region_ids": ["region-a", "region-b", "region-c"],
            }
        ),
    )
    targets = TargetAnnotationManifest.model_validate(
        {
            "schema_version": "1.0.0",
            "scene_id": "RetroNeighborhood",
            "frame": "map",
            "source_format": "unit-test",
            "instances": [
                _target_instance("target-a", "region-a", [4.0, 0.0, 1.0]),
                _target_instance("target-b", "region-b", [0.0, 4.0, 1.0]),
                _target_instance("target-c", "region-c", [4.0, 4.0, 1.0]),
            ],
            "confirmation_regions": [
                _region_payload("region-a", "target-a", [4.0, 0.0, 0.0]),
                _region_payload("region-b", "target-b", [0.0, 4.0, 0.0]),
                _region_payload("region-c", "target-c", [4.0, 4.0, 0.0]),
            ],
        }
    )
    visibility = VisibilityOcclusionReport.model_validate(
        {
            "schema_version": "1.0.0",
            "scene_id": "RetroNeighborhood",
            "frame": "map",
            "generator": "airground-grid-obb-visibility-occlusion-proxy-v1",
            "generator_version": "unit-test",
            "config": {},
            "target_count": 3,
            "metrics": [
                _visibility_metric("target-a", 0.9, 0.1),
                _visibility_metric("target-b", 0.5, 0.3),
                _visibility_metric("target-c", 0.1, 0.8),
            ],
        }
    )
    return starts, targets, visibility, grid


def _target_instance(instance_id: str, region_id: str, center_xyz_m: list[float]) -> dict[str, object]:
    return {
        "instance_id": instance_id,
        "semantic_class": "target",
        "source_class": "target",
        "source_index": int(instance_id[-1], 36),
        "ground_reachable": "reachable",
        "confirmation_region_id": region_id,
        "obb": {
            "frame": "map",
            "center_xyz_m": center_xyz_m,
            "size_xyz_m": [1.0, 1.0, 2.0],
        },
    }


def _region_payload(region_id: str, instance_id: str, position_xyz_m: list[float]) -> dict[str, object]:
    return {
        "region_id": region_id,
        "instance_id": instance_id,
        "reachable": True,
        "yaw_range_rad": [-3.14, 3.14],
        "poses": [
            {
                "frame": "map",
                "position_xyz_m": position_xyz_m,
                "yaw_rad": 0.0,
                "distance_to_target_m": 2.0,
                "visible_fraction": 0.5,
                "traversability_component": 1,
            }
        ],
    }


def _visibility_metric(instance_id: str, visibility: float, occlusion: float) -> dict[str, object]:
    return {
        "instance_id": instance_id,
        "semantic_class": "target",
        "visibility": visibility,
        "occlusion": occlusion,
        "candidate_sample_count": 10,
        "visible_sample_count": 5,
        "ray_count": 20,
        "occluded_ray_count": int(20 * occlusion),
    }
