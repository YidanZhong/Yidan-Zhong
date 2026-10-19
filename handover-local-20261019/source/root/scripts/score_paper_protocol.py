#!/usr/bin/env python3
"""Score a paper-protocol run directory and print the aggregate.

Wraps the documented evaluation entry points for the 30-episode
RetroNeighborhood set (``docs/development/ugv-ogn/ugv-ogn-paper-protocol-eval.md``):

1. every ``<run>/episodes/<id>/trajectory.parquet`` (or the top-level
   ``trajectory.parquet``) is scored with ``airground metrics ugv-progress``
   against the reviewed task catalog -- ``--task-id`` is recovered from the
   episode id (``retro-paper-<task>-s<k>`` -> ``retro-<task>``);
2. the per-episode JSONs are aggregated with
   ``airground metrics aggregate-progress`` (suite + per-family Progress / PPL /
   SR / SPL) and a per-task K/M table is printed.

Failed episodes keep their trajectory artifact, so they score as ``K=0``
rather than being skipped -- the benchmark's failures are data.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CATALOG = "runs/p1_09_episode/paper_protocol_20261005/task_catalog.json"
DEFAULT_TARGETS = (
    "runs/p1_05_targets/p1_05_red_car_binding_20260930/reach_recalibrated/"
    "targets.reviewed.with_regions.json"
)
DEFAULT_ARRIVAL_DIR = "runs/p1_05_targets/p1_05_red_car_binding_20260930/reach_recalibrated"
DEFAULT_TRAV_PACKAGE = "runs/p1_03_traversability/p1_03_single_gpu_0p05_full_20260930_r2_native/package"


def task_id_from_episode(episode_id: str) -> str:
    """``retro-paper-type-i-bus-stop-s2`` -> ``retro-type-i-bus-stop``."""

    match = re.fullmatch(r"([a-z0-9-]+)-paper-(type-i{1,3}-.+)-s([1-9][0-9]*)", episode_id)
    if match is None:
        raise SystemExit(f"cannot recover the task id from {episode_id!r}")
    return f"{match.group(1)}-{match.group(2)}"



def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--scores-dir", required=True, type=Path)
    parser.add_argument("--budget-s", type=float, default=300.0)
    parser.add_argument("--catalog", default=DEFAULT_CATALOG)
    parser.add_argument("--targets", default=DEFAULT_TARGETS)
    parser.add_argument("--arrival-dir", default=DEFAULT_ARRIVAL_DIR)
    parser.add_argument("--traversability-package", default=DEFAULT_TRAV_PACKAGE)
    args = parser.parse_args()

    run_dir = args.run_dir.expanduser().resolve(strict=True)
    scores_dir = args.scores_dir.expanduser()
    scores_dir.mkdir(parents=True, exist_ok=True)
    catalog = REPO_ROOT / args.catalog
    targets = REPO_ROOT / args.targets
    arrival_dir = REPO_ROOT / args.arrival_dir
    trav_package = REPO_ROOT / args.traversability_package
    trav_npz = next(trav_package.glob("*.npz"))
    trav_meta = next(trav_package.glob("*.metadata.yaml"))

    episode_dirs = sorted(
        path for path in (run_dir / "episodes").glob("*") if path.is_dir()
    )
    if not episode_dirs:
        raise SystemExit(f"no episode directories under {run_dir / 'episodes'}")

    reports: list[Path] = []
    for episode_dir in episode_dirs:
        trajectory = episode_dir / "trajectory.parquet"
        if not trajectory.is_file():
            print(f"skip {episode_dir.name}: no trajectory.parquet", file=sys.stderr)
            continue
        episode_id = episode_dir.name
        task_id = task_id_from_episode(episode_id)
        output = scores_dir / f"{episode_id}.json"
        command = [
            str(Path(sys.executable).with_name("airground")),
            "metrics",
            "ugv-progress",
            "--trajectory",
            str(trajectory),
            "--targets",
            str(targets),
            "--catalog",
            str(catalog),
            "--task-id",
            task_id,
            "--budget-s",
            str(args.budget_s),
            "--window-start-s",
            "0",
            "--episode-id",
            episode_id,
            "--traversability-npz",
            str(trav_npz),
            "--traversability-metadata",
            str(trav_meta),
            "--arrival-regions",
            str(arrival_dir / "arrival_regions.npz"),
            "--arrival-region-index",
            str(arrival_dir / "region_index.json"),
            "--output",
            str(output),
        ]
        result = subprocess.run(command, cwd=REPO_ROOT, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"score failed for {episode_id}: {result.stderr.strip()[:300]}", file=sys.stderr)
            continue
        reports.append(output)

    if not reports:
        raise SystemExit("no per-episode reports were produced")

    aggregate_command = [
        str(Path(sys.executable).with_name("airground")),
        "metrics",
        "aggregate-progress",
    ]
    for report in reports:
        aggregate_command += ["--report", str(report)]
    aggregate_command += ["--output", str(scores_dir / "aggregate.json")]
    subprocess.run(aggregate_command, cwd=REPO_ROOT, check=True)

    rows = [json.loads(report.read_text(encoding="utf-8")) for report in reports]
    print(f"{'episode':<44} {'task':<46} K/M  Prog   PPL    SR  SPL")
    for row in sorted(rows, key=lambda item: str(item.get("episode_id"))):
        print(
            "%-44s %-46s %d/%-2d %.2f  %-6s %-3d %s"
            % (
                row.get("episode_id"),
                row.get("task_id"),
                row.get("k"),
                row.get("m"),
                row.get("progress") or 0.0,
                ("%.3f" % row["ppl"]) if row.get("ppl") is not None else "-",
                row.get("sr") or 0,
                ("%.3f" % row["spl"]) if row.get("spl") is not None else "-",
            )
        )
    aggregate = json.loads((scores_dir / "aggregate.json").read_text(encoding="utf-8"))
    print()
    print(
        "suite: episodes=%s tasks=%s mean_progress=%.4f mean_ppl=%s sr=%.4f spl=%s"
        % (
            aggregate.get("episode_count"),
            aggregate.get("task_count"),
            aggregate.get("mean_progress") or 0.0,
            aggregate.get("mean_ppl"),
            aggregate.get("sr") or 0.0,
            aggregate.get("spl"),
        )
    )
    for family in aggregate.get("families", []):
        print(
            "  %-10s episodes=%s mean_progress=%.4f mean_ppl=%s sr=%.4f spl=%s"
            % (
                family.get("family"),
                family.get("episode_count"),
                family.get("mean_progress") or 0.0,
                family.get("mean_ppl"),
                family.get("sr") or 0.0,
                family.get("spl"),
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
