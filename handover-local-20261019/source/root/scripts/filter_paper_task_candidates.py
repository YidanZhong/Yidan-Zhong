#!/usr/bin/env python3
"""Keep only candidate episodes whose class set is a RAVEN Table A.3 task.

2026-09-24: the UGV-OGN smoke lane must only use the paper's search targets for
RetroNeighborhood (Type I 4 tasks, Type II 3 tasks, Type III 3 tasks).  The
upstream candidate pool also contains reachable *scene* objects that are not part
of any paper task (trees, porches, chimneys, fountains), so this filter drops
those candidates before release sampling.
"""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parent.parent
BENCHMARK_ROOT = REPO_ROOT / "benchmark"
if str(BENCHMARK_ROOT) not in sys.path:
    sys.path.insert(0, str(BENCHMARK_ROOT))

from airground_benchmark.task_catalog import upstream_tasks  # noqa: E402
from airground_benchmark.scenes import paper_class_key  # noqa: E402

FAMILY_BY_TASK_TYPE = {
    "single_target": "type_i",
    "unordered_multi_target": "type_ii",
    "sequential_target": "type_iii",
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidates", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--report", type=Path, default=None)
    args = parser.parse_args(argv)

    pool = json.loads(args.candidates.read_text(encoding="utf-8"))
    allowed: dict[str, set[tuple[str, ...] | frozenset[str]]] = {
        task_type: set() for task_type in FAMILY_BY_TASK_TYPE
    }
    for task in upstream_tasks(pool["scene_id"]):
        task_type = {value: key for key, value in FAMILY_BY_TASK_TYPE.items()}[task.family]
        keys = tuple(paper_class_key(name) for name in task.query_classes)
        allowed[task_type].add(keys if task_type == "sequential_target" else frozenset(keys))

    kept: list[dict] = []
    dropped = Counter()
    for candidate in pool.get("candidates", []):
        targets = candidate["targets"]
        if candidate["task_type"] == "sequential_target":
            targets = sorted(targets, key=lambda target: target["sequence_index"])
        keys = tuple(paper_class_key(target["semantic_class"]) for target in targets)
        classes = keys if candidate["task_type"] == "sequential_target" else frozenset(keys)
        if classes in allowed.get(candidate["task_type"], set()):
            kept.append(candidate)
        else:
            dropped[", ".join(sorted(classes)) or "<empty>"] += 1

    filtered = dict(pool)
    filtered["candidates"] = kept
    filtered["source"] = str(pool.get("source", "")) + "+paper-tasks-only"
    args.output.write_text(
        json.dumps(filtered, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    report = {
        "candidates_in": len(pool.get("candidates", [])),
        "candidates_out": len(kept),
        "dropped_class_sets": dropped.most_common(20),
        "paper_task_class_sets": {
            key: sorted(", ".join(sorted(value)) for value in values)
            for key, values in sorted(allowed.items())
        },
        "status": "ok",
    }
    if args.report:
        args.report.write_text(
            json.dumps(report, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    print(json.dumps({k: report[k] for k in ("candidates_in", "candidates_out", "status")}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
