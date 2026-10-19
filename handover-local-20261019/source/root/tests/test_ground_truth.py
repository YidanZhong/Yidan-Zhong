"""Ground-truth schema tests."""

from __future__ import annotations

import json
import math

import numpy as np
import pytest
from pydantic import ValidationError

from airground_benchmark.communication import RaycastHit
from airground_benchmark.ground_truth import (
    ConfirmationRegion,
    ConfirmationPose,
    GroundTruthError,
    TargetAnnotationManifest,
    TargetReviewLedger,
    UsdPrimCandidateManifest,
    TraversabilityMetadata,
    apply_target_review_ledger,
    build_target_review_ledger_template,
    audit_target_annotations,
    bind_target_annotations_to_usd_prims,
    build_confirmation_regions_from_traversability,
    build_visibility_occlusion_report_from_traversability,
    canonical_confirmation_visibility_report_json,
    canonical_raycast_confirmation_visibility_report_json,
    canonical_sensor_frame_confirmation_visibility_report_json,
    canonical_target_annotation_audit_report_json,
    canonical_target_annotations_json,
    canonical_target_review_apply_report_json,
    canonical_target_review_ledger_template_json,
    canonical_target_prim_binding_report_json,
    canonical_target_annotations_schema_json,
    canonical_usd_prim_candidate_manifest_json,
    canonical_traversability_metadata_json,
    canonical_traversability_schema_json,
    canonical_visibility_occlusion_report_json,
    confirmation_sensor_frame_records_from_pose,
    convert_rayfronts_bbox_annotations,
    load_default_target_annotations,
    target_annotations_sha256,
    traversability_npz_sha256,
    validate_confirmation_visibility_sensor_trace,
    validate_confirmation_visibility_with_raycast,
    validate_traversability_npz,
    validate_confirmation_visibility_from_traversability,
    write_target_review_artifacts,
)


def _metadata(npz_sha256: str | None = None) -> TraversabilityMetadata:
    return TraversabilityMetadata.model_validate(
        {
            "schema_version": "1.0.0",
            "scene_id": "RetroNeighborhood",
            "frame": "map",
            "origin": {"x_m": -1.0, "y_m": -2.0, "z_m": 0.0},
            "resolution_m": 0.1,
            "shape": [2, 3],
            "generator": "unit-test",
            "generator_version": "0",
            "npz_sha256": npz_sha256,
        }
    )


def _write_valid_npz(path) -> None:
    np.savez_compressed(
        path,
        height=np.zeros((2, 3), dtype=np.float32),
        normal=np.dstack(
            [
                np.zeros((2, 3), dtype=np.float32),
                np.zeros((2, 3), dtype=np.float32),
                np.ones((2, 3), dtype=np.float32),
            ]
        ),
        cost=np.ones((2, 3), dtype=np.float32),
        mask=np.array([[1, 1, 0], [0, 1, 1]], dtype=np.uint8),
        component=np.array([[1, 1, -1], [-1, 2, 2]], dtype=np.int32),
    )


def _target_manifest() -> TargetAnnotationManifest:
    return TargetAnnotationManifest.model_validate(
        {
            "schema_version": "1.0.0",
            "scene_id": "RetroNeighborhood",
            "frame": "map",
            "source_format": "unit-test",
            "instances": [
                {
                    "instance_id": "RetroNeighborhood.target.0000",
                    "semantic_class": "target",
                    "source_class": "target",
                    "source_index": 0,
                    "obb": {
                        "frame": "map",
                        "center_xyz_m": [0.0, 0.0, 1.0],
                        "size_xyz_m": [1.0, 1.0, 2.0],
                    },
                }
            ],
        }
    )


def _confirmation_metadata() -> TraversabilityMetadata:
    return TraversabilityMetadata.model_validate(
        {
            "schema_version": "1.0.0",
            "scene_id": "RetroNeighborhood",
            "frame": "map",
            "origin": {"x_m": -5.5, "y_m": -5.5, "z_m": 0.0},
            "resolution_m": 1.0,
            "shape": [11, 11],
            "generator": "unit-test",
            "generator_version": "0",
        }
    )


def _write_confirmation_npz(path, *, traversable: bool = True) -> None:
    mask = np.ones((11, 11), dtype=np.uint8) if traversable else np.zeros((11, 11), dtype=np.uint8)
    np.savez_compressed(
        path,
        height=np.zeros((11, 11), dtype=np.float32),
        normal=np.dstack(
            [
                np.zeros((11, 11), dtype=np.float32),
                np.zeros((11, 11), dtype=np.float32),
                np.ones((11, 11), dtype=np.float32),
            ]
        ),
        cost=np.ones((11, 11), dtype=np.float32),
        mask=mask,
        component=np.ones((11, 11), dtype=np.int32),
    )


def _write_visibility_npz(path, *, blocked_wall: bool = False) -> None:
    mask = np.ones((5, 5), dtype=np.uint8)
    if blocked_wall:
        mask[:, 1] = 0
    np.savez_compressed(
        path,
        height=np.zeros((5, 5), dtype=np.float32),
        normal=np.dstack(
            [
                np.zeros((5, 5), dtype=np.float32),
                np.zeros((5, 5), dtype=np.float32),
                np.ones((5, 5), dtype=np.float32),
            ]
        ),
        cost=np.ones((5, 5), dtype=np.float32),
        mask=mask,
        component=np.where(mask, 1, -1).astype(np.int32),
    )


def test_traversability_metadata_schema_is_json() -> None:
    schema = json.loads(canonical_traversability_schema_json())
    assert schema["additionalProperties"] is False
    from airground_benchmark.scenes import SCENE_IDS
    assert schema["properties"]["scene_id"]["enum"] == list(SCENE_IDS)


def test_traversability_npz_validates_against_metadata(tmp_path) -> None:
    npz = tmp_path / "traversability.npz"
    _write_valid_npz(npz)
    metadata = _metadata(traversability_npz_sha256(npz))
    summary = validate_traversability_npz(npz, metadata)
    assert summary["status"] == "ok"
    assert summary["shape"] == [2, 3]
    assert summary["traversable_cells"] == 4
    assert summary["component_count"] == 2


def test_traversability_metadata_json_is_stable() -> None:
    metadata = _metadata()
    first = canonical_traversability_metadata_json(metadata)
    second = canonical_traversability_metadata_json(metadata)
    assert first == second
    assert json.loads(first)["resolution_m"] == 0.1


