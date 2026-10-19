#!/usr/bin/env python3
"""Recalibrate the UGV reachable region and the GT arrival regions (CPU only).

2026-09-24 workflow (no GPU):

1. build the ``1.5x UGV width`` reachable region from the current band obstacle
   map (``airground gt traversability reach-region`` output package),
2. rebuild every arrival (confirmation) region as a dense set of traversable
   cells whose planar distance to the instance OBB *surface* is 1.5-8.0 m,
3. count the paper search targets per reachable component and select the
   component holding the most of them,
4. write the restricted GT (``targets.reviewed.with_regions.json``), the arrival
   raster (``arrival_regions.npz`` + ``region_index.json``), the human-readable
   target table (JSON/CSV) and an annotated obstacle-map PNG.

The script only reads GT artifacts and writes new dated directories; nothing is
overwritten in place.
"""

from __future__ import annotations

import argparse
from collections import Counter
import csv
import json
from pathlib import Path
import sys

import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent
BENCHMARK_ROOT = REPO_ROOT / "benchmark"
if str(BENCHMARK_ROOT) not in sys.path:
    sys.path.insert(0, str(BENCHMARK_ROOT))

from airground_benchmark.scenes import is_paper_class, paper_classes
from airground_benchmark.ground_truth import (  # noqa: E402
    build_arrival_regions_from_traversability,
    canonical_target_annotations_json,
    load_target_annotations,
    load_traversability_metadata,
    write_arrival_regions_npz,
)

#: RAVEN paper Table A.3 word list for the Neighborhood (RetroNeighborhood) scene.
PAPER_CLASSES: tuple[str, ...] = (
    "billboard",
    "blue container",
    "bus stop",
    "house",
    "red car",
    "red container",
    "tunnel",
    "yellow car",
)

PRIM_EXCLUDED_PREFIX = "no reliable USD prim path"


