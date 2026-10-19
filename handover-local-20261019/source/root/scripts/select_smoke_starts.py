#!/usr/bin/env python3
"""Pick the three UGV-OGN smoke episodes (one per paper family) on the recalibrated map.

2026-09-24 workflow (CPU only, no GPU):

1. read the upstream release-pair public manifest that was regenerated on the
   ``1.5x UGV width`` reachable region (limited to the selected component),
2. walk the episodes family by family (Type I = single target, Type II =
   unordered multi target, Type III = sequential target) in manifest order,
3. accept the first episode per family whose start

   * lies inside the selected reachable component,
   * is at least ``--min-start-arrival-distance`` away from every queried
     target's dense arrival region (so K cannot be 1 at t = 0),
   * keeps every queried target invisible from both the UGV camera (0.3 m) and
     the docked UAV camera (0.45 m), and
   * does not reuse a start already taken by another family,

4. write the smoke episode manifest plus a selection report listing every
   rejected candidate and its reason.  If a family has no qualifying episode the
   script fails closed instead of falling back to an inherited start.

The input is the paper-task-filtered candidate pool
(``scripts/filter_paper_task_candidates.py``) rather than the 60-episode public
manifest: restricting the pool to Table A.3 tasks leaves too few candidates for
the 30/15/15 sampler, and the smoke lane only needs one episode per family.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import sys

import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent
BENCHMARK_ROOT = REPO_ROOT / "benchmark"
if str(BENCHMARK_ROOT) not in sys.path:
    sys.path.insert(0, str(BENCHMARK_ROOT))

from airground_benchmark.episode_manifest import (  # noqa: E402
    EpisodeManifest,
    EpisodeSpec,
    canonical_episode_manifest_json,
)
from airground_benchmark.ground_truth import (  # noqa: E402
    evaluate_target_visibility_at_pose,
    load_arrival_region_labels,
    load_target_annotations,
    load_traversability_metadata,
)
from airground_benchmark.task_catalog import NEIGHBORHOOD_UPSTREAM_TASKS, upstream_tasks  # noqa: E402

from airground_benchmark.scenes import scene_slug, paper_class_key

FAMILIES: tuple[tuple[str, str, str, int, int], ...] = (
    ("type-i", "single_target", "retro-ugv-smoke-type-i", 91001, 600),
    ("type-ii", "unordered_multi_target", "retro-ugv-smoke-type-ii", 91002, 900),
    ("type-iii", "sequential_target", "retro-ugv-smoke-type-iii", 91003, 900),
)

#: Paper Table A.3 class sets per family, e.g. ``frozenset({"bus stop", "blue container"})``.
PAPER_TASK_CLASS_SETS: dict[str, tuple[frozenset[str], ...]] = {
    "single_target": tuple(
        frozenset(task.query_classes)
        for task in NEIGHBORHOOD_UPSTREAM_TASKS
        if task.family == "type_i"
    ),
    "unordered_multi_target": tuple(
        frozenset(task.query_classes)
        for task in NEIGHBORHOOD_UPSTREAM_TASKS
        if task.family == "type_ii"
    ),
    "sequential_target": tuple(
        frozenset(task.query_classes)
        for task in NEIGHBORHOOD_UPSTREAM_TASKS
        if task.family == "type_iii"
    ),
}


def _matches_paper_task(task_type: str, classes: frozenset[str], scene_id: str = "RetroNeighborhood") -> bool:
    """True when the candidate's class set is one of the paper's tasks for this family."""

    return _paper_task_for(task_type, classes, scene_id) is not None


def _paper_task_for(task_type: str, classes: frozenset[str], scene_id: str = "RetroNeighborhood"):
    """Return the Table A.3 task whose class set matches (first in paper order)."""

    family = {
        "single_target": "type_i",
        "unordered_multi_target": "type_ii",
        "sequential_target": "type_iii",
    }[task_type]
    for task in upstream_tasks(scene_id):
        if task.family == family and frozenset(map(paper_class_key, task.query_classes)) == frozenset(map(paper_class_key, classes)):
            return task
    return None


def _ordered_targets(candidate: dict, paper_task) -> list[dict]:
    """Reorder the candidate targets to the paper's class order for Type III."""

    targets = [dict(target) for target in candidate["targets"]]
    if paper_task.sequence_classes:
        order: list[str] = []
        for group in paper_task.sequence_classes:
            order.extend(group)
        position = {paper_class_key(name): index for index, name in enumerate(order)}
        targets.sort(key=lambda target: position.get(paper_class_key(target["semantic_class"]), len(order)))
        for index, target in enumerate(targets):
            target["sequence_index"] = index
    return targets