def test_traversability_rejects_wrong_array_shape(tmp_path) -> None:
    npz = tmp_path / "bad.npz"
    np.savez_compressed(
        npz,
        height=np.zeros((2, 2), dtype=np.float32),
        normal=np.zeros((2, 3, 3), dtype=np.float32),
        cost=np.zeros((2, 3), dtype=np.float32),
        mask=np.ones((2, 3), dtype=np.uint8),
        component=np.ones((2, 3), dtype=np.int32),
    )
    with pytest.raises(GroundTruthError, match="height shape"):
        validate_traversability_npz(npz, _metadata())


def test_traversability_rejects_invalid_mask_values(tmp_path) -> None:
    npz = tmp_path / "bad-mask.npz"
    _write_valid_npz(npz)
    data = dict(np.load(npz))
    data["mask"] = np.array([[1, 2, 0], [0, 1, 1]], dtype=np.uint8)
    np.savez_compressed(npz, **data)
    with pytest.raises(GroundTruthError, match="0/1"):
        validate_traversability_npz(npz, _metadata())


def test_traversability_shape_dimensions_must_be_positive() -> None:
    with pytest.raises(ValidationError, match="shape dimensions must be positive"):
        TraversabilityMetadata.model_validate(
            {
                "schema_version": "1.0.0",
                "scene_id": "RetroNeighborhood",
                "frame": "map",
                "origin": {"x_m": 0.0, "y_m": 0.0},
                "resolution_m": 0.1,
                "shape": [0, 3],
                "generator": "unit-test",
                "generator_version": "0",
            }
        )


def test_target_annotation_schema_is_json() -> None:
    schema = json.loads(canonical_target_annotations_schema_json())
    assert schema["additionalProperties"] is False
    assert "TargetInstance" in schema["$defs"]


def test_convert_rayfronts_bbox_annotations_is_stable(tmp_path) -> None:
    legacy = tmp_path / "RetroNeighborhood.json"
    legacy.write_text(
        json.dumps(
            [
                {
                    "class": "Bus Stop",
                    "bbox_world": {
                        "center_xyz_m": [10.0, 20.0, 3.0],
                        "size_xyz_m": [1.0, 2.0, 3.0],
                        "orientation_deg": [0.0, 0.0, 90.0],
                    },
                },
                {
                    "class": "Bus Stop",
                    "bbox_world": {
                        "center_xyz_m": [11.0, 21.0, 4.0],
                        "size_xyz_m": [2.0, 3.0, 4.0],
                    },
                },
            ]
        ),
        encoding="utf-8",
    )
    manifest = convert_rayfronts_bbox_annotations(
        legacy,
        spawn_offset_xyz_m=(1.0, 2.0, 0.5),
    )
    assert [instance.instance_id for instance in manifest.instances] == [
        "RetroNeighborhood.bus_stop.0000",
        "RetroNeighborhood.bus_stop.0001",
    ]
    assert manifest.instances[0].semantic_class == "bus stop"
    assert manifest.instances[0].obb.center_xyz_m == (9.0, 18.0, 2.5)
    assert manifest.instances[0].obb.orientation_rpy_rad[2] == pytest.approx(1.57079632679)
    assert canonical_target_annotations_json(manifest) == canonical_target_annotations_json(manifest)
    assert manifest.source_path == str(legacy)


def test_convert_rayfronts_bbox_annotations_supports_stable_source_path(tmp_path) -> None:
    legacy = tmp_path / "RetroNeighborhood.json"
    legacy.write_text(
        json.dumps(
            [
                {
                    "class": "Red Car",
                    "bbox_world": {
                        "center_xyz_m": [1.0, 2.0, 0.5],
                        "size_xyz_m": [3.0, 4.0, 2.0],
                    },
                }
            ]
        ),
        encoding="utf-8",
    )
    manifest = convert_rayfronts_bbox_annotations(
        legacy,
        source_path="RayFronts/rayfronts/annotations/RetroNeighborhood.json",
    )
    assert manifest.source_path == "RayFronts/rayfronts/annotations/RetroNeighborhood.json"
    assert len(target_annotations_sha256(manifest)) == 64


def test_packaged_target_annotations_are_valid_and_path_stable() -> None:
    manifest = load_default_target_annotations()
    assert manifest.scene_id == "RetroNeighborhood"
    assert len(manifest.instances) >= 100
    assert manifest.source_path == "RayFronts/rayfronts/annotations/RetroNeighborhood.json"
    assert "/home/" not in canonical_target_annotations_json(manifest)
    assert len(target_annotations_sha256(manifest)) == 64


def test_load_target_annotations_json_fast_path_matches_yaml_parse(tmp_path, caplog) -> None:
    import yaml

    from airground_benchmark import ground_truth

    manifest = load_default_target_annotations()
    payload = manifest.model_dump(mode="json")
    payload["instances"][0]["obb"]["orientation_rpy_rad"] = [1e-05, 0.0, 0.0]  # json.dumps writes 1e-05 (YAML 1.1: a str)
    text = json.dumps(payload)
    json_path = tmp_path / "targets.json"
    json_path.write_text(text, encoding="utf-8")
    via_yaml = ground_truth.TargetAnnotationManifest.model_validate(yaml.safe_load(text))
    assert ground_truth.load_target_annotations(json_path) == via_yaml

    # A .json file that is only YAML (flow mapping with bare keys) still loads, with a warning.
    yaml_only = tmp_path / "yaml_only.json"
    yaml_only.write_text(yaml.safe_dump(payload, default_flow_style=True), encoding="utf-8")
    with caplog.at_level("WARNING", logger="airground_benchmark.ground_truth"):
        assert ground_truth.load_target_annotations(yaml_only) == via_yaml
    assert "parsing it as YAML" in caplog.text


def test_target_annotation_audit_reports_release_completeness_issues() -> None:
    manifest = TargetAnnotationManifest.model_validate(
        {
            "schema_version": "1.0.0",
            "scene_id": "RetroNeighborhood",
            "frame": "map",
            "source_format": "unit-test",
            "instances": [
                {
                    "instance_id": "target.0000",
                    "semantic_class": "target",
                    "source_class": "target",
                    "source_index": 0,
                    "obb": {
                        "frame": "map",
                        "center_xyz_m": [0.0, 0.0, 1.0],
                        "size_xyz_m": [1.0, 1.0, 2.0],
                    },
                }
            ],
        }
    )

    report = audit_target_annotations(
        manifest,
        require_source_path=True,
        require_usd_prim_path=True,
        require_verified=True,
        require_review_version=True,
    )
    summary = report.summary()

    assert summary["status"] == "failed"
    assert summary["issue_counts"] == {
        "missing_review_version": 1,
        "missing_source_path": 1,
        "missing_usd_prim_path": 1,
        "unstable_instance_id": 1,
        "unverified_target": 1,
    }
    assert canonical_target_annotation_audit_report_json(report) == canonical_target_annotation_audit_report_json(report)


