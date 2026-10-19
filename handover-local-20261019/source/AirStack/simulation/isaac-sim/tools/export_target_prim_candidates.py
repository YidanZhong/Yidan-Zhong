#!/usr/bin/env python3
"""Export USD prim candidates for target annotation binding.

This tool reads the real USD stage with Pixar USD/PXR APIs and writes the
candidate surface consumed by ``airground gt targets bind-usd-prims``.  It does
not mark targets as human-reviewed; it only exposes stable prim paths and
world-space aligned bounding boxes for automatic matching and later review.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import re
from typing import Any


TARGET_ALIAS_TOKENS: dict[str, tuple[str, ...]] = {
    "billboard": ("billboard",),
    # 2026-09-24: the RetroNeighborhood crates are ``SM_ShippingContainer*``
    # (bound to ``MI_ShippingContainer_Blue``/``_Red``/... ), not garbage bins.
    # The old token set never matched them, so the three container targets had
    # no candidate at all even though the prims sit 0.18-0.24 m away.
    "blue container": (
        "blue_container",
        "container",
        "garbage_container",
        "shipping_container",
        "shippingcontainer",
    ),
    "bus stop": ("bus_stop", "busstop"),
    "chimney": ("chimney",),
    "fountain": ("fountain",),
    "house": ("house",),
    "porch": ("porch",),
    # Nissan's prim is named after its model and contains no "car" token.
    "red car": ("red_car", "hovercar", "car", "nissan_fairlady", "nissan_s30"),
    "red container": (
        "red_container",
        "container",
        "garbage_container",
        "shipping_container",
        "shippingcontainer",
    ),
    "tree": ("tree",),
    "tunnel": ("tunnel",),
    "yellow car": ("yellow_car", "car"),
}

#: Color words that appear in the scene's material names.  They let the binder
#: tell "blue container" from "red container" without any rendering.
MATERIAL_COLOR_HINTS: tuple[str, ...] = (
    "blue",
    "red",
    "green",
    "yellow",
    "white",
    "black",
    "grey",
    "gray",
    "orange",
)


def _semantic_key(value: str) -> str:
    return re.sub(r"_+", "_", re.sub(r"[^a-z0-9]+", "_", value.strip().lower())).strip("_")


def _tokens(value: str) -> set[str]:
    normalized = _semantic_key(value)
    tokens = {token for token in normalized.split("_") if token}
    tokens.add(normalized)
    for compound in ("bus_stop", "blue_container", "red_container", "red_car", "yellow_car"):
        if compound in normalized:
            tokens.add(compound)
    if "street" in tokens:
        tokens.discard("tree")
    return tokens


def _hints_for_path(path: str, classes: tuple[str, ...]) -> tuple[str, ...]:
    path_tokens = _tokens(path)
    compact = re.sub(r"[^a-z0-9]+", "", path.lower())
    hints: list[str] = []
    for semantic_class in classes:
        aliases = set(TARGET_ALIAS_TOKENS[semantic_class])
        aliases.add(_semantic_key(semantic_class))
        # Match whole tokens (bus_stop) and compact substrings
        # (``sm_shippingcontainer3`` -> ``shippingcontainer``/``container``).
        if path_tokens & aliases or any(alias.replace("_", "") in compact for alias in aliases):
            hints.append(semantic_class)
    return tuple(hints)


def _material_color_hint(prim: Any) -> tuple[str | None, str | None]:
    """Return ``(material_path, color_hint)`` for one prim, or ``(None, None)``."""

    try:
        from pxr import UsdShade  # type: ignore[import-not-found]
    except Exception:  # pragma: no cover - PXR always available in the Isaac image
        return None, None
    node = prim
    first_material: str | None = None
    while node and node.IsValid():
        binding = UsdShade.MaterialBindingAPI(node).ComputeBoundMaterial()[0]
        if binding:
            material_path = str(binding.GetPath())
            if first_material is None:
                first_material = material_path
            tokens = set(_semantic_key(material_path).split("_"))
            for color in MATERIAL_COLOR_HINTS:
                if color in tokens:
                    return material_path, ("grey" if color == "gray" else color)
        node = node.GetParent()
    return first_material, None


def _finite_vec3(values: Any) -> tuple[float, float, float] | None:
    try:
        x, y, z = values
    except Exception:
        return None
    result = (float(x), float(y), float(z))
    if not all(math.isfinite(value) for value in result):
        return None
    return result


def export_candidates(
    stage_path: Path,
    *,
    scene_id: str = "RetroNeighborhood",
    frame: str = "map",
    root_prefix: str = "/World/stage",
    classes: tuple[str, ...] = tuple(TARGET_ALIAS_TOKENS),
    min_volume_m3: float = 1.0e-6,
    generator_version: str = "p1-05b",
) -> dict[str, Any]:
    """Return a deterministic USD prim candidate manifest."""
    from pxr import Usd, UsdGeom  # type: ignore[import-not-found]

    resolved_stage = Path(stage_path).expanduser().resolve(strict=True)
    stage = Usd.Stage.Open(str(resolved_stage))
    if stage is None:
        raise RuntimeError(f"failed to open USD stage: {resolved_stage}")

    cache = UsdGeom.BBoxCache(
        Usd.TimeCode.Default(),
        ["default", "render", "proxy"],
        useExtentsHint=True,
    )
    rows: list[dict[str, Any]] = []
    for prim in stage.Traverse():
        prim_path = str(prim.GetPath())
        if root_prefix and not prim_path.startswith(root_prefix):
            continue
        if not prim.IsA(UsdGeom.Imageable):
            continue
        hints = _hints_for_path(prim_path, classes)
        if not hints:
            continue
        aligned = cache.ComputeWorldBound(prim).ComputeAlignedBox()
        size = _finite_vec3(aligned.GetSize())
        center = _finite_vec3(aligned.GetMidpoint())
        if center is None or size is None:
            continue
        volume = size[0] * size[1] * size[2]
        if volume < min_volume_m3:
            continue
        material_path, material_color = _material_color_hint(prim)
        rows.append(
            {
                "center_xyz_m": [round(value, 6) for value in center],
                "color_hint": material_color,
                "material_path": material_path,
                "prim_path": prim_path,
                "semantic_hints": list(hints),
                "size_xyz_m": [round(value, 6) for value in size],
            }
        )

    rows.sort(
        key=lambda row: (
            tuple(row["semantic_hints"]),
            row["prim_path"],
            tuple(row["center_xyz_m"]),
        )
    )
    return {
        "candidates": rows,
        "frame": frame,
        "generator": "airground-usd-prim-candidate-exporter-v1",
        "generator_version": generator_version,
        "scene_id": scene_id,
        "schema_version": "1.0.0",
        "source_usd_path": str(stage_path),
    }


def _parse_classes(values: list[str] | None) -> tuple[str, ...]:
    if not values:
        return tuple(TARGET_ALIAS_TOKENS)
    classes: list[str] = []
    for value in values:
        semantic_class = value.strip().lower()
        if semantic_class not in TARGET_ALIAS_TOKENS:
            choices = ", ".join(sorted(TARGET_ALIAS_TOKENS))
            raise ValueError(f"unsupported class {value!r}; choices: {choices}")
        classes.append(semantic_class)
    return tuple(dict.fromkeys(classes))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", required=True, help="USD stage path to inspect")
    parser.add_argument("--output", required=True, help="candidate manifest JSON output")
    parser.add_argument("--scene-id", default="RetroNeighborhood")
    parser.add_argument("--frame", default="map")
    parser.add_argument("--root-prefix", default="/World/stage")
    parser.add_argument("--class", dest="classes", action="append", help="target class to export")
    parser.add_argument("--aliases", help="JSON mapping of additional class names to USD name hints; not review approval")
    parser.add_argument("--min-volume", type=float, default=1.0e-6)
    parser.add_argument("--generator-version", default="p1-05b")
    args = parser.parse_args(argv)

    if args.aliases:
        aliases = json.loads(Path(args.aliases).read_text(encoding="utf-8"))
        if not isinstance(aliases, dict) or any(
            not isinstance(key, str) or not key.strip()
            or not isinstance(values, list) or not values
            or any(not isinstance(value, str) or not value.strip() for value in values)
            for key, values in aliases.items()
        ):
            parser.error("--aliases must map nonempty class names to nonempty lists of string hints")
        TARGET_ALIAS_TOKENS.update({key.strip().lower(): tuple(values) for key, values in aliases.items()})

    manifest = export_candidates(
        Path(args.stage),
        scene_id=args.scene_id,
        frame=args.frame,
        root_prefix=args.root_prefix,
        classes=_parse_classes(args.classes),
        min_volume_m3=args.min_volume,
        generator_version=args.generator_version,
    )
    output = Path(args.output).expanduser()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(manifest, ensure_ascii=True, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "candidate_count": len(manifest["candidates"]),
                "output": str(output),
                "scene_id": manifest["scene_id"],
                "status": "ok",
            },
            ensure_ascii=True,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
