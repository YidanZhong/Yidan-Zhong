#!/usr/bin/env python3
"""Build a scene-specific upstream-paper evaluation manifest.

Protocol source: RAVEN (arXiv 2509.23563) Table A.3 pins 10 tasks for the
``Neighborhood`` scene (4 Type I + 3 Type II + 3 Type III), and the evaluation
section states "each environment is tested with three starting poses".  The
paper does not say explicitly that every task runs from every pose; this
builder adopts the natural product -- **10 tasks x 3 starts = 30 episodes** --
and records that interpretation in the manifest note and the docs.

Starts are chosen deterministically from a reviewed template manifest (the
paired UGV+UAV starts the pool sampler already produced): the three episodes
whose UGV starts maximise the minimum pairwise distance, so the three poses
spread over the traversable map instead of clustering.

Everything else follows the existing UGV-centric smoke builder
(``scripts/build_ugv_ogn_smoke_episodes.py``): the task catalog supplies the
goal set (``M`` is the evaluator's job), the reviewed annotations supply the
confirmation-region ids, the query string carries the paper word list plus the
auxiliary LVLM-cue labels the mapper's multi-label softmax needs, and the
template supplies ``starts``/``difficulty``/``ground_truth`` (the current
calibrated packages).

Timezone-free, offline: only reads the catalog/targets/templates and writes the
draft manifest.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import math
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parent.parent
BENCHMARK_ROOT = REPO_ROOT / "benchmark"
if str(BENCHMARK_ROOT) not in sys.path:
    sys.path.insert(0, str(BENCHMARK_ROOT))

from airground_benchmark.episode_manifest import EpisodeManifest, EpisodeSpec  # noqa: E402
from airground_benchmark.scenes import scene_slug  # noqa: E402
from airground_benchmark.ground_truth import load_target_annotations  # noqa: E402
from airground_benchmark.task_catalog import (  # noqa: E402
    TaskCatalogEntry,
    find_catalog_entry,
    load_task_catalog,
)

# Upstream RAVEN runs the mapper with auxiliary labels suggested by the LVLM
# (paper Fig. 2 / Sec. III-D); the multi-label softmax needs more than the
# single query class.  Same stand-in list as the smoke builder.
AUXILIARY_CUES: tuple[str, ...] = ("sidewalk", "building", "road")
#: Default per-episode simulated budget.  The paper's time budget T is not
#: reported; the repo's episode default is 300 simulated seconds.
DEFAULT_TIMEOUT_S = 300
#: The episode schema caps the declared ``targets`` list at three (the pool
#: sampler's 1-3 convention).  That list is a declaration/GT subset, not the
#: scored goal set -- the evaluator's ``M`` comes from the task catalog, which
#: is unbounded (the house task resolves 18 reachable instances).
MAX_DECLARED_TARGETS = 3


def _load_episodes(path: Path) -> dict[str, dict]:
    payload = json.loads(path.expanduser().resolve(strict=True).read_text(encoding="utf-8"))
    episodes = payload.get("episodes")
    if not isinstance(episodes, list):
        raise SystemExit(f"{path} does not contain an episode list")
    return {str(episode["episode_id"]): episode for episode in episodes}


def _ugv_start_xy(episode: dict) -> tuple[float, float]:
    start = (episode.get("starts") or {}).get("ugv") or {}
    return float(start.get("x_m", 0.0)), float(start.get("y_m", 0.0))


def select_starts(templates: dict[str, dict], count: int) -> list[str]:
    """Pick ``count`` template episode ids whose UGV starts spread out most."""

    if count < 1:
        raise SystemExit("--starts must be >= 1")
    ids = sorted(templates)
    if len(ids) < count:
        raise SystemExit(f"need {count} start templates, got {len(ids)}")
    if count == 1:
        return [ids[0]]
    best: tuple[float, tuple[str, ...]] | None = None
    for combo in itertools.combinations(ids, count):
        points = [_ugv_start_xy(templates[item]) for item in combo]
        spread = min(
            math.dist(points[a], points[b])
            for a, b in itertools.combinations(range(len(points)), 2)
        )
        candidate = (spread, combo)
        if best is None or candidate[0] > best[0] + 1e-9 or (
            abs(candidate[0] - best[0]) <= 1e-9 and candidate[1] < best[1]
        ):
            best = candidate
    assert best is not None
    return list(best[1])


def episode_task_type(entry: TaskCatalogEntry) -> str:
    """Map a Table A.3 task to the manifest's task_type."""

    if entry.family == "type_iii":
        return "sequential_target"
    if entry.family == "type_ii":
        return "unordered_multi_target"
    return "single_target" if entry.m <= 1 else "unordered_multi_target"


