"""Export complete per-instance geometric candidates without approving any GT.

This private diagnostic format intentionally differs from arrival_regions.npz:
each instance has its own flat-index array, preserving overlapping regions.
It is not a scoring input and has no visibility or human-review claims.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
from pathlib import Path
import sys
import time
from typing import Any

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "benchmark"))
from airground_benchmark.ground_truth import TraversabilityMetadata, load_target_annotations
from airground_benchmark.roi_analysis import surface_window
from airground_benchmark.scenes import is_paper_class


def digest(path: Path) -> str:
    checksum = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            checksum.update(chunk)
    return checksum.hexdigest()


def export_candidates(postprocess: Path, targets: Path, output: Path) -> dict[str, Any]:
    started = time.monotonic()
    if (postprocess / "INVALIDATED.json").exists():
        raise ValueError("Map contract was invalidated; preserve evidence and resample before exporting candidates")
    target_hash = digest(targets)
    report = json.loads((postprocess / "report.json").read_text(encoding="utf-8"))
    if report["status"] != "passed" or report["formal_gt_approved"]:
        raise ValueError("Expected a completed, explicitly unreviewed diagnostic map")
    if report["targets_sha256"] != target_hash:
        raise ValueError("Target hash differs from the sampled scene contract")
    manifest = load_target_annotations(targets)
    if any(instance.verified for instance in manifest.instances):
        raise ValueError("This tool accepts only wholly unreviewed annotations")
    paper_instances = sorted((instance for instance in manifest.instances
                              if is_paper_class(manifest.scene_id, instance.semantic_class)),
                             key=lambda instance: instance.instance_id)
    coverage_file = postprocess / "component-report.unreviewed.json"
    if digest(coverage_file) != report["files"][coverage_file.name]["sha256"]:
        raise ValueError("Component report hash mismatch")
    coverage = json.loads(coverage_file.read_text(encoding="utf-8"))
    if [instance.instance_id for instance in paper_instances] != sorted(item["instance_id"] for item in coverage["targets"]):
        raise ValueError("Paper target identities differ from postprocessed component selection")
    metadata_file = postprocess / "reach/reach.metadata.yaml"
    if digest(metadata_file) != report["files"]["reach/reach.metadata.yaml"]["sha256"]:
        raise ValueError("Reach metadata hash mismatch")
    metadata = TraversabilityMetadata.model_validate_json(metadata_file.read_text(encoding="utf-8"))
    if metadata.scene_id != manifest.scene_id or metadata.frame != manifest.frame or metadata.resolution_m != .05:
        raise ValueError("Scene/frame/resolution mismatch")
    if any(abs(value) > 1e-10 for instance in manifest.instances for value in instance.obb.orientation_rpy_rad[:2]):
        raise ValueError("Planar OBB distance requires zero roll/pitch")
    npz = postprocess / "reach/reach.npz"
    map_hash = digest(npz)
    if map_hash != report["exports"]["reach"]["npz_sha256"] or map_hash != metadata.npz_sha256:
        raise ValueError("Reach map hash mismatch")
    selected = int(report["selected_component"]["component_id"])
    with np.load(npz, allow_pickle=False) as data:
        allowed = (data["component"] == selected) & data["mask"].astype(bool)
    if allowed.shape != tuple(metadata.shape) or not allowed.any():
        raise ValueError("Invalid or empty selected component")
    if manifest.instances and len(manifest.instances) > np.iinfo(np.uint16).max:
        raise ValueError("Too many annotations for diagnostic overlap counter")
    output.mkdir(parents=True, exist_ok=False)
    arrays: dict[str, np.ndarray] = {}
    overlap = np.zeros(metadata.shape, dtype=np.uint16)
    entries = []
    for index, instance in enumerate(paper_instances):
        window, distances = surface_window(instance.obb, metadata, maximum=8.)
        mask = allowed[window] & (distances >= 1.5) & (distances <= 8.)
        rows, cols = np.nonzero(mask)
        flat = (rows.astype(np.int64) + window[0].start) * metadata.shape[1] + cols + window[1].start
        key = f"instance_{index:04d}_flat_cells"
        arrays[key] = flat.astype(np.uint32 if allowed.size <= np.iinfo(np.uint32).max else np.uint64)
        overlap[window] += mask.astype(np.uint16)
        entries.append({"instance_id": instance.instance_id, "array_key": key, "cell_count": len(flat),
                        "usd_prim_path": instance.usd_prim_path, "verified": False,
                        "scoring_eligible": False, "visibility_checked": False,
                        "distance_reference": "obb_surface_xy", "window_m": [1.5, 8.],
                        "component_id": selected,
                        "minimum_distance_m": float(distances[mask].min()) if len(flat) else None,
                        "maximum_distance_m": float(distances[mask].max()) if len(flat) else None})
        logging.info("Candidate %s: %d cells, human review pending", instance.instance_id, len(flat))
    target = output / "geometric-candidates.unreviewed.npz"
    np.savez_compressed(target, **arrays)
    with np.load(target, allow_pickle=False) as saved:
        for key, expected in arrays.items():
            if not np.array_equal(saved[key], expected):
                raise RuntimeError("Saved per-instance cells differ")
            if len(expected) and (not np.all(allowed.reshape(-1)[expected]) or np.any(np.diff(expected.astype(np.int64)) <= 0)):
                raise RuntimeError("Candidate cells escaped component or are duplicated")
    if digest(targets) != target_hash:
        raise RuntimeError("Input annotations changed during read-only export")
    result = {"scope": "private_unreviewed_geometry_only_not_scoring_input", "scene_id": manifest.scene_id,
              "formal_gt_approved": False, "status": "diagnostic_prepared",
              "input_targets_sha256": target_hash, "input_map_sha256": map_hash,
              "input_report_sha256": digest(postprocess / "report.json"),
              "scene_contract_sha256": report["contract_sha256"],
              "source_sha256": {"script": digest(Path(__file__)),
                                  "roi_analysis.py": digest(Path(__file__).resolve().parents[1] / "benchmark/airground_benchmark/roi_analysis.py")},
              "metadata": metadata.model_dump(mode="json"), "selected_component": selected,
              "input_annotation_count": len(manifest.instances), "paper_target_count": len(paper_instances),
              "entries": entries, "overlap_cells": int((overlap > 1).sum()),
              "max_instances_per_cell": int(overlap.max()), "union_cells": int((overlap > 0).sum()),
              "sum_instance_cells": int(sum(e["cell_count"] for e in entries)),
              "output_sha256": digest(target), "readback_equal": True,
              "input_targets_unchanged": True, "elapsed_s": time.monotonic() - started,
              "limitations": ["Unbound and unreviewed geometry remains in this diagnostic only.",
                              "No target annotation, verified/reachable flag, or visibility value was changed.",
                              "This preserves overlapping candidates but does not change the official arrival format.",
                              "Collision-profile or coordinate changes invalidate these candidates."]}
    (output / "index.unreviewed.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("postprocess", "targets", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    result = export_candidates(args.postprocess, args.targets, args.output)
    logging.info("Saved %d candidate instances; %d overlapping cells", len(result["entries"]), result["overlap_cells"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