def test_target_annotation_audit_accepts_complete_reviewed_target() -> None:
    manifest = TargetAnnotationManifest.model_validate(
        {
            "schema_version": "1.0.0",
            "scene_id": "RetroNeighborhood",
            "frame": "map",
            "source_format": "unit-test",
            "source_path": "RayFronts/rayfronts/annotations/RetroNeighborhood.json",
            "instances": [
                {
                    "instance_id": "RetroNeighborhood.red_car.0000",
                    "semantic_class": "red car",
                    "source_class": "red car",
                    "source_index": 0,
                    "usd_prim_path": "/World/RetroNeighborhood/Vehicles/RedCar",
                    "verified": True,
                    "review_version": "manual-v1",
                    "obb": {
                        "frame": "map",
                        "center_xyz_m": [0.0, 0.0, 1.0],
                        "size_xyz_m": [2.0, 4.0, 2.0],
                    },
                }
            ],
        }
    )

    report = audit_target_annotations(
        manifest,
        require_source_path=True,
        require_usd_prim_path=True,
        require_verified=True,
        require_review_version=True,
    )
    assert report.summary()["status"] == "ok"
    assert report.summary()["issue_count"] == 0


def test_target_annotation_audit_accepts_reviewed_exclusion_without_usd_prim() -> None:
    manifest = TargetAnnotationManifest.model_validate(
        {
            "schema_version": "1.0.0",
            "scene_id": "RetroNeighborhood",
            "frame": "map",
            "source_format": "unit-test",
            "source_path": "RayFronts/rayfronts/annotations/RetroNeighborhood.json",
            "instances": [
                {
                    "instance_id": "RetroNeighborhood.red_car.0000",
                    "semantic_class": "red car",
                    "source_class": "red car",
                    "source_index": 0,
                    "usd_prim_path": None,
                    "verified": True,
                    "excluded_reason": "no reliable USD prim path after hybrid human review",
                    "review_version": "manual-v1",
                    "obb": {
                        "frame": "map",
                        "center_xyz_m": [0.0, 0.0, 1.0],
                        "size_xyz_m": [2.0, 4.0, 2.0],
                    },
                }
            ],
        }
    )

    report = audit_target_annotations(
        manifest,
        require_source_path=True,
        require_usd_prim_path=True,
        require_verified=True,
        require_review_version=True,
    )
    assert report.summary()["status"] == "ok"
    assert report.summary()["issue_count"] == 0


def test_apply_target_review_ledger_updates_reviewed_rows() -> None:
    manifest = TargetAnnotationManifest.model_validate(
        {
            "schema_version": "1.0.0",
            "scene_id": "RetroNeighborhood",
            "frame": "map",
            "source_format": "unit-test",
            "source_path": "RayFronts/rayfronts/annotations/RetroNeighborhood.json",
            "instances": [
                {
                    "instance_id": "RetroNeighborhood.red_car.0000",
                    "semantic_class": "red car",
                    "source_class": "red car",
                    "source_index": 0,
                    "obb": {
                        "frame": "map",
                        "center_xyz_m": [0.0, 0.0, 1.0],
                        "size_xyz_m": [2.0, 4.0, 2.0],
                    },
                },
                {
                    "instance_id": "RetroNeighborhood.tree.0000",
                    "semantic_class": "tree",
                    "source_class": "tree",
                    "source_index": 1,
                    "obb": {
                        "frame": "map",
                        "center_xyz_m": [10.0, 0.0, 2.0],
                        "size_xyz_m": [1.0, 1.0, 4.0],
                    },
                },
            ],
        }
    )
    ledger = TargetReviewLedger.model_validate(
        {
            "schema_version": "1.0.0",
            "scene_id": "RetroNeighborhood",
            "frame": "map",
            "generator": "airground-target-human-review-ledger-v1",
            "generator_version": "unit-test",
            "review_version": "manual-review-v1",
            "source_annotations_sha256": target_annotations_sha256(manifest),
            "decisions": [
                {
                    "instance_id": "RetroNeighborhood.red_car.0000",
                    "action": "verify",
                    "usd_prim_path": "/World/stage/Vehicles/RedCar",
                },
                {
                    "instance_id": "RetroNeighborhood.tree.0000",
                    "action": "exclude",
                    "excluded_reason": "ambiguous tree cluster in review video",
                },
            ],
        }
    )

    updated, report = apply_target_review_ledger(manifest, ledger)

    assert updated.instances[0].verified is True
    assert updated.instances[0].usd_prim_path == "/World/stage/Vehicles/RedCar"
    assert updated.instances[0].review_version == "manual-review-v1"
    assert updated.instances[0].excluded_reason is None
    assert updated.instances[1].verified is True
    assert updated.instances[1].excluded_reason == "ambiguous tree cluster in review video"
    assert report.verify_decision_count == 1
    assert report.exclude_decision_count == 1
    assert report.untouched_count == 0
    assert report.output_annotations_sha256 == target_annotations_sha256(updated)
    assert canonical_target_review_apply_report_json(report) == canonical_target_review_apply_report_json(report)


def test_build_target_review_ledger_template_is_not_final_ledger() -> None:
    manifest = TargetAnnotationManifest.model_validate(
        {
            "schema_version": "1.0.0",
            "scene_id": "RetroNeighborhood",
            "frame": "map",
            "source_format": "unit-test",
            "instances": [
                {
                    "instance_id": "RetroNeighborhood.red_car.0000",
                    "semantic_class": "red car",
                    "source_class": "red car",
                    "source_index": 0,
                    "usd_prim_path": "/World/stage/Vehicles/RedCarCandidate",
                    "obb": {
                        "frame": "map",
                        "center_xyz_m": [0.0, 0.0, 1.0],
                        "size_xyz_m": [2.0, 4.0, 2.0],
                    },
                },
                {
                    "instance_id": "RetroNeighborhood.tree.0000",
                    "semantic_class": "tree",
                    "source_class": "tree",
                    "source_index": 1,
                    "obb": {
                        "frame": "map",
                        "center_xyz_m": [10.0, 0.0, 2.0],
                        "size_xyz_m": [1.0, 1.0, 4.0],
                    },
                },
            ],
        }
    )
    template = build_target_review_ledger_template(
        manifest,
        {
            "schema_version": "1.0.0",
            "scene_id": "RetroNeighborhood",
            "rows": [
                {
                    "instance_id": "RetroNeighborhood.tree.0000",
                    "issues": "no_semantic_candidate_within_threshold",
                    "priority": 0,
                    "usd_prim_path": "",
                },
                {
                    "instance_id": "RetroNeighborhood.red_car.0000",
                    "issues": "ambiguous_match",
                    "priority": 1,
                    "usd_prim_path": "/World/stage/Vehicles/RedCarCandidate",
                },
            ],
        },
        review_version="manual-review-v1",
        source_review_queue_sha256="1" * 64,
        source_review_media="runs/p1_05_targets/review.mp4",
    )

    assert template.generator == "airground-target-human-review-ledger-template-v1"
    assert template.source_annotations_sha256 == target_annotations_sha256(manifest)
    assert template.source_review_queue_sha256 == "1" * 64
    assert template.review_required_count == 2
    assert template.rows[0].instance_id == "RetroNeighborhood.tree.0000"
    assert template.rows[0].review_frame_index == 1
    assert template.rows[0].suggested_next_step == "choose_usd_prim_path_or_exclude"
    assert template.rows[1].suggested_next_step == "confirm_or_correct_candidate"
    assert template.rows[1].final_decision_fields["action"] == "verify_or_exclude"
    assert canonical_target_review_ledger_template_json(template) == canonical_target_review_ledger_template_json(template)


