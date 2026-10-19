#!/usr/bin/env python3
"""Prepare handover S1-S3 from real local files; never synthesize reviewed GT.

Run with the isolated Python environment containing usd-core and this package.
Outputs are evaluator-private, under an ignored runs directory. S4-S10 require
actual renderer/PhysX evidence and remain pending regardless of binding count.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "benchmark"))
from airground_benchmark.ground_truth import (
    UsdPrimCandidateManifest, bind_target_annotations_to_usd_prims,
    build_target_review_ledger_template, canonical_target_annotations_json,
    convert_rayfronts_bbox_annotations,
)
from airground_benchmark.roi_analysis import annotation_roi
from airground_benchmark.scenes import (
    SCENE_IDS, SCENE_REVIEW_NOTES, EXTRA_USD_ALIASES, paper_classes, paper_class_key,
)
from airground_benchmark.task_catalog import build_task_catalog


def write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def prepare(scene: str, output: Path) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    source = ROOT / "RayFronts/rayfronts/annotations" / f"{scene}.json"
    manifest = convert_rayfronts_bbox_annotations(
        source, scene_id=scene, spawn_offset_xyz_m=(0., 0., 0.),
        source_path=source.relative_to(ROOT).as_posix(),
    )
    (output / "targets.converted.json").write_text(canonical_target_annotations_json(manifest), encoding="utf-8")
    classes = sorted({item.semantic_class for item in manifest.instances})
    missing = sorted(c for c in paper_classes(scene) if paper_class_key(c) not in {paper_class_key(v) for v in classes})
    summary = {
        "scene_id": scene, "annotation_count": len(manifest.instances),
        "source_annotation_sha256": sha256(source), "annotation_classes": classes,
        "missing_paper_classes": missing, "notes": SCENE_REVIEW_NOTES.get(scene, ()),
        "spawn_offset_xyz_m": [0, 0, 0],
        "coordinate_status": "upstream world coordinates retained; runtime transform still needs verification",
        "S1": "converted", "S2": "blocked_missing_usd", "S3": "blocked_missing_usd",
        "S4_S10": "pending_real_RGB_review_PhysX_GT_and_UGV_runtime",
        "verified_count": 0, "ground_reachable_count": 0,
    }
    # These are requested settings for a future real raycast, NOT measured GT.
    write_json(output / "raycast.request.json", {
        "scene_id": scene, "status": "not_executed", "roi": annotation_roi(manifest, margin_m=2, resolution_m=.05),
        "raycast_z_m": [8, -2], "min_normal_z": .35, "obstacle_height_band_m": [.05, 1.0],
        "support_plane_top_z_m": 0, "footprint_m": [.508, .430], "yaw_samples": 16,
        "max_slope_deg": 15, "max_step_m": .05, "overhead_clearance_m": .5,
        "reach_clearance_m": .1075, "connectivity": 8, "reach_window_m": [1.5, 8],
        "component_selection": "target_coverage_desc_then_area_desc",
        "visibility": {"camera_height_m": 1.2, "horizontal_fov_deg": 90, "range_m": [1.5, 8],
                       "surface_points": 5, "min_visible_fraction": .2, "consecutive_frames": 5},
        "note": "ROI from all annotation OBBs. Support-plane extents and runtime transform require scene review.",
    })
    scene_dir = ROOT / "AirStack/scenes" / scene
    stages = sorted(p for p in scene_dir.glob("*.usd*") if p.suffix.lower() in (".usd", ".usda", ".usdc"))
    if len(stages) == 1:
        stage = stages[0]
        aliases = output / "usd_aliases.json"
        write_json(aliases, EXTRA_USD_ALIASES)
        candidates_path = output / "prim_candidates.json"
        command = [sys.executable, str(ROOT / "AirStack/simulation/isaac-sim/tools/export_target_prim_candidates.py"),
                   "--stage", str(stage), "--output", str(candidates_path), "--scene-id", scene,
                   "--root-prefix", "/World/stage", "--min-volume", "0.1", "--aliases", str(aliases)]
        for name in classes:
            command.extend(("--class", name))
        with (output / "export.log").open("w", encoding="utf-8") as log:
            result = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, check=False)
        summary.update(usd_path=stage.relative_to(ROOT).as_posix(), usd_sha256=sha256(stage), export_exit_code=result.returncode)
        write_json(output / "export.command.json", command)
        candidate_payload = json.loads(candidates_path.read_text(encoding="utf-8")) if result.returncode == 0 else {}
        if result.returncode == 0 and candidate_payload.get("candidates"):
            prims = UsdPrimCandidateManifest.model_validate_json(candidates_path.read_text(encoding="utf-8"))
            manifest, report = bind_target_annotations_to_usd_prims(manifest, prims, max_center_distance_m=3.)
            write_json(output / "binding.report.json", report.model_dump(mode="json"))
            summary.update(S2="exported_real_USD", S3="automatic_binding_pending_review",
                           candidate_count=len(prims.candidates), bound_count=sum(bool(i.usd_prim_path) for i in manifest.instances))
            summary["unbound_by_class"] = dict(Counter(i.semantic_class for i in manifest.instances if not i.usd_prim_path))
            summary["ambiguous_count"] = report.ambiguous_count
        elif result.returncode == 0:
            summary.update(S2="real_USD_has_no_semantic_name_candidates", S3="blocked_no_candidates",
                           candidate_count=0, bound_count=0,
                           unbound_by_class=dict(Counter(i.semantic_class for i in manifest.instances)))
        else:
            summary.update(S2="export_failed_see_log", S3="blocked_export_failed")
    elif len(stages) > 1:
        summary.update(S2="blocked_multiple_USD_roots_require_selection", S3="blocked_ambiguous_stage")
    (output / "targets.unreviewed.json").write_text(canonical_target_annotations_json(manifest), encoding="utf-8")
    queue = {"scene_id": scene, "rows": [
        {"instance_id": item.instance_id, "usd_prim_path": item.usd_prim_path,
         "priority": index, "issues": ["real_RGB_review_required"] + ([] if item.usd_prim_path else ["unbound"])}
        for index, item in enumerate(manifest.instances)
    ]}
    write_json(output / "review.queue.json", queue)
    ledger = build_target_review_ledger_template(manifest, queue, review_version="scene-gt-handover-draft")
    write_json(output / "review.ledger.template.json", ledger.model_dump(mode="json"))
    catalog = build_task_catalog(manifest, source_annotation_path=str(output / "targets.unreviewed.json"))
    write_json(output / "task_catalog.blocked.json", catalog.model_dump(mode="json"))
    summary.update(task_count=catalog.task_count, blocked_task_count=catalog.blocked_count)
    write_json(output / "summary.json", summary)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scene", action="append", choices=SCENE_IDS)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    results = []
    for scene in args.scene or SCENE_IDS[1:]:
        result = prepare(scene, output / scene)
        results.append(result)
        print(json.dumps(result, ensure_ascii=False), flush=True)
    write_json(output / "summary.json", {"status": "cpu_preparation_only", "scenes": results})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