def ordered_goal_ids(entry: TaskCatalogEntry) -> list[str]:
    """Goal instance ids; sequential tasks follow their declared phase order."""

    if not entry.sequence_classes:
        return list(entry.goal_instance_ids)
    ordered: list[str] = []
    resolutions = {resolution.requested_class: resolution for resolution in entry.class_resolutions}
    for phase in entry.sequence_classes:
        for requested_class in phase:
            resolution = resolutions.get(requested_class)
            if resolution is None:
                continue
            for instance_id in resolution.reachable_instance_ids:
                if instance_id not in ordered:
                    ordered.append(instance_id)
    ordered.extend(item for item in entry.goal_instance_ids if item not in ordered)
    return ordered


def _ground_truth_block(
    *,
    targets_path: Path,
    traversability_path: Path | None,
    confirmation_regions_path: Path | None,
) -> dict[str, str]:
    """Ground-truth pointers for every episode (checksum over the targets file)."""

    targets = targets_path.expanduser().resolve(strict=True)
    block = {
        "targets": str(targets),
        "confirmation_regions": str(
            (confirmation_regions_path or targets_path).expanduser().resolve(strict=True)
        ),
        "checksum_sha256": hashlib.sha256(targets.read_bytes()).hexdigest(),
    }
    if traversability_path is not None:
        block["traversability"] = str(traversability_path.expanduser().resolve(strict=True))
    return block


def _declared_target_ids(goal_ids: list[str], task_type: str) -> list[str]:
    """Pick the episode's declared targets (schema cap: three).

    Sequential tasks keep one instance per phase first so the declared order
    still reads as the paper's reveal order; the remaining slots fill in goal
    order.  ``M`` itself is the catalog's, never this list.
    """

    if len(goal_ids) <= MAX_DECLARED_TARGETS:
        return list(goal_ids)
    if task_type != "sequential_target":
        return list(goal_ids[:MAX_DECLARED_TARGETS])
    ordered: list[str] = []
    seen_classes: set[str] = set()
    for instance_id in goal_ids:
        prefix = instance_id.rsplit(".", 1)[0]
        if prefix not in seen_classes:
            seen_classes.add(prefix)
            ordered.append(instance_id)
        if len(ordered) == MAX_DECLARED_TARGETS:
            return ordered
    for instance_id in goal_ids:
        if instance_id not in ordered:
            ordered.append(instance_id)
        if len(ordered) == MAX_DECLARED_TARGETS:
            break
    return ordered