def test_apply_target_review_ledger_rejects_stale_source_checksum() -> None:
    manifest = TargetAnnotationManifest.model_validate(
        {
            "schema_version": "1.0.0",
            "scene_id": "RetroNeighborhood",
            "frame": "map",
            "source_format": "unit-test",
            "instances": [
                {
                    "instance_id": "RetroNeighborhood.red_car.0000",
                    "semantic_class": "red car",
                    "source_class": "red car",
                    "source_index": 0,
                    "obb": {
                        "frame": "map",
                        "center_xyz_m": [0.0, 0.0, 1.0],
                        "size_xyz_m": [2.0, 4.0, 2.0],
                    },
                }
            ],
        }
    )
    ledger = TargetReviewLedger.model_validate(
        {
            "schema_version": "1.0.0",
            "scene_id": "RetroNeighborhood",
            "frame": "map",
            "generator": "airground-target-human-review-ledger-v1",
            "generator_version": "unit-test",
            "review_version": "manual-review-v1",
            "source_annotations_sha256": "0" * 64,
            "decisions": [
                {
                    "instance_id": "RetroNeighborhood.red_car.0000",
                    "action": "verify",
                    "usd_prim_path": "/World/stage/Vehicles/RedCar",
                }
            ],
        }
    )

    with pytest.raises(GroundTruthError, match="source_annotations_sha256"):
        apply_target_review_ledger(manifest, ledger)


def test_bind_target_annotations_to_usd_prims_attaches_best_candidate() -> None:
    manifest = TargetAnnotationManifest.model_validate(
        {
            "schema_version": "1.0.0",
            "scene_id": "RetroNeighborhood",
            "frame": "map",
            "source_format": "unit-test",
            "source_path": "RayFronts/rayfronts/annotations/RetroNeighborhood.json",
            "instances": [
                {
                    "instance_id": "RetroNeighborhood.bus_stop.0000",
                    "semantic_class": "bus stop",
                    "source_class": "Bus Stop",
                    "source_index": 0,
                    "obb": {
                        "frame": "map",
                        "center_xyz_m": [10.0, 20.0, 1.5],
                        "size_xyz_m": [2.0, 6.0, 3.0],
                    },
                }
            ],
        }
    )
    prims = UsdPrimCandidateManifest.model_validate(
        {
            "schema_version": "1.0.0",
            "scene_id": "RetroNeighborhood",
            "frame": "map",
            "generator": "unit-test",
            "generator_version": "0",
            "source_usd_path": "AirStack/scenes/RetroNeighborhood/RetroNeighborhood_Export.usd",
            "candidates": [
                {
                    "prim_path": "/World/stage/Neighborhood/BP_BusStop",
                    "semantic_hints": ["bus stop"],
                    "center_xyz_m": [10.1, 20.0, 1.4],
                    "size_xyz_m": [2.1, 6.2, 2.9],
                },
                {
                    "prim_path": "/World/stage/Neighborhood/BP_House_01",
                    "semantic_hints": ["house"],
                    "center_xyz_m": [10.0, 20.0, 1.5],
                    "size_xyz_m": [20.0, 10.0, 8.0],
                },
            ],
        }
    )

    updated, report = bind_target_annotations_to_usd_prims(
        manifest,
        prims,
        max_center_distance_m=1.0,
    )

    assert report.status == "ok"
    assert report.bound_count == 1
    assert report.bindings[0].usd_prim_path == "/World/stage/Neighborhood/BP_BusStop"
    assert updated.instances[0].usd_prim_path == "/World/stage/Neighborhood/BP_BusStop"
    assert updated.instances[0].verified is False
    assert updated.instances[0].review_version is None
    assert canonical_target_prim_binding_report_json(report) == canonical_target_prim_binding_report_json(report)
    assert canonical_usd_prim_candidate_manifest_json(prims) == canonical_usd_prim_candidate_manifest_json(prims)


def test_bind_target_annotations_to_usd_prims_reports_unbound_and_ambiguous() -> None:
    manifest = TargetAnnotationManifest.model_validate(
        {
            "schema_version": "1.0.0",
            "scene_id": "RetroNeighborhood",
            "frame": "map",
            "source_format": "unit-test",
            "instances": [
                {
                    "instance_id": "RetroNeighborhood.tree.0000",
                    "semantic_class": "tree",
                    "source_class": "tree",
                    "source_index": 0,
                    "obb": {
                        "frame": "map",
                        "center_xyz_m": [0.0, 0.0, 2.0],
                        "size_xyz_m": [5.0, 5.0, 4.0],
                    },
                },
                {
                    "instance_id": "RetroNeighborhood.fountain.0000",
                    "semantic_class": "fountain",
                    "source_class": "fountain",
                    "source_index": 1,
                    "obb": {
                        "frame": "map",
                        "center_xyz_m": [50.0, 50.0, 1.0],
                        "size_xyz_m": [4.0, 4.0, 2.0],
                    },
                },
            ],
        }
    )
    prims = UsdPrimCandidateManifest.model_validate(
        {
            "schema_version": "1.0.0",
            "scene_id": "RetroNeighborhood",
            "frame": "map",
            "generator": "unit-test",
            "generator_version": "0",
            "candidates": [
                {
                    "prim_path": "/World/stage/Neighborhood/BP_Tree_A",
                    "semantic_hints": ["tree"],
                    "center_xyz_m": [0.0, 0.0, 2.0],
                    "size_xyz_m": [5.0, 5.0, 4.0],
                },
                {
                    "prim_path": "/World/stage/Neighborhood/BP_Tree_B",
                    "semantic_hints": ["tree"],
                    "center_xyz_m": [0.05, 0.0, 2.0],
                    "size_xyz_m": [5.0, 5.0, 4.0],
                },
            ],
        }
    )

    updated, report = bind_target_annotations_to_usd_prims(
        manifest,
        prims,
        max_center_distance_m=1.0,
        fail_on_ambiguous=True,
    )

    assert report.status == "failed"
    assert report.bound_count == 1
    assert report.unbound_count == 1
    assert report.ambiguous_count == 1
    assert "ambiguous_match" in report.bindings[0].issues
    assert report.bindings[1].issues == ("no_semantic_candidate_within_threshold",)
    assert updated.instances[1].usd_prim_path is None


