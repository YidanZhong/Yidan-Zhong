"""UGV traction/solver setup shared by Isaac-side probes.

These helpers mirror the definitions in
``launch_scripts/RetroNeighborhood_Launch.py`` (the mission launcher is the
source of truth for the benchmark drivetrain configuration).  They live here so
Isaac-side probe tools can build the benchmark Jackal without importing the
launcher module, which creates its own ``SimulationApp`` at import time.
The constant names, defaults, and env overrides are kept identical so a probe
applied under the same environment reproduces the mission drivetrain; every
probe records the applied values in its evidence.
"""

from __future__ import annotations

import os
from typing import Any

import carb
from pxr import Gf, PhysxSchema, Sdf, UsdPhysics


def _env_bool(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


AIRGROUND_UGV_WHEEL_STATIC_FRICTION = float(
    os.environ.get("AIRGROUND_UGV_WHEEL_STATIC_FRICTION") or "0.7"
)
AIRGROUND_UGV_WHEEL_DYNAMIC_FRICTION = float(
    os.environ.get("AIRGROUND_UGV_WHEEL_DYNAMIC_FRICTION") or "0.6"
)
AIRGROUND_UGV_WHEEL_FRICTION_COMBINE_MODE = (
    os.environ.get("AIRGROUND_UGV_WHEEL_FRICTION_COMBINE_MODE") or "min"
).strip()
AIRGROUND_UGV_WHEEL_MAX_TORQUE_NM = float(
    os.environ.get("AIRGROUND_UGV_WHEEL_MAX_TORQUE_NM") or "8.0"
)
AIRGROUND_WHEEL_CONTACT_OFFSET_M = float(
    os.environ.get("AIRGROUND_WHEEL_CONTACT_OFFSET_M") or "0.004"
)
AIRGROUND_WHEEL_REST_OFFSET_M = float(
    os.environ.get("AIRGROUND_WHEEL_REST_OFFSET_M") or "0.0"
)
AIRGROUND_UGV_SOLVER_POSITION_ITERATIONS = int(
    os.environ.get("AIRGROUND_UGV_SOLVER_POSITION_ITERATIONS") or "16"
)
AIRGROUND_UGV_SOLVER_VELOCITY_ITERATIONS = int(
    os.environ.get("AIRGROUND_UGV_SOLVER_VELOCITY_ITERATIONS") or "4"
)

AIRGROUND_ENABLE_GROUND_SUPPORT_PLANE = _env_bool("AIRGROUND_ENABLE_GROUND_SUPPORT_PLANE", True)
AIRGROUND_GROUND_SUPPORT_CENTER_X_M = float(
    os.environ.get("AIRGROUND_GROUND_SUPPORT_CENTER_X_M") or "-24.0"
)
AIRGROUND_GROUND_SUPPORT_CENTER_Y_M = float(
    os.environ.get("AIRGROUND_GROUND_SUPPORT_CENTER_Y_M") or "0.0"
)
AIRGROUND_GROUND_SUPPORT_SIZE_X_M = float(
    os.environ.get("AIRGROUND_GROUND_SUPPORT_SIZE_X_M") or "128.0"
)
AIRGROUND_GROUND_SUPPORT_SIZE_Y_M = float(
    os.environ.get("AIRGROUND_GROUND_SUPPORT_SIZE_Y_M") or "128.0"
)
AIRGROUND_GROUND_SUPPORT_TOP_Z_M = float(
    os.environ.get("AIRGROUND_GROUND_SUPPORT_TOP_Z_M") or "0.0"
)
AIRGROUND_GROUND_SUPPORT_THICKNESS_M = float(
    os.environ.get("AIRGROUND_GROUND_SUPPORT_THICKNESS_M") or "0.04"
)
AIRGROUND_GROUND_SUPPORT_CONTACT_OFFSET_M = float(
    os.environ.get("AIRGROUND_GROUND_SUPPORT_CONTACT_OFFSET_M") or "0.004"
)
AIRGROUND_GROUND_SUPPORT_REST_OFFSET_M = float(
    os.environ.get("AIRGROUND_GROUND_SUPPORT_REST_OFFSET_M") or "0.0"
)
AIRGROUND_UGV_CMD_VEL_ANGULAR_GAIN = float(
    # Mirrors the 2026-10-02 realization-bench calibration (see the launcher).
    os.environ.get("AIRGROUND_UGV_CMD_VEL_ANGULAR_GAIN") or "4.0"
)
AIRGROUND_UGV_CMD_VEL_MAX_ANGULAR_RADPS = float(
    os.environ.get("AIRGROUND_UGV_CMD_VEL_MAX_ANGULAR_RADPS") or "4.0"
)
UGV_WHEEL_VELOCITY_SCALE = float(
    os.environ.get("AIRGROUND_JACKAL_WHEEL_VELOCITY_SCALE") or "1.0"
)

#: Jackal wheel links whose colliders must carry an explicit PhysX contact
#: offset (the Clearpath asset leaves them on the 2 cm PhysX default).
UGV_WHEEL_LINK_NAMES: tuple[str, ...] = (
    "front_left_wheel_link",
    "front_right_wheel_link",
    "rear_left_wheel_link",
    "rear_right_wheel_link",
)

#: Wheel drive joints of the Jackal articulation, relative to the robot root.
UGV_WHEEL_JOINT_NAMES: tuple[str, ...] = (
    "front_left_wheel_joint",
    "front_right_wheel_joint",
    "rear_left_wheel_joint",
    "rear_right_wheel_joint",
)

#: PhysX material combine-mode tokens (Isaac Sim "Combine Modes").
PHYSX_COMBINE_MODES: frozenset[str] = frozenset({"average", "min", "multiply", "max"})

UGV_SOLVER_ITERATION_ATTRS: tuple[tuple[str, str], ...] = (
    ("physxArticulation:solverPositionIterationCount", "solver_position_iteration_count"),
    ("physxArticulation:solverVelocityIterationCount", "solver_velocity_iteration_count"),
)


def ensure_articulation_root(stage: Any, prim_path: str, label: str) -> None:
    prim = stage.GetPrimAtPath(prim_path)
    if not prim.IsValid():
        raise RuntimeError(f"{label} prim not found: {prim_path}")
    if prim.HasAPI(UsdPhysics.ArticulationRootAPI):
        carb.log_warn(f"{label} articulation root verified: {prim_path}")
    else:
        UsdPhysics.ArticulationRootAPI.Apply(prim)
        carb.log_warn(f"Applied PhysicsArticulationRootAPI to {label}: {prim_path}")


def _iter_prim_tree(prim: Any) -> Any:
    for child in prim.GetChildren():
        yield child
        yield from _iter_prim_tree(child)


def apply_wheel_contact_offsets(
    stage: Any,
    *,
    robot_prim_path: str,
    contact_offset_m: float,
    rest_offset_m: float,
    wheel_link_names: tuple[str, ...] = UGV_WHEEL_LINK_NAMES,
) -> dict[str, Any]:
    """Pin every Jackal wheel collider to a small, explicit PhysX contact offset."""
    summary: dict[str, Any] = {
        "contact_offset_m": float(contact_offset_m),
        "rest_offset_m": float(rest_offset_m),
        "collider_count": 0,
        "links": [],
        "status": "ok",
    }
    if contact_offset_m <= 0.0 or rest_offset_m < 0.0:
        summary["status"] = "invalid"
        summary["error"] = "contact offset must be positive and rest offset non-negative"
        return summary
    for link_name in wheel_link_names:
        link_path = f"{robot_prim_path.rstrip('/')}/{link_name}"
        link_summary: dict[str, Any] = {"link_path": link_path, "colliders": []}
        link_prim = stage.GetPrimAtPath(link_path)
        if not link_prim.IsValid():
            link_summary["status"] = "missing"
            summary["status"] = "warning"
            summary["links"].append(link_summary)
            continue
        for prim in (link_prim, *_iter_prim_tree(link_prim)):
            if not prim.HasAPI(UsdPhysics.CollisionAPI):
                continue
            collider_summary: dict[str, Any] = {"prim_path": str(prim.GetPath())}
            try:
                physx_collision = PhysxSchema.PhysxCollisionAPI.Apply(prim)
            except Exception as exc:  # pragma: no cover - live Isaac diagnostic path.
                collider_summary["status"] = "failed"
                collider_summary["error"] = f"{type(exc).__name__}: {exc}"
                summary["status"] = "warning"
                link_summary["colliders"].append(collider_summary)
                continue
            for attr_name, value in (
                ("ContactOffset", float(contact_offset_m)),
                ("RestOffset", float(rest_offset_m)),
            ):
                creator = getattr(physx_collision, f"Create{attr_name}Attr", None)
                getter = getattr(physx_collision, f"Get{attr_name}Attr", None)
                attr = creator() if creator is not None else getter() if getter is not None else None
                if attr is None:
                    collider_summary[attr_name] = "unsupported"
                    continue
                attr.Set(value)
                collider_summary[attr_name] = float(attr.Get())
            collider_summary["status"] = "ok"
            link_summary["colliders"].append(collider_summary)
            summary["collider_count"] += 1
        if not link_summary["colliders"]:
            link_summary["status"] = "no_collider"
            summary["status"] = "warning"
        else:
            link_summary["status"] = "ok"
        summary["links"].append(link_summary)
    return summary


def apply_ugv_solver_iterations(
    stage: Any,
    *,
    articulation_prim_path: str,
    position_iterations: int,
    velocity_iterations: int,
) -> dict[str, Any]:
    """Raise the UGV articulation's PhysX solver iteration budget."""
    summary: dict[str, Any] = {
        "articulation_prim_path": articulation_prim_path,
        "requested": {
            "solver_position_iteration_count": int(position_iterations),
            "solver_velocity_iteration_count": int(velocity_iterations),
        },
        "applied": {},
        "status": "ok",
    }
    if position_iterations <= 0 or velocity_iterations <= 0:
        summary["status"] = "invalid"
        summary["error"] = "solver iteration counts must be positive"
        return summary
    prim = stage.GetPrimAtPath(articulation_prim_path)
    if not prim.IsValid():
        summary["status"] = "missing"
        summary["error"] = f"invalid articulation prim: {articulation_prim_path}"
        return summary
    summary["has_articulation_api_before"] = bool(prim.HasAPI(UsdPhysics.ArticulationRootAPI))
    for attr_name, key in UGV_SOLVER_ITERATION_ATTRS:
        value = (
            int(position_iterations)
            if key == "solver_position_iteration_count"
            else int(velocity_iterations)
        )
        attr = prim.GetAttribute(attr_name)
        if not attr.IsValid():
            attr = prim.CreateAttribute(attr_name, Sdf.ValueTypeNames.UInt)
        attr.Set(value)
        summary["applied"][key] = int(attr.Get())
    return summary


def apply_ugv_wheel_traction(
    stage: Any,
    *,
    robot_prim_path: str,
    material_paths: tuple[str, ...],
    static_friction: float,
    dynamic_friction: float,
    friction_combine_mode: str,
    max_torque_nm: float,
    wheel_joint_names: tuple[str, ...] = UGV_WHEEL_JOINT_NAMES,
) -> dict[str, Any]:
    """Make the wheel/ground friction pair explicit and cap the drive torque.

    Both sides of every contact pair get the combine mode (see the mission
    launcher for the measured rationale); the wheel material's friction values
    are written and the four drive joints get ``max_torque_nm``.
    """
    summary: dict[str, Any] = {
        "requested": {
            "dynamic_friction": float(dynamic_friction),
            "friction_combine_mode": friction_combine_mode,
            "max_torque_nm": float(max_torque_nm),
            "static_friction": float(static_friction),
        },
        "materials": [],
        "wheel_joints": [],
        "status": "ok",
    }
    if friction_combine_mode not in PHYSX_COMBINE_MODES:
        summary["status"] = "invalid"
        summary["error"] = f"friction combine mode must be one of {sorted(PHYSX_COMBINE_MODES)}"
        return summary
    if static_friction < 0.0 or dynamic_friction < 0.0 or max_torque_nm <= 0.0:
        summary["status"] = "invalid"
        summary["error"] = "friction must be non-negative and the torque cap positive"
        return summary

    for material_path in material_paths:
        entry: dict[str, Any] = {"path": material_path}
        material_prim = stage.GetPrimAtPath(material_path)
        if not material_prim.IsValid():
            entry["status"] = "missing"
            summary["status"] = "warning"
            summary["materials"].append(entry)
            continue
        try:
            material_api = UsdPhysics.MaterialAPI.Apply(material_prim)
            if material_path.endswith("/wheels"):
                material_api.CreateStaticFrictionAttr().Set(float(static_friction))
                material_api.CreateDynamicFrictionAttr().Set(float(dynamic_friction))
                material_api.CreateRestitutionAttr().Set(0.0)
            applied_attrs: dict[str, Any] = {
                "static_friction": float(material_api.GetStaticFrictionAttr().Get()),
                "dynamic_friction": float(material_api.GetDynamicFrictionAttr().Get()),
                "restitution": float(material_api.GetRestitutionAttr().Get()),
            }
            combine_mode_written = "unavailable"
            try:
                physx_material = PhysxSchema.PhysxMaterialAPI.Apply(material_prim)
                combine_attr = physx_material.CreateFrictionCombineModeAttr()
                combine_attr.Set(friction_combine_mode)
                combine_mode_written = str(combine_attr.Get())
            except Exception as exc:  # pragma: no cover - depends on the Isaac build.
                combine_mode_written = f"failed: {type(exc).__name__}: {exc}"
            applied_attrs["friction_combine_mode"] = combine_mode_written
            entry["applied"] = applied_attrs
            entry["status"] = "ok" if combine_mode_written == friction_combine_mode else "warning"
            if entry["status"] != "ok":
                summary["status"] = "warning"
        except Exception as exc:  # pragma: no cover - live Isaac diagnostic path.
            summary["status"] = "warning"
            entry["error"] = f"{type(exc).__name__}: {exc}"
            entry["status"] = "failed"
        summary["materials"].append(entry)

    for joint_name in wheel_joint_names:
        joint_path = f"{robot_prim_path.rstrip('/')}/{joint_name}"
        joint_summary: dict[str, Any] = {"joint_path": joint_path}
        joint_prim = stage.GetPrimAtPath(joint_path)
        if not joint_prim.IsValid():
            joint_summary["status"] = "missing"
            summary["status"] = "warning"
            summary["wheel_joints"].append(joint_summary)
            continue
        try:
            attr = joint_prim.GetAttribute("drive:angular:physics:maxForce")
            if not attr.IsValid():
                attr = joint_prim.CreateAttribute(
                    "drive:angular:physics:maxForce", Sdf.ValueTypeNames.Float
                )
            current = attr.Get()
            joint_summary["max_force_before"] = float(current) if current is not None else None
            attr.Set(float(max_torque_nm))
            joint_summary["max_force_after"] = float(attr.Get())
            joint_summary["status"] = "ok"
        except Exception as exc:  # pragma: no cover - live Isaac diagnostic path.
            joint_summary["status"] = "failed"
            joint_summary["error"] = f"{type(exc).__name__}: {exc}"
            summary["status"] = "warning"
        summary["wheel_joints"].append(joint_summary)
    return summary