def build_manifest(
    *,
    catalog_path: Path,
    targets_path: Path,
    template_episodes_path: Path,
    starts: int,
    timeout_s: int,
    ground_truth: dict[str, str] | None = None,
) -> EpisodeManifest:
    catalog = load_task_catalog(catalog_path)
    targets = load_target_annotations(targets_path)
    templates = _load_episodes(template_episodes_path)
    if targets.scene_id != catalog.scene_id or any(
        row.get("scene_id") != catalog.scene_id for row in templates.values()
    ):
        raise SystemExit("catalog, annotations and start templates must belong to the same scene")
    prefix = scene_slug(catalog.scene_id)
    start_ids = select_starts(templates, starts)
    regions_by_instance = {
        instance.instance_id: instance.confirmation_region_id for instance in targets.instances
    }
    instances_by_id = {instance.instance_id: instance for instance in targets.instances}

    episodes: list[EpisodeSpec] = []
    counts = {"single_target": 0, "unordered_multi_target": 0, "sequential_target": 0}
    for entry in catalog.entries:
        if entry.status == "blocked":
            raise SystemExit(f"paper task {entry.task_id} is blocked")
        task_type = episode_task_type(entry)
        goal_ids = ordered_goal_ids(entry)
        if not goal_ids:
            raise SystemExit(f"paper task {entry.task_id} resolved no goal instances")
        declared = _declared_target_ids(goal_ids, task_type)
        for index, template_id in enumerate(start_ids, start=1):
            template = templates[template_id]
            target_rows = []
            for position, instance_id in enumerate(declared):
                instance = instances_by_id.get(instance_id)
                if instance is None:
                    raise SystemExit(f"goal {instance_id} is not in the reviewed annotations")
                region_id = regions_by_instance.get(instance_id)
                if not region_id:
                    raise SystemExit(f"goal {instance_id} has no confirmation region")
                row = {
                    "query_id": f"q{position}",
                    "semantic_class": instance.semantic_class,
                    "instance_id": instance_id,
                    "confirmation_region_id": region_id,
                }
                if task_type == "sequential_target":
                    row["sequence_index"] = position
                target_rows.append(row)
            episodes.append(
                EpisodeSpec.model_validate(
                    {
                        "episode_id": f"{prefix}-paper-{entry.task_id.removeprefix(prefix + '-')}-s{index}",
                        "seed": 92000 + len(episodes),
                        "split": "public",
                        "release_channel": "public",
                        "difficulty_version": template["difficulty_version"],
                        "scene_id": template["scene_id"],
                        "task_type": task_type,
                        "query": ", ".join(entry.query_classes + AUXILIARY_CUES),
                        "timeout_s": timeout_s,
                        "starts": template["starts"],
                        "targets": target_rows,
                        "difficulty": template["difficulty"],
                        "ground_truth": ground_truth or template["ground_truth"],
                    }
                )
            )
            counts[task_type] += 1
    return EpisodeManifest.model_validate(
        {
            "schema_version": "1.0.0",
            "catalog_id": f"benchmark-v1.0-{prefix}",
            "scene_id": catalog.scene_id,
            "split": "public",
            "release_channel": "public",
            "difficulty_version": episodes[0].difficulty_version,
            "public": True,
            "zero_shot": True,
            "status": "draft",
            "expected_counts": {
                "total": len(episodes),
                "single_target": counts["single_target"],
                "unordered_multi_target": counts["unordered_multi_target"],
                "sequential_target": counts["sequential_target"],
            },
            "episodes": [episode.model_dump(mode="json") for episode in episodes],
        }
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", required=True, type=Path)
    parser.add_argument("--targets", required=True, type=Path)
    parser.add_argument(
        "--template-episodes",
        required=True,
        type=Path,
        help="reviewed episode manifest supplying starts/difficulty/ground_truth",
    )
    parser.add_argument("--starts", type=int, default=3, help="starting poses per task (paper: 3)")
    parser.add_argument("--timeout-s", type=int, default=DEFAULT_TIMEOUT_S)
    parser.add_argument(
        "--ground-truth-traversability",
        type=Path,
        help="traversability npz to record in every episode's ground_truth block",
    )
    parser.add_argument(
        "--ground-truth-confirmation-regions",
        type=Path,
        help="confirmation-region manifest (default: the --targets file)",
    )
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    ground_truth = _ground_truth_block(
        targets_path=args.targets,
        traversability_path=args.ground_truth_traversability,
        confirmation_regions_path=args.ground_truth_confirmation_regions,
    )
    manifest = build_manifest(
        catalog_path=args.catalog,
        targets_path=args.targets,
        template_episodes_path=args.template_episodes,
        starts=args.starts,
        timeout_s=args.timeout_s,
        ground_truth=ground_truth,
    )
    # The manifest schema is strict (extra keys rejected); the protocol note
    # lives in this docstring and docs/development instead of in the payload.
    payload = manifest.model_dump(mode="json")
    args.output.expanduser().write_text(
        json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    for episode in manifest.episodes:
        print(episode.episode_id, episode.task_type, "targets=", len(episode.targets))
    print(
        "total",
        len(manifest.episodes),
        "counts",
        payload["expected_counts"],
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