def test_raycast_confirmation_visibility_accepts_clear_target_hit() -> None:
    manifest = TargetAnnotationManifest.model_validate(
        {
            "schema_version": "1.0.0",
            "scene_id": "RetroNeighborhood",
            "frame": "map",
            "source_format": "unit-test",
            "instances": [
                {
                    "instance_id": "RetroNeighborhood.bus_stop.0000",
                    "semantic_class": "bus stop",
                    "source_class": "Bus Stop",
                    "source_index": 0,
                    "usd_prim_path": "/World/stage/Neighborhood/BP_BusStop",
                    "ground_reachable": "reachable",
                    "confirmation_region_id": "confirm/RetroNeighborhood.bus_stop.0000",
                    "obb": {
                        "frame": "map",
                        "center_xyz_m": [0.0, 0.0, 1.2],
                        "size_xyz_m": [2.0, 2.0, 2.0],
                    },
                }
            ],
            "confirmation_regions": [
                {
                    "region_id": "confirm/RetroNeighborhood.bus_stop.0000",
                    "instance_id": "RetroNeighborhood.bus_stop.0000",
                    "reachable": True,
                    "yaw_range_rad": [3.0, 3.2],
                    "poses": [
                        {
                            "frame": "map",
                            "position_xyz_m": [2.0, 0.0, 0.0],
                            "yaw_rad": math.pi,
                            "distance_to_target_m": 2.0,
                            "visible_fraction": 1.0,
                            "traversability_component": 1,
                        }
                    ],
                }
            ],
        }
    )

    def raycast(_origin, endpoint):
        return (RaycastHit(distance_m=2.3, prim_path="/World/stage/Neighborhood/BP_BusStop"),)

    report = validate_confirmation_visibility_with_raycast(
        manifest,
        raycast,
        min_distance_m=1.0,
        max_distance_m=4.0,
        target_sample_count=1,
    )

    assert report.status == "ok"
    assert report.valid_region_count == 1
    pose_metric = report.metrics[0].pose_metrics[0]
    assert pose_metric.valid is True
    assert pose_metric.clear_ray_count == 1
    assert pose_metric.blocked_ray_count == 0
    assert canonical_raycast_confirmation_visibility_report_json(report) == canonical_raycast_confirmation_visibility_report_json(report)


def test_confirmation_sensor_frame_records_from_live_pose_validate() -> None:
    manifest = TargetAnnotationManifest.model_validate(
        {
            "schema_version": "1.0.0",
            "scene_id": "RetroNeighborhood",
            "frame": "map",
            "source_format": "unit-test",
            "instances": [
                {
                    "instance_id": "RetroNeighborhood.bus_stop.0000",
                    "semantic_class": "bus stop",
                    "source_class": "Bus Stop",
                    "source_index": 0,
                    "usd_prim_path": "/World/stage/Neighborhood/BP_BusStop",
                    "ground_reachable": "reachable",
                    "confirmation_region_id": "confirm/RetroNeighborhood.bus_stop.0000",
                    "obb": {
                        "frame": "map",
                        "center_xyz_m": [0.0, 0.0, 1.2],
                        "size_xyz_m": [2.0, 2.0, 2.0],
                    },
                }
            ],
            "confirmation_regions": [
                {
                    "region_id": "confirm/RetroNeighborhood.bus_stop.0000",
                    "instance_id": "RetroNeighborhood.bus_stop.0000",
                    "reachable": True,
                    "poses": [
                        {
                            "frame": "map",
                            "position_xyz_m": [2.0, 0.0, 0.0],
                            "yaw_rad": math.pi,
                            "distance_to_target_m": 2.0,
                            "visible_fraction": 1.0,
                        }
                    ],
                }
            ],
        }
    )

    def raycast(_origin, _endpoint):
        return (RaycastHit(distance_m=2.0, prim_path="/World/stage/Neighborhood/BP_BusStop"),)

    records = tuple(
        record
        for frame_index in range(5)
        for record in confirmation_sensor_frame_records_from_pose(
            manifest,
            raycast,
            camera_position_xyz_m=(2.0, 0.0, 1.2),
            camera_yaw_rad=math.pi,
            camera_frame="ugv_camera",
            sim_time_s=frame_index * 0.1,
            target_sample_count=1,
            min_distance_m=1.0,
            max_distance_m=4.0,
        )
    )

    assert len(records) == 5
    assert records[0]["event"] == "confirmation_visibility_sensor_frame"
    assert records[0]["camera_frame"] == "ugv_camera"
    assert records[0]["clear_ray_count"] == 1
    report = validate_confirmation_visibility_sensor_trace(
        manifest,
        records,
        min_distance_m=1.0,
        max_distance_m=4.0,
    )
    assert report.status == "ok"


def test_raycast_confirmation_visibility_uses_ground_distance_for_tall_targets() -> None:
    manifest = TargetAnnotationManifest.model_validate(
        {
            "schema_version": "1.0.0",
            "scene_id": "RetroNeighborhood",
            "frame": "map",
            "source_format": "unit-test",
            "instances": [
                {
                    "instance_id": "RetroNeighborhood.billboard.0000",
                    "semantic_class": "billboard",
                    "source_class": "billboard",
                    "source_index": 0,
                    "usd_prim_path": "/World/stage/Neighborhood/BP_Billboard",
                    "ground_reachable": "reachable",
                    "confirmation_region_id": "confirm/RetroNeighborhood.billboard.0000",
                    "obb": {
                        "frame": "map",
                        "center_xyz_m": [0.0, 0.0, 9.0],
                        "size_xyz_m": [2.0, 2.0, 12.0],
                    },
                }
            ],
            "confirmation_regions": [
                {
                    "region_id": "confirm/RetroNeighborhood.billboard.0000",
                    "instance_id": "RetroNeighborhood.billboard.0000",
                    "reachable": True,
                    "poses": [
                        {
                            "frame": "map",
                            "position_xyz_m": [2.0, 0.0, 0.0],
                            "yaw_rad": math.pi,
                            "distance_to_target_m": 2.0,
                            "visible_fraction": 1.0,
                            "traversability_component": 1,
                        }
                    ],
                }
            ],
        }
    )

    def raycast(_origin, endpoint):
        return (RaycastHit(distance_m=2.0, prim_path="/World/stage/Neighborhood/BP_Billboard"),)

    report = validate_confirmation_visibility_with_raycast(
        manifest,
        raycast,
        min_distance_m=1.0,
        max_distance_m=4.0,
        target_sample_count=1,
    )

    assert report.status == "ok"
    assert report.metrics[0].pose_metrics[0].distance_to_target_m == pytest.approx(2.0)


