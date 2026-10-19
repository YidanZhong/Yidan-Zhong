"""AirGround physics profile helpers for Isaac Sim USD scenes.

This module avoids Omni imports so it can be unit-tested with `usd-core`.
Isaac-specific PhysX schema attributes are applied when `pxr.PhysxSchema` is
available inside Isaac Sim.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pxr import Gf, Sdf, UsdGeom, UsdPhysics, UsdShade

from scene_audit import classify_scene_mesh


@dataclass(frozen=True)
class PhysicsProfile:
    meters_per_unit: float = 1.0
    gravity_magnitude: float = 9.81
    physics_hz: int = 250
    solver_type: str = "TGS"
    broadphase_type: str = "MBP"
    enable_ccd: bool = True
    enable_stabilization: bool = True
    enable_gpu_dynamics: bool = False
    ground_static_friction: float = 1.0
    ground_dynamic_friction: float = 0.8
    obstacle_static_friction: float = 0.9
    obstacle_dynamic_friction: float = 0.7
    restitution: float = 0.0
    contact_offset: float = 0.02
    rest_offset: float = 0.0


DEFAULT_AIRGROUND_PHYSICS_PROFILE = PhysicsProfile()


def _physics_scene(stage, path: str):
    scene = stage.GetPrimAtPath(path)
    if scene.IsValid() and scene.IsA(UsdPhysics.Scene):
        return UsdPhysics.Scene(scene)
    return UsdPhysics.Scene.Define(stage, Sdf.Path(path))


def _set_physx_attr(api, attr_name: str, value: Any) -> bool:
    creator = getattr(api, f"Create{attr_name}Attr", None)
    getter = getattr(api, f"Get{attr_name}Attr", None)
    if creator is not None:
        attr = creator()
    elif getter is not None:
        attr = getter()
    else:
        return False
    attr.Set(value)
    return True


def _define_physics_material(stage, path: str, *, static_friction: float, dynamic_friction: float, restitution: float):
    material = UsdShade.Material.Define(stage, Sdf.Path(path))
    material_api = UsdPhysics.MaterialAPI.Apply(material.GetPrim())
    material_api.CreateStaticFrictionAttr().Set(float(static_friction))
    material_api.CreateDynamicFrictionAttr().Set(float(dynamic_friction))
    material_api.CreateRestitutionAttr().Set(float(restitution))
    return material


def _bind_physics_material(prim, material) -> None:
    """Bind a physics material without clobbering the mesh's visual material.

    2026-09-13: ``UsdShade.MaterialBindingAPI.Bind(material)`` writes the default
    ``material:binding`` relationship, which replaced the scene's visual material
    on every ground and obstacle mesh.  The onboard cameras then rendered the
    whole neighborhood as a flat white "untextured" model while the sky (which
    has no physics material) kept its texture - exactly the "white model" the
    reviewers reported.  Binding with the ``physics`` purpose writes
    ``material:binding:physics`` instead: PhysX still finds the friction values
    and RTX keeps shading the original material.
    """
    api = UsdShade.MaterialBindingAPI.Apply(prim)
    try:
        api.Bind(material, UsdShade.Tokens.weakerThanDescendants, "physics")
    except TypeError:  # older/looser python bindings take plain strings
        api.Bind(material, "weakerThanDescendants", "physics")


def _iter_descendants(prim):
    for child in prim.GetChildren():
        yield child
        yield from _iter_descendants(child)


def configure_airground_physics_profile(
    stage,
    *,
    root_prim_path: str = "/World/stage",
    physics_scene_path: str = "/World/PhysicsScene",
    profile: PhysicsProfile = DEFAULT_AIRGROUND_PHYSICS_PROFILE,
    profile_overrides: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Apply AirGround stage, scene, material, and PhysX contact settings."""

    UsdGeom.SetStageMetersPerUnit(stage, profile.meters_per_unit)
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)

    scene = _physics_scene(stage, physics_scene_path)
    scene.CreateGravityDirectionAttr().Set(Gf.Vec3f(0.0, 0.0, -1.0))
    scene.CreateGravityMagnitudeAttr().Set(float(profile.gravity_magnitude))

    summary: dict[str, Any] = {
        "meters_per_unit": profile.meters_per_unit,
        "up_axis": "Z",
        "gravity_magnitude": profile.gravity_magnitude,
        "physics_scene": physics_scene_path,
        "physx_schema_available": False,
        "physx_scene_attrs": {},
        "ground_material_bindings": 0,
        "obstacle_material_bindings": 0,
        "contact_offsets": 0,
        "rest_offsets": 0,
        "skipped": 0,
    }

    try:
        from pxr import PhysxSchema  # type: ignore
    except ImportError:
        PhysxSchema = None  # type: ignore

    if PhysxSchema is not None:
        summary["physx_schema_available"] = True
        physx_scene = PhysxSchema.PhysxSceneAPI.Apply(scene.GetPrim())
        physx_attrs = {
            "TimeStepsPerSecond": int(profile.physics_hz),
            "SolverType": profile.solver_type,
            "BroadphaseType": profile.broadphase_type,
            "EnableCCD": bool(profile.enable_ccd),
            "EnableStabilization": bool(profile.enable_stabilization),
            "EnableGPUDynamics": bool(profile.enable_gpu_dynamics),
        }
        for attr_name, value in physx_attrs.items():
            if _set_physx_attr(physx_scene, attr_name, value):
                summary["physx_scene_attrs"][attr_name] = value

    ground_material = _define_physics_material(
        stage,
        "/World/PhysicsMaterials/airground_ground_contact",
        static_friction=profile.ground_static_friction,
        dynamic_friction=profile.ground_dynamic_friction,
        restitution=profile.restitution,
    )
    obstacle_material = _define_physics_material(
        stage,
        "/World/PhysicsMaterials/airground_obstacle_contact",
        static_friction=profile.obstacle_static_friction,
        dynamic_friction=profile.obstacle_dynamic_friction,
        restitution=profile.restitution,
    )

    root_prim = stage.GetPrimAtPath(root_prim_path)
    if not root_prim.IsValid():
        summary["skipped"] += 1
        return summary

    for prim in _iter_descendants(root_prim):
        if not prim.IsA(UsdGeom.Mesh):
            continue
        has_collision = prim.HasAPI(UsdPhysics.CollisionAPI)
        profile_name = classify_scene_mesh(
            str(prim.GetPath()),
            has_collision=has_collision,
            has_rigid_body=prim.HasAPI(UsdPhysics.RigidBodyAPI),
        )
        profile_name = (profile_overrides or {}).get(str(prim.GetPath()), profile_name)
        if profile_name == "ground":
            _bind_physics_material(prim, ground_material)
            summary["ground_material_bindings"] += 1
        elif profile_name == "static_obstacle":
            _bind_physics_material(prim, obstacle_material)
            summary["obstacle_material_bindings"] += 1
        else:
            summary["skipped"] += 1
            continue

        if PhysxSchema is not None:
            physx_collision = PhysxSchema.PhysxCollisionAPI.Apply(prim)
            if _set_physx_attr(physx_collision, "ContactOffset", float(profile.contact_offset)):
                summary["contact_offsets"] += 1
            if _set_physx_attr(physx_collision, "RestOffset", float(profile.rest_offset)):
                summary["rest_offsets"] += 1

    return summary
