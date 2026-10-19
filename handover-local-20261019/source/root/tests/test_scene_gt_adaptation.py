"""Cross-scene input and fail-closed handover preparation regressions."""
import importlib.util
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from airground_benchmark.ground_truth import (
    TargetAnnotationManifest, UsdPrimCandidateManifest, GroundTruthError,
    bind_target_annotations_to_usd_prims, convert_rayfronts_bbox_annotations,
)
from airground_benchmark.scenes import SCENE_IDS, is_paper_class, scene_slug
from airground_benchmark.task_catalog import build_task_catalog, upstream_tasks, NEIGHBORHOOD_UPSTREAM_TASKS
from airground_benchmark.episode_manifest import load_episode_manifest, EpisodeManifest

ROOT = Path(__file__).resolve().parents[1]


def script(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("scene", SCENE_IDS)
def test_actual_annotations_convert_without_claiming_verified_or_reachable(scene):
    manifest = convert_rayfronts_bbox_annotations(
        ROOT / "RayFronts/rayfronts/annotations" / f"{scene}.json", scene_id=scene,
    )
    assert manifest.instances
    assert all(not item.verified and item.ground_reachable == "unknown" for item in manifest.instances)
    catalog = build_task_catalog(manifest)
    assert catalog.scene_id == scene
    assert catalog.catalog_id.endswith(scene_slug(scene))
    assert (catalog.type_i_count, catalog.type_ii_count, catalog.type_iii_count) == (4, 3, 3)
    assert catalog.blocked_count == 10
    assert len({entry.task_id for entry in catalog.entries}) == 10
    assert all(len(task.sequence_classes) == 2 for task in upstream_tasks(scene) if task.family == "type_iii")


def test_retro_preserved_and_cross_scene_aliases_conservative():
    assert upstream_tasks("RetroNeighborhood") is NEIGHBORHOOD_UPSTREAM_TASKS
    assert is_paper_class("ConstructionSite", "biotoilet")
    assert is_paper_class("Shipyard", "white silo")
    assert not is_paper_class("SnowyVillage", "water tower")
    with pytest.raises(ValueError, match="unsupported"):
        scene_slug("typo")


@pytest.mark.parametrize("scene", SCENE_IDS[1:])
def test_episode_manifest_catalog_supports_new_scenes_and_rejects_mismatch(scene):
    payload = load_episode_manifest().model_dump(mode="json")
    payload["scene_id"] = scene
    payload["catalog_id"] = f"benchmark-v1.0-{scene_slug(scene)}"
    for episode in payload["episodes"]:
        episode["scene_id"] = scene
    assert EpisodeManifest.model_validate(payload).scene_id == scene
    payload["catalog_id"] = "benchmark-v1.0-retro"
    with pytest.raises(ValidationError, match="catalog_id must correspond"):
        EpisodeManifest.model_validate(payload)


def test_binder_rejects_cross_scene_geometry():
    manifest = convert_rayfronts_bbox_annotations(ROOT / "RayFronts/rayfronts/annotations/FireAcademy.json", scene_id="FireAcademy")
    prims = UsdPrimCandidateManifest(schema_version="1.0.0", scene_id="ConstructionSite", frame="map",
        generator="airground-usd-prim-candidate-exporter-v1", generator_version="test", source_usd_path="test.usd",
        candidates=({"prim_path": "/World/tower", "center_xyz_m": (0, 0, 0), "size_xyz_m": (1, 1, 1)},))
    with pytest.raises(GroundTruthError, match="scene_id"):
        bind_target_annotations_to_usd_prims(manifest, prims)
    payload = manifest.model_dump(mode="json")
    payload["scene_id"] = "Typo"
    with pytest.raises(ValidationError):
        TargetAnnotationManifest.model_validate(payload)


def test_filter_keeps_sequence_direction_and_biotoilet_alias(tmp_path):
    module = script("filter_paper_task_candidates")
    def candidate(names):
        return {"task_type": "sequential_target", "targets": [
            {"semantic_class": name, "sequence_index": index} for index, name in enumerate(names)]}
    good = candidate(["cabling winches", "biotoilet"])
    bad = candidate(["biotoilet", "cabling winches"])
    source, output = tmp_path / "in.json", tmp_path / "out.json"
    source.write_text(json.dumps({"scene_id": "ConstructionSite", "candidates": [good, bad]}))
    assert module.main(["--candidates", str(source), "--output", str(output)]) == 0
    assert json.loads(output.read_text())["candidates"] == [good]


def test_paper_builder_requires_three_available_starts():
    with pytest.raises(SystemExit, match="need 3"):
        script("build_paper_protocol_episodes").select_starts({}, 3)


def test_roi_scene_and_resolution_follow_target_input(tmp_path):
    module=script('run_roi_analysis')
    payload=convert_rayfronts_bbox_annotations(ROOT/'RayFronts/rayfronts/annotations/ConstructionSite.json',scene_id='ConstructionSite')
    targets=tmp_path/'targets.json';targets.write_text(payload.model_dump_json())
    scene,path,stem=module.scene_inputs(targets,None,.05)
    assert scene=='ConstructionSite' and path==ROOT/'AirStack/scenes/ConstructionSite/ConstructionSite_Export.usd'
    assert stem=='construction_site_gt_aabb_0p05'
    with pytest.raises(GroundTruthError,match='mounted repository'):
        module.scene_inputs(targets,tmp_path/'external.usd',.05)


def test_scene_specific_smoke_tasks_and_score_identifiers():
    select = script("select_smoke_starts")
    assert select._matches_paper_task("single_target", frozenset(["biotoilet"]), "ConstructionSite")
    assert not select._matches_paper_task("single_target", frozenset(["biotoilet"]), "RetroNeighborhood")
    score = script("score_paper_protocol")
    assert score.task_id_from_episode("construction-site-paper-type-iii-blue-tarp-to-orange-towercrane-s3") == "construction-site-type-iii-blue-tarp-to-orange-towercrane"
    assert score.task_id_from_episode("retro-paper-type-i-bus-stop-s2") == "retro-type-i-bus-stop"
    with pytest.raises(SystemExit):
        score.task_id_from_episode("retro-paper-type-i-bus-stop-sbad")


def test_preparation_does_not_publish_missing_asset_scene_as_ready(tmp_path):
    report = script("prepare_scene_gt").prepare("SnowyVillage", tmp_path)
    assert report["S2"] == "blocked_missing_usd"
    assert report["missing_paper_classes"] == ["tower"]
    assert report["blocked_task_count"] == 10
    ledger = json.loads((tmp_path / "review.ledger.template.json").read_text())
    assert ledger["generator"] == "airground-target-human-review-ledger-template-v1"
    targets = json.loads((tmp_path / "targets.unreviewed.json").read_text())
    assert not any(row["verified"] for row in targets["instances"])


def test_exporter_accepts_explicit_aliases_with_real_usd(tmp_path):
    pytest.importorskip("pxr")
    from pxr import Usd, UsdGeom
    path = ROOT / "AirStack/simulation/isaac-sim/tools/export_target_prim_candidates.py"
    spec = importlib.util.spec_from_file_location("scene_exporter_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    stage_path, output, aliases = tmp_path / "scene.usda", tmp_path / "candidates.json", tmp_path / "aliases.json"
    stage = Usd.Stage.CreateNew(str(stage_path))
    UsdGeom.Cube.Define(stage, "/World/stage/SM_CustomTank").GetSizeAttr().Set(2)
    stage.GetRootLayer().Save()
    aliases.write_text(json.dumps({"fuel tank": ["customtank"]}))
    assert module.main(["--stage", str(stage_path), "--output", str(output), "--scene-id", "FireAcademy",
                        "--aliases", str(aliases), "--class", "fuel tank"]) == 0
    payload = json.loads(output.read_text())
    assert payload["scene_id"] == "FireAcademy"
    assert payload["candidates"][0]["semantic_hints"] == ["fuel tank"]
    assert payload["candidates"][0]["size_xyz_m"] == [2., 2., 2.]
    aliases.write_text(json.dumps({"fuel tank": []}))
    with pytest.raises(SystemExit):
        module.main(["--stage", str(stage_path), "--output", str(output), "--aliases", str(aliases)])