def test_raycast_confirmation_visibility_allows_invalid_alternate_poses() -> None:
    manifest = TargetAnnotationManifest.model_validate(
        {
            "schema_version": "1.0.0",
            "scene_id": "RetroNeighborhood",
            "frame": "map",
            "source_format": "unit-test",
            "instances": [
                {
                    "instance_id": "RetroNeighborhood.sign.0000",
                    "semantic_class": "sign",
                    "source_class": "sign",
                    "source_index": 0,
                    "usd_prim_path": "/World/stage/Neighborhood/BP_Sign",
                    "ground_reachable": "reachable",
                    "confirmation_region_id": "confirm/RetroNeighborhood.sign.0000",
                    "obb": {
                        "frame": "map",
                        "center_xyz_m": [0.0, 0.0, 1.0],
                        "size_xyz_m": [1.0, 1.0, 1.0],
                    },
                }
            ],
            "confirmation_regions": [
                {
                    "region_id": "confirm/RetroNeighborhood.sign.0000",
                    "instance_id": "RetroNeighborhood.sign.0000",
                    "reachable": True,
                    "poses": [
                        {
                            "frame": "map",
                            "position_xyz_m": [2.0, 0.0, 0.0],
                            "yaw_rad": 0.0,
                            "distance_to_target_m": 2.0,
                            "visible_fraction": 1.0,
                            "traversability_component": 1,
                        },
                        {
                            "frame": "map",
                            "position_xyz_m": [2.0, 0.0, 0.0],
                            "yaw_rad": math.pi,
                            "distance_to_target_m": 2.0,
                            "visible_fraction": 1.0,
                            "traversability_component": 1,
                        },
                    ],
                }
            ],
        }
    )

    def raycast(_origin, _endpoint):
        return ()

    report = validate_confirmation_visibility_with_raycast(
        manifest,
        raycast,
        min_distance_m=1.0,
        max_distance_m=4.0,
        target_sample_count=1,
    )

    assert report.status == "ok"
    assert report.issue_count == 0
    assert report.metrics[0].valid_pose_count == 1
    assert report.metrics[0].pose_metrics[0].issues == ("outside_horizontal_fov",)


def test_raycast_confirmation_visibility_rejects_mesh_occlusion() -> None:
    manifest = TargetAnnotationManifest.model_validate(
        {
            "schema_version": "1.0.0",
            "scene_id": "RetroNeighborhood",
            "frame": "map",
            "source_format": "unit-test",
            "instances": [
                {
                    "instance_id": "RetroNeighborhood.house.0000",
                    "semantic_class": "house",
                    "source_class": "house",
                    "source_index": 0,
                    "usd_prim_path": "/World/stage/Neighborhood/BP_House",
                    "ground_reachable": "reachable",
                    "confirmation_region_id": "confirm/RetroNeighborhood.house.0000",
                    "obb": {
                        "frame": "map",
                        "center_xyz_m": [0.0, 0.0, 1.0],
                        "size_xyz_m": [2.0, 2.0, 2.0],
                    },
                }
            ],
            "confirmation_regions": [
                {
                    "region_id": "confirm/RetroNeighborhood.house.0000",
                    "instance_id": "RetroNeighborhood.house.0000",
                    "reachable": True,
                    "poses": [
                        {
                            "frame": "map",
                            "position_xyz_m": [2.0, 0.0, 0.0],
                            "yaw_rad": math.pi,
                            "distance_to_target_m": 2.0,
                            "visible_fraction": 1.0,
                        }
                    ],
                }
            ],
        }
    )

    def raycast(_origin, _endpoint):
        return (RaycastHit(distance_m=0.5, prim_path="/World/stage/Neighborhood/Fence"),)

    report = validate_confirmation_visibility_with_raycast(
        manifest,
        raycast,
        min_distance_m=1.0,
        max_distance_m=4.0,
        target_sample_count=1,
    )

    assert report.status == "failed"
    assert report.valid_region_count == 0
    pose_metric = report.metrics[0].pose_metrics[0]
    assert pose_metric.blocked_ray_count == 1
    assert pose_metric.blocking_prim_paths == ("/World/stage/Neighborhood/Fence",)
    assert "visible_fraction_below_threshold" in pose_metric.issues


def test_sensor_frame_confirmation_visibility_accepts_continuous_trace() -> None:
    manifest = TargetAnnotationManifest.model_validate(
        {
            "schema_version": "1.0.0",
            "scene_id": "RetroNeighborhood",
            "frame": "map",
            "source_format": "unit-test",
            "instances": [
                {
                    "instance_id": "RetroNeighborhood.sign.0000",
                    "semantic_class": "sign",
                    "source_class": "sign",
                    "source_index": 0,
                    "ground_reachable": "reachable",
                    "confirmation_region_id": "confirm/RetroNeighborhood.sign.0000",
                    "obb": {
                        "frame": "map",
                        "center_xyz_m": [0.0, 0.0, 1.0],
                        "size_xyz_m": [1.0, 1.0, 1.0],
                    },
                }
            ],
            "confirmation_regions": [
                {
                    "region_id": "confirm/RetroNeighborhood.sign.0000",
                    "instance_id": "RetroNeighborhood.sign.0000",
                    "reachable": True,
                    "poses": [
                        {
                            "frame": "map",
                            "position_xyz_m": [2.0, 0.0, 0.0],
                            "yaw_rad": math.pi,
                            "distance_to_target_m": 2.0,
                            "visible_fraction": 1.0,
                        }
                    ],
                }
            ],
        }
    )
    trace = [
        {
            "event": "confirmation_visibility_sensor_frame",
            "sim_time_s": index * 0.1,
            "region_id": "confirm/RetroNeighborhood.sign.0000",
            "instance_id": "RetroNeighborhood.sign.0000",
            "pose_index": 0,
            "distance_to_target_m": 2.0,
            "yaw_error_rad": 0.0,
            "visible_fraction": 0.8,
            "ray_count": 5,
            "clear_ray_count": 4,
            "blocked_ray_count": 1,
        }
        for index in range(5)
    ]

    report = validate_confirmation_visibility_sensor_trace(
        manifest,
        trace,
        min_distance_m=1.0,
        max_distance_m=4.0,
        required_consecutive_frames=5,
    )

    assert report.status == "ok"
    assert report.generator == "airground-sensor-frame-confirmation-visibility-v1"
    assert report.trace_frame_count == 5
    assert report.valid_region_count == 1
    pose_metric = report.metrics[0].pose_metrics[0]
    assert pose_metric.valid is True
    assert pose_metric.max_consecutive_visible_frames == 5
    assert pose_metric.ray_count == 25
    assert canonical_sensor_frame_confirmation_visibility_report_json(report) == (
        canonical_sensor_frame_confirmation_visibility_report_json(report)
    )