def _render_map(
    *,
    base_mask: np.ndarray,
    reach_mask: np.ndarray,
    component: np.ndarray,
    selected: int,
    origin_x: float,
    origin_y: float,
    resolution: float,
    targets: list[dict[str, object]],
    starts: list[dict[str, float]],
    output: Path,
) -> None:
    from PIL import Image, ImageDraw, ImageFont

    height, width = base_mask.shape
    canvas = np.zeros((height, width, 3), dtype=np.uint8)
    # Base layer = the *original* obstacle map: blocked dark, traversable light.
    canvas[~base_mask.astype(bool)] = (28, 30, 34)
    canvas[base_mask.astype(bool)] = (232, 232, 232)
    # Reachable region (1.5x corridor rule) and the selected component on top.
    if reach_mask.any():
        canvas[reach_mask.astype(bool)] = (206, 226, 206)
    selected_cells = component == selected
    if selected_cells.any():
        canvas[selected_cells] = (168, 214, 168)
    # Repository convention (see rgbd_search_cloud provenance): +y is **up**.
    canvas = np.flipud(canvas)
    image = Image.fromarray(canvas, mode="RGB")
    draw = ImageDraw.Draw(image)
    try:
        font = ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 16
        )
        small = ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 14
        )
    except Exception:  # pragma: no cover - font availability
        font = ImageFont.load_default()
        small = font

    legend = (
        ((28, 30, 34), "obstacle / blocked"),
        ((232, 232, 232), "traversable (base map)"),
        ((206, 226, 206), "reachable region (1.5x UGV width)"),
        ((168, 214, 168), f"selected component {selected}"),
        ((0, 128, 0), "search target reachable"),
        ((110, 110, 110), "search target unreachable"),
        ((200, 40, 40), "search target prim-excluded"),
        ((0, 0, 255), "smoke start (triangle + heading)"),
    )
    box_height = 18 + 22 * len(legend)
    draw.rectangle((12, 12, 12 + 430, 12 + box_height), fill=(255, 255, 255), outline=(60, 60, 60))
    for index, (colour, label) in enumerate(legend):
        top = 22 + 22 * index
        draw.rectangle((22, top, 38, top + 14), fill=colour, outline=(90, 90, 90))
        draw.text((46, top - 2), label, fill=(20, 20, 20), font=small)
    # 10 m scale bar (bottom-right).
    bar_m = 10.0
    bar_px = bar_m / resolution
    x1 = width - 30
    x0 = x1 - bar_px
    y0 = height - 30
    draw.line([(x0, y0), (x1, y0)], fill=(0, 0, 0), width=4)
    draw.text((x0, y0 - 22), f"{bar_m:g} m", fill=(0, 0, 0), font=small)
    draw.text((14, height - 30), f"resolution {resolution:g} m/cell, grid {width}x{height}",
              fill=(60, 60, 60), font=small)

    def to_px(x_m: float, y_m: float) -> tuple[float, float]:
        return (x_m - origin_x) / resolution, (height - 1) - (y_m - origin_y) / resolution

    for row in targets:
        x_px, y_px = to_px(float(row["center_x_m"]), float(row["center_y_m"]))
        size = float(row["marker_size_px"])
        if row["status"] == "reachable":
            colour = (0, 128, 0)
        elif row["status"] == "prim_excluded":
            colour = (200, 40, 40)
        else:
            colour = (110, 110, 110)
        draw.ellipse(
            (x_px - size, y_px - size, x_px + size, y_px + size),
            outline=colour,
            width=3 if row["status"] == "reachable" else 2,
        )
        draw.text((x_px + size + 2, y_px - size), str(row["label"]), fill=colour, font=font)
    for index, start in enumerate(starts, start=1):
        x_px, y_px = to_px(float(start["x_m"]), float(start["y_m"]))
        draw.polygon(
            [(x_px, y_px - 12), (x_px - 10, y_px + 9), (x_px + 10, y_px + 9)],
            outline=(0, 0, 255),
            fill=(0, 0, 255),
        )
        yaw = float(start.get("yaw_rad") or 0.0)
        draw.line(
            # Image rows grow downwards, so a positive map-frame yaw points up.
            [(x_px, y_px), (x_px + 30 * np.cos(yaw), y_px - 30 * np.sin(yaw))],
            fill=(0, 0, 255),
            width=3,
        )
        draw.text((x_px + 12, y_px + 10), f"S{index}", fill=(0, 0, 255), font=font)
    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--targets", required=True, type=Path, help="reviewed target annotations")
    parser.add_argument(
        "--reach-package-dir",
        required=True,
        type=Path,
        help="package dir written by 'airground gt traversability reach-region'",
    )
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument(
        "--base-npz",
        type=Path,
        default=None,
        help="original obstacle-map NPZ (defaults to the reach package NPZ); "
        "used as the annotated base layer so the full ROI is visible",
    )
    parser.add_argument("--min-distance", type=float, default=1.5)
    parser.add_argument("--max-distance", type=float, default=8.0)
    parser.add_argument("--max-poses-per-target", type=int, default=128)
    parser.add_argument("--starts-json", type=Path, default=None, help="optional start selection to overlay")
    args = parser.parse_args(argv)

    output_dir = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    package_dir = args.reach_package_dir.expanduser().resolve()
    metadata_path = next(package_dir.glob("*.metadata.yaml"))
    npz_path = next(package_dir.glob("*.npz"))
    metadata = load_traversability_metadata(metadata_path)
    with np.load(npz_path) as data:
        reach_mask = np.asarray(data["mask"], dtype=bool)
        component = np.asarray(data["component"], dtype=np.int32)
        height_array = np.asarray(data["height"])
    if args.base_npz is not None:
        with np.load(args.base_npz.expanduser().resolve(strict=True)) as base_data:
            base_mask = np.asarray(base_data["mask"], dtype=bool)
        if base_mask.shape != reach_mask.shape:
            raise SystemExit("--base-npz mask shape must match the reach package")
    else:
        base_mask = reach_mask
    manifest = load_target_annotations(args.targets)

    unrestricted, bundle = build_arrival_regions_from_traversability(
        manifest,
        metadata,
        npz_path,
        min_distance_m=args.min_distance,
        max_distance_m=args.max_distance,
        distance_reference="obb_surface",
        max_poses_per_target=args.max_poses_per_target,
    )
    instances = {row.instance_id: row for row in unrestricted.instances}
    per_component: dict[int, set[str]] = {}
    per_instance: dict[str, dict[str, object]] = {}
    for row in bundle.region_index:
        instance = instances[str(row["instance_id"])]
        record = per_instance.setdefault(
            instance.instance_id,
            {
                "cell_count": 0,
                "components": set(),
            },
        )
        record["cell_count"] = int(row["cell_count"])
        record["components"].update(int(value) for value in row["components"])
        if is_paper_class(manifest.scene_id, instance.semantic_class):
            for value in row["components"]:
                per_component.setdefault(int(value), set()).add(instance.instance_id)

    component_sizes = Counter(int(value) for value in component[component >= 0].ravel().tolist())
    if not per_component:
        raise SystemExit("no reachable arrival region for any paper class; nothing to select")
    selected = max(
        per_component,
        key=lambda value: (len(per_component[value]), component_sizes.get(value, 0), -value),
    )
    selected_targets = sorted(per_component[selected])

    restricted, restricted_bundle = build_arrival_regions_from_traversability(
        manifest,
        metadata,
        npz_path,
        min_distance_m=args.min_distance,
        max_distance_m=args.max_distance,
        distance_reference="obb_surface",
        restrict_components=(selected,),
        max_poses_per_target=args.max_poses_per_target,
    )
    npz_sha = write_arrival_regions_npz(output_dir / "arrival_regions.npz", restricted_bundle)
    (output_dir / "targets.reviewed.with_regions.json").write_text(
        canonical_target_annotations_json(restricted), encoding="utf-8"
    )
    (output_dir / "region_index.json").write_text(
        json.dumps(
            {
                "distance_reference": restricted_bundle.distance_reference,
                "regions": [dict(row) for row in restricted_bundle.region_index],
                "selected_component": selected,
                "schema_version": metadata.schema_version,
            },
            ensure_ascii=True,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    reachable_instances = {
        row.instance_id for row in restricted.instances if row.ground_reachable == "reachable"
    }
    restricted_cells = {
        str(row["instance_id"]): int(row["cell_count"]) for row in restricted_bundle.region_index
    }
    table: list[dict[str, object]] = []
    for instance in restricted.instances:
        if not is_paper_class(manifest.scene_id, instance.semantic_class):
            continue
        before = per_instance.get(instance.instance_id, {})
        table.append(
            {
                "cell_count": restricted_cells.get(instance.instance_id, 0),
                "center_x_m": round(float(instance.obb.center_xyz_m[0]), 3),
                "center_y_m": round(float(instance.obb.center_xyz_m[1]), 3),
                "center_z_m": round(float(instance.obb.center_xyz_m[2]), 3),
                "components": sorted(int(v) for v in before.get("components", ())),
                "distance_reference": "obb_surface",
                "excluded_reason": instance.excluded_reason,
                "ground_reachable": instance.ground_reachable,
                "instance_id": instance.instance_id,
                "semantic_class": instance.semantic_class,
                "size_x_m": round(float(instance.obb.size_xyz_m[0]), 3),
                "size_y_m": round(float(instance.obb.size_xyz_m[1]), 3),
                "size_z_m": round(float(instance.obb.size_xyz_m[2]), 3),
                "unrestricted_cell_count": int(before.get("cell_count", 0)),
                "usd_prim_path": instance.usd_prim_path,
            }
        )
    (output_dir / "target_reach_annotations.json").write_text(
        json.dumps(
            {
                "distance_reference": "obb_surface",
                "instance_count": len(table),
                "reach_window_m": [args.min_distance, args.max_distance],
                "rows": table,
                "schema_version": metadata.schema_version,
                "scene_id": metadata.scene_id,
                "search_target_classes": list(paper_classes(manifest.scene_id)),
                "selected_component": selected,
            },
            ensure_ascii=True,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    with (output_dir / "target_reach_annotations.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(table[0].keys()) if table else [])
        writer.writeheader()
        for row in table:
            writer.writerow(row)

    marker_rows = []
    for row in table:
        if row["ground_reachable"] == "reachable":
            status = "reachable"
        elif (row["excluded_reason"] or "").startswith(PRIM_EXCLUDED_PREFIX):
            status = "prim_excluded"
        else:
            status = "unreachable"
        marker_rows.append(
            {
                "center_x_m": row["center_x_m"],
                "center_y_m": row["center_y_m"],
                "label": f"{row['semantic_class']}",
                "marker_size_px": 12.0,
                "status": status,
            }
        )
    starts: list[dict[str, float]] = []
    if args.starts_json and args.starts_json.exists():
        payload = json.loads(args.starts_json.read_text(encoding="utf-8"))
        starts = [
            {
                "x_m": float(row["starts"]["ugv"]["x_m"]),
                "y_m": float(row["starts"]["ugv"]["y_m"]),
                "yaw_rad": float(row["starts"]["ugv"]["yaw_rad"]),
            }
            for row in payload.get("episodes", payload.get("starts", []))
        ]

    _render_map(
        base_mask=base_mask,
        reach_mask=reach_mask,
        component=component,
        selected=selected,
        origin_x=metadata.origin.x_m,
        origin_y=metadata.origin.y_m,
        resolution=metadata.resolution_m,
        targets=marker_rows,
        starts=starts,
        output=output_dir / "reach_map_annotated.png",
    )

    report = {
        "arrival_npz_sha256": npz_sha,
        "component_sizes_desc": component_sizes.most_common(8),
        "distance_reference": "obb_surface",
        "instance_count": len(table),
        "per_component_paper_targets": {
            str(key): sorted(value) for key, value in sorted(per_component.items())
        },
        "reach_window_m": [args.min_distance, args.max_distance],
        "reachable_paper_targets": sorted(
            row["instance_id"] for row in table if row["ground_reachable"] == "reachable"
        ),
        "restricted_reachable_count": len(reachable_instances),
        "schema_version": metadata.schema_version,
        "selected_component": selected,
        "selected_component_cells": component_sizes.get(selected, 0),
        "selected_component_paper_targets": selected_targets,
        "status": "ok",
        "total_arrival_cells": restricted_bundle.summary()["total_cells"],
    }
    (output_dir / "reach_region_report.json").write_text(
        json.dumps(report, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({k: report[k] for k in ("instance_count", "selected_component", "selected_component_cells", "status")}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
