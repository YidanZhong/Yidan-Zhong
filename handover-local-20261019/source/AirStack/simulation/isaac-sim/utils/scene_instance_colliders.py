"""Explicit, checksum-pinned static instance collision preparation.

This changes a stage's session layer only. It does not approve semantic targets,
save source USD files, or choose collision donors automatically.
"""
from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Any

LOGGER = logging.getLogger(__name__)


def mesh_geometry_sha256(prim: Any) -> str:
    import numpy as np
    from pxr import UsdGeom

    if not prim or not prim.IsA(UsdGeom.Mesh):
        raise ValueError("Collision manifest path must identify a mesh")
    mesh = UsdGeom.Mesh(prim)
    digest = hashlib.sha256()
    for attr in (mesh.GetPointsAttr(), mesh.GetFaceVertexCountsAttr(), mesh.GetFaceVertexIndicesAttr()):
        value = attr.Get()
        if value is None or not len(value):
            raise ValueError(f"Collision mesh has no geometry: {prim.GetPath()}")
        digest.update(np.asarray(value).tobytes())
    return digest.hexdigest()


def prepare_static_instance_colliders(
    stage: Any, *, manifest_path: Path, asset_path: Path,
    reference_root: str | None = None, max_roots: int = 10000,
) -> dict[str, Any]:
    """Restore explicitly declared static proxies from identical collider meshes.

    ``reference_root`` maps the asset default prim to its runtime reference mount.
    Omit it for a stage opened directly. Rejection checks run before expansion.
    The returned profile overrides must feed both collision and material setup.
    """
    import numpy as np
    from pxr import Sdf, Usd, UsdGeom, UsdPhysics
    from scene_audit import classify_scene_mesh

    payload_bytes = Path(manifest_path).read_bytes()
    manifest = json.loads(payload_bytes)
    if manifest.get("schema") != "static-instance-collision-manifest-v1":
        raise ValueError("Unsupported static instance collision manifest")
    asset_sha = hashlib.sha256(Path(asset_path).read_bytes()).hexdigest()
    if manifest.get("asset_sha256") != asset_sha:
        raise ValueError("Collision manifest asset SHA256 differs")
    if manifest.get("human_gt_approved") is not False:
        raise ValueError("Collision preparation cannot imply human GT approval")
    if manifest.get("unmatched_count") != 0 or manifest.get("ambiguous_count") != 0:
        raise ValueError("Unresolved collision donor matches")
    rows = manifest.get("matches", [])
    if not rows or len(rows) > max_roots or not 1 <= max_roots <= 10000:
        raise ValueError("Static instance expansion budget exceeded or empty manifest")
    asset = Usd.Stage.Open(str(asset_path), load=Usd.Stage.LoadNone)
    if not asset or not asset.GetDefaultPrim():
        raise ValueError("Asset requires an explicit default prim")
    source_root = str(asset.GetDefaultPrim().GetPath())
    if manifest.get("asset_default_prim") != source_root:
        raise ValueError("Asset default prim differs from collision manifest")
    mount = source_root if reference_root is None else reference_root
    if not Sdf.Path(mount).IsAbsoluteRootOrPrimPath() or mount == "/":
        raise ValueError("Reference root must be an absolute prim path")

    def mapped(path: str) -> str:
        value = Sdf.Path(path)
        if not value.IsAbsoluteRootOrPrimPath() or not value.HasPrefix(Sdf.Path(source_root)):
            raise ValueError("Collision manifest path escapes the asset default prim")
        return str(value.ReplacePrefix(Sdf.Path(source_root), Sdf.Path(mount)))

    root_path = mapped(manifest["scene_root"])
    root = stage.GetPrimAtPath(root_path)
    if not root:
        raise ValueError("Mapped collision scene root is missing")
    ancestor = root.GetParent()
    while ancestor and not ancestor.IsPseudoRoot():
        if ancestor.HasAPI(UsdPhysics.RigidBodyAPI) and UsdPhysics.RigidBodyAPI(ancestor).GetRigidBodyEnabledAttr().Get():
            raise ValueError("Dynamic scene ancestors require a separate collision policy")
        ancestor = ancestor.GetParent()
    paths: set[str] = set()
    prepared = []
    digest_cache: dict[str, str] = {}

    def geometry(prim: Any) -> str:
        key = str(prim.GetPath())
        if key not in digest_cache:
            digest_cache[key] = mesh_geometry_sha256(prim)
        return digest_cache[key]

    for prim in Usd.PrimRange(root, Usd.TraverseInstanceProxies()):
        if prim.HasAPI(UsdPhysics.RigidBodyAPI) and UsdPhysics.RigidBodyAPI(prim).GetRigidBodyEnabledAttr().Get():
            raise ValueError("Dynamic rigid bodies require a separate instance collision policy")
    for row in rows:
        target_path, donor_path = mapped(row["path"]), mapped(row["donor"])
        if target_path in paths or not Sdf.Path(target_path).HasPrefix(Sdf.Path(root_path)) or not Sdf.Path(donor_path).HasPrefix(Sdf.Path(root_path)):
            raise ValueError("Duplicate collision target or path outside scene root")
        paths.add(target_path)
        target, donor = stage.GetPrimAtPath(target_path), stage.GetPrimAtPath(donor_path)
        if not target or not target.IsInstanceProxy():
            raise ValueError("Expected an unexpanded instance proxy target")
        if not donor or donor.IsInstanceProxy() or not donor.HasAPI(UsdPhysics.CollisionAPI) or not UsdPhysics.CollisionAPI(donor).GetCollisionEnabledAttr().Get():
            raise ValueError("Collision donor must be an existing enabled non-proxy collider")
        expected = row["geometry_sha256"]
        if geometry(target) != expected or geometry(donor) != expected:
            raise ValueError("Collision donor/instance geometry differs from manifest")
        role = classify_scene_mesh(donor_path, has_collision=True, has_rigid_body=False)
        if role != row["profile"] or role not in {"ground", "static_obstacle"}:
            raise ValueError("Collision donor profile differs or is not static")
        prepared.append((target_path, role))

    before = {}
    for prim in Usd.PrimRange(root, Usd.TraverseInstanceProxies()):
        if prim.IsA(UsdGeom.Mesh):
            path = str(prim.GetPath())
            before[path] = (geometry(prim), np.asarray(UsdGeom.Xformable(prim).ComputeLocalToWorldTransform(Usd.TimeCode.Default())).tobytes(), str(UsdGeom.Imageable(prim).ComputeVisibility()))
            missing_collision = not prim.HasAPI(UsdPhysics.CollisionAPI) or not UsdPhysics.CollisionAPI(prim).GetCollisionEnabledAttr().Get()
            if prim.IsInstanceProxy() and missing_collision and before[path][2] != "invisible" and path not in paths:
                raise ValueError("Visible proxy without collision omitted from manifest")
    expanded: list[str] = []
    session = stage.GetSessionLayer()
    original_session = session.ExportToString()
    try:
        with Usd.EditContext(stage, session):
            for _ in range(8):
                instances = [prim for prim in Usd.PrimRange(root) if prim.IsInstance()]
                if not instances:
                    break
                if len(expanded) + len(instances) > max_roots:
                    raise ValueError("Nested instance expansion exceeds root budget")
                for prim in instances:
                    expanded.append(str(prim.GetPath()))
                    prim.SetInstanceable(False)
            else:
                raise RuntimeError("Nested instance expansion exceeds eight passes")
            for path, expected in before.items():
                prim = stage.GetPrimAtPath(path)
                actual = (mesh_geometry_sha256(prim), np.asarray(UsdGeom.Xformable(prim).ComputeLocalToWorldTransform(Usd.TimeCode.Default())).tobytes(), str(UsdGeom.Imageable(prim).ComputeVisibility()))
                if prim.IsInstanceProxy() or actual != expected:
                    raise RuntimeError("Instance expansion changed mesh geometry, transform, or visibility")
            for path, _ in prepared:
                UsdPhysics.CollisionAPI.Apply(stage.GetPrimAtPath(path)).CreateCollisionEnabledAttr().Set(True)
    except Exception:
        session.ImportFromString(original_session)
        raise
    result = {"scope": "explicit static collision preparation, not human GT approval",
              "manifest_sha256": hashlib.sha256(payload_bytes).hexdigest(), "asset_sha256": asset_sha,
              "source_default_prim": source_root, "runtime_reference_root": mount,
              "expanded_roots": len(expanded), "seeded_meshes": len(prepared),
              "mesh_geometry_transforms_visibility_unchanged": len(before),
              "source_saved": False, "profile_overrides": dict(prepared)}
    LOGGER.info("Prepared %d static instance colliders in session layer", len(prepared))
    return result