def test_sensor_frame_confirmation_visibility_rejects_gapped_trace() -> None:
    manifest = TargetAnnotationManifest.model_validate(
        {
            "schema_version": "1.0.0",
            "scene_id": "RetroNeighborhood",
            "frame": "map",
            "source_format": "unit-test",
            "instances": [
                {
                    "instance_id": "RetroNeighborhood.sign.0000",
                    "semantic_class": "sign",
                    "source_class": "sign",
                    "source_index": 0,
                    "ground_reachable": "reachable",
                    "confirmation_region_id": "confirm/RetroNeighborhood.sign.0000",
                    "obb": {
                        "frame": "map",
                        "center_xyz_m": [0.0, 0.0, 1.0],
                        "size_xyz_m": [1.0, 1.0, 1.0],
                    },
                }
            ],
            "confirmation_regions": [
                {
                    "region_id": "confirm/RetroNeighborhood.sign.0000",
                    "instance_id": "RetroNeighborhood.sign.0000",
                    "reachable": True,
                    "poses": [
                        {
                            "frame": "map",
                            "position_xyz_m": [2.0, 0.0, 0.0],
                            "yaw_rad": math.pi,
                            "distance_to_target_m": 2.0,
                            "visible_fraction": 1.0,
                        }
                    ],
                }
            ],
        }
    )
    trace = [
        {
            "event": "confirmation_visibility_sensor_frame",
            "sim_time_s": time_s,
            "region_id": "confirm/RetroNeighborhood.sign.0000",
            "instance_id": "RetroNeighborhood.sign.0000",
            "pose_index": 0,
            "distance_to_target_m": 2.0,
            "yaw_error_rad": 0.0,
            "visible_fraction": 0.8,
            "ray_count": 1,
            "clear_ray_count": 1,
            "blocked_ray_count": 0,
        }
        for time_s in (0.0, 0.3, 0.6)
    ]

    report = validate_confirmation_visibility_sensor_trace(
        manifest,
        trace,
        min_distance_m=1.0,
        max_distance_m=4.0,
        required_consecutive_frames=3,
        max_frame_gap_s=0.15,
    )

    assert report.status == "failed"
    assert report.valid_region_count == 0
    assert report.metrics[0].pose_metrics[0].max_consecutive_visible_frames == 1
    assert "insufficient_consecutive_visible_frames" in report.metrics[0].pose_metrics[0].issues


def test_target_review_artifacts_show_labels_prim_and_views(tmp_path) -> None:
    manifest = TargetAnnotationManifest.model_validate(
        {
            "schema_version": "1.0.0",
            "scene_id": "RetroNeighborhood",
            "frame": "map",
            "source_format": "unit-test",
            "instances": [
                {
                    "instance_id": "RetroNeighborhood.red_car.0000",
                    "semantic_class": "red car",
                    "source_class": "red car",
                    "source_index": 0,
                    "usd_prim_path": "/World/RetroNeighborhood/Vehicles/RedCar",
                    "obb": {
                        "frame": "map",
                        "center_xyz_m": [0.0, 0.0, 1.0],
                        "size_xyz_m": [2.0, 4.0, 2.0],
                        "orientation_rpy_rad": [0.0, 0.0, 1.5707963267948966],
                    },
                }
            ],
        }
    )

    summary = write_target_review_artifacts(
        manifest,
        tmp_path,
        camera_position_xyz_m=(-6.0, 0.0, 1.5),
        camera_yaw_rad=0.0,
        max_distance_m=20.0,
    )

    assert summary["status"] == "ok"
    assert summary["rendered_instance_count"] == 1
    assert summary["first_person_visible_count"] == 1
    assert len(summary["artifacts"]["topdown_svg"]["sha256"]) == 64
    topdown = (tmp_path / "targets_topdown.svg").read_text(encoding="utf-8")
    first_person = (tmp_path / "targets_first_person.svg").read_text(encoding="utf-8")
    review_manifest = json.loads((tmp_path / "review_manifest.json").read_text(encoding="utf-8"))
    assert "RetroNeighborhood.red_car.0000" in topdown
    assert "/World/RetroNeighborhood/Vehicles/RedCar" in topdown
    assert "first-person proxy" in first_person
    assert review_manifest["targets"][0]["first_person_visible"] is True
    assert review_manifest["artifacts"]["review_manifest"]["path"] == "review_manifest.json"


def test_target_annotations_validate_confirmation_region_references() -> None:
    manifest = TargetAnnotationManifest.model_validate(
        {
            "schema_version": "1.0.0",
            "scene_id": "RetroNeighborhood",
            "frame": "map",
            "source_format": "unit-test",
            "instances": [
                {
                    "instance_id": "RetroNeighborhood.person.0000",
                    "semantic_class": "person",
                    "source_class": "person",
                    "source_index": 0,
                    "ground_reachable": "reachable",
                    "confirmation_region_id": "confirm/person/0000",
                    "obb": {
                        "frame": "map",
                        "center_xyz_m": [0.0, 0.0, 1.0],
                        "size_xyz_m": [1.0, 1.0, 2.0],
                    },
                }
            ],
            "confirmation_regions": [
                {
                    "region_id": "confirm/person/0000",
                    "instance_id": "RetroNeighborhood.person.0000",
                    "reachable": True,
                    "yaw_range_rad": [-1.0, 1.0],
                    "poses": [
                        {
                            "frame": "map",
                            "position_xyz_m": [2.0, 0.0, 0.0],
                            "yaw_rad": 3.14,
                            "distance_to_target_m": 2.0,
                            "visible_fraction": 0.25,
                            "traversability_component": 1,
                        }
                    ],
                }
            ],
        }
    )
    assert manifest.confirmation_regions[0].reachable is True


