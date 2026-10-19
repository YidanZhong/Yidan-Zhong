"""Evaluator-only ROI analysis and deterministic human review proposals.

No algorithm/runtime observation API imports this module. Coarse maps and
proposed placements are diagnostic geometry, never scoring GT.
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
from scipy import ndimage

from .ground_truth import GroundTruthError, OrientedBoundingBox, TargetAnnotationManifest, TraversabilityMetadata
from .scenes import is_paper_class
from .traversability import build_reach_region

PAPER_CLASSES = ("billboard", "blue container", "bus stop", "house", "red car", "red container", "tunnel", "yellow car")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True, allow_nan=False) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]) if rows else ["instance_id"])
        writer.writeheader()
        for row in rows:
            writer.writerow({key: json.dumps(value, sort_keys=True) if isinstance(value, (list, dict)) else value for key, value in row.items()})


def obb_corners(obb: OrientedBoundingBox) -> np.ndarray:
    roll, pitch, yaw = obb.orientation_rpy_rad
    cr, sr, cp, sp, cy, sy = math.cos(roll), math.sin(roll), math.cos(pitch), math.sin(pitch), math.cos(yaw), math.sin(yaw)
    rotation = np.array([[cy*cp, cy*sp*sr-sy*cr, cy*sp*cr+sy*sr], [sy*cp, sy*sp*sr+cy*cr, sy*sp*cr-cy*sr], [-sp, cp*sr, cp*cr]])
    signs = np.array([[x, y, z] for x in (-1, 1) for y in (-1, 1) for z in (-1, 1)])
    return (signs * np.array(obb.size_xyz_m) / 2) @ rotation.T + np.array(obb.center_xyz_m)


def snapped_roi(bounds: np.ndarray, *, margin_m: float, resolution_m: float) -> dict[str, Any]:
    if resolution_m <= 0 or margin_m < 0 or not np.isfinite(bounds).all():
        raise GroundTruthError("ROI requires finite bounds, positive resolution and nonnegative margin")
    # Integer grid coordinates avoid binary floating point extra cells at exact boundaries.
    lower = np.floor((bounds[0, :2] - margin_m) / resolution_m + 1e-9).astype(np.int64)
    upper = np.ceil((bounds[1, :2] + margin_m) / resolution_m - 1e-9).astype(np.int64)
    if np.any(upper <= lower):
        raise GroundTruthError("ROI extent is empty")
    return {"origin_xy_m": (lower * resolution_m).tolist(), "upper_xy_m": (upper * resolution_m).tolist(), "shape": [int(upper[1]-lower[1]), int(upper[0]-lower[0])], "resolution_m": resolution_m, "margin_m": margin_m}


def annotation_roi(manifest: TargetAnnotationManifest, *, margin_m: float = 2, resolution_m: float = .1) -> dict[str, Any]:
    points = np.concatenate([obb_corners(instance.obb) for instance in manifest.instances])
    bounds = np.array([points.min(axis=0), points.max(axis=0)])
    return {**snapped_roi(bounds, margin_m=margin_m, resolution_m=resolution_m), "annotation_aabb_xyz_m": bounds.tolist(), "annotation_count": len(manifest.instances), "basis": "all_annotation_OBBs_world_AABB"}


def surface_window(obb: OrientedBoundingBox, metadata: TraversabilityMetadata, maximum: float = 8) -> tuple[tuple[slice, slice], np.ndarray]:
    x, y, _ = obb.center_xyz_m
    res = metadata.resolution_m
    radius = math.hypot(*obb.size_xyz_m[:2])/2 + maximum + res
    height, width = metadata.shape
    c0 = max(0, min(width, math.floor((x-radius-metadata.origin.x_m)/res)))
    c1 = max(0, min(width, math.ceil((x+radius-metadata.origin.x_m)/res)))
    r0 = max(0, min(height, math.floor((y-radius-metadata.origin.y_m)/res)))
    r1 = max(0, min(height, math.ceil((y+radius-metadata.origin.y_m)/res)))
    dx = metadata.origin.x_m + (np.arange(c0, c1)[None, :] + .5)*res - x
    dy = metadata.origin.y_m + (np.arange(r0, r1)[:, None] + .5)*res - y
    cy, sy = math.cos(obb.orientation_rpy_rad[2]), math.sin(obb.orientation_rpy_rad[2])
    distances = np.hypot(np.maximum(np.abs(cy*dx + sy*dy)-obb.size_xyz_m[0]/2, 0), np.maximum(np.abs(-sy*dx + cy*dy)-obb.size_xyz_m[1]/2, 0))
    return (slice(r0, r1), slice(c0, c1)), distances


def arrival_mask(obb: OrientedBoundingBox, metadata: TraversabilityMetadata, allowed: np.ndarray) -> tuple[tuple[slice, slice], np.ndarray]:
    window, distances = surface_window(obb, metadata)
    return window, np.asarray(allowed[window], dtype=bool) & (distances >= 1.5) & (distances <= 8)


def component_report(manifest: TargetAnnotationManifest, metadata: TraversabilityMetadata, base: np.ndarray, component: np.ndarray, *, expected_targets: int | None = None) -> dict[str, Any]:
    if manifest.scene_id != metadata.scene_id:
        raise GroundTruthError("annotation and traversability scenes differ")
    if expected_targets is None and manifest.scene_id == "RetroNeighborhood":
        expected_targets = 31  # Retain the existing calibrated Retro acceptance gate.
    recomputed = build_reach_region(base, resolution_m=metadata.resolution_m)
    if not np.array_equal(component, recomputed.reach_component):
        raise GroundTruthError("reach package labels differ from recomputed 0.1075 m / 8-connected rule")
    paper = sorted((row for row in manifest.instances if is_paper_class(manifest.scene_id, row.semantic_class)), key=lambda row: row.instance_id)
    if expected_targets is not None and len(paper) != expected_targets:
        raise GroundTruthError(f"expected {expected_targets} paper instances, got {len(paper)}")
    members: dict[int, list[str]] = {index: [] for index in range(recomputed.component_count)}
    rows: list[dict[str, Any]] = []
    for instance in paper:
        unbound = not instance.usd_prim_path or (instance.excluded_reason or "").startswith("no reliable USD prim path")
        window, region = arrival_mask(instance.obb, metadata, component >= 0)
        # Geometry membership is independent of binding validity. An unbound
        # annotation remains reviewable, but is never made scoring eligible.
        ids = np.unique(component[window][region]).tolist()
        for index in ids:
            members[index].append(instance.instance_id)
        rows.append({"instance_id": instance.instance_id, "semantic_class": instance.semantic_class, "usd_prim_path": instance.usd_prim_path, "obb": instance.obb.model_dump(mode="json"), "components": ids, "arrival_cell_count": int(region.sum()), "binding_status": "unbound" if unbound else "bound"})
    if not members:
        raise GroundTruthError("no component in the reach map")
    selected = max(members, key=lambda index: (len(members[index]), recomputed.component_cell_counts[index], -index))
    for row in rows:
        inside = selected in row["components"]
        bound = row["binding_status"] == "bound"
        row.update({"in_selected_component": inside, "eligible_in_selected_component": inside and bound, "requires_binding_review": not bound, "reason": "no_reliable_prim_binding" if not bound else "arrival_intersects_selected_component" if inside else "arrival_only_in_other_components" if row["components"] else "no_arrival_cell_on_reach_grid"})
    rr, cc = np.nonzero(component == selected)
    res = metadata.resolution_m
    aabb = [[metadata.origin.x_m+int(cc.min())*res, metadata.origin.y_m+int(rr.min())*res], [metadata.origin.x_m+(int(cc.max())+1)*res, metadata.origin.y_m+(int(rr.max())+1)*res]]
    bound_ids = {row["instance_id"] for row in rows if row["binding_status"] == "bound"}
    return {"schema_version": "1.0.0", "status": "ok", "purpose": "coarse_decision_only", "selection_rule": "paper_target_count_desc,area_desc,component_id_asc", "membership_rule": "OBB_surface_1.5_to_8m_arrival_intersects_component", "binding_note": "all paper annotation geometry counts for selection; unbound annotations require individual review and remain excluded from scoring", "reach_rule": recomputed.summary(), "resolution_note": f"ceil(0.1075/res)={math.ceil(.1075/res)} axial cells; Euclidean distance threshold, 8 connectivity; 0.10m decision grid is conservative", "roi": annotation_roi(manifest), "map": metadata.model_dump(mode="json"), "selected_component": selected, "selected_component_aabb_xy_m": aabb, "target_count": len(rows), "targets": rows, "components": [{"component_id": index, "cell_count": count, "area_m2": round(count*res*res, 6), "target_count": len(members[index]), "bound_target_count": len(set(members[index]) & bound_ids), "target_ids": members[index]} for index, count in enumerate(recomputed.component_cell_counts)]}


def road_axis(base: np.ndarray, row: int, col: int, resolution: float) -> tuple[float, float]:
    half = math.ceil(5/resolution)
    local = base[max(0,row-half):row+half+1, max(0,col-half):col+half+1]
    rr, cc = np.nonzero(local)
    if len(rr) < 3:
        raise GroundTruthError("too few free cells for road PCA")
    eigenvalues, vectors = np.linalg.eigh(np.cov(np.stack((cc, rr))))
    vector = vectors[:, -1]
    yaw = math.atan2(float(vector[1]), float(vector[0])) % math.pi
    return yaw, float(eigenvalues[-1]/max(eigenvalues[0], 1e-12))


def candidate_positions(instance: Any, manifest: TargetAnnotationManifest, metadata: TraversabilityMetadata, base: np.ndarray, component: np.ndarray, selected: int, starts_xy: list[tuple[float, float]], *, limit: int = 3) -> list[dict[str, Any]]:
    res = metadata.resolution_m
    clearance = ndimage.distance_transform_edt(np.pad(base, 1))[1:-1,1:-1]*res
    valid = (component == selected) & (clearance >= .5)
    other_arrivals = np.zeros_like(base, dtype=bool)
    for other in manifest.instances:
        if other.instance_id == instance.instance_id or not is_paper_class(manifest.scene_id, other.semantic_class) or not other.usd_prim_path:
            continue
        window, arrival = arrival_mask(other.obb, metadata, component >= 0)
        other_arrivals[window] |= arrival
    arrival_clearance = ndimage.distance_transform_edt(~other_arrivals)*res if other_arrivals.any() else np.full(base.shape, math.hypot(*base.shape)*res)
    valid &= arrival_clearance >= 1.5
    for x, y in starts_xy:
        col, row = math.floor((x-metadata.origin.x_m)/res), math.floor((y-metadata.origin.y_m)/res)
        if 0 <= row < base.shape[0] and 0 <= col < base.shape[1]:
            valid[row,col] = False
    rr, cc = np.nonzero(valid)
    x = metadata.origin.x_m+(cc+.5)*res
    y = metadata.origin.y_m+(rr+.5)*res
    distances = np.hypot(x-instance.obb.center_xyz_m[0], y-instance.obb.center_xyz_m[1])
    from scipy.spatial import cKDTree
    other_positions = [other.obb.center_xyz_m[:2] for other in manifest.instances if other.instance_id != instance.instance_id and is_paper_class(manifest.scene_id, other.semantic_class)]
    spacing = cKDTree(other_positions).query(np.column_stack((x,y)))[0] if other_positions else np.zeros(len(rr))
    order = np.lexsort((cc, rr, -spacing, distances))
    candidates: list[dict[str, Any]] = []
    # Check the whole rotated footprint, reserve every listed start and retain
    # useful, distinct alternatives. Unexamined cells are not reported as valid.
    for index in order:
        px, py = float(x[index]), float(y[index])
        if any(math.hypot(px-c["obb"]["center_xyz_m"][0], py-c["obb"]["center_xyz_m"][1]) < max(2, max(instance.obb.size_xyz_m[:2])) for c in candidates):
            continue
        row, col = int(rr[index]), int(cc[index])
        yaw, anisotropy = road_axis(base, row, col, res)
        # PCA is an explicit geometry proxy: near-isotropic areas lack a road axis.
        if anisotropy < 1.2:
            continue
        yaw += round((instance.obb.orientation_rpy_rad[2]-yaw)/math.pi)*math.pi
        proposed = instance.obb.model_copy(update={"center_xyz_m": (px,py,instance.obb.center_xyz_m[2]), "orientation_rpy_rad": (*instance.obb.orientation_rpy_rad[:2],yaw)})
        window, footprint_dist = surface_window(proposed, metadata, maximum=res)
        footprint = footprint_dist <= res*math.sqrt(2)/2
        if not footprint.any() or not np.all(base[window][footprint]) or np.any(clearance[window][footprint] < .5):
            continue
        if np.any(arrival_clearance[window][footprint] < 1.5):
            continue
        corners = obb_corners(proposed)[:,:2]
        if (corners[:,0].min() < metadata.origin.x_m or corners[:,1].min() < metadata.origin.y_m or corners[:,0].max() > metadata.origin.x_m+base.shape[1]*res or corners[:,1].max() > metadata.origin.y_m+base.shape[0]*res):
            continue
        if any(_point_in_obb(sx,sy,proposed,margin=res) for sx,sy in starts_xy):
            continue
        modified = (component == selected).copy()
        modified[window] &= ~footprint
        if ndimage.label(modified, structure=np.ones((3,3)))[1] != 1:
            continue
        aw, arrival = arrival_mask(proposed, metadata, modified)
        if not arrival.any():
            continue
        candidates.append({"candidate_id": len(candidates)+1, "obb": proposed.model_dump(mode="json"), "move_distance_m": round(float(distances[index]),6), "minimum_footprint_clearance_m": round(float(clearance[window][footprint].min()),6), "minimum_other_arrival_distance_m": round(float(arrival_clearance[window][footprint].min()),6), "other_target_center_spacing_m": round(float(spacing[index]),6), "road_axis_yaw_rad": yaw, "road_alignment_error_deg": 0., "road_pca_anisotropy": round(anisotropy,6), "arrival_cell_count_after_footprint": int(arrival.sum()), "single_move_splits_component": False, "reason": "nearest feasible placement aligned with 10m free-space PCA; full footprint clearance and reserved starts checked", "realism_review": "pending: road/sidewalk/parking semantics and attachment need visual review", "z_policy": "preserve old bbox center provisionally; USD patch must use reviewed ground-support height"})
        if len(candidates) >= limit:
            break
    return candidates


def _point_in_obb(x: float, y: float, obb: OrientedBoundingBox, *, margin: float = 0) -> bool:
    dx,dy = x-obb.center_xyz_m[0], y-obb.center_xyz_m[1]
    cy,sy = math.cos(obb.orientation_rpy_rad[2]), math.sin(obb.orientation_rpy_rad[2])
    return abs(cy*dx+sy*dy) <= obb.size_xyz_m[0]/2+margin and abs(-sy*dx+cy*dy) <= obb.size_xyz_m[1]/2+margin


def final_roi(component: np.ndarray, selected: int, metadata: TraversabilityMetadata, reachable_obbs: list[OrientedBoundingBox]) -> dict[str, Any]:
    rr,cc = np.nonzero(component == selected)
    if not len(rr):
        raise GroundTruthError("selected component is empty")
    res = metadata.resolution_m
    points = [[metadata.origin.x_m+cc.min()*res, metadata.origin.y_m+rr.min()*res,0], [metadata.origin.x_m+(cc.max()+1)*res,metadata.origin.y_m+(rr.max()+1)*res,0]]
    points.extend(point.tolist() for obb in reachable_obbs for point in obb_corners(obb))
    array = np.array(points)
    return snapped_roi(np.array([array.min(axis=0),array.max(axis=0)]), margin_m=5, resolution_m=.05)
