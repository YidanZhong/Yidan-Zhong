"""Actual USD composition checks; these are not PhysX cooking/navigation tests."""
import hashlib
import json
from pathlib import Path
import sys

import pytest

pxr = pytest.importorskip("pxr")
from pxr import Usd, UsdGeom, UsdPhysics

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "utils"))
from scene_instance_colliders import mesh_geometry_sha256, prepare_static_instance_colliders


@pytest.fixture
def asset_manifest(tmp_path):
    asset = tmp_path / "scene.usda"
    stage = Usd.Stage.CreateNew(str(asset))
    world = UsdGeom.Xform.Define(stage, "/World").GetPrim()
    stage.SetDefaultPrim(world)
    UsdGeom.Xform.Define(stage, "/World/stage")
    for name in ["Donor", "Template"]:
        UsdGeom.Xform.Define(stage, "/World/stage/" + name)
        mesh = UsdGeom.Mesh.Define(stage, "/World/stage/" + name + "/Mesh")
        mesh.CreatePointsAttr([(0, 0, 0), (1, 0, 0), (0, 1, 0)])
        mesh.CreateFaceVertexCountsAttr([3])
        mesh.CreateFaceVertexIndicesAttr([0, 1, 2])
    UsdPhysics.CollisionAPI.Apply(stage.GetPrimAtPath("/World/stage/Donor/Mesh")).CreateCollisionEnabledAttr(True)
    clone = stage.DefinePrim("/World/stage/Clone", "Xform")
    clone.GetReferences().AddInternalReference("/World/stage/Template")
    clone.SetInstanceable(True)
    UsdGeom.Xformable(clone).AddTranslateOp().Set((2, 3, 0))
    stage.GetRootLayer().Save()
    manifest = {"schema": "static-instance-collision-manifest-v1",
                "asset_sha256": hashlib.sha256(asset.read_bytes()).hexdigest(),
                "asset_default_prim": "/World", "scene_root": "/World/stage",
                "human_gt_approved": False, "unmatched_count": 0, "ambiguous_count": 0,
                "matches": [{"path": "/World/stage/Clone/Mesh", "donor": "/World/stage/Donor/Mesh",
                             "geometry_sha256": mesh_geometry_sha256(stage.GetPrimAtPath("/World/stage/Donor/Mesh")),
                             "profile": "static_obstacle"}]}
    path = tmp_path / "collision.json"
    path.write_text(json.dumps(manifest))
    return asset, path, manifest


@pytest.mark.parametrize("mount", [None, "/World/environment"])
def test_native_and_referenced_instances_keep_geometry_and_file_bytes(asset_manifest, mount):
    asset, manifest, _ = asset_manifest
    original = asset.read_bytes()
    if mount is None:
        stage = Usd.Stage.Open(str(asset))
        prefix = "/World"
    else:
        stage = Usd.Stage.CreateInMemory()
        stage.DefinePrim(mount, "Xform").GetReferences().AddReference(str(asset))
        prefix = mount
    target = prefix + "/stage/Clone/Mesh"
    result = prepare_static_instance_colliders(stage, manifest_path=manifest, asset_path=asset, reference_root=mount)
    prim = stage.GetPrimAtPath(target)
    assert not prim.IsInstanceProxy()
    assert UsdPhysics.CollisionAPI(prim).GetCollisionEnabledAttr().Get()
    assert result["profile_overrides"] == {target: "static_obstacle"}
    assert result["mesh_geometry_transforms_visibility_unchanged"] == 3
    assert result["expanded_roots"] == result["seeded_meshes"] == 1
    assert not result["source_saved"]
    assert asset.read_bytes() == original
    assert stage.GetSessionLayer().GetPrimAtPath(prefix + "/stage/Clone")


@pytest.mark.parametrize("fault", ["asset_hash", "geometry", "duplicate", "profile", "escaped_path", "dynamic", "dynamic_ancestor"])
def test_bad_inputs_leave_session_and_instances_untouched(asset_manifest, fault):
    asset, path, manifest = asset_manifest
    stage = Usd.Stage.Open(str(asset))
    if fault == "asset_hash":
        manifest["asset_sha256"] = "0" * 64
    elif fault == "geometry":
        manifest["matches"][0]["geometry_sha256"] = "0" * 64
    elif fault == "duplicate":
        manifest["matches"].append(dict(manifest["matches"][0]))
    elif fault == "profile":
        manifest["matches"][0]["profile"] = "dynamic"
    elif fault == "escaped_path":
        manifest["matches"][0]["donor"] = "/Other/Mesh"
    else:
        body = "/World" if fault == "dynamic_ancestor" else "/World/stage/Clone"
        UsdPhysics.RigidBodyAPI.Apply(stage.GetPrimAtPath(body)).CreateRigidBodyEnabledAttr(True)
    path.write_text(json.dumps(manifest))
    before = stage.GetSessionLayer().ExportToString()
    with pytest.raises(ValueError):
        prepare_static_instance_colliders(stage, manifest_path=path, asset_path=asset)
    assert stage.GetPrimAtPath("/World/stage/Clone/Mesh").IsInstanceProxy()
    assert stage.GetSessionLayer().ExportToString() == before


def test_post_expansion_validation_error_rolls_back_session_changes(asset_manifest, monkeypatch):
    import scene_instance_colliders

    asset, path, _ = asset_manifest
    stage = Usd.Stage.Open(str(asset))
    before = stage.GetSessionLayer().ExportToString()
    original = scene_instance_colliders.mesh_geometry_sha256

    def simulate_changed_geometry_after_expansion(prim):
        if str(prim.GetPath()) == "/World/stage/Clone/Mesh" and not prim.IsInstanceProxy():
            return "0" * 64
        return original(prim)

    monkeypatch.setattr(scene_instance_colliders, "mesh_geometry_sha256", simulate_changed_geometry_after_expansion)
    with pytest.raises(RuntimeError, match="changed mesh geometry"):
        prepare_static_instance_colliders(stage, manifest_path=path, asset_path=asset)
    assert stage.GetSessionLayer().ExportToString() == before
    assert stage.GetPrimAtPath("/World/stage/Clone").IsInstance()