def test_target_annotations_reject_bad_confirmation_pose() -> None:
    with pytest.raises(ValidationError, match="visible_fraction"):
        ConfirmationRegion(
            region_id="confirm/bad",
            instance_id="RetroNeighborhood.person.0000",
            reachable=True,
            yaw_range_rad=(0.0, 1.0),
            poses=(
                ConfirmationPose(
                    frame="map",
                    position_xyz_m=(2.0, 0.0, 0.0),
                    yaw_rad=0.0,
                    distance_to_target_m=2.0,
                    visible_fraction=0.1,
                ),
            ),
        )


def test_build_confirmation_regions_from_traversability_marks_reachable(tmp_path) -> None:
    npz = tmp_path / "traversability.npz"
    _write_confirmation_npz(npz)
    updated = build_confirmation_regions_from_traversability(
        _target_manifest(),
        _confirmation_metadata(),
        npz,
        min_distance_m=2.0,
        max_distance_m=2.0,
        radial_step_m=1.0,
        angle_count=4,
    )

    instance = updated.instances[0]
    region = updated.confirmation_regions[0]
    assert instance.ground_reachable == "reachable"
    assert instance.confirmation_region_id == "confirm/RetroNeighborhood.target.0000"
    assert region.reachable is True
    assert len(region.poses) == 4
    assert {pose.traversability_component for pose in region.poses} == {1}
    assert {round(pose.distance_to_target_m, 6) for pose in region.poses} == {2.0}
    assert region.yaw_range_rad is not None
    yaw_low, yaw_high = region.yaw_range_rad
    pose_yaws = [pose.yaw_rad for pose in region.poses]
    assert yaw_low == min(pose_yaws)
    assert yaw_high == max(pose_yaws)
    assert canonical_target_annotations_json(updated) == canonical_target_annotations_json(updated)


def test_build_confirmation_regions_from_traversability_marks_unreachable(tmp_path) -> None:
    npz = tmp_path / "blocked.npz"
    _write_confirmation_npz(npz, traversable=False)
    updated = build_confirmation_regions_from_traversability(
        _target_manifest(),
        _confirmation_metadata(),
        npz,
        min_distance_m=2.0,
        max_distance_m=2.0,
        radial_step_m=1.0,
        angle_count=4,
    )

    instance = updated.instances[0]
    region = updated.confirmation_regions[0]
    assert instance.ground_reachable == "unreachable"
    assert instance.excluded_reason == "no_traversable_pose_within_confirmation_radius"
    assert region.reachable is False
    assert region.excluded_reason == "no_traversable_pose_within_confirmation_radius"


def test_validate_confirmation_visibility_proxy_accepts_valid_region(tmp_path) -> None:
    npz = tmp_path / "traversability.npz"
    _write_confirmation_npz(npz)
    updated = build_confirmation_regions_from_traversability(
        _target_manifest(),
        _confirmation_metadata(),
        npz,
        min_distance_m=2.0,
        max_distance_m=2.0,
        radial_step_m=1.0,
        angle_count=4,
    )

    report = validate_confirmation_visibility_from_traversability(
        updated,
        _confirmation_metadata(),
        npz,
        min_distance_m=2.0,
        max_distance_m=2.0,
    )

    assert report.status == "ok"
    assert report.valid_region_count == 1
    assert report.metrics[0].valid_pose_count == 4
    assert report.metrics[0].poses[0].consecutive_visible_frames == 5
    assert canonical_confirmation_visibility_report_json(report) == canonical_confirmation_visibility_report_json(report)


def test_validate_confirmation_visibility_proxy_rejects_bad_yaw(tmp_path) -> None:
    npz = tmp_path / "traversability.npz"
    _write_confirmation_npz(npz)
    updated = build_confirmation_regions_from_traversability(
        _target_manifest(),
        _confirmation_metadata(),
        npz,
        min_distance_m=2.0,
        max_distance_m=2.0,
        radial_step_m=1.0,
        angle_count=4,
    )
    region = updated.confirmation_regions[0]
    bad_region = region.model_copy(
        update={
            "poses": tuple(
                pose.model_copy(update={"yaw_rad": pose.yaw_rad + math.pi})
                for pose in region.poses
            )
        }
    )
    bad_manifest = updated.model_copy(update={"confirmation_regions": (bad_region,)})

    report = validate_confirmation_visibility_from_traversability(
        bad_manifest,
        _confirmation_metadata(),
        npz,
        min_distance_m=2.0,
        max_distance_m=2.0,
    )

    assert report.status == "failed"
    assert report.valid_region_count == 0
    assert report.metrics[0].issues == ("no_pose_passes_visibility_proxy",)
    assert {pose.in_fov for pose in report.metrics[0].poses} == {False}


def test_visibility_occlusion_report_is_deterministic_and_detects_blocked_rays(tmp_path) -> None:
    open_npz = tmp_path / "open.npz"
    blocked_npz = tmp_path / "blocked.npz"
    _write_visibility_npz(open_npz)
    _write_visibility_npz(blocked_npz, blocked_wall=True)
    metadata = TraversabilityMetadata.model_validate(
        {
            "schema_version": "1.0.0",
            "scene_id": "RetroNeighborhood",
            "frame": "map",
            "origin": {"x_m": -2.5, "y_m": -2.5, "z_m": 0.0},
            "resolution_m": 1.0,
            "shape": [5, 5],
            "generator": "unit-test",
            "generator_version": "0",
        }
    )

    open_report = build_visibility_occlusion_report_from_traversability(
        _target_manifest(),
        metadata,
        open_npz,
        uav_altitudes_m=(2.0,),
        max_range_m=10.0,
        yaw_samples=4,
    )
    blocked_report = build_visibility_occlusion_report_from_traversability(
        _target_manifest(),
        metadata,
        blocked_npz,
        uav_altitudes_m=(2.0,),
        max_range_m=10.0,
        yaw_samples=4,
    )

    open_metric = open_report.metrics[0]
    blocked_metric = blocked_report.metrics[0]
    assert open_metric.candidate_sample_count == 100
    assert open_metric.visible_sample_count > 0
    assert open_metric.occlusion == 0.0
    assert open_metric.occluded_ray_count == 0
    assert blocked_metric.visible_sample_count == open_metric.visible_sample_count
    assert blocked_metric.ray_count == open_metric.ray_count
    assert blocked_metric.occluded_ray_count > 0
    assert blocked_metric.occlusion > 0.0
    assert canonical_visibility_occlusion_report_json(open_report) == (
        canonical_visibility_occlusion_report_json(open_report)
    )