def _component_at(component: np.ndarray, metadata, x_m: float, y_m: float) -> int | None:
    col = math.floor((x_m - metadata.origin.x_m) / metadata.resolution_m)
    row = math.floor((y_m - metadata.origin.y_m) / metadata.resolution_m)
    rows, cols = component.shape
    if row < 0 or col < 0 or row >= rows or col >= cols:
        return None
    return int(component[row, col])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--candidate-pool",
        required=True,
        type=Path,
        help="paper-task-filtered candidate pool JSON",
    )
    parser.add_argument("--targets", required=True, type=Path)
    parser.add_argument("--reach-package-dir", required=True, type=Path)
    parser.add_argument("--arrival-regions", required=True, type=Path)
    parser.add_argument("--region-index", required=True, type=Path)
    parser.add_argument("--selected-component", required=True, type=int)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--min-start-arrival-distance", type=float, default=1.5)
    parser.add_argument("--ugv-camera-height", type=float, default=0.3)
    parser.add_argument("--uav-camera-height", type=float, default=0.45)
    args = parser.parse_args(argv)

    pool = json.loads(args.candidate_pool.read_text(encoding="utf-8"))
    pool_candidates = list(pool.get("candidates", []))
    targets = load_target_annotations(args.targets)
    package_dir = args.reach_package_dir.expanduser().resolve()
    metadata = load_traversability_metadata(next(package_dir.glob("*.metadata.yaml")))
    if not (pool["scene_id"] == targets.scene_id == metadata.scene_id):
        raise SystemExit("candidate pool, targets and traversability must share a scene")
    npz_path = next(package_dir.glob("*.npz"))
    with np.load(npz_path) as data:
        component = np.asarray(data["component"], dtype=np.int32)
    labels = load_arrival_region_labels(args.arrival_regions)
    index_payload = json.loads(args.region_index.read_text(encoding="utf-8"))
    label_by_instance = {
        str(row["instance_id"]): int(row["label"]) for row in index_payload.get("regions", [])
    }
    distance_cache: dict[int, np.ndarray] = {}

    def arrival_distance(instance_id: str, x_m: float, y_m: float) -> float | None:
        label = label_by_instance.get(instance_id)
        if label is None:
            return None
        cached = distance_cache.get(label)
        if cached is None:
            from scipy import ndimage  # type: ignore[import-not-found]

            cached = ndimage.distance_transform_edt(labels != label) * float(metadata.resolution_m)
            distance_cache[label] = cached
        col = math.floor((x_m - metadata.origin.x_m) / metadata.resolution_m)
        row = math.floor((y_m - metadata.origin.y_m) / metadata.resolution_m)
        rows, cols = cached.shape
        if row < 0 or col < 0 or row >= rows or col >= cols:
            return None
        return float(cached[row, col])

    output_dir = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    selected_starts: set[tuple[float, float]] = set()
    report: dict[str, object] = {
        "families": [],
        "min_start_arrival_distance_m": args.min_start_arrival_distance,
        "observer_heights_m": [args.ugv_camera_height, args.uav_camera_height],
        "candidate_pool": str(args.candidate_pool),
        "selected_component": int(args.selected_component),
        "status": "ok",
    }

    selected_specs: list[EpisodeSpec] = []
    for family, task_type, smoke_prefix, seed, timeout_s in FAMILIES:
        smoke_prefix = smoke_prefix.replace("retro-", scene_slug(pool["scene_id"]) + "-", 1)
        family_rows: list[dict[str, object]] = []
        chosen = None
        for candidate in pool_candidates:
            if candidate["task_type"] != task_type:
                continue
            start = candidate["starts"]["ugv"]
            start_x = float(start["x_m"])
            start_y = float(start["y_m"])
            reasons: list[str] = []
            classes = frozenset(target["semantic_class"] for target in candidate["targets"])
            if not _matches_paper_task(task_type, classes, pool["scene_id"]):
                reasons.append("not_a_paper_task (" + ", ".join(sorted(classes)) + ")")
            cell_component = _component_at(component, metadata, start_x, start_y)
            if cell_component != args.selected_component:
                reasons.append(f"start_outside_selected_component ({cell_component})")
            if (start_x, start_y) in selected_starts:
                reasons.append("duplicate_start")
            instance_ids = [target["instance_id"] for target in candidate["targets"]]
            for instance_id in instance_ids:
                distance = arrival_distance(instance_id, start_x, start_y)
                if distance is None:
                    reasons.append(f"arrival_region_missing ({instance_id})")
                elif distance < args.min_start_arrival_distance:
                    reasons.append(
                        f"start_inside_arrival_tolerance ({instance_id}: {distance:.3f} m)"
                    )
            if not reasons:
                visibility = evaluate_target_visibility_at_pose(
                    targets,
                    metadata,
                    npz_path,
                    observer_xy_m=(start_x, start_y),
                    observer_heights_m=(args.ugv_camera_height, args.uav_camera_height),
                    instance_ids=instance_ids,
                )
                visible = [
                    row.instance_id for row in visibility.results if row.visible
                ]
                if visible:
                    reasons.append("target_visible_from_start (" + ", ".join(visible) + ")")
                else:
                    chosen = (candidate, visibility)
            family_rows.append(
                {
                    "candidate_id": candidate["candidate_id"],
                    "query": candidate["query"],
                    "reasons": reasons,
                    "start_xy_m": [start_x, start_y],
                    "status": "selected" if chosen and chosen[0] is candidate else "rejected",
                    "target_instance_ids": instance_ids,
                }
            )
            if chosen is not None:
                break
        if chosen is None:
            report["status"] = "failed"
            report["families"].append({"family": family, "rows": family_rows, "selected": None})
            continue
        candidate, visibility = chosen
        selected_starts.add((start_x, start_y))
        paper_task = _paper_task_for(task_type, frozenset(
            target["semantic_class"] for target in candidate["targets"]
        ), pool["scene_id"])
        episode_targets = _ordered_targets(candidate, paper_task) if paper_task else candidate["targets"]
        selected_specs.append(
            EpisodeSpec.model_validate(
                {
                    "difficulty": candidate["difficulty"],
                    "difficulty_version": candidate["difficulty_version"]
                    if "difficulty_version" in candidate
                    else pool["difficulty_version"],
                    "episode_id": smoke_prefix,
                    "ground_truth": candidate["ground_truth"],
                    "query": paper_task.query_text if paper_task else candidate["query"],
                    "release_channel": "public",
                    "scene_id": pool["scene_id"],
                    "seed": seed,
                    "split": "public",
                    "starts": candidate["starts"],
                    "targets": episode_targets,
                    "task_type": candidate["task_type"],
                    "timeout_s": timeout_s,
                }
            )
        )
        report["families"].append(
            {
                "family": family,
                "rows": family_rows,
                "selected": {
                    "candidate_id": candidate["candidate_id"],
                    "episode_id": smoke_prefix,
                    "observer_heights_m": list(visibility.observer_heights_m),
                    "paper_task_id": paper_task.task_id if paper_task else None,
                    "paper_task_query": paper_task.query_text if paper_task else None,
                    "query": paper_task.query_text if paper_task else candidate["query"],
                    "start_xy_m": [candidate["starts"]["ugv"]["x_m"], candidate["starts"]["ugv"]["y_m"]],
                    "start_yaw_rad": candidate["starts"]["ugv"]["yaw_rad"],
                    "target_instance_ids": [
                        target["instance_id"] for target in episode_targets
                    ],
                    "visibility": [
                        {
                            "instance_id": row.instance_id,
                            "visible": row.visible,
                            "visible_point_count": row.visible_point_count,
                        }
                        for row in visibility.results
                    ],
                },
            }
        )

    smoke_manifest = EpisodeManifest.model_validate(
        {
            "schema_version": pool["schema_version"],
            "catalog_id": pool["catalog_id"],
            "scene_id": pool["scene_id"],
            "split": "public",
            "release_channel": "public",
            "difficulty_version": pool["difficulty_version"],
            "public": True,
            "zero_shot": True,
            "status": "draft",
            # The smoke lane reuses the catalog's 60-episode counts contract and
            # only materialises the three family episodes (same convention as
            # scripts/build_ugv_ogn_smoke_episodes.py).
            "expected_counts": {
                "total": 60,
                "single_target": 30,
                "unordered_multi_target": 15,
                "sequential_target": 15,
            },
            "episodes": [episode.model_dump(mode="json") for episode in selected_specs],
        }
    )
    (output_dir / "smoke_episodes.reach1p5w.json").write_text(
        canonical_episode_manifest_json(smoke_manifest), encoding="utf-8"
    )
    (output_dir / "smoke_start_selection.json").write_text(
        json.dumps(report, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "output_dir": str(output_dir),
                "selected": [
                    (row["selected"] or {}).get("episode_id") for row in report["families"]
                ],
                "status": report["status"],
            },
            sort_keys=True,
        )
    )
    return 0 if report["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
