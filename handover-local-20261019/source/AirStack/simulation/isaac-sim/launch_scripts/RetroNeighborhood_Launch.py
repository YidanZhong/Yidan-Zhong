#!/usr/bin/env python
import json
import faulthandler
import math
import os
import re
import time
from pathlib import Path
from typing import Any, Mapping

import carb
from isaacsim import SimulationApp

_STARTUP_TRACE_FILE = os.environ.get("AIRGROUND_STARTUP_TRACE_FILE") or ""
_STARTUP_MONOTONIC_S = time.monotonic()


def _trace_startup(stage: str, **details: Any) -> None:
    """Optional wall-clock stage evidence; it never changes simulation state."""
    if not _STARTUP_TRACE_FILE:
        return
    payload = {"stage": stage, "wall_time_s": time.time(),
               "monotonic_s": time.monotonic(),
               "elapsed_s": time.monotonic() - _STARTUP_MONOTONIC_S, **details}
    path = Path(_STARTUP_TRACE_FILE)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(payload, sort_keys=True) + "\n")

# Optional startup/hang evidence without a debugger or ptrace permission.
_STACK_WATCHDOG_S = float(os.environ.get("AIRGROUND_STACK_WATCHDOG_S") or "0")
if not math.isfinite(_STACK_WATCHDOG_S) or _STACK_WATCHDOG_S < 0:
    raise ValueError("AIRGROUND_STACK_WATCHDOG_S must be finite and >= 0")
if _STACK_WATCHDOG_S:
    faulthandler.dump_traceback_later(_STACK_WATCHDOG_S, repeat=True)


def _env_bool(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None or value.strip() == "":
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be a boolean: true/false, 1/0, yes/no, or on/off")


def _env_csv_tokens(name: str) -> set[str] | None:
    value = os.environ.get(name)
    if value is None or value.strip() == "":
        return None
    tokens = {token.strip() for token in value.split(",") if token.strip()}
    if not tokens or "all" in tokens:
        return None
    return tokens


def _compact_float_sequence(value: Any, *, limit: int = 8) -> list[float] | None:
    """Return a short JSON-safe float list for diagnostics."""
    if value is None:
        return None
    try:
        return [float(item) for item in list(value)[:limit]]
    except Exception:
        return None


AIRGROUND_HEADLESS = _env_bool("AIRGROUND_HEADLESS", False)
AIRGROUND_CPU_THREAD_LIMIT = int(os.environ.get("AIRGROUND_CPU_THREAD_LIMIT") or "0")
if AIRGROUND_CPU_THREAD_LIMIT < 0:
    raise ValueError("AIRGROUND_CPU_THREAD_LIMIT must be >= 0")
AIRGROUND_RENDER = _env_bool("AIRGROUND_RENDER", not AIRGROUND_HEADLESS)
AIRGROUND_RENDERER = os.environ.get("AIRGROUND_RENDERER") or (
    "MinimalRendering" if AIRGROUND_HEADLESS and not AIRGROUND_RENDER else "RayTracedLighting"
)
# Isaac Sim's SimulationApp only recognises RaytracedLighting/PathTracing.  Any
# other value is written verbatim to ``/rtx/rendermode``; the RTX pipeline then
# never produces a frame and ``world.step(render=True)`` blocks forever while
# the carb tasking pool spins at full CPU.  Fail loud with a working renderer
# instead of hanging without a usable error.
AIRGROUND_RENDERER_FALLBACK_REASON = None
if AIRGROUND_RENDER and AIRGROUND_RENDERER.strip().lower() not in {
    "raytracedlighting",
    "pathtracing",
}:
    AIRGROUND_RENDERER_FALLBACK_REASON = (
        f"AIRGROUND_RENDERER={AIRGROUND_RENDERER!r} is not a supported Isaac renderer; "
        "falling back to RayTracedLighting because render=True cannot produce frames otherwise"
    )
    AIRGROUND_RENDERER = "RayTracedLighting"

AIRGROUND_RENDER_WIDTH = int(os.environ.get("AIRGROUND_RENDER_WIDTH") or ("64" if AIRGROUND_HEADLESS else "1280"))
AIRGROUND_RENDER_HEIGHT = int(os.environ.get("AIRGROUND_RENDER_HEIGHT") or ("64" if AIRGROUND_HEADLESS else "720"))
AIRGROUND_MINIMAL_SHADING_MODE = int(
    os.environ.get("AIRGROUND_MINIMAL_SHADING_MODE") or ("4" if AIRGROUND_HEADLESS and not AIRGROUND_RENDER else "0")
)
AIRGROUND_DISABLE_VIEWPORT_UPDATES = _env_bool(
    "AIRGROUND_DISABLE_VIEWPORT_UPDATES",
    AIRGROUND_HEADLESS and not AIRGROUND_RENDER,
)
AIRGROUND_RENDER_STARTUP_WARMUP_STEPS = int(os.environ.get("AIRGROUND_RENDER_STARTUP_WARMUP_STEPS") or "0")
AIRGROUND_RENDER_MAIN_LOOP_MODE = os.environ.get("AIRGROUND_RENDER_MAIN_LOOP_MODE", "world_step").strip().lower()
if AIRGROUND_RENDER_MAIN_LOOP_MODE not in {"world_step", "replicator_pulse"}:
    raise ValueError("AIRGROUND_RENDER_MAIN_LOOP_MODE must be 'world_step' or 'replicator_pulse'")
# 0 (the default) means "derive from AIRGROUND_RENDER_HZ" once the camera
# publish rate is known; see the rendering-cadence block below.
AIRGROUND_RENDER_PULSE_EVERY_N_ENV = int(os.environ.get("AIRGROUND_RENDER_PULSE_EVERY_N") or "0")
if AIRGROUND_RENDER_PULSE_EVERY_N_ENV < 0:
    raise ValueError("AIRGROUND_RENDER_PULSE_EVERY_N must be >= 0")
AIRGROUND_MAIN_LOOP_TRACE_EVERY_N = int(os.environ.get("AIRGROUND_MAIN_LOOP_TRACE_EVERY_N") or "0")
AIRGROUND_MAIN_LOOP_TRACE_FILE = os.environ.get("AIRGROUND_MAIN_LOOP_TRACE_FILE") or ""
AIRGROUND_CREATE_NEW_STAGE = _env_bool("AIRGROUND_CREATE_NEW_STAGE", not AIRGROUND_HEADLESS)
AIRGROUND_SCENE_COLLIDER_MODE = os.environ.get("AIRGROUND_SCENE_COLLIDER_MODE", "profiled").strip().lower()
AIRGROUND_SKIP_CLEANUP_ON_CLOSE = _env_bool("AIRGROUND_SKIP_CLEANUP_ON_CLOSE", AIRGROUND_HEADLESS)
AIRGROUND_POST_STOP_UPDATES = int(
    os.environ.get("AIRGROUND_POST_STOP_UPDATES") or ("0" if AIRGROUND_HEADLESS else "3")
)
AIRGROUND_ENABLE_GROUND_SUPPORT_PLANE = _env_bool("AIRGROUND_ENABLE_GROUND_SUPPORT_PLANE", True)
AIRGROUND_GROUND_SUPPORT_CENTER_X_M = float(os.environ.get("AIRGROUND_GROUND_SUPPORT_CENTER_X_M") or "-24.0")
AIRGROUND_GROUND_SUPPORT_CENTER_Y_M = float(os.environ.get("AIRGROUND_GROUND_SUPPORT_CENTER_Y_M") or "0.0")
AIRGROUND_GROUND_SUPPORT_SIZE_X_M = float(os.environ.get("AIRGROUND_GROUND_SUPPORT_SIZE_X_M") or "128.0")
AIRGROUND_GROUND_SUPPORT_SIZE_Y_M = float(os.environ.get("AIRGROUND_GROUND_SUPPORT_SIZE_Y_M") or "128.0")
AIRGROUND_GROUND_SUPPORT_TOP_Z_M = float(os.environ.get("AIRGROUND_GROUND_SUPPORT_TOP_Z_M") or "0.0")
AIRGROUND_GROUND_SUPPORT_THICKNESS_M = float(os.environ.get("AIRGROUND_GROUND_SUPPORT_THICKNESS_M") or "0.04")
# 2026-09-21 (jitter fix, measured): the support plane and the Jackal wheel
# colliders used to rely on the 2 cm PhysX default contact offset, which makes
# the wheels ride on a soft contact cushion: on a GT-flat straight leg the
# chassis z oscillated 0.4-2.1 cm at 3-5 Hz (17.8 % of samples > 5 mm off the
# 0.0635 m ride height) while roll/pitch stayed ~0.  The Isaac Sim docs describe
# the contact offset as "how far from the collision geometry the engine starts
# generating contact constraints" and warn that both extremes are wrong, so the
# wheels *and* the ground are now pinned to a small, explicit offset.
AIRGROUND_GROUND_SUPPORT_CONTACT_OFFSET_M = float(
    os.environ.get("AIRGROUND_GROUND_SUPPORT_CONTACT_OFFSET_M") or "0.004"
)
AIRGROUND_GROUND_SUPPORT_REST_OFFSET_M = float(
    os.environ.get("AIRGROUND_GROUND_SUPPORT_REST_OFFSET_M") or "0.0"
)
AIRGROUND_WHEEL_CONTACT_OFFSET_M = float(
    os.environ.get("AIRGROUND_WHEEL_CONTACT_OFFSET_M") or "0.004"
)
AIRGROUND_WHEEL_REST_OFFSET_M = float(
    os.environ.get("AIRGROUND_WHEEL_REST_OFFSET_M") or "0.0"
)
# 2026-09-21 (jitter fix, second lever): NVIDIA's own checklist for a bouncing
# wheeled robot also calls for raising the articulation solver iteration counts
# (position 16-64, velocity 4-8) so the contact and the wheel velocity drive are
# resolved instead of fought.  Measured on the flat-ground route probe
# (``runs/p0_ugv_ogn/20260913_migration/jitter_probe_20260921``): pinning both
# sides of the contact pair to 4 mm alone left the driven chassis z swinging
# 0.031-0.073 m, so the solver budget is raised here as well.
AIRGROUND_UGV_SOLVER_POSITION_ITERATIONS = int(
    os.environ.get("AIRGROUND_UGV_SOLVER_POSITION_ITERATIONS") or "16"
)
AIRGROUND_UGV_SOLVER_VELOCITY_ITERATIONS = int(
    os.environ.get("AIRGROUND_UGV_SOLVER_VELOCITY_ITERATIONS") or "4"
)
# 2026-09-21 (in-place turning).  A four-wheel skid-steer has to slide its
# contacts sideways to yaw, so the *steady* in-place spin rate is set by geometry
# only: resolving the four contact forces gives ``omega = omega_cmd * b^2/(a^2 +
# b^2) = 0.67 * omega_cmd`` (b = 0.1878 m, a = 0.131 m), independent of the
# friction coefficient and the mass.  What the friction is *not* independent of
# is whether the drives can hold their commanded wheel speed against the scrub
# reaction: each wheel must sustain ``0.574 * mu * N`` of longitudinal force
# (``tan(theta) = b/a``), i.e. ``tau = 0.574 * mu * N * r``.  Measured
# 2026-09-21 on the spin probe (``--spin-probe-only``):
#   average combine, 3 N*m  -> yaw execution 0.2-1.5 %   (right wheels stalled)
#   max combine,     5 N*m  -> yaw execution 17 %        (right wheels 56 % of command)
# so the binding constraint was the torque/scrub product, not the geometry: the
# configuration that reaches the geometric ceiling is a *moderate* tyre friction
# (0.7/0.6, forced onto the pair with the ``min`` combine mode so the scene
# materials cannot raise it again) plus a torque cap (8 N*m) that keeps every
# wheel rolling instead of stalling.
AIRGROUND_UGV_WHEEL_STATIC_FRICTION = float(
    os.environ.get("AIRGROUND_UGV_WHEEL_STATIC_FRICTION") or "0.7"
)
AIRGROUND_UGV_WHEEL_DYNAMIC_FRICTION = float(
    os.environ.get("AIRGROUND_UGV_WHEEL_DYNAMIC_FRICTION") or "0.6"
)
AIRGROUND_UGV_WHEEL_FRICTION_COMBINE_MODE = (
    os.environ.get("AIRGROUND_UGV_WHEEL_FRICTION_COMBINE_MODE") or "min"
).strip().lower()
AIRGROUND_UGV_WHEEL_MAX_TORQUE_NM = float(
    os.environ.get("AIRGROUND_UGV_WHEEL_MAX_TORQUE_NM") or "8.0"
)
# 2026-09-21 (command shaping).  Nav2's controllers assume command == execution,
# but this skid-steer realises only ~0.40 of the commanded in-place yaw rate
# (measured with the spin probe, linearly, both directions).  The yaw command is
# therefore shaped before the differential split so the standard Nav2 tuning
# keeps its meaning; the *achievable* body yaw rate is unchanged.
AIRGROUND_UGV_CMD_VEL_ANGULAR_GAIN = float(
    # 2026-10-02 (realization bench, `runs/p0_ugv_ogn/20261002_realization/`):
    # 4.0 makes command == execution on the 5 cm edge rig (arcs realize
    # 0.48-1.12, in-place 0.92-1.2) where 2.5 realized 0.11-0.19 on arcs.
    os.environ.get("AIRGROUND_UGV_CMD_VEL_ANGULAR_GAIN") or "4.0"
)
AIRGROUND_UGV_CMD_VEL_MAX_ANGULAR_RADPS = float(
    # 2026-09-22 (measured speed doubling): 1.2 -> 2.4 rad/s.  With the old clamp
    # every rotation command above 0.48 rad/s was pinned to 1.2 and the realized
    # in-place yaw stayed at ~0.2 rad/s; at 2.4 the same command realizes
    # 0.942 rad/s (roll <= 0.25 deg, nominal ride height).  2026-10-02
    # (realization bench): at the 4.0 gain the 2.4 clamp clipped the gate arc
    # (3.56 -> 2.4, realized 0.15-0.19); above 3.6 it realizes 0.66-1.0, so the
    # default moves to 4.0.  Keep in sync with ``docker/docker-compose.yaml``
    # (the container default) and ``tools/run_nav2_smoke.py`` (the Nav2 ceiling).
    os.environ.get("AIRGROUND_UGV_CMD_VEL_MAX_ANGULAR_RADPS") or "4.0"
)
AIRGROUND_UAV_RESET_FORCE_SKIP_STEPS = int(os.environ.get("AIRGROUND_UAV_RESET_FORCE_SKIP_STEPS") or "180")
_AIRGROUND_SIMULATOR_VERSION = (
    os.environ.get("AIRGROUND_SIMULATOR_VERSION") or os.environ.get("ISAAC_VERSION") or ""
).strip()
AIRGROUND_EPISODE_WORLD_RESET = _env_bool(
    "AIRGROUND_EPISODE_WORLD_RESET",
    _AIRGROUND_SIMULATOR_VERSION not in {"4.5.0"},
)
AIRGROUND_UAV_PREARM_STRICT_TELEMETRY = _env_bool(
    "AIRGROUND_UAV_PREARM_STRICT_TELEMETRY",
    not _AIRGROUND_SIMULATOR_VERSION.startswith("4.5"),
)
UAV_PX4_ENABLE_LOCKSTEP = _env_bool(
    "AIRGROUND_UAV_PX4_ENABLE_LOCKSTEP",
    not _AIRGROUND_SIMULATOR_VERSION.startswith("4.5"),
)
AIRGROUND_UAV_CONTROL_STEP_RENDER = _env_bool(
    "AIRGROUND_UAV_CONTROL_STEP_RENDER",
    False if _AIRGROUND_SIMULATOR_VERSION.startswith("4.5") else AIRGROUND_RENDER,
)
# The OFFBOARD control runner drives one physics step per pump iteration and
# then blocks on MAVLink, which left the mission control window at ~0.3x real
# time while PX4 free-ran on the wall clock (2026-09-12 bug).
# ``_step_once_for_uav_control`` therefore catches up to the wall clock by
# default; these knobs bound that catch-up and allow disabling it.
AIRGROUND_UAV_CONTROL_STEP_CATCHUP = _env_bool("AIRGROUND_UAV_CONTROL_STEP_CATCHUP", True)
AIRGROUND_UAV_CONTROL_MAX_CATCHUP_STEPS = max(
    1,
    int(os.environ.get("AIRGROUND_UAV_CONTROL_MAX_CATCHUP_STEPS") or "25"),
)
AIRGROUND_USE_DIRECT_JACKAL_ADAPTER = _env_bool(
    "AIRGROUND_USE_DIRECT_JACKAL_ADAPTER",
    _AIRGROUND_SIMULATOR_VERSION.startswith("4.5"),
)
PEGASUS_EXT_FOLDER = os.path.expanduser(
    os.environ.get("AIRGROUND_PEGASUS_EXT_FOLDER")
    or "~/.local/share/ov/data/documents/Kit/shared/exts"
)
_APP_EXTRA_ARGS = ["--ext-folder", PEGASUS_EXT_FOLDER]
if _env_bool("AIRGROUND_USE_FABRIC_STATE", False):
    # NVIDIA requires this before opening an instanced stage when Fabric
    # supplies its runtime transforms to OmniHydra.
    _APP_EXTRA_ARGS.append("--/persistent/omnihydra/useSceneGraphInstancing=true")
_PHYSX_THREADS = os.environ.get("AIRGROUND_PHYSX_THREADS", "").strip()
if _PHYSX_THREADS:
    if int(_PHYSX_THREADS) < 0:
        raise ValueError("AIRGROUND_PHYSX_THREADS must be nonnegative")
    # Configure before Kit/PhysX allocates its dispatcher, not just after
    # World construction. A changed setting does not prove a live pool changed.
    _APP_EXTRA_ARGS.append(f"--/persistent/physics/numThreads={int(_PHYSX_THREADS)}")
if AIRGROUND_CPU_THREAD_LIMIT:
    # Rootless no-cgroup Docker exposes the full host core count even when
    # --cpus is requested. Configure Kit before its tasking pool is created.
    _APP_EXTRA_ARGS.append(
        f"--/plugins/carb.tasking.plugin/threadCount={AIRGROUND_CPU_THREAD_LIMIT}"
    )
    _APP_EXTRA_ARGS.append(
        f"--/plugins/omni.tbb.globalcontrol/maxThreadCount={AIRGROUND_CPU_THREAD_LIMIT}"
    )

print(
    "AirGround SimulationApp config: "
    f"headless={AIRGROUND_HEADLESS}, render={AIRGROUND_RENDER}, "
    f"renderer={AIRGROUND_RENDERER}, minimal_shading_mode={AIRGROUND_MINIMAL_SHADING_MODE}, "
    f"disable_viewport_updates={AIRGROUND_DISABLE_VIEWPORT_UPDATES}, "
    f"create_new_stage={AIRGROUND_CREATE_NEW_STAGE}, "
    f"render_main_loop_mode={AIRGROUND_RENDER_MAIN_LOOP_MODE}, "
    f"uav_control_step_render={AIRGROUND_UAV_CONTROL_STEP_RENDER}, "
    f"cpu_thread_limit={AIRGROUND_CPU_THREAD_LIMIT}, "
    f"direct_jackal_adapter={AIRGROUND_USE_DIRECT_JACKAL_ADAPTER}, "
    f"renderer_fallback={AIRGROUND_RENDERER_FALLBACK_REASON}",
    flush=True,
)

def _parse_cpu_list(text: str) -> set[int]:
    cpus: set[int] = set()
    for part in text.split(","):
        part = part.strip()
        if not part:
            continue
        lo, _, hi = part.partition("-")
        cpus.update(range(int(lo), int(hi or lo) + 1))
    return cpus


# SimMT-6 NUMA pinning: rootless Docker here does not delegate the cpuset
# controller (compose ``cpuset`` is silently ignored, measured 2026-10-11), so
# the Kit process pins itself before SimulationApp starts; every thread Kit
# creates afterwards inherits the mask.  Empty = unpinned (unchanged).
AIRGROUND_ISAAC_CPU_AFFINITY = os.environ.get("AIRGROUND_ISAAC_CPU_AFFINITY", "").strip()
if AIRGROUND_ISAAC_CPU_AFFINITY:
    _requested_cpus = _parse_cpu_list(AIRGROUND_ISAAC_CPU_AFFINITY)
    os.sched_setaffinity(0, _requested_cpus)
    _effective_cpus = os.sched_getaffinity(0)
    if _effective_cpus != _requested_cpus:
        raise RuntimeError(
            f"AIRGROUND_ISAAC_CPU_AFFINITY={AIRGROUND_ISAAC_CPU_AFFINITY} not applied: "
            f"effective {sorted(_effective_cpus)}"
        )
    print(f"AirGround CPU affinity: {len(_effective_cpus)} CPUs ({AIRGROUND_ISAAC_CPU_AFFINITY})", flush=True)

# SimMT opt-in: a physical core of its own for the Kit main thread (see airground_sidecar/main_core.py).
# The mask "everything but that core" is taken before SimulationApp so every Kit thread inherits it; the
# main thread moves onto the core after start-up and a scanner keeps every other thread off it.
AIRGROUND_MAIN_THREAD_CPU = os.environ.get("AIRGROUND_MAIN_THREAD_CPU", "").strip()
_MAIN_CORE_PLAN: Any = None
if AIRGROUND_MAIN_THREAD_CPU:
    import sys  # noqa: E402 - the module-level import comes after SimulationApp
    _main_core_dir = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "airground_sidecar"))
    if _main_core_dir not in sys.path:
        sys.path.insert(0, _main_core_dir)
    import main_core as _main_core  # noqa: E402

    _MAIN_CORE_PLAN = _main_core.reserve(AIRGROUND_MAIN_THREAD_CPU, log=lambda m: print(m, flush=True),
                                         confine=bool(AIRGROUND_ISAAC_CPU_AFFINITY))

_trace_startup("before_simulation_app")
simulation_app = SimulationApp(
    {
        "headless": AIRGROUND_HEADLESS,
        "hide_gui": AIRGROUND_HEADLESS,
        "renderer": AIRGROUND_RENDERER,
        "minimal_shading_mode": AIRGROUND_MINIMAL_SHADING_MODE,
        "anti_aliasing": 0 if AIRGROUND_HEADLESS and not AIRGROUND_RENDER else 3,
        # SimulationApp forwards this flag to /rtx/materialDb/syncLoads,
        # /rtx/hydra/materialSyncLoads and /omni.kit.plugin/syncUsdLoads.  With
        # sync_loads=False (the previous headless value) the first
        # world.step(render=True) deadlocks: the main thread parks inside
        # librtx.materialdb.plugin -> libcarb.tasking waiting for an async MDL
        # compile task while every tasking worker idles, so no frame is ever
        # produced (gdb stack captured in
        # runs/local_isaac45_stacktrace_render_20260911_152946/isaac_gdb_threads.txt).
        "sync_loads": True,
        "multi_gpu": False if AIRGROUND_HEADLESS else True,
        "create_new_stage": AIRGROUND_CREATE_NEW_STAGE,
        "disable_viewport_updates": AIRGROUND_DISABLE_VIEWPORT_UPDATES,
        "width": AIRGROUND_RENDER_WIDTH,
        "height": AIRGROUND_RENDER_HEIGHT,
        "extra_args": _APP_EXTRA_ARGS,
    }
)
if _MAIN_CORE_PLAN is not None:
    _main_core.pin_main(_MAIN_CORE_PLAN)
    _main_core.start_scanner(_MAIN_CORE_PLAN)
_trace_startup("after_simulation_app", kit_settings={
    key: carb.settings.get_settings().get(key) for key in (
        "/app/runLoops/main/rateLimitEnabled", "/app/runLoops/main/rateLimitFrequency",
        "/app/runLoops/main/rateLimitUseBusyLoop", "/app/player/useFixedTimeStepping",
        "/app/renderer/skipWhileMinimized", "/rtx/materialDb/syncLoads",
    )
})

import sys
import time
import types
import traceback

import numpy as np
import omni.graph.core as og
import omni.kit.app
import omni.timeline
import omni.usd
import omni.client
from pxr import Gf, Sdf, Usd, UsdGeom, UsdPhysics
try:
    from scipy.spatial.transform import Rotation as ScipyRotation
except Exception:
    ScipyRotation = None

from isaacsim.core.api.world import World
try:
    from isaacsim.core.experimental.prims import Articulation, RigidPrim
except Exception:
    try:
        from isaacsim.core.prims import Articulation, RigidPrim
    except Exception:
        Articulation = None
        RigidPrim = None

from pegasus.simulator.logic.interface.pegasus_interface import PegasusInterface
from pegasus.simulator.logic.vehicles.airground_dock_joint import (
    AirGroundDockJointConfig,
    AirGroundDockJointController,
    _multiply_quaternions_wxyz,
    docked_uav_root_world_pose,
    docked_uav_world_pose,
)
from pegasus.simulator.logic.vehicles.jackal import (
    JackalDirectJointVelocityRobot,
    JackalWheeledRobot,
)
from pegasus.simulator.logic.vehicles.jackal_diff_drive import JackalDriveConfig
def _install_physx_velocity_caller_trace() -> None:
    """Record the Python call sites that query PhysX body velocities.

    Isaac Sim 4.5 logs ``Incompatible size of velocity tensor ... expected total
    size 6, received total size 18 with shape (3, 6)`` from
    ``SingleArticulation.get_linear_velocity``/``get_angular_velocity`` (and the
    RigidPrim equivalents) whenever the underlying view holds three prims.  The
    AirGround Jackal state publisher no longer uses that path, yet the storm
    persisted (~95 lines/s, twice per physics step), so the remaining caller has
    to be identified from a real stack instead of by reading code.  Gated behind
    AIRGROUND_TRACE_PHYSX_VELOCITY_CALLERS so normal runs are unaffected.
    """

    if os.environ.get("AIRGROUND_TRACE_PHYSX_VELOCITY_CALLERS", "").strip().lower() not in {
        "1",
        "true",
        "yes",
        "on",
    }:
        return
    trace_path = Path(os.environ.get("AIRGROUND_PHYSX_VELOCITY_TRACE_PATH", "/tmp/airground_physx_velocity_callers.log"))
    seen: set[str] = set()

    def _wrap(cls: Any, method_name: str, label: str) -> None:
        original = getattr(cls, method_name, None)
        if original is None or getattr(original, "_airground_traced", False):
            return

        def _traced(self, *args, **kwargs):
            try:
                stack = "".join(traceback.format_stack(limit=8)[:-1])
                key = f"{label}:{stack.splitlines()[-1] if stack else ''}"
                if key not in seen:
                    seen.add(key)
                    with open(trace_path, "a", encoding="utf-8") as stream:
                        stream.write(f"=== {label} call site ===\n{stack}\n")
            except Exception:
                pass
            return original(self, *args, **kwargs)

        setattr(_traced, "_airground_traced", True)
        try:
            setattr(cls, method_name, _traced)
        except Exception:
            pass

    candidates: list[Any] = []
    for module_name, attr_name in (
        ("isaacsim.core.prims", "SingleArticulation"),
        ("isaacsim.core.prims", "SingleRigidPrim"),
        ("isaacsim.core.prims", "Articulation"),
        ("isaacsim.core.prims", "RigidPrim"),
        ("isaacsim.core.prims.impl.articulation", "Articulation"),
        ("isaacsim.core.prims.impl.rigid_prim", "RigidPrim"),
        ("isaacsim.core.prims.impl.single_articulation", "SingleArticulation"),
        ("isaacsim.core.prims.impl.single_rigid_prim", "SingleRigidPrim"),
        ("omni.physics.tensors.impl.api", "ArticulationView"),
        ("omni.physics.tensors.impl.api", "RigidBodyView"),
        ("omni.physics.tensors.impl.api", "RigidPrimView"),
    ):
        try:
            module = __import__(module_name, fromlist=[attr_name])
            candidates.append(getattr(module, attr_name))
        except Exception:
            continue
    for cls in candidates:
        if cls is None:
            continue
        for method_name in (
            "get_linear_velocity",
            "get_angular_velocity",
            "get_velocities",
            "get_linear_velocities",
            "get_angular_velocities",
        ):
            _wrap(cls, method_name, f"{cls.__name__}.{method_name}")


_install_physx_velocity_caller_trace()

from pegasus.simulator.logic.vehicles.jackal_proximity_scan import (
    JackalProximityScanConfig,
    JackalProximityScanPublisher,
)
from pegasus.simulator.logic.vehicles.jackal_proximity_cloud import (
    DEFAULT_ELEVATION_DEG,
    JackalProximityCloudConfig,
    JackalProximityCloudPublisher,
)
from pegasus.simulator.logic.vehicles.jackal_state_publisher import (
    JackalContactPublisher,
    JackalContactPublisherConfig,
    JackalSensorFrame,
    JackalStatePublisher,
    JackalStatePublisherConfig,
)
from pegasus.simulator.logic.vehicles.multirotor_state_publisher import (
    MultirotorStatePublisher,
    MultirotorStatePublisherConfig,
)
from pegasus.simulator.logic.vehicles.multirotor_paths import MultirotorPrimPaths
from pegasus.simulator.logic.vehicles.multirotor import _env_int as _multirotor_env_int
from pegasus.simulator.logic.vehicles.rgbd_camera_publisher import (
    AirGroundRgbdCameraPublisher,
    RgbdCameraPublisherConfig,
    RgbdCameraSurfaceConfig,
)
from pegasus.simulator.ogn.OgnPegasusMultirotorArduPilotNodeDatabase import (
    OgnPegasusMultirotorArduPilotNodeDatabase,
)
from pegasus.simulator.ogn.OgnPegasusMultirotorPX4NodeDatabase import (
    OgnPegasusMultirotorPX4NodeDatabase,
)
from pegasus.simulator.ogn.api.spawn_multirotor import spawn_px4_multirotor_node
from pegasus.simulator.ogn.api.spawn_zed_camera import (
    add_zed_stereo_camera_subgraph,
    attach_zed_legacy_omnigraph_writers,
    attach_zed_replicator_writers,
    rebind_detached_camera_mounts,
)
from pegasus.simulator.ogn.api.spawn_ouster_lidar import add_ouster_lidar_subgraph
from pegasus.simulator.ogn.python.nodes.OgnPegasusMultirotorArduPilotNode import (
    OgnPegasusMultirotorArduPilotNode,
)
from pegasus.simulator.ogn.python.nodes.OgnPegasusMultirotorPX4Node import (
    OgnPegasusMultirotorPX4Node,
)
from pegasus.simulator.logic.backends.tools.px4_launch_tool import PX4LaunchTool

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "utils"))
import scene_prep
from scene_prep import (
    scale_stage_prim, add_profiled_colliders, add_dome_light, get_stage_meters_per_unit,
    reference_root_prims_under_world, dedupe_physics_scenes,
    add_orthographic_camera, add_overhead_camera_publisher, configure_airground_physics_profile,
    add_static_obstacle_box_proxies, add_ground_support_plane,
)

# --------------------- CONFIGURATION ---------------------
DEFAULT_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
PROJECT_ROOT = os.environ.get("AIRGROUND_PROJECT_ROOT") or DEFAULT_PROJECT_ROOT
DEFAULT_ENV_URL = os.path.join(
    PROJECT_ROOT,
    "scenes/RetroNeighborhood/RetroNeighborhood_Export.usd",
)
ENV_URL = os.environ.get("AIRGROUND_ENV_URL") or DEFAULT_ENV_URL

UAV_MODEL = (os.environ.get("AIRGROUND_UAV_MODEL") or "quadcopter").strip().lower()
if UAV_MODEL not in {"iris", "quadcopter"}:
    raise ValueError("AIRGROUND_UAV_MODEL must be 'iris' or 'quadcopter'")

UAV_PRIM = os.environ.get("AIRGROUND_UAV_PRIM") or "/World/uav"
UAV_ROBOT_NAME = os.environ.get("AIRGROUND_UAV_NAMESPACE") or "uav"
UAV_VEHICLE_ID = int(os.environ.get("AIRGROUND_UAV_VEHICLE_ID", "1"))
UAV_DOMAIN_ID = int(os.environ.get("AIRGROUND_UAV_DOMAIN_ID", "1"))
UAV_PX4_MODEL = os.environ.get("AIRGROUND_UAV_PX4_MODEL") or (
    "airground_quadcopter" if UAV_MODEL == "quadcopter" else "gazebo-classic_iris"
)
UAV_PX4_AUTOLAUNCH = _env_bool("AIRGROUND_UAV_PX4_AUTOLAUNCH", True)
UGV_PRIM = os.environ.get("AIRGROUND_UGV_PRIM") or "/World/ugv"
UGV_ROBOT_NAME = os.environ.get("AIRGROUND_UGV_NAMESPACE") or "ugv"
UGV_X = float(os.environ.get("UGV_X") or "0.0")
UGV_Y = float(os.environ.get("UGV_Y") or "0.0")
UGV_Z = float(os.environ.get("UGV_Z") or "0.20")
UGV_YAW = float(os.environ.get("UGV_YAW") or "0.0")
if not math.isfinite(UGV_YAW):
    raise ValueError("UGV_YAW must be finite")
UGV_ORIENTATION_WXYZ = np.asarray(
    [math.cos(UGV_YAW * 0.5), 0.0, 0.0, math.sin(UGV_YAW * 0.5)],
    dtype=np.float32,
)
UGV_WHEEL_VELOCITY_SCALE = float(
    os.environ.get("AIRGROUND_JACKAL_WHEEL_VELOCITY_SCALE") or "1.0"
)
UGV_SENSOR_BODY_PATH = os.environ.get("AIRGROUND_UGV_SENSOR_BODY_PRIM") or f"{UGV_PRIM}/base_link"
ENABLE_UGV_STATE_PUBLISHERS = (
    os.environ.get("AIRGROUND_ENABLE_UGV_STATE_PUBLISHERS", "true").lower() == "true"
)
ENABLE_UGV_CONTACT_PUBLISHER = _env_bool("AIRGROUND_ENABLE_UGV_CONTACT_PUBLISHER", True)
ENABLE_UAV_STATE_PUBLISHERS = (
    os.environ.get("AIRGROUND_ENABLE_UAV_STATE_PUBLISHERS", "true").lower() == "true"
)
ENABLE_SENSOR_GRAPHS = (
    os.environ.get("AIRGROUND_ENABLE_SENSOR_GRAPHS", "true").lower() == "true"
)
ENABLE_UAV_SENSOR_GRAPHS = ENABLE_SENSOR_GRAPHS and _env_bool(
    "AIRGROUND_ENABLE_UAV_SENSOR_GRAPHS", True
)
ENABLE_UGV_SENSOR_GRAPHS = ENABLE_SENSOR_GRAPHS and _env_bool(
    "AIRGROUND_ENABLE_UGV_SENSOR_GRAPHS", True
)
ENABLE_UAV_RGBD_SENSOR_GRAPH = ENABLE_UAV_SENSOR_GRAPHS and _env_bool(
    "AIRGROUND_ENABLE_UAV_RGBD_SENSOR_GRAPH", True
)
ENABLE_UAV_LIDAR_SENSOR_GRAPH = ENABLE_UAV_SENSOR_GRAPHS and _env_bool(
    "AIRGROUND_ENABLE_UAV_LIDAR_SENSOR_GRAPH", True
)
ENABLE_UGV_RGBD_SENSOR_GRAPH = ENABLE_UGV_SENSOR_GRAPHS and _env_bool(
    "AIRGROUND_ENABLE_UGV_RGBD_SENSOR_GRAPH", True
)
ENABLE_UGV_LIDAR_SENSOR_GRAPH = ENABLE_UGV_SENSOR_GRAPHS and _env_bool(
    "AIRGROUND_ENABLE_UGV_LIDAR_SENSOR_GRAPH", True
)
#: ROS frame of the UGV Ouster OS1.  Nav2's voxel layers consume the cloud
#: through tf2, so this name has to match the sensor graph, the static transform
#: published below the Jackal base frame and the smoke topic-trace contract.
UGV_LIDAR_FRAME_ID = os.environ.get("AIRGROUND_UGV_LIDAR_FRAME_ID") or "ugv_os1_lidar"
#: ``rtx`` uses the Isaac RTX LiDAR Replicator writer; ``physx_raycast`` publishes
#: a CPU multi-elevation PhysX scene-query cloud on the same topic/frame.  Isaac
#: Sim 4.5's Replicator LiDAR writer registers the topic but publishes empty
#: clouds (measured 2026-09-17), so that route needs the CPU source.
UGV_LIDAR_SOURCE = (os.environ.get("AIRGROUND_UGV_LIDAR_SOURCE") or "rtx").strip().lower()
UGV_CLOUD_BACKEND = (os.environ.get("AIRGROUND_UGV_CLOUD_BACKEND") or "cpu").strip().lower()
if UGV_CLOUD_BACKEND not in {"cpu", "gpu"}:
    raise ValueError("AIRGROUND_UGV_CLOUD_BACKEND must be cpu or gpu")
STATE_BRIDGE = (os.environ.get("AIRGROUND_STATE_BRIDGE") or "python").strip().lower()
if STATE_BRIDGE not in {"python", "native"}:
    raise ValueError("AIRGROUND_STATE_BRIDGE must be python or native")
# Opt-in fused native math for the 250 Hz UAV control/sensor callbacks.  The
# library lives in the mounted AirGroundRuns tree and the Fabric pose lane must
# be active; the tool fails closed when either precondition is missing.
NATIVE_VEHICLE_MATH_LIBRARY = (
    os.environ.get("AIRGROUND_NATIVE_VEHICLE_MATH_LIBRARY") or ""
).strip()
USE_FABRIC_STATE = _env_bool("AIRGROUND_USE_FABRIC_STATE", False)
# PX4 MAVLink link implementation: ``python`` is the pymavlink-based Pegasus backend; ``native_hub``
# services every task's UAV link from one C++ call per physics step (tools/px4_hub.cpp).
PX4_LINK = (os.environ.get("AIRGROUND_PX4_LINK") or "python").strip().lower()
if PX4_LINK not in {"python", "native_hub"}:
    raise ValueError("AIRGROUND_PX4_LINK must be python or native_hub")
PX4_HUB_LIBRARY = (os.environ.get("AIRGROUND_PX4_HUB_LIBRARY") or "").strip()
#: Wall-clock bound of one lockstep wait inside the hub; 0 waits forever like the pymavlink backend.
PX4_HUB_LOCKSTEP_TIMEOUT_S = float(os.environ.get("AIRGROUND_PX4_HUB_LOCKSTEP_TIMEOUT_S") or "0")
UGV_LIDAR_MOUNT_OFFSET_M = (0.0, 0.0, 0.42)
#: The Ouster asset's baked-in corrective rotation measured from the live USD
#: prim (2026-09-17): +90 deg about Z relative to ``ugv/base_link``.
UGV_LIDAR_FRAME_YAW_RAD = math.pi / 2.0
UGV_CLOUD_RAY_COUNT = int(os.environ.get("AIRGROUND_UGV_CLOUD_RAY_COUNT") or "240")
UGV_CLOUD_ELEVATION_DEG = tuple(
    float(token)
    for token in (
        os.environ.get("AIRGROUND_UGV_CLOUD_ELEVATION_DEG")
        or " ".join(str(value) for value in DEFAULT_ELEVATION_DEG)
    ).replace(",", " ").split()
)
UGV_CLOUD_MAX_RANGE_M = float(os.environ.get("AIRGROUND_UGV_CLOUD_MAX_RANGE_M") or "12.0")
UGV_CLOUD_MIN_RANGE_M = float(os.environ.get("AIRGROUND_UGV_CLOUD_MIN_RANGE_M") or "0.30")
UGV_CLOUD_PERIOD_S = float(os.environ.get("AIRGROUND_UGV_CLOUD_PERIOD_S") or "0.2")

# Nav2 obstacle layer source.  The UGV GT map is a vertical-raycast
# traversability prior and structurally misses thin vertical geometry (see the
# 2026-09-12 fence probe in IMPLEMENTATION_PLAN.md); without a live obstacle
# source the controller drives straight into runtime fences.  This scan is
# PhysX scene-query only: CPU side, no RTX lidar render product.
# 2026-09-17: the 240-ray planar PhysX scan at ``base_link + 0.25 m`` was the
# only runtime obstacle source, so anything shorter than the scan plane (the
# 5-10 cm curbs and tire stacks the Jackal climbed in the 2026-09-17 Type I run)
# was invisible to Nav2.  The UGV now feeds Nav2 the Ouster OS1 point cloud
# voxelized with a 5 cm height floor; the planar scan stays available as a
# fallback/diagnostic switch but is off by default.
ENABLE_UGV_PROXIMITY_SCAN = _env_bool("AIRGROUND_ENABLE_UGV_PROXIMITY_SCAN", False)
UGV_PROXIMITY_SCAN_RAY_COUNT = int(
    os.environ.get("AIRGROUND_UGV_PROXIMITY_SCAN_RAY_COUNT") or "240"
)
UGV_PROXIMITY_SCAN_MAX_RANGE_M = float(
    os.environ.get("AIRGROUND_UGV_PROXIMITY_SCAN_MAX_RANGE_M") or "12.0"
)
UGV_PROXIMITY_SCAN_MIN_RANGE_M = float(
    os.environ.get("AIRGROUND_UGV_PROXIMITY_SCAN_MIN_RANGE_M") or "0.30"
)
UGV_PROXIMITY_SCAN_HEIGHT_OFFSET_M = float(
    os.environ.get("AIRGROUND_UGV_PROXIMITY_SCAN_HEIGHT_OFFSET_M") or "0.25"
)
UGV_PROXIMITY_SCAN_PERIOD_S = float(
    os.environ.get("AIRGROUND_UGV_PROXIMITY_SCAN_PERIOD_S") or "0.2"
)
UAV_CAMERA_WIDTH = int(os.environ.get("AIRGROUND_UAV_CAMERA_WIDTH") or "480")
UAV_CAMERA_HEIGHT = int(os.environ.get("AIRGROUND_UAV_CAMERA_HEIGHT") or "300")
if UAV_CAMERA_WIDTH <= 0 or UAV_CAMERA_HEIGHT <= 0:
    raise ValueError(
        "AIRGROUND_UAV_CAMERA_WIDTH and AIRGROUND_UAV_CAMERA_HEIGHT must be positive"
    )
AIRGROUND_RGBD_PUBLISHER_HZ = float(os.environ.get("AIRGROUND_RGBD_PUBLISHER_HZ") or "10.0")
if not math.isfinite(AIRGROUND_RGBD_PUBLISHER_HZ) or AIRGROUND_RGBD_PUBLISHER_HZ <= 0.0:
    raise ValueError("AIRGROUND_RGBD_PUBLISHER_HZ must be finite and positive")
AIRGROUND_RGBD_PUBLISHER_SURFACES = _env_csv_tokens("AIRGROUND_RGBD_PUBLISHER_SURFACES")
# P0-Sim-MultiTask: "tiled_sidecar" renders every RGB-D camera into one tiled render
# product and publishes through a sidecar process (see airground_sidecar/); the
# default keeps the in-process manual publisher.
AIRGROUND_RGBD_BACKEND = (os.environ.get("AIRGROUND_RGBD_BACKEND") or "manual").strip().lower()
if AIRGROUND_RGBD_BACKEND not in {"manual", "tiled_sidecar"}:
    raise ValueError("AIRGROUND_RGBD_BACKEND must be 'manual' or 'tiled_sidecar'")
# AIRGROUND_SINGLE_CLOCK_PUBLISHER (default off): with the tiled RGB-D backend the first task's /clock had two
# publishers, the OmniGraph ROS2PublishClock (end-of-step stamp) and the Python pre-tick (start-of-step stamp).
# Their messages arrive out of order (~0.1 s, one render step, apart), so the first task's runner saw /clock
# regress while waiting for Nav2 and dropped every UGV goal (s7acc6/s7acc7 t0 and every N=1 run of the
# UGV-OGN-MultiTaskEquivalence check, 2026-10-13). On: the first task disconnects its OmniGraph clock tick
# and its Python publisher emits both stamps, exactly as every later task already does.
AIRGROUND_SINGLE_CLOCK_PUBLISHER = (os.environ.get("AIRGROUND_SINGLE_CLOCK_PUBLISHER") or "").strip().lower() in {
    "1", "true", "yes", "on"}
# AIRGROUND_SIDECAR_DISPARITY (default off) publishes the droan disparity from the tiled RGB-D sidecar; the
# manual publisher has no sidecar, so the switch without the tiled backend would leave the planner without disparity.
if (os.environ.get("AIRGROUND_SIDECAR_DISPARITY") or "").strip().lower() in {"1", "true", "yes", "on"} and (
    AIRGROUND_RGBD_BACKEND != "tiled_sidecar"
):
    raise ValueError("AIRGROUND_SIDECAR_DISPARITY=on needs AIRGROUND_RGBD_BACKEND=tiled_sidecar")


# SimMT-2: run evidence requests (episode reset, UAV control sessions) as
# cooperative greenlet sessions that share one ``world.step`` through the main
# loop instead of stepping the world themselves.  Off by default; with one
# session the call order is unchanged.
AIRGROUND_COOPERATIVE_SESSIONS = _env_bool("AIRGROUND_COOPERATIVE_SESSIONS", False)

# Rendering cadence.  2026-09-12 measurement (runs/local_isaac45_uavfix1_*):
# one `world.step(render=True)` costs ~17 ms and the camera readback ~140 ms per
# published frame, which capped the simulation at 0.4x real time.  Topics are
# timestamped in simulated seconds, so a low real-time factor makes every topic
# look slow to a `ros2 topic hz` observer (camera 10 Hz sim == ~4 Hz wall) and
# starves the PX4 HIL loop.  Rendering only as often as the cameras need frames
# (default 2x the RGB-D publish rate) removes the wasted renders without
# changing any topic contract.
try:
    from pegasus.simulator.params import DEFAULT_WORLD_SETTINGS as _PEGASUS_WORLD_SETTINGS

    _PEGASUS_RENDERING_HZ = 1.0 / float(_PEGASUS_WORLD_SETTINGS["rendering_dt"])
except Exception:  # pragma: no cover - import-time fallback for stub hosts.
    _PEGASUS_RENDERING_HZ = 60.0
# Render only on the iterations whose camera publish is due, instead of the
# fixed ``render_every_n`` cadence (measured 2026-10-01: a render step costs
# ~14.6 ms of Kit app.update against ~2.6 ms for a physics step, while the
# cadence rendered about twice as often as the 10 Hz camera contract).
AIRGROUND_RENDER_ON_CAMERA_DUE = _env_bool("AIRGROUND_RENDER_ON_CAMERA_DUE", False)
AIRGROUND_RENDER_HZ = float(os.environ.get("AIRGROUND_RENDER_HZ") or "0.0")
if not math.isfinite(AIRGROUND_RENDER_HZ) or AIRGROUND_RENDER_HZ < 0.0:
    raise ValueError("AIRGROUND_RENDER_HZ must be finite and >= 0")
if AIRGROUND_RENDER_HZ <= 0.0:
    AIRGROUND_RENDER_HZ = (
        AIRGROUND_RGBD_PUBLISHER_HZ * 2.0
        if AIRGROUND_RGBD_PUBLISHER_SURFACES
        else _PEGASUS_RENDERING_HZ
    )
AIRGROUND_RENDER_PULSE_EVERY_N = (
    AIRGROUND_RENDER_PULSE_EVERY_N_ENV
    if AIRGROUND_RENDER_PULSE_EVERY_N_ENV > 0
    else max(1, int(round(_PEGASUS_RENDERING_HZ / AIRGROUND_RENDER_HZ)))
)
print(
    "AirGround render cadence: "
    f"render_hz={AIRGROUND_RENDER_HZ:.3f}, "
    f"render_every_n_steps={AIRGROUND_RENDER_PULSE_EVERY_N}, "
    f"rgbd_publish_hz={AIRGROUND_RGBD_PUBLISHER_HZ:.3f}, "
    f"pegasus_rendering_hz={_PEGASUS_RENDERING_HZ:.3f}",
    flush=True,
)
ENABLE_FULL_MISSION_EVIDENCE_SERVER = _env_bool("AIRGROUND_ENABLE_FULL_MISSION_EVIDENCE_SERVER", True)
CREATE_DOCK_JOINT = os.environ.get("AIRGROUND_CREATE_DOCK_JOINT", "true").lower() == "true"
ALIGN_UAV_TO_DOCK = _env_bool("AIRGROUND_ALIGN_UAV_TO_DOCK", True)
# 2026-09-12: with the physical dock joint disabled (the Isaac Sim 4.5 local
# route) the UAV is only pose-aligned to the platform.  Aligning the chassis
# origin exactly to the 2 cm-above-deck anchor let the Quadcopter collision
# envelope penetrate the deck, so PhysX ejected it ~1.2 m upwards within one
# second and it landed beside the Jackal.  Lift the soft dock by a small
# clearance so the landing gear rests on the deck instead.
try:
    SOFT_DOCK_CLEARANCE_M = float(os.environ.get("AIRGROUND_SOFT_DOCK_CLEARANCE_M", "0.08"))
except ValueError:
    SOFT_DOCK_CLEARANCE_M = 0.08
# 2026-09-12: with the physical fixed joint disabled, the Quadcopter can slide
# off the small Jackal deck during the long pre-arm dwell (observed: pitch
# 0.92rad, altitude 0.015m -> pre-arm gate correctly aborted).  Model the dock
# latch explicitly: hold the UAV at the aligned deck pose until PX4 reports
# armed, correcting only when it drifts outside a small tolerance.
SOFT_DOCK_HOLD_ENABLED = _env_bool("AIRGROUND_SOFT_DOCK_HOLD", True)
try:
    SOFT_DOCK_HOLD_TOLERANCE_M = float(os.environ.get("AIRGROUND_SOFT_DOCK_HOLD_TOLERANCE_M", "0.03"))
except ValueError:
    SOFT_DOCK_HOLD_TOLERANCE_M = 0.03
try:
    SOFT_DOCK_HOLD_MAX_TILT_RAD = float(os.environ.get("AIRGROUND_SOFT_DOCK_HOLD_MAX_TILT_RAD", "0.2"))
except ValueError:
    SOFT_DOCK_HOLD_MAX_TILT_RAD = 0.2
try:
    SOFT_DOCK_HOLD_SETTLE_STEPS = max(
        0, int(os.environ.get("AIRGROUND_SOFT_DOCK_HOLD_SETTLE_STEPS", "180"))
    )
except ValueError:
    SOFT_DOCK_HOLD_SETTLE_STEPS = 180
# 2026-09-12: correcting the chassis live pose from Python destabilises the
# Isaac 4.5 articulation (first correction moved the body ~1.6m and the loop
# never converged), so corrections are diagnostic-only by default.  Use the
# physical fixed joint (with a break force) to hold the dock instead.
SOFT_DOCK_HOLD_CORRECT_ENABLED = _env_bool("AIRGROUND_SOFT_DOCK_HOLD_CORRECT", False)
# Physical dock latch strength for the fixed-joint route.  A very large break
# force holds the UAV forever; a force slightly above the vehicle weight lets
# the joint hold through the long pre-arm dwell yet break naturally when the
# takeoff thrust ramps up, instead of releasing at the arm ACK and leaving
# residual velocity for the hover controller.
# SimMT-7: release the dock joint when the task's PX4 reports armed (the OFFBOARD lane's after_arm_ack
# policy, for the planner lane too); off by default.
DOCK_RELEASE_ON_ARM = _env_bool("AIRGROUND_DOCK_RELEASE_ON_ARM", False)
try:
    DOCK_BREAK_FORCE_N = float(os.environ.get("AIRGROUND_DOCK_BREAK_FORCE_N", "1.0e9"))
except ValueError:
    DOCK_BREAK_FORCE_N = 1.0e9
try:
    DOCK_BREAK_TORQUE_NM = float(os.environ.get("AIRGROUND_DOCK_BREAK_TORQUE_NM", "1.0e9"))
except ValueError:
    DOCK_BREAK_TORQUE_NM = 1.0e9
MAX_STEPS = int(os.environ.get("AIRGROUND_MAX_STEPS") or "0")
AIRGROUND_STATE_PUBLISH_DEBUG_EVERY_N = int(
    os.environ.get("AIRGROUND_STATE_PUBLISH_DEBUG_EVERY_N") or "0"
)
AIRGROUND_STATE_PUBLISH_DEBUG_FILE = os.environ.get("AIRGROUND_STATE_PUBLISH_DEBUG_FILE") or ""
# 2026-09-12: the onboard ZED cameras render washed-out RGB while the replay
# renderer (default camera, same scene) is correctly exposed.  Dump the RTX
# exposure/tonemap settings at startup so both paths can be compared from run
# evidence instead of guesswork.
AIRGROUND_DUMP_RTX_EXPOSURE_SETTINGS = _env_bool(
    "AIRGROUND_DUMP_RTX_EXPOSURE_SETTINGS", False
)
# 2026-09-13: the mission stage keeps the Kit default stage's
# ``/Environment/defaultLight`` (DistantLight, intensity 3000) on top of the
# scene's own sun (DistantLight, intensity 5000) and sky dome, while the replay
# app only references the scene's default prim.  Opt-in switch so the fix can be
# proven by a frame-statistics stage sweep before it becomes the default.
AIRGROUND_HIDE_DEFAULT_STAGE_ENV = _env_bool("AIRGROUND_HIDE_DEFAULT_STAGE_ENV", False)
# 2026-09-13: Kit's default RTX camera exposure (fNumber 5.0, exposureTime 0.02 s,
# filmIso 100) is ~2.3 stops too bright for this scene in the mission app: 56.6%
# of the onboard UGV pixels clipped at 255 (mean 243), while a replay render of
# the same scene is unclipped.  The stage sweep proved these carb settings drive
# the rendered frames (f/8 -> 22% clipped.. 3.2%, f/11 -> 0%, f/16 -> mean 167),
# so the benchmark pins the aperture for deterministic, unclipped onboard RGB.
# Set ``AIRGROUND_RTX_TONEMAP_SETTINGS=none`` to keep the Kit defaults.
AIRGROUND_RTX_TONEMAP_SETTINGS = (
    os.environ.get("AIRGROUND_RTX_TONEMAP_SETTINGS") or ""
).strip()
if not AIRGROUND_RTX_TONEMAP_SETTINGS:
    AIRGROUND_RTX_TONEMAP_SETTINGS = "fNumber=11"
AIRGROUND_STATE_PUBLISH_TRACE_STAGES = _env_bool("AIRGROUND_STATE_PUBLISH_TRACE_STAGES", False)
# Diagnostic only: accumulate true per-stage wall time of the main loop (no cProfile
# inflation) and log a summary every AIRGROUND_STAGE_TIMING_EVERY_N loop iterations.
AIRGROUND_STAGE_TIMING = _env_bool("AIRGROUND_STAGE_TIMING", False)
AIRGROUND_STAGE_TIMING_EVERY_N = int(os.environ.get("AIRGROUND_STAGE_TIMING_EVERY_N") or "2000")
# SimMT-4c diagnostic (default off): with the stage timing, also log omni.physx's own profile zones
# (IPhysxBenchmarks.get_profile_stats) so the PhysX share of world.step splits into simulate, fetch,
# contact processing, USD/Fabric write-back, ...
AIRGROUND_PHYSX_PROFILE = _env_bool("AIRGROUND_PHYSX_PROFILE", False)
_PHYSX_PROFILE_STATE: dict[str, Any] = {}


def _physx_scene_stats() -> Any:
    """omni.physx IPhysxStatistics of every physics scene (counts of the last simulated step)."""
    out: dict[str, Any] = {}
    try:
        import omni.physx  # noqa: PLC0415 - Isaac-only
        import omni.usd  # noqa: PLC0415
        from omni.physx.bindings._physx import PhysicsSceneStats  # noqa: PLC0415
        from pxr import PhysicsSchemaTools, UsdPhysics, UsdUtils  # noqa: PLC0415

        stage = omni.usd.get_context().get_stage()
        paths = _PHYSX_PROFILE_STATE.get("scene_paths")
        if paths is None:
            paths = [str(p.GetPath()) for p in stage.Traverse() if p.IsA(UsdPhysics.Scene)]
            _PHYSX_PROFILE_STATE["scene_paths"] = paths
        iface = omni.physx.get_physx_statistics_interface()
        stage_id = UsdUtils.StageCache.Get().Insert(stage).ToLongInt()
        for path in paths:
            stats = PhysicsSceneStats()
            path_int = PhysicsSchemaTools.sdfPathToInt(path)
            if iface.get_physx_scene_statistics(stage_id, path_int, stats):
                out[path] = {name: getattr(stats, name) for name in dir(stats) if name.startswith("nb_")}
            else:
                out[path] = "unavailable"
    except Exception as exc:  # noqa: BLE001 - diagnostics must not stop the run
        out["error"] = f"{type(exc).__name__}: {exc}"
    return out


def _physx_profile_snapshot() -> Any:
    """Raw ``get_profile_stats()`` (enabled on the first call) plus the scene statistics."""
    try:
        import omni.physx  # noqa: PLC0415 - Isaac-only

        bench = _PHYSX_PROFILE_STATE.get("bench")
        if bench is None:
            bench = omni.physx.get_physx_benchmarks_interface()
            bench.enable_profile(True)
            _PHYSX_PROFILE_STATE["bench"] = bench
            return {"enabled": True}
        return json.loads(json.dumps(bench.get_profile_stats(), default=str))
    except Exception as exc:  # noqa: BLE001 - diagnostics must not stop the run
        return f"{type(exc).__name__}: {exc}"


_STAGE_TIMER = None

if AIRGROUND_SCENE_COLLIDER_MODE not in {"profiled", "ground_only", "proxy", "none"}:
    raise ValueError(
        "AIRGROUND_SCENE_COLLIDER_MODE must be one of: profiled, ground_only, proxy, none "
        f"(got {AIRGROUND_SCENE_COLLIDER_MODE!r})"
    )
UAV_MAPPING = (
    MultirotorPrimPaths.isaac_sim_quadcopter()
    if UAV_MODEL == "quadcopter"
    else MultirotorPrimPaths.iris()
)

if UAV_MODEL == "quadcopter":
    DEFAULT_UAV_USD = os.path.abspath(
        os.path.join(
            os.path.dirname(__file__),
            "../assets/robots/quadcopter_airground.usda",
        )
    )
else:
    from pegasus.simulator.params import ROBOTS

    DEFAULT_UAV_USD = ROBOTS["Iris"]

DEFAULT_UGV_USD = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        "../assets/robots/jackal_airground.usda",
    )
)

DRONE_USD = os.environ.get("AIRGROUND_UAV_ASSET") or DEFAULT_UAV_USD
UGV_USD = os.environ.get("AIRGROUND_UGV_ASSET") or DEFAULT_UGV_USD
ASSET_ROOT = os.environ.get("AIRGROUND_ASSET_ROOT") or "/isaac-sim/AirGroundAssets/4.5.0"
ZED_USD = os.environ.get("AIRGROUND_ZED_USD") or os.path.join(
    ASSET_ROOT, "Isaac/Sensors/Stereolabs/ZED_X/ZED_X.usdc"
)
OUSTER_USD = os.environ.get("AIRGROUND_OUSTER_USD") or os.path.join(
    ASSET_ROOT, "Isaac/Sensors/Ouster/OS1/OS1.usd"
)

DRONE_X  = float(os.environ.get('DRONE_X') or str(UGV_X))
DRONE_Y  = float(os.environ.get('DRONE_Y') or str(UGV_Y))
DRONE_Z  = float(os.environ.get('DRONE_Z') or str(UGV_Z + 0.25))
DRONE_QX = float(os.environ.get('DRONE_QX') or '0.0')
DRONE_QY = float(os.environ.get('DRONE_QY') or '0.0')
DRONE_QZ = float(os.environ.get('DRONE_QZ') or '0.0')
DRONE_QW = float(os.environ.get('DRONE_QW') or '1.0')

# Multi-task runs (SimMT-2): AIRGROUND_TASKS_JSON lists per-task overrides; empty
# means the single legacy task described by the variables above.
_airground_sidecar_dir = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "airground_sidecar")
)
if _airground_sidecar_dir not in sys.path:
    sys.path.insert(0, _airground_sidecar_dir)
if AIRGROUND_STAGE_TIMING:
    from stage_timer import StageTimer  # noqa: E402 - needs the airground_sidecar path inserted above

    _STAGE_TIMER = StageTimer()


def _log_python_speed_probe() -> None:
    """Diagnostic (stage timing only): interpreter hooks and a fixed pure-Python workload.

    Kit-side Python measured several times slower than the same code under a plain CPython; a global
    trace/profile hook (debugger, coverage, profiler extension) would explain that, so log both.
    """
    import threading

    def work(n: int) -> float:
        total = 0.0
        for i in range(n):
            total += (i * 0.5) % 7.0
        return total

    def call(x: float) -> float:
        return x + 1.0

    start = time.perf_counter()
    work(200000)
    loop_ns = (time.perf_counter() - start) / 200000 * 1e9
    start = time.perf_counter()
    value = 0.0
    for _ in range(200000):
        value = call(value)
    call_ns = (time.perf_counter() - start) / 200000 * 1e9
    carb.log_warn(
        "AirGround python speed probe: "
        + json.dumps({"sys_gettrace": repr(sys.gettrace()), "sys_getprofile": repr(sys.getprofile()),
                      "threading_trace": repr(getattr(threading, "_trace_hook", None)),
                      "threading_profile": repr(getattr(threading, "_profile_hook", None)),
                      "loop_ns_per_iter": round(loop_ns, 1), "call_ns": round(call_ns, 1),
                      "python": sys.version.split()[0], "switch_interval_s": sys.getswitchinterval()},
                     sort_keys=True)
    )


# SimMT diagnostic (default off): count USD change notices between stage-timing lines.  omni.physx parses
# USD changes inside simulate(); per-step attribute writes from our code would show up here.
AIRGROUND_USD_CHANGE_PROBE = _env_bool("AIRGROUND_USD_CHANGE_PROBE", False)
_USD_CHANGES: dict[str, Any] = {"listener": None, "notices": 0, "paths": {}}


def _usd_change_probe_snapshot() -> dict[str, Any]:
    """Notices and the most frequently changed property paths since the last call (installs on first call)."""
    state = _USD_CHANGES
    try:
        if state["listener"] is None:
            import omni.usd  # noqa: PLC0415 - Isaac-only
            from pxr import Tf, Usd  # noqa: PLC0415

            def _changed(notice: Any, _stage: Any) -> None:
                state["notices"] += 1
                paths = state["paths"]
                for path in list(notice.GetChangedInfoOnlyPaths()) + list(notice.GetResyncedPaths()):
                    key = str(path)
                    # group per-task copies: /World/uav_3/... -> /World/uav_*/...
                    key = re.sub(r"(uav|ugv)_\d+", r"\1_*", key)
                    paths[key] = paths.get(key, 0) + 1

            state["listener"] = Tf.Notice.Register(Usd.Notice.ObjectsChanged, _changed,
                                                   omni.usd.get_context().get_stage())
            return {"installed": True}
        out = {"notices": state["notices"],
               "top_paths": dict(sorted(state["paths"].items(), key=lambda item: -item[1])[:20]),
               "distinct_paths": len(state["paths"])}
        state["notices"] = 0
        state["paths"] = {}
        return out
    except Exception as exc:  # noqa: BLE001 - diagnostics must not stop the run
        return {"error": f"{type(exc).__name__}: {exc}"}


# Per world.step: when our timed physics callbacks start/end, so the step splits into PhysX before the
# callbacks, untimed work between them (other step subscribers), and work after the last one.
_WORLD_STEP_SPLIT: dict[str, Any] = {}
_MAIN_LOOP_WATCHDOG: Any = None  # main_loop_watchdog module when AIRGROUND_MAIN_LOOP_WATCHDOG_S > 0


def _world_step_split_begin() -> None:
    _WORLD_STEP_SPLIT.clear()
    _WORLD_STEP_SPLIT["begin"] = time.perf_counter()


def _world_step_split_end(kind: str) -> None:
    split = _WORLD_STEP_SPLIT
    begin = split.get("begin")
    if begin is None or _STAGE_TIMER is None:
        return
    end = time.perf_counter()
    first, last_end = split.get("first"), split.get("last_end")
    if first is None:
        _STAGE_TIMER.add(f"ws.{kind}.no_cb", end - begin)
    else:
        _STAGE_TIMER.add(f"ws.{kind}.pre_cb", first - begin)
        _STAGE_TIMER.add(f"ws.{kind}.between_cb", max(0.0, (last_end - first) - split.get("cb_sum", 0.0)))
        _STAGE_TIMER.add(f"ws.{kind}.post_cb", end - last_end)
    update_first, update_last = split.get("update_first"), split.get("update_last")
    if update_first is not None and update_last is not None:
        # Kit update events bracket every update subscriber (Python extensions, followers, physics
        # driven by the app loop); what follows them is the post-update work, i.e. Hydra sync + render.
        _STAGE_TIMER.add(f"ws.{kind}.before_update_events", update_first - begin)
        _STAGE_TIMER.add(f"ws.{kind}.update_events", update_last - update_first)
        _STAGE_TIMER.add(f"ws.{kind}.after_update_events", end - update_last)
    split.clear()


_UPDATE_EVENT_MARKERS: list[Any] = []


def _instrument_update_events() -> None:
    """Diagnostic only: timestamp the first and last Kit update-event subscriber of each update."""
    import omni.kit.app

    stream = omni.kit.app.get_app().get_update_event_stream()

    def _first(_event: Any) -> None:
        if _WORLD_STEP_SPLIT.get("begin") is not None and "update_first" not in _WORLD_STEP_SPLIT:
            _WORLD_STEP_SPLIT["update_first"] = time.perf_counter()

    def _last(_event: Any) -> None:
        if _WORLD_STEP_SPLIT.get("begin") is not None:
            _WORLD_STEP_SPLIT["update_last"] = time.perf_counter()

    _UPDATE_EVENT_MARKERS[:] = [
        stream.create_subscription_to_pop(_first, order=-1000000, name="airground_update_marker_first"),
        stream.create_subscription_to_pop(_last, order=1000000, name="airground_update_marker_last"),
    ]


def _instrument_physics_callbacks(world: Any) -> None:
    """Diagnostic only: time every physics callback registered on ``world``.

    The callbacks (Pegasus ``update``/``update_state``/``update_sensors``/...) run inside
    ``world.step``; this separates them from PhysX itself.  Time accumulates per
    callback kind under ``cb.<kind>`` and is wrapped once per name registration.
    """
    original = getattr(world, "add_physics_callback", None)
    if not callable(original) or getattr(world, "_airground_cb_timed", False):
        return

    def _timed(callback_name: str, callback: Any, *args: Any, **kwargs: Any) -> Any:
        kind = "cb." + str(callback_name).rsplit("/", 1)[-1]

        def _wrapped(*cb_args: Any, **cb_kwargs: Any) -> Any:
            start = time.perf_counter()
            _STAGE_TIMER.begin(kind)
            try:
                return callback(*cb_args, **cb_kwargs)
            finally:
                _STAGE_TIMER.end(kind)
                end = time.perf_counter()
                split = _WORLD_STEP_SPLIT
                if split.get("begin") is not None:
                    if split.get("first") is None:
                        split["first"] = start
                    split["last_end"] = end
                    split["cb_sum"] = split.get("cb_sum", 0.0) + (end - start)

        return original(callback_name, _wrapped, *args, **kwargs)

    world.add_physics_callback = _timed
    world._airground_cb_timed = True


def _instrument_tensor_velocity_reads() -> None:
    """Diagnostic only: name the caller of every RigidBodyView's first ``get_velocities``.

    Every N=16 arm logs ~1 ``getVelocities`` size error per step from a view whose buffer has 48 rows
    while 16 bodies matched (detached ZED camera mounts are not rigid bodies); this finds the caller.
    """
    import traceback

    try:
        from omni.physics.tensors.impl.api import RigidBodyView
    except Exception as exc:  # noqa: BLE001
        carb.log_warn(f"AirGround tensor velocity diagnostics unavailable: {exc}")
        return
    original = RigidBodyView.get_velocities
    seen: set[int] = set()

    def _logged(self: Any, *args: Any, **kwargs: Any) -> Any:
        if id(self) not in seen:
            seen.add(id(self))
            paths = list(getattr(self, "prim_paths", []) or [])
            carb.log_warn(
                f"AirGround tensor view get_velocities: count={getattr(self, 'count', None)} "
                f"paths={len(paths)} e.g. {paths[:3]} caller="
                + " <- ".join(f"{frame.name}@{Path(frame.filename).name}:{frame.lineno}"
                              for frame in traceback.extract_stack(limit=6)[:-1][::-1])
            )
        return original(self, *args, **kwargs)

    RigidBodyView.get_velocities = _logged


def _instrument_state_samplers() -> None:
    """Diagnostic only: time the Isaac-side state sampling inside the state publishers.

    ``sample.ugv`` / ``sample.uav`` (USD / articulation reads) are separated from the
    rest of ``publish`` (message construction + rclpy publish) by wrapping the module
    level sampler each publisher calls.
    """
    import pegasus.simulator.logic.vehicles.jackal_state_publisher as _jackal_mod
    import pegasus.simulator.logic.vehicles.multirotor_state_publisher as _uav_mod

    def _wrap(module: Any, attribute: str, kind: str) -> None:
        original = getattr(module, attribute)
        if getattr(original, "_airground_timed", False):
            return

        def _timed(*args: Any, **kwargs: Any) -> Any:
            _STAGE_TIMER.begin(kind)
            try:
                return original(*args, **kwargs)
            finally:
                _STAGE_TIMER.end(kind)

        _timed._airground_timed = True  # type: ignore[attr-defined]
        setattr(module, attribute, _timed)

    _wrap(_jackal_mod, "sample_jackal_state", "sample.ugv")
    if hasattr(_jackal_mod, "sample_jackal_state_fast"):
        _wrap(_jackal_mod, "sample_jackal_state_fast", "sample.ugv_fast")
    _wrap(_uav_mod, "sample_multirotor_state", "sample.uav")
    _wrap(_jackal_mod, "_usd_world_pose", "usd_pose.ugv")
    # Inside the fast UGV sampler: PhysX velocity read and the joint fleet read (the rest is the pose).
    if hasattr(_jackal_mod, "_physx_body_velocity"):
        _wrap(_jackal_mod, "_physx_body_velocity", "sample.ugv.velocity")
    fleet = getattr(_jackal_mod, "_JACKAL_JOINT_FLEET", None)
    if fleet is not None and hasattr(fleet, "read"):
        _wrap(fleet, "read", "sample.ugv.joint_fleet")
    _wrap(_uav_mod, "_usd_world_pose", "usd_pose.uav")
    from pegasus.simulator.logic import ros_context as _ros_context_mod

    _wrap(_ros_context_mod, "spin_once", "ros.spin_once")
from task_context import baseline_values as _task_baseline_values  # noqa: E402
from task_context import parse_tasks_json as _parse_tasks_json  # noqa: E402

TASKS = _parse_tasks_json(os.environ.get("AIRGROUND_TASKS_JSON"), _task_baseline_values(globals()))
# Hide every robot (and the detached sensor mounts) from the RTX renderer; physics, raycasts and
# mounted cameras are unaffected (SimMT-0 probe 2).  Default on with several tasks in one world
# (user decision 2026-10-11): co-located tasks otherwise see each other's robots and ZED housings
# within 14 cm, which costs droan seconds per frame and starved Isaac's GPU (gpd52-gpd60).  It also
# hides each task's own robots, so a single task keeps the old default (off).
AIRGROUND_ROBOTS_INVISIBLE_TO_SENSORS = _env_bool("AIRGROUND_ROBOTS_INVISIBLE_TO_SENSORS", len(TASKS) > 1)

# ---------------------------------------------------------


for asset_name, asset_path in {
    "environment": ENV_URL,
    "uav": DRONE_USD,
    "ugv": UGV_USD,
    "zed_x": ZED_USD,
    "ouster_os1": OUSTER_USD,
}.items():
    expanded_path = os.path.expanduser(asset_path)
    if not os.path.isfile(expanded_path):
        raise FileNotFoundError(
            f"{asset_name} asset is missing: {expanded_path}; "
            "fetch the pinned assets before starting Isaac Sim"
        )


ext_manager = omni.kit.app.get_app().get_extension_manager()
if os.path.isdir(PEGASUS_EXT_FOLDER):
    try:
        ext_manager.add_path(PEGASUS_EXT_FOLDER)
    except AttributeError:
        carb.log_warn(
            "Extension manager does not expose add_path(); relying on Kit --ext-folder"
        )
else:
    carb.log_warn(f"Pegasus extension folder is missing: {PEGASUS_EXT_FOLDER}")

for ext in [
    "omni.graph.core",
    "omni.graph.action",
    "omni.graph.action_nodes",
    "isaacsim.core.nodes",
    "omni.graph.ui",
    "omni.graph.visualization.nodes",
    "omni.graph.scriptnode",
    "omni.graph.window.action",
    "omni.graph.window.generic",
    "omni.graph.ui_nodes",
    "pegasus.simulator",
]:
    if not ext_manager.is_extension_enabled(ext):
        try:
            ext_manager.set_extension_enabled_immediate(ext, True)
        except Exception:
            ext_manager.set_extension_enabled(ext, True)


def wait_for_stage(stage, timeout_s: float = 10.0):
    for _ in range(int(timeout_s / 0.1)):
        omni.kit.app.get_app().update()
        world_prim = stage.GetPrimAtPath("/World")
        if world_prim.IsValid():
            non_physics = [c for c in world_prim.GetChildren() if c.GetName() != "PhysicsScene"]
            if non_physics:
                return True
        time.sleep(0.1)
    return False


_PX4_HUB_CONFIGURED = False


def configure_px4_hub_link(capacity: int) -> None:
    """Create the process-wide PX4 hub group once when ``AIRGROUND_PX4_LINK=native_hub``."""
    global _PX4_HUB_CONFIGURED
    if PX4_LINK != "native_hub" or _PX4_HUB_CONFIGURED:
        return
    if not PX4_HUB_LIBRARY:
        raise RuntimeError("AIRGROUND_PX4_LINK=native_hub requires AIRGROUND_PX4_HUB_LIBRARY")
    tools = str(Path(__file__).resolve().parents[1] / "tools")
    if tools not in sys.path:
        sys.path.insert(0, tools)
    import px4_hub
    from pegasus.simulator.logic.backends import px4_hub_backend, px4_mavlink_backend

    def spec_factory(config: Any) -> Any:
        return px4_hub.spec_from_backend_config(
            config, gyro_clamp=px4_mavlink_backend.AIRGROUND_PX4_PREACTUATOR_GYRO_CLAMP
        )

    hub = px4_hub.PX4Hub(Path(PX4_HUB_LIBRARY), capacity=max(1, int(capacity)))
    group = px4_hub_backend.PX4HubGroup(
        hub, lockstep_timeout_s=PX4_HUB_LOCKSTEP_TIMEOUT_S, spec_factory=spec_factory
    )
    px4_hub_backend.configure_process_group(group)
    _PX4_HUB_CONFIGURED = True
    carb.log_warn(
        f"AirGround PX4 link: native hub {PX4_HUB_LIBRARY} capacity={hub.capacity} "
        f"lockstep_timeout_s={PX4_HUB_LOCKSTEP_TIMEOUT_S}"
    )


def ensure_pegasus_ogn_nodes_registered() -> None:
    """Register Pegasus multirotor OGN node types for Isaac 6 headless runs."""

    registry = og.GraphRegistry()
    node_registrations = (
        (
            "pegasus.simulator.PegasusMultirotorPX4Node",
            OgnPegasusMultirotorPX4NodeDatabase,
            OgnPegasusMultirotorPX4Node,
        ),
        (
            "pegasus.simulator.PegasusMultirotorArduPilotNode",
            OgnPegasusMultirotorArduPilotNodeDatabase,
            OgnPegasusMultirotorArduPilotNode,
        ),
    )

    for node_type, database_cls, node_cls in node_registrations:
        try:
            version = int(registry.get_node_type_version(node_type))
        except Exception:
            version = 0
        if version <= 0:
            database_cls.register(node_cls)
            carb.log_warn(f"Registered Pegasus OGN node type: {node_type}")


def _px4_killer_for_active_task():
    """PX4 stop callable: every instance for one task, the active task's only when several share the process."""
    if len(TASKS) > 1:
        vehicle_id = int(UAV_VEHICLE_ID)
        return lambda: PX4LaunchTool.kill_vehicle_px4(vehicle_id)
    return getattr(PX4LaunchTool, "kill_all_px4", None)


def stop_px4_autolaunch_processes() -> None:
    try:
        PX4LaunchTool.kill_all_px4()
    except Exception as exc:
        carb.log_warn(f"PX4 autolaunch shutdown failed: {exc}")


def ensure_articulation_root(stage, prim_path: str, label: str) -> None:
    prim = stage.GetPrimAtPath(prim_path)
    if not prim.IsValid():
        raise RuntimeError(f"{label} prim not found: {prim_path}")
    if prim.HasAPI(UsdPhysics.ArticulationRootAPI):
        carb.log_warn(f"{label} articulation root verified: {prim_path}")
    else:
        UsdPhysics.ArticulationRootAPI.Apply(prim)
        carb.log_warn(f"Applied PhysicsArticulationRootAPI to {label}: {prim_path}")


UAV_RIGID_BODY_PRIM_SUFFIXES = (
    "/chassis",
    "/rotor_arm0",
    "/rotor_arm1",
    "/rotor_arm2",
    "/rotor_arm3",
    "/rotor0",
    "/rotor1",
    "/rotor2",
    "/rotor3",
)
RIGID_BODY_RUNTIME_ATTR_TYPES = {
    "physics:kinematicEnabled": Sdf.ValueTypeNames.Bool,
    "physics:rigidBodyEnabled": Sdf.ValueTypeNames.Bool,
    "physxRigidBody:disableGravity": Sdf.ValueTypeNames.Bool,
    "physxRigidBody:lockedPosAxis": Sdf.ValueTypeNames.Int,
    "physxRigidBody:lockedRotAxis": Sdf.ValueTypeNames.Int,
}
RIGID_BODY_RUNTIME_ATTR_DEFAULTS = {
    "physics:kinematicEnabled": False,
    "physics:rigidBodyEnabled": True,
    "physxRigidBody:disableGravity": False,
    "physxRigidBody:lockedPosAxis": 0,
    "physxRigidBody:lockedRotAxis": 0,
}
RIGID_BODY_DIAGNOSTIC_ATTRS = (
    "physics:mass",
    "physics:centerOfMass",
    "physics:diagonalInertia",
    "physics:principalAxes",
    *tuple(RIGID_BODY_RUNTIME_ATTR_DEFAULTS.keys()),
)


def _json_safe_value(value: Any) -> Any:
    if value is None or isinstance(value, bool | int | float | str):
        return value
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, list | tuple):
        return [_json_safe_value(item) for item in value]
    if hasattr(value, "GetReal") and hasattr(value, "GetImaginary"):
        imaginary = value.GetImaginary()
        return [
            float(value.GetReal()),
            float(imaginary[0]),
            float(imaginary[1]),
            float(imaginary[2]),
        ]
    if hasattr(value, "__len__") and not isinstance(value, str):
        try:
            return [float(value[index]) for index in range(len(value))]
        except Exception:
            pass
    for fields in (("x", "y", "z"), ("w", "x", "y", "z")):
        if all(hasattr(value, field) for field in fields):
            return [float(getattr(value, field)) for field in fields]
    return str(value)


def prim_attribute_snapshot(prim: Usd.Prim, attr_names: tuple[str, ...]) -> dict[str, Any]:
    snapshot: dict[str, Any] = {}
    for attr_name in attr_names:
        attr = prim.GetAttribute(attr_name)
        if not attr.IsValid():
            snapshot[attr_name] = {"valid": False}
            continue
        try:
            value = attr.Get()
        except Exception as exc:
            snapshot[attr_name] = {
                "error": f"{type(exc).__name__}: {exc}",
                "type": str(attr.GetTypeName()),
                "valid": True,
            }
            continue
        snapshot[attr_name] = {
            "type": str(attr.GetTypeName()),
            "valid": True,
            "value": _json_safe_value(value),
        }
    return snapshot


def ensure_rigid_body_runtime_flags(stage, prim_paths: tuple[str, ...], *, label: str) -> dict[str, Any]:
    summary: dict[str, Any] = {"label": label, "prims": [], "status": "ok"}
    for prim_path in prim_paths:
        prim_summary: dict[str, Any] = {"prim_path": prim_path}
        prim = stage.GetPrimAtPath(prim_path)
        if not prim.IsValid():
            prim_summary["status"] = "missing"
            summary["status"] = "warning"
            summary["prims"].append(prim_summary)
            continue
        prim_summary["applied_schemas"] = list(prim.GetAppliedSchemas())
        prim_summary["before"] = prim_attribute_snapshot(prim, tuple(RIGID_BODY_RUNTIME_ATTR_DEFAULTS.keys()))
        for attr_name, desired_value in RIGID_BODY_RUNTIME_ATTR_DEFAULTS.items():
            attr = prim.GetAttribute(attr_name)
            if not attr.IsValid():
                attr = prim.CreateAttribute(attr_name, RIGID_BODY_RUNTIME_ATTR_TYPES[attr_name])
            attr.Set(desired_value)
        prim_summary["after"] = prim_attribute_snapshot(prim, tuple(RIGID_BODY_RUNTIME_ATTR_DEFAULTS.keys()))
        prim_summary["status"] = "ok"
        summary["prims"].append(prim_summary)
    return summary


def rigid_body_diagnostic_snapshot(stage, prim_path: str) -> dict[str, Any]:
    prim = stage.GetPrimAtPath(prim_path)
    if not prim.IsValid():
        return {"prim_path": prim_path, "status": "missing"}
    return {
        "applied_schemas": list(prim.GetAppliedSchemas()),
        "attributes": prim_attribute_snapshot(prim, RIGID_BODY_DIAGNOSTIC_ATTRS),
        "prim_path": prim_path,
        "status": "ok",
    }


#: Jackal wheel links whose colliders must carry an explicit PhysX contact
#: offset.  The Clearpath asset leaves every wheel collider and the ground on the
#: PhysX default (2 cm on Isaac Sim 4.5), which is a property of the *pair*.
UGV_WHEEL_LINK_NAMES: tuple[str, ...] = (
    "front_left_wheel_link",
    "front_right_wheel_link",
    "rear_left_wheel_link",
    "rear_right_wheel_link",
)


def _iter_prim_tree(prim) -> Any:
    for child in prim.GetChildren():
        yield child
        yield from _iter_prim_tree(child)


def apply_wheel_contact_offsets(
    stage,
    *,
    robot_prim_path: str,
    contact_offset_m: float,
    rest_offset_m: float,
    wheel_link_names: tuple[str, ...] = UGV_WHEEL_LINK_NAMES,
) -> dict[str, Any]:
    """Pin every Jackal wheel collider to a small, explicit PhysX contact offset.

    2026-09-21 (flat-ground jitter, first-class problem).  Isaac Sim's own
    physics documentation defines the contact offset as "how far from the
    collision geometry ... the simulation engine starts generating contact
    constraints", and the NVIDIA forum guidance for bouncing/jittering wheeled
    robots says to keep it small and, in particular, to avoid the large
    defaults that leave the vehicle "oscillating between contact states".

    Measured here: on the GT-flat straight legs of ``smoke_20260921_010543``
    the chassis ``z`` swung between 0.0421 m and 0.0635 m at 3-5 Hz while
    roll/pitch stayed within 0.03 deg, i.e. a pure contact-model limit cycle on
    a surface the GT calls flat.  Both sides of the contact are therefore
    pinned: the invisible ground support plane (see
    ``airground_ground_support_contact_offset_m``) and the four wheel
    cylinders handled here.  The values are env-overridable so a regression can
    be re-measured instead of hard-coded.
    """
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
    try:
        from pxr import PhysxSchema  # type: ignore
    except ImportError as exc:  # pragma: no cover - depends on the Isaac build.
        summary["status"] = "unavailable"
        summary["error"] = f"PhysxSchema import failed: {type(exc).__name__}: {exc}"
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


def _float3(value: tuple[float, float, float]) -> Any:
    return carb._carb.Float3(float(value[0]), float(value[1]), float(value[2]))


#: PhysX articulation schema attributes, written as raw USD attributes so the
#: values land whether or not ``pxr.PhysxSchema`` exposes the getters.
UGV_SOLVER_ITERATION_ATTRS: tuple[tuple[str, str], ...] = (
    ("physxArticulation:solverPositionIterationCount", "solver_position_iteration_count"),
    ("physxArticulation:solverVelocityIterationCount", "solver_velocity_iteration_count"),
)


def apply_ugv_solver_iterations(
    stage,
    *,
    articulation_prim_path: str,
    position_iterations: int,
    velocity_iterations: int,
) -> dict[str, Any]:
    """Raise the UGV articulation's PhysX solver iteration budget.

    2026-09-21 (flat-ground jitter).  The UGV is a four-wheel skid-steer
    articulation whose wheels are velocity drives capped at 3 N*m and whose
    ground is a single static box, so the contact and the drive are solved
    against each other many times per step.  NVIDIA's documented checklist for a
    bouncing/jittering wheeled robot asks for ``solver_position_iteration_count``
    16-64 and ``solver_velocity_iteration_count`` 4-8; the values are applied to
    the articulation root and recorded in the run evidence instead of being left
    at the PhysX default.
    """
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


#: PhysX material combine-mode tokens (Isaac Sim "Combine Modes"): the friction of
#: a contact is derived from *both* materials, so the pair value is only known
#: once the mode is explicit.
PHYSX_COMBINE_MODES: frozenset[str] = frozenset({"average", "min", "multiply", "max"})

#: Wheel drive joints of the Jackal articulation, relative to the robot root.
UGV_WHEEL_JOINT_NAMES: tuple[str, ...] = (
    "front_left_wheel_joint",
    "front_right_wheel_joint",
    "rear_left_wheel_joint",
    "rear_right_wheel_joint",
)


def apply_ugv_wheel_traction(
    stage,
    *,
    robot_prim_path: str,
    material_paths: tuple[str, ...],
    static_friction: float,
    dynamic_friction: float,
    friction_combine_mode: str,
    max_torque_nm: float,
    wheel_joint_names: tuple[str, ...] = UGV_WHEEL_JOINT_NAMES,
) -> dict[str, Any]:
    """Make the wheel/ground friction pair explicit and give the drives margin.

    A skid-steer has to slide its contacts sideways to yaw, so "can it turn in
    place" is decided by two numbers the default configuration leaves implicit:

    * the *effective* wheel/ground friction.  PhysX derives it from both
      materials through the combine mode; on the default ``average`` our
      1.2/1.0 tyre against the 1.0/0.8 ground material lands on 1.1/0.9, i.e.
      right on the boundary the steady-state spin needs;
    * the drive torque cap, because the scrub reaction has to be pushed through
      the very same contacts: the steady in-place spin needs
      ``tau = 0.573 * mu * N * r`` per wheel (``tan(theta) = b/a`` with
      ``b = 0.1878 m``, ``a = 0.131 m``, so ``theta = 55 deg`` and
      ``0.573 * 1.0 * 46.6 N * 0.098 m = 2.62 N*m``), which a 3 N*m cap meets
      with no margin at all -- exactly the measured 0.2-1.5 % yaw execution.

    The values are applied to the spawned robot (wheel material + the four drive
    joints) and echoed into the run evidence.
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

    # Both sides of the contact pair get the combine mode: PhysX resolves the
    # pair value from the two materials, and leaving the ground material on
    # ``average`` would silently halve the intent.
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
                from pxr import PhysxSchema  # type: ignore

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


def dynamic_control_rigid_body_snapshot(prim_path: str, *, root_path: str) -> dict[str, Any]:
    snapshot: dict[str, Any] = {"available": False, "prim_path": prim_path, "root_path": root_path}
    try:
        from omni.isaac.dynamic_control import _dynamic_control  # type: ignore[import-not-found]
    except Exception as exc:
        snapshot["import_error"] = f"{type(exc).__name__}: {exc}"
        return snapshot
    snapshot["available"] = True
    try:
        dc = _dynamic_control.acquire_dynamic_control_interface()
        rb = dc.get_rigid_body(prim_path)
        articulation = dc.get_articulation(root_path)
        snapshot["rigid_body_handle"] = int(rb)
        snapshot["articulation_handle"] = int(articulation)
        snapshot["rigid_body_valid"] = rb != _dynamic_control.INVALID_HANDLE
        snapshot["articulation_valid"] = articulation != _dynamic_control.INVALID_HANDLE
        if rb != _dynamic_control.INVALID_HANDLE:
            for method_name, output_key in (
                ("get_rigid_body_pose", "pose"),
                ("get_rigid_body_linear_velocity", "linear_velocity"),
                ("get_rigid_body_angular_velocity", "angular_velocity"),
                ("get_rigid_body_properties", "properties"),
            ):
                method = getattr(dc, method_name, None)
                if not callable(method):
                    snapshot[f"{output_key}_status"] = "unavailable"
                    continue
                try:
                    value = method(rb)
                    snapshot[output_key] = _json_safe_value(value)
                    if output_key == "pose":
                        snapshot["pose_position"] = _json_safe_value(getattr(value, "p", None))
                        snapshot["pose_rotation"] = _json_safe_value(getattr(value, "r", None))
                except Exception as exc:
                    snapshot[f"{output_key}_error"] = f"{type(exc).__name__}: {exc}"
    except Exception as exc:
        snapshot["error"] = f"{type(exc).__name__}: {exc}"
    return snapshot


def apply_dynamic_control_probe_force(
    prim_path: str,
    *,
    root_path: str,
    force_n: tuple[float, float, float],
    position_m: tuple[float, float, float],
    is_global: bool,
) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "backend": "dynamic_control",
        "force_n": list(force_n),
        "is_global": bool(is_global),
        "position_m": list(position_m),
        "prim_path": prim_path,
        "root_path": root_path,
    }
    try:
        from omni.isaac.dynamic_control import _dynamic_control  # type: ignore[import-not-found]
    except Exception as exc:
        summary.update({"applied": False, "error": f"{type(exc).__name__}: {exc}"})
        return summary
    try:
        dc = _dynamic_control.acquire_dynamic_control_interface()
        rb = dc.get_rigid_body(prim_path)
        articulation = dc.get_articulation(root_path)
        summary["rigid_body_handle"] = int(rb)
        summary["articulation_handle"] = int(articulation)
        if rb == _dynamic_control.INVALID_HANDLE:
            raise RuntimeError(f"invalid dynamic_control rigid body handle: {prim_path}")
        wake_applied = False
        if articulation != _dynamic_control.INVALID_HANDLE:
            dc.wake_up_articulation(articulation)
            wake_applied = True
        else:
            wake = getattr(dc, "wake_up_rigid_body", None)
            if callable(wake):
                wake(rb)
                wake_applied = True
        dc.apply_body_force(rb, _float3(force_n), _float3(position_m), bool(is_global))
        summary.update({"applied": True, "wake_applied": wake_applied})
    except Exception as exc:
        summary.update({"applied": False, "error": f"{type(exc).__name__}: {exc}"})
    return summary


def apply_rigid_prim_probe_force(
    prim_path: str,
    *,
    force_n: tuple[float, float, float],
    position_m: tuple[float, float, float],
    local_frame: bool,
) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "backend": "rigid_prim",
        "force_n": list(force_n),
        "local_frame": bool(local_frame),
        "position_m": list(position_m),
        "prim_path": prim_path,
    }
    if RigidPrim is None:
        summary.update({"applied": False, "error": "RigidPrim unavailable"})
        return summary
    try:
        rigid_prim = make_isaac_prim_view(RigidPrim, prim_path)
        rigid_prim.apply_forces_and_torques_at_pos(
            forces=np.asarray([force_n], dtype=np.float32),
            positions=np.asarray([position_m], dtype=np.float32),
            local_frame=bool(local_frame),
        )
        summary["applied"] = True
    except Exception as exc:
        summary.update({"applied": False, "error": f"{type(exc).__name__}: {exc}"})
    return summary


def set_root_prim_pose(stage, prim_path: str, position_m, orientation_wxyz) -> None:
    prim = stage.GetPrimAtPath(prim_path)
    if not prim.IsValid():
        raise RuntimeError(f"prim not found for pose alignment: {prim_path}")
    xformable = UsdGeom.Xformable(prim)
    xformable.ClearXformOpOrder()

    translate_attr = prim.GetAttribute("xformOp:translate")
    translate_precision = (
        UsdGeom.XformOp.PrecisionFloat
        if translate_attr.IsValid() and str(translate_attr.GetTypeName()) == "float3"
        else UsdGeom.XformOp.PrecisionDouble
    )
    orient_attr = prim.GetAttribute("xformOp:orient")
    orient_precision = (
        UsdGeom.XformOp.PrecisionFloat
        if orient_attr.IsValid() and str(orient_attr.GetTypeName()) == "quatf"
        else UsdGeom.XformOp.PrecisionDouble
    )

    translate_op = xformable.AddTranslateOp(translate_precision)
    if translate_precision == UsdGeom.XformOp.PrecisionFloat:
        translate_op.Set(Gf.Vec3f(float(position_m[0]), float(position_m[1]), float(position_m[2])))
    else:
        translate_op.Set(Gf.Vec3d(float(position_m[0]), float(position_m[1]), float(position_m[2])))

    orient_op = xformable.AddOrientOp(orient_precision)
    if orient_precision == UsdGeom.XformOp.PrecisionFloat:
        orient_op.Set(
            Gf.Quatf(
                float(orientation_wxyz[0]),
                Gf.Vec3f(
                    float(orientation_wxyz[1]),
                    float(orientation_wxyz[2]),
                    float(orientation_wxyz[3]),
                ),
            )
        )
    else:
        orient_op.Set(
            Gf.Quatd(
                float(orientation_wxyz[0]),
                Gf.Vec3d(
                    float(orientation_wxyz[1]),
                    float(orientation_wxyz[2]),
                    float(orientation_wxyz[3]),
                ),
            )
        )


def set_local_prim_pose(stage, prim_path: str, position_m, orientation_wxyz) -> None:
    """Author a prim's local transform.

    This is intentionally separate from ``set_root_prim_pose``.  Chassis/body
    prims under an articulation root need their baked local offset restored,
    not a world coordinate written into their local xform stack.
    """
    set_root_prim_pose(stage, prim_path, position_m, orientation_wxyz)


def set_articulation_root_world_pose(stage, prim_path: str, position_m, orientation_wxyz) -> None:
    """Teleport an Isaac 6 articulation root to a world pose.

    After ``world.reset()`` PhysX owns the live articulation state.  Updating
    only USD xform ops can leave the Quadcopter chassis at its previous
    physical pose while the root prim appears correctly aligned.  Write through
    Isaac's articulation API when available, while still keeping the authored
    root xform synchronized for USD-only diagnostics.
    """
    prim = stage.GetPrimAtPath(prim_path)
    if not prim.IsValid():
        raise RuntimeError(f"articulation prim not found for world pose alignment: {prim_path}")
    set_root_prim_pose(stage, prim_path, position_m, orientation_wxyz)
    if Articulation is None:
        carb.log_warn(
            "isaacsim.core.experimental.prims.Articulation is unavailable; "
            "falling back to USD-authored articulation root pose"
        )
        return
    articulation = make_isaac_prim_view(Articulation, prim_path)
    position = np.asarray([[float(position_m[0]), float(position_m[1]), float(position_m[2])]], dtype=np.float32)
    orientation = np.asarray(
        [[
            float(orientation_wxyz[0]),
            float(orientation_wxyz[1]),
            float(orientation_wxyz[2]),
            float(orientation_wxyz[3]),
        ]],
        dtype=np.float32,
    )
    articulation.set_world_poses(positions=position, orientations=orientation)
    # The articulation API owns the live root state.  Clearing only the
    # chassis rigid body leaves stale root velocity for dynamic-control to
    # report again on the next physics step.
    zero_rigid_prim_velocities(prim_path, rigid_prim=articulation)
    if hasattr(articulation, "set_default_state"):
        try:
            articulation.set_default_state(
                positions=position,
                orientations=orientation,
                linear_velocities=np.zeros((1, 3), dtype=np.float32),
                angular_velocities=np.zeros((1, 3), dtype=np.float32),
            )
        except Exception:
            # Some Isaac backends reject default-state updates on live
            # articulations.  The immediate teleport above is the required
            # operation; default state is only a reset-stability aid.
            pass


def set_rigid_prim_world_pose_and_zero_velocity(
    stage,
    prim_path: str,
    position_m,
    orientation_wxyz,
    *,
    author_usd_xform: bool = True,
) -> dict[str, Any]:
    """Teleport a live rigid body and clear velocities for reset stability."""
    summary: dict[str, Any] = {
        "prim_path": prim_path,
        "rigid_prim_available": RigidPrim is not None,
    }
    prim = stage.GetPrimAtPath(prim_path)
    if not prim.IsValid():
        raise RuntimeError(f"rigid prim not found for world pose reset: {prim_path}")
    summary["author_usd_xform"] = bool(author_usd_xform)
    if author_usd_xform:
        set_root_prim_pose(stage, prim_path, position_m, orientation_wxyz)
    if RigidPrim is None:
        summary["status"] = "usd_pose_only"
        return summary
    position = np.asarray([[float(position_m[0]), float(position_m[1]), float(position_m[2])]], dtype=np.float32)
    orientation = np.asarray(
        [[
            float(orientation_wxyz[0]),
            float(orientation_wxyz[1]),
            float(orientation_wxyz[2]),
            float(orientation_wxyz[3]),
        ]],
        dtype=np.float32,
    )
    try:
        rigid_prim = make_isaac_prim_view(RigidPrim, prim_path)
        rigid_prim.set_world_poses(positions=position, orientations=orientation)
        summary["set_world_poses_called"] = True
        summary.update(zero_rigid_prim_velocities(prim_path, rigid_prim=rigid_prim))
        summary["status"] = "ok"
    except Exception as exc:
        summary["view_error"] = f"{type(exc).__name__}: {exc}"
        summary["status"] = "usd_pose_only_after_view_error" if author_usd_xform else "view_unavailable"
    return summary


def skip_articulation_child_world_pose_reset(
    stage,
    *,
    root_path: str,
    child_path: str,
    target_position_m,
    target_orientation_wxyz,
    label: str,
) -> dict[str, Any]:
    """Record an intentionally skipped live pose reset for articulation children.

    The UAV chassis is a rigid body below an articulation root.  Isaac 4.5 on
    LFT-W02 can leave that chassis physically unresponsive after a soft reset
    when reset code writes both the articulation root pose and the child rigid
    body's live world pose in the same reset boundary.  The root teleport and
    restored child local xform are sufficient to place the chassis on the dock;
    do not also call ``RigidPrim.set_world_poses`` on the child body.
    """
    summary: dict[str, Any] = {
        "child_path": child_path,
        "label": label,
        "reason": "articulation_child_live_world_pose_reset_disabled",
        "root_path": root_path,
        "status": "skipped",
        "target_orientation_wxyz": [float(value) for value in target_orientation_wxyz],
        "target_position_m": [float(value) for value in target_position_m],
    }
    try:
        current_position, current_orientation = prim_world_pose_wxyz(stage, child_path)
        position_delta = [
            float(current_position[index]) - float(target_position_m[index])
            for index in range(3)
        ]
        summary.update(
            {
                "current_orientation_wxyz": list(current_orientation),
                "current_position_m": list(current_position),
                "position_error_m": math.sqrt(sum(component * component for component in position_delta)),
                "position_delta_m": position_delta,
            }
        )
    except Exception as exc:
        summary["current_pose_error"] = f"{type(exc).__name__}: {exc}"
    return summary


def zero_rigid_prim_velocities(
    prim_path: str,
    *,
    rigid_prim: Any | None = None,
) -> dict[str, Any]:
    """Clear a live rigid body's velocities across Isaac core API variants.

    Isaac Sim 6 exposes the unified ``set_velocities`` setter on ``RigidPrim``
    while older Isaac releases used the plural ``RigidPrimView`` spelling.
    Reset code must use the unified API first and retain the older fallbacks:
    leaving stale angular velocity on a docked UAV causes PX4 EKF2 to reject
    HIL data and emit no local-position/attitude estimate.
    """
    summary: dict[str, Any] = {
        "prim_path": prim_path,
        "linear_velocity_zeroed": "unavailable",
        "angular_velocity_zeroed": "unavailable",
    }
    if prim_path.rstrip("/") in {UAV_PRIM.rstrip("/"), UGV_PRIM.rstrip("/")}:
        summary.update(
            {
                "reason": "articulation_root_velocity_reset_uses_multi_body_tensor_view",
                "status": "skipped_articulation_root",
            }
        )
        return summary
    try:
        stage = omni.usd.get_context().get_stage()
        prim = stage.GetPrimAtPath(prim_path) if stage is not None else None
        if prim is not None and prim.IsValid() and prim.HasAPI(UsdPhysics.ArticulationRootAPI):
            summary.update(
                {
                    "reason": "articulation_root_velocity_reset_uses_multi_body_tensor_view",
                    "status": "skipped_articulation_root",
                }
            )
            return summary
    except Exception as exc:
        summary["articulation_root_check_error"] = f"{type(exc).__name__}: {exc}"
    if rigid_prim is None:
        if RigidPrim is None:
            return summary
        try:
            rigid_prim = make_isaac_prim_view(RigidPrim, prim_path)
        except Exception as exc:
            summary["view_error"] = f"{type(exc).__name__}: {exc}"
            summary["status"] = "view_unavailable"
            return summary
    zero_vector = np.zeros(3, dtype=np.float32)
    zero_batch = zero_vector.reshape((1, 3))
    set_velocities = getattr(rigid_prim, "set_velocities", None)
    if callable(set_velocities):
        try:
            set_velocities(
                linear_velocities=zero_batch,
                angular_velocities=zero_batch,
            )
            summary["linear_velocity_zeroed"] = True
            summary["angular_velocity_zeroed"] = True
            summary["velocity_zero_method"] = "set_velocities"
            return summary
        except Exception as exc:
            summary["velocity_zero_error"] = f"{type(exc).__name__}: {exc}"
    setter_specs = (
        (
            "linear",
            getattr(rigid_prim, "set_linear_velocities", None),
            getattr(rigid_prim, "set_linear_velocity", None),
            zero_batch,
            zero_vector,
        ),
        (
            "angular",
            getattr(rigid_prim, "set_angular_velocities", None),
            getattr(rigid_prim, "set_angular_velocity", None),
            zero_batch,
            zero_vector,
        ),
    )
    for kind, plural_setter, singular_setter, plural_value, singular_value in setter_specs:
        error_key = f"{kind}_velocity_zero_error"
        if callable(plural_setter):
            try:
                plural_setter(velocities=plural_value)
                summary[f"{kind}_velocity_zeroed"] = True
                continue
            except Exception as exc:
                summary[error_key] = f"{type(exc).__name__}: {exc}"
        if callable(singular_setter):
            try:
                singular_setter(velocity=singular_value)
                summary[f"{kind}_velocity_zeroed"] = True
                continue
            except Exception as exc:
                summary[error_key] = f"{type(exc).__name__}: {exc}"
        if not callable(plural_setter) and not callable(singular_setter):
            summary[f"{kind}_velocity_zeroed"] = "unavailable"
    return summary


def make_isaac_prim_view(view_cls: Any, prim_path: str) -> Any:
    """Construct an Isaac core prim view across 4.5/5/6 API variants."""
    exact_expr = f"^{re.escape(prim_path)}$"
    attempts = (
        ((), {"prim_paths_expr": exact_expr}),
        ((prim_path,), {}),
        ((), {"prim_path": prim_path}),
    )
    errors: list[str] = []
    for args, kwargs in attempts:
        try:
            return view_cls(*args, **kwargs)
        except Exception as exc:
            errors.append(f"{kwargs or args}: {exc}")
    raise RuntimeError(
        f"failed to construct {getattr(view_cls, '__name__', view_cls)} for {prim_path}: "
        + "; ".join(errors)
    )


def set_robot_world_pose_and_zero_velocity(robot: Any, position_m, orientation_wxyz, *, label: str) -> dict[str, Any]:
    """Teleport an Isaac robot wrapper and clear cached motion state.

    ``set_articulation_root_world_pose`` synchronizes USD and the live
    articulation view, but ROS odom is published from the Jackal robot wrapper.
    In batch full-mission runs that wrapper can keep returning the previous
    episode pose unless its own world pose/default state are refreshed too.
    """
    summary: dict[str, Any] = {"label": label, "status": "ok"}
    position = np.asarray([float(position_m[0]), float(position_m[1]), float(position_m[2])], dtype=np.float32)
    orientation = np.asarray(
        [
            float(orientation_wxyz[0]),
            float(orientation_wxyz[1]),
            float(orientation_wxyz[2]),
            float(orientation_wxyz[3]),
        ],
        dtype=np.float32,
    )
    zeros = np.zeros(3, dtype=np.float32)
    calls = [("set_world_pose", {"position": position, "orientation": orientation})]
    if _AIRGROUND_SIMULATOR_VERSION.startswith("4.5"):
        summary["velocity_setters_skipped"] = True
        summary["velocity_setters_skip_reason"] = "isaac45_articulation_root_velocity_tensor_shape_guard"
        summary["set_linear_velocity_called"] = "skipped"
        summary["set_angular_velocity_called"] = "skipped"
    else:
        calls.extend(
            (
                ("set_linear_velocity", {"velocity": zeros}),
                ("set_angular_velocity", {"velocity": zeros}),
            )
        )
    for method_name, kwargs in calls:
        method = getattr(robot, method_name, None)
        if not callable(method):
            summary[f"{method_name}_called"] = "unavailable"
            continue
        try:
            method(**kwargs)
            summary[f"{method_name}_called"] = True
        except TypeError:
            # Isaac APIs have varied between singular/plural velocity keyword
            # names.  Retry common variants before recording a reset issue.
            retry_kwargs = dict(kwargs)
            if "velocity" in retry_kwargs:
                retry_kwargs["velocities"] = retry_kwargs.pop("velocity")
            elif "position" in retry_kwargs:
                retry_kwargs["positions"] = retry_kwargs.pop("position")
                retry_kwargs["orientations"] = retry_kwargs.pop("orientation")
            try:
                method(**retry_kwargs)
                summary[f"{method_name}_called"] = True
            except Exception as exc:
                summary[f"{method_name}_error"] = f"{type(exc).__name__}: {exc}"
        except Exception as exc:
            summary[f"{method_name}_error"] = f"{type(exc).__name__}: {exc}"
    set_default_state = getattr(robot, "set_default_state", None)
    if callable(set_default_state):
        variants = (
            {"position": position, "orientation": orientation},
            {
                "position": position,
                "orientation": orientation,
                "linear_velocity": zeros,
                "angular_velocity": zeros,
            },
            {"positions": position.reshape((1, 3)), "orientations": orientation.reshape((1, 4))},
        )
        for index, kwargs in enumerate(variants):
            try:
                set_default_state(**kwargs)
                summary["set_default_state_called"] = True
                summary["set_default_state_variant"] = index
                break
            except Exception as exc:
                summary[f"set_default_state_variant_{index}_error"] = f"{type(exc).__name__}: {exc}"
        else:
            summary["set_default_state_called"] = False
    else:
        summary["set_default_state_called"] = "unavailable"
    set_joint_velocities = getattr(robot, "set_joint_velocities", None)
    drive = getattr(robot, "drive", None)
    joint_names = tuple(getattr(getattr(drive, "config", None), "wheel_joint_names", ()) or ())
    if callable(set_joint_velocities) and joint_names:
        try:
            set_joint_velocities(np.zeros(len(joint_names), dtype=np.float32))
            summary["set_joint_velocities_called"] = True
        except Exception as exc:
            summary["set_joint_velocities_error"] = f"{type(exc).__name__}: {exc}"
    else:
        summary["set_joint_velocities_called"] = "unavailable"
    try:
        if hasattr(robot, "_last_cmd_vel"):
            robot._last_cmd_vel = (0.0, 0.0)
        if hasattr(robot, "_last_wheel_speeds"):
            robot._last_wheel_speeds = {}
        summary["cmd_vel_state_cleared"] = True
    except Exception as exc:
        summary["cmd_vel_state_clear_error"] = f"{type(exc).__name__}: {exc}"
    return summary


def _normalize_wxyz(value: tuple[float, float, float, float]) -> tuple[float, float, float, float]:
    norm = math.sqrt(sum(float(component) * float(component) for component in value))
    if norm <= 0.0:
        raise RuntimeError("quaternion must have non-zero norm")
    return tuple(float(component) / norm for component in value)


def child_local_pose_wxyz(
    stage,
    root_path: str,
    child_path: str,
) -> tuple[tuple[float, float, float], tuple[float, float, float, float]]:
    """Return ``child_path`` pose in ``root_path`` coordinates.

    The Isaac Sim Quadcopter root prim is not colocated with its rigid body
    chassis.  Docking connects the Jackal base link to the UAV chassis, so the
    launch script must align the UAV root by subtracting this local chassis
    offset and compensating the chassis' baked-in local rotation.  Otherwise
    the root lands on the dock anchor while the chassis can be physically left
    tilted or inverted, which produces PX4 preflight attitude failures.
    """
    root_prim = stage.GetPrimAtPath(root_path)
    child_prim = stage.GetPrimAtPath(child_path)
    if not root_prim.IsValid():
        raise RuntimeError(f"root prim not found for dock alignment: {root_path}")
    if not child_prim.IsValid():
        raise RuntimeError(f"child prim not found for dock alignment: {child_path}")

    root_world = UsdGeom.Xformable(root_prim).ComputeLocalToWorldTransform(
        Usd.TimeCode.Default()
    )
    child_world = UsdGeom.Xformable(child_prim).ComputeLocalToWorldTransform(
        Usd.TimeCode.Default()
    )
    child_local = child_world * root_world.GetInverse()
    translation = child_local.ExtractTranslation()
    rotation = child_local.ExtractRotationQuat()
    imaginary = rotation.GetImaginary()
    return (
        (float(translation[0]), float(translation[1]), float(translation[2])),
        _normalize_wxyz(
            (
                float(rotation.GetReal()),
                float(imaginary[0]),
                float(imaginary[1]),
                float(imaginary[2]),
            )
        ),
    )


def child_local_translation(stage, root_path: str, child_path: str) -> tuple[float, float, float]:
    """Return ``child_path`` translation in ``root_path`` coordinates."""
    translation, _orientation = child_local_pose_wxyz(stage, root_path, child_path)
    return translation


def airground_sensor_frame_from_usd(
    stage,
    *,
    root_path: str,
    sensor_prim_path: str | None,
    frame_id: str,
) -> "JackalSensorFrame | None":
    """Static TF entry for a sensor prim, measured from the live USD mount.

    Nav2 transforms costmap observations with tf2, so a point cloud published in
    a sensor frame (``ugv_os1_lidar`` for the Ouster OS1 on the Jackal) is
    unusable until that frame exists in the TF tree.  Reading the mount back from
    the stage keeps TF and simulator geometry identical instead of duplicating
    the offset and the asset's baked-in corrective rotation by hand.
    """
    if not sensor_prim_path:
        return None
    try:
        translation, orientation_wxyz = child_local_pose_wxyz(
            stage, root_path, sensor_prim_path
        )
    except Exception as exc:
        carb.log_warn(
            f"AirGround sensor frame '{frame_id}' unavailable for TF: {exc}"
        )
        return None
    w, qx, qy, qz = orientation_wxyz
    frame = JackalSensorFrame(
        frame_id=frame_id,
        translation_m=translation,
        rotation_xyzw=(qx, qy, qz, w),
    )
    carb.log_warn(
        "AirGround sensor frame TF: "
        f"{frame_id} in {root_path} translation_m="
        f"[{frame.translation_m[0]:.4f}, {frame.translation_m[1]:.4f}, {frame.translation_m[2]:.4f}] "
        f"rotation_xyzw=[{frame.rotation_xyzw[0]:.4f}, {frame.rotation_xyzw[1]:.4f}, "
        f"{frame.rotation_xyzw[2]:.4f}, {frame.rotation_xyzw[3]:.4f}]"
    )
    return frame


def _usd_during_episode_reset(method):
    """Keep authored reset transforms and root bindings on current USD."""
    from functools import wraps

    @wraps(method)
    def wrapped(self, *args, **kwargs):
        capture = getattr(self, '_main_loop_capture', None)
        if capture is not None and not capture.closed and getattr(capture, 'blocks_reset', False):
            raise RuntimeError('reset is unavailable during the private native math ABBA capture')
        owner = getattr(self, "_fabric_state", None)
        if owner is None:
            return method(self, *args, **kwargs)
        with owner.reset_output():
            result = method(self, *args, **kwargs)
        result["fabric_state"] = {"active":owner.active,"binding_generation":owner.bind_count}
        return result
    return wrapped


def prim_world_pose_wxyz(stage, prim_path: str) -> tuple[tuple[float, float, float], tuple[float, float, float, float]]:
    """Return an absolute USD prim world pose as position and wxyz orientation."""
    prim = stage.GetPrimAtPath(prim_path)
    if not prim.IsValid():
        raise RuntimeError(f"prim not found for world pose sampling: {prim_path}")
    world = UsdGeom.Xformable(prim).ComputeLocalToWorldTransform(Usd.TimeCode.Default())
    translation = world.ExtractTranslation()
    rotation = world.ExtractRotationQuat()
    imaginary = rotation.GetImaginary()
    return (
        (float(translation[0]), float(translation[1]), float(translation[2])),
        (
            float(rotation.GetReal()),
            float(imaginary[0]),
            float(imaginary[1]),
            float(imaginary[2]),
        ),
    )


FULL_MISSION_EVIDENCE_REQUEST_TOPIC = "/airground/full_mission/evidence_request"
FULL_MISSION_EVIDENCE_RESPONSE_TOPIC = "/airground/full_mission/evidence_response"
FULL_MISSION_EVIDENCE_REQUEST_SCHEMA = "airground-full-mission-evidence-request-v1"
FULL_MISSION_EVIDENCE_RESPONSE_SCHEMA = "airground-full-mission-evidence-response-v1"
CONFIRMATION_SENSOR_FRAME_TOPIC = "/ugv/confirmation_visibility_sensor_frames"
CONFIRMATION_CAMERA_HEIGHT_M = 1.2
CONFIRMATION_IGNORED_PRIM_PREFIXES = (
    "/World/UAV",
    "/World/uav",
    "/World/UGV",
    "/World/ugv",
)
#: Every task's robot roots: raycasts, clouds and the GPU collision snapshot must
#: not see any robot of any task (prefix matching is exact-or-child, so
#: ``/World/ugv_1`` is not covered by ``/World/ugv``).
ROBOT_IGNORED_PRIM_PREFIXES = tuple(
    dict.fromkeys(
        CONFIRMATION_IGNORED_PRIM_PREFIXES
        + tuple(path for task in TASKS for path in (task.values["UAV_PRIM"], task.values["UGV_PRIM"]))
    )
)


def _airground_yaw_from_wxyz(orientation_wxyz: tuple[float, float, float, float]) -> float:
    w, x, y, z = (float(value) for value in orientation_wxyz[:4])
    return math.atan2(2.0 * (w * z + x * y), 1.0 - 2.0 * (y * y + z * z))


def _airground_physx_raycast_fn() -> tuple[Any, tuple[str, ...]]:
    """Return the shared benchmark PhysX raycast callable and ignored prims."""
    _airground_prepare_benchmark_package_import()
    import omni.physx
    from airground_benchmark.isaac_los import (  # noqa: WPS433
        DEFAULT_IGNORED_LOS_PRIM_PATHS,
        make_isaac_physx_raycast_fn,
    )

    scene_query = omni.physx.get_physx_scene_query_interface()
    raycast_fn = make_isaac_physx_raycast_fn(scene_query)
    return raycast_fn, tuple(dict.fromkeys(tuple(DEFAULT_IGNORED_LOS_PRIM_PATHS) + ROBOT_IGNORED_PRIM_PREFIXES))


def _airground_physx_segment_raycast_fn() -> Any:
    """Adapt the benchmark PhysX raycast to plain ``(origin, target)`` tuples."""
    raycast_fn, _ignored = _airground_physx_raycast_fn()
    from airground_benchmark.communication import RadioPose  # noqa: WPS433

    def segment_raycast(origin: Any, target: Any) -> Any:
        return raycast_fn(RadioPose(*origin), RadioPose(*target))

    return segment_raycast


def _airground_lazy_physx_segment_raycast_fn() -> Any:
    """Resolve the benchmark PhysX raycast lazily and retry until available.

    The full-mission wrapper copies ``airground_benchmark`` into the container
    only right before it starts the mission runner, so the Isaac launch process
    must not require the package during app init (an eager import failed with
    ``cannot locate airground_benchmark package`` on the 2026-09-12 scan run).
    Until the package appears the scan publishes an all-``inf`` frame, which
    Nav2's obstacle layer ignores because ``inf_is_valid`` is false.
    """
    state: dict[str, Any] = {"active_logged": False, "raycast_fn": None, "warned": False}

    def segment_raycast(origin: Any, target: Any) -> Any:
        raycast_fn = state["raycast_fn"]
        if raycast_fn is None:
            try:
                raycast_fn = _airground_physx_segment_raycast_fn()
            except Exception as exc:
                if not state["warned"]:
                    state["warned"] = True
                    carb.log_warn(
                        f"UGV proximity scan waiting for benchmark PhysX raycast: {exc}"
                    )
                return ()
            state["raycast_fn"] = raycast_fn
            if not state["active_logged"]:
                state["active_logged"] = True
                carb.log_warn("UGV proximity scan active: benchmark PhysX raycast resolved")
        return raycast_fn(origin, target)

    return segment_raycast


_SHARED_GPU_CLOUD: "_LazyGpuCloud | None" = None


AIRGROUND_UGV_CLOUD_BATCH = _env_bool("AIRGROUND_UGV_CLOUD_BATCH", False)
AIRGROUND_DOCK_DIAG = _env_bool("AIRGROUND_DOCK_DIAG", False)


def _shared_gpu_cloud() -> "_LazyGpuCloud":
    """One collision snapshot for all tasks: the scene is static and sampling is a pure function of pose."""
    global _SHARED_GPU_CLOUD
    if _SHARED_GPU_CLOUD is None:
        _SHARED_GPU_CLOUD = _LazyGpuCloud()
    return _SHARED_GPU_CLOUD


class _LazyGpuCloud:
    """Initialize the native collision snapshot once the runtime package exists."""

    def __init__(self) -> None:
        self.backend = None
        self.initialization_error = None

    def sample_proximity_cloud_points(self, position: Any, orientation: Any, config: Any) -> Any:
        if self.backend is None:
            if self.initialization_error is not None:
                raise RuntimeError("GPU cloud initialization failed; restart after fixing the cause") from self.initialization_error
            # The runtime package appears later during reset preparation; retry
            # that transient import, but never repeat a failed native export.
            _airground_prepare_benchmark_package_import()
            tools = str(Path(__file__).resolve().parents[1] / "tools")
            if tools not in sys.path:
                sys.path.insert(0, tools)
            from gpu_proximity_cloud import GpuProximityCloud
            trace = os.environ.get("AIRGROUND_STARTUP_TRACE_FILE")
            # AirGroundRuns is the host's shared runs/ directory: without a trace file,
            # concurrent containers would export and re-read each other's scene
            # (2026-10-11, gpd63 overwrote gpd62's snapshot), so key it by container.
            output = (
                Path(trace).parent / "gpu_cloud"
                if trace
                else Path("/isaac-sim/AirGroundRuns/gpu_cloud_runtime") / f"{os.uname().nodename}_{os.getpid()}"
            )
            try:
                self.backend = GpuProximityCloud(omni.usd.get_context().get_stage(), config,
                                                  output)
            except Exception as exc:
                self.initialization_error = exc
                raise
        return self.backend.sample_proximity_cloud_points(position, orientation, config)


def _airground_wxyz_from_yaw(yaw_rad: float) -> tuple[float, float, float, float]:
    yaw = float(yaw_rad)
    if not math.isfinite(yaw):
        raise RuntimeError("yaw_rad must be finite")
    return (math.cos(yaw * 0.5), 0.0, 0.0, math.sin(yaw * 0.5))


def _rgbd_surface_configs(surface: Mapping[str, Any] | None) -> list[RgbdCameraSurfaceConfig]:
    if not isinstance(surface, Mapping) or surface.get("mode") != "manual":
        return []
    configs: list[RgbdCameraSurfaceConfig] = []
    for side in ("left", "right"):
        payload = surface.get(side)
        if not isinstance(payload, Mapping):
            continue
        namespace = str(payload["namespace"])
        robot_token = namespace.strip("/").split("/", 1)[0]
        surface_token = f"{robot_token}_{side}"
        aliases = {
            side,
            robot_token,
            surface_token,
            namespace,
            str(payload["camera_prim"]),
            str(payload["frame_id"]),
            str(payload["rgb_topic"]),
            str(payload["depth_topic"]),
        }
        if AIRGROUND_RGBD_PUBLISHER_SURFACES is not None and aliases.isdisjoint(
            AIRGROUND_RGBD_PUBLISHER_SURFACES
        ):
            continue
        configs.append(
            RgbdCameraSurfaceConfig(
                namespace=namespace,
                camera_prim=str(payload["camera_prim"]),
                frame_id=str(payload["frame_id"]),
                width=int(payload["width"]),
                height=int(payload["height"]),
                rgb_topic=str(payload["rgb_topic"]),
                depth_topic=str(payload["depth_topic"]),
                info_topic=str(payload["info_topic"]),
            )
        )
    return configs


def _airground_prepare_benchmark_package_import() -> None:
    candidates: list[Path] = []
    explicit = os.environ.get("AIRGROUND_BENCHMARK_PACKAGE")
    if explicit:
        candidates.append(Path(explicit))
    candidates.extend(
        [
            Path("/tmp/airground_benchmark"),
            Path("/isaac-sim/benchmark/airground_benchmark"),
            Path.cwd() / "benchmark/airground_benchmark",
        ]
    )
    for candidate in candidates:
        if (candidate / "runtime_communication.py").exists() and (candidate / "communication.py").exists():
            package = types.ModuleType("airground_benchmark")
            package.__path__ = [str(candidate)]  # type: ignore[attr-defined]
            sys.modules.setdefault("airground_benchmark", package)
            return
    raise ModuleNotFoundError("cannot locate airground_benchmark package for Isaac-resident evidence server")


class AirGroundFullMissionEvidenceServer:
    """Generate full-mission evidence inside the live Isaac/PhysX process."""

    def __init__(self, app: Any) -> None:
        try:
            import rclpy
            from std_msgs.msg import String
        except Exception as exc:  # pragma: no cover - exercised in Isaac/ROS runtime.
            raise RuntimeError("full-mission evidence server requires ROS 2 String support") from exc
        self.app = app
        self.stage = omni.usd.get_context().get_stage()
        if self.stage is None:
            raise RuntimeError("full-mission evidence server requires a loaded USD stage")
        self._rclpy = rclpy
        self._String = String
        from pegasus.simulator.logic import ros_context  # per-task ROS domain (SimMT-2)

        self.node = ros_context.create_node("airground_full_mission_evidence_server")
        self.response_pub = self.node.create_publisher(String, FULL_MISSION_EVIDENCE_RESPONSE_TOPIC, 10)
        self.sensor_frame_pub = self.node.create_publisher(String, CONFIRMATION_SENSOR_FRAME_TOPIC, 10)
        self.request_sub = ros_context.create_subscription(
            self.node,
            String,
            FULL_MISSION_EVIDENCE_REQUEST_TOPIC,
            self._on_request,
            10,
        )
        self._pending_requests: list[dict[str, Any]] = []
        self._pending_request_ids: set[str] = set()
        self._response_cache: dict[str, dict[str, Any]] = {}
        self._active_request_id = ""
        self._processing_request = False

    def spin_once(self) -> None:
        from pegasus.simulator.logic import ros_context

        ros_context.spin_once(self.node)
        if self._processing_request or not self._pending_requests:
            return
        request = self._pending_requests.pop(0)
        request_id = str(request.get("request_id") or "")
        kind = str(request.get("kind") or "unknown")
        self._pending_request_ids.discard(request_id)
        self._active_request_id = request_id
        self._processing_request = True
        scheduler = getattr(self.app, "session_scheduler", None)
        if scheduler is not None and not scheduler.in_session():
            # Cooperative mode: the handler runs as a session that parks wherever
            # it used to call world.step (see airground_sidecar/session_scheduler.py).
            scheduler.start(self._run_request, request, request_id, kind, owner=self.app)
        else:
            self._run_request(request, request_id, kind)

    def _run_request(self, request: Mapping[str, Any], request_id: str, kind: str) -> None:
        carb.log_info(f"AirGround full-mission evidence request start: kind={kind} request_id={request_id}")
        try:
            response = self._handle_request(request)
            carb.log_info(f"AirGround full-mission evidence request done: kind={kind} request_id={request_id}")
        except Exception as exc:  # pragma: no cover - exercised in live Isaac/ROS.
            traceback_text = traceback.format_exc()
            response = {
                "error": f"{type(exc).__name__}: {exc}",
                "kind": kind,
                "payload": {},
                "request_id": request_id,
                "schema_version": FULL_MISSION_EVIDENCE_RESPONSE_SCHEMA,
                "status": "failed",
                "traceback": traceback_text,
            }
            carb.log_error(
                f"AirGround full-mission evidence request failed: "
                f"kind={kind} request_id={request_id} error={response['error']}\n{traceback_text}"
            )
        finally:
            self._processing_request = False
            self._active_request_id = ""
        if request_id:
            self._response_cache[request_id] = response
        self._publish_response(response)

    def close(self) -> None:
        self.node.destroy_node()

    def _publish_response(self, response: Mapping[str, Any]) -> None:
        message = self._String()
        message.data = json.dumps(dict(response), allow_nan=False, sort_keys=True, separators=(",", ":"))
        self.response_pub.publish(message)

    def _on_request(self, message: Any) -> None:  # pragma: no cover - exercised in live Isaac/ROS.
        request_id = ""
        kind = "unknown"
        try:
            request = json.loads(message.data)
            if not isinstance(request, dict):
                raise RuntimeError("request must be a JSON object")
            if request.get("schema_version") != FULL_MISSION_EVIDENCE_REQUEST_SCHEMA:
                return
            request_id = str(request.get("request_id") or "")
            kind = str(request.get("kind") or "")
            payload = request.get("payload")
            if not request_id or not kind or not isinstance(payload, dict):
                raise RuntimeError("request_id, kind and payload object are required")
            cached = self._response_cache.get(request_id)
            if cached is not None:
                self._publish_response(cached)
                return
            if request_id == self._active_request_id or request_id in self._pending_request_ids:
                return
            self._pending_requests.append({"kind": kind, "payload": dict(payload), "request_id": request_id})
            self._pending_request_ids.add(request_id)
            carb.log_info(f"AirGround full-mission evidence request queued: kind={kind} request_id={request_id}")
            return
        except Exception as exc:
            traceback_text = traceback.format_exc()
            response = {
                "error": f"{type(exc).__name__}: {exc}",
                "kind": kind,
                "payload": {},
                "request_id": request_id,
                "schema_version": FULL_MISSION_EVIDENCE_RESPONSE_SCHEMA,
                "status": "failed",
                "traceback": traceback_text,
            }
        self._publish_response(response)

    def _handle_request(self, request: Mapping[str, Any]) -> dict[str, Any]:
        request_id = str(request.get("request_id") or "")
        kind = str(request.get("kind") or "")
        payload = request.get("payload")
        if not request_id or not kind or not isinstance(payload, dict):
            raise RuntimeError("request_id, kind and payload object are required")
        if kind == "communication_los":
            response_payload = self._communication_los(payload)
        elif kind == "confirmation_sensor_frames":
            response_payload = self._confirmation_sensor_frames(payload)
        elif kind == "episode_reset":
            response_payload = self._episode_reset(payload)
        elif kind == "uav_force_response_probe":
            response_payload = self._uav_force_response_probe(payload)
        elif kind == "uav_control_offboard":
            response_payload = self._uav_control_offboard(payload)
        elif kind == "runtime_performance_probe":
            if not _env_bool("AIRGROUND_RUNTIME_PERFORMANCE_PROBE", False):
                raise RuntimeError("private runtime performance probe is not enabled")
            # Kit's fast importer can retain old probe bytecode across reload.
            # Load only our fixed operator-owned source; no request-selected
            # module, path or code is executed here. Warp modules stay loaded.
            import hashlib
            probe_path = Path(__file__).with_name('runtime_performance_probe.py')
            source = probe_path.read_text(encoding='utf-8')
            probe_module = types.ModuleType('airground_private_runtime_performance_probe')
            probe_module.__file__ = str(probe_path)
            exec(compile(source,str(probe_path),'exec'),probe_module.__dict__)
            response_payload = probe_module.probe(self.app, payload)
            response_payload['probe_source_sha256'] = hashlib.sha256(source.encode()).hexdigest()
        else:
            raise RuntimeError(f"unsupported full-mission evidence kind: {kind}")
        return {
            "kind": kind,
            "payload": response_payload,
            "request_id": request_id,
            "schema_version": FULL_MISSION_EVIDENCE_RESPONSE_SCHEMA,
            "status": "ok",
        }

    def _raycast_fn(self) -> tuple[Any, tuple[str, ...]]:
        return _airground_physx_raycast_fn()

    @staticmethod
    def _position_tuple(value: Any, field: str) -> tuple[float, float, float]:
        if not isinstance(value, list | tuple) or len(value) != 3:
            raise RuntimeError(f"{field} must be a three-element position")
        result = tuple(float(component) for component in value)
        if not all(math.isfinite(component) for component in result):
            raise RuntimeError(f"{field} must contain finite values")
        return result

    @staticmethod
    def _communication_hit_json(hit: Any) -> dict[str, Any]:
        return {
            "distance_m": float(getattr(hit, "distance_m", 0.0)),
            "prim_path": str(getattr(hit, "prim_path", "")),
        }

    def _communication_los(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        _airground_prepare_benchmark_package_import()
        from airground_benchmark.communication import RadioPose  # noqa: WPS433
        from airground_benchmark.runtime_communication import RuntimeCommunicationBridge  # noqa: WPS433

        uav_pose = self._position_tuple(payload.get("uav_position_m"), "uav_position_m")
        ugv_pose = self._position_tuple(payload.get("ugv_position_m"), "ugv_position_m")
        message_payload = bytes.fromhex(str(payload.get("payload_hex") or ""))
        detection_time_s = float(payload.get("detection_time_s", 0.0))
        seed = int(payload.get("seed", 0))
        raycast_fn, ignored_los_prim_paths = self._raycast_fn()
        uav_radio_pose = RadioPose(*uav_pose)
        ugv_radio_pose = RadioPose(*ugv_pose)
        raycast_hits = tuple(raycast_fn(uav_radio_pose, ugv_radio_pose))
        bridge = RuntimeCommunicationBridge(
            seed=seed,
            raycast=raycast_fn,
            ignored_los_prim_paths=ignored_los_prim_paths,
            jitter_max_ms=0.0,
        )
        bridge.set_radio_poses({"uav": uav_radio_pose, "ugv": ugv_radio_pose})
        los_clear = bridge.link_los_clear("uav", "ugv")
        receipt = bridge.submit(sender="uav", recipient="ugv", payload=message_payload, submit_time_s=detection_time_s)
        delivered = bridge.advance((receipt.deliver_time_s or detection_time_s) + 1.0e-6)
        inbox = bridge.drain_inbox("ugv")
        delivered_message = delivered[0] if delivered else None
        evidence = {
            "airtime_ms": (delivered_message.airtime_ms if delivered_message is not None else 0.0),
            "delivered": len(delivered) == 1 and len(inbox) == 1,
            "distance_m": (delivered_message.distance_m if delivered_message is not None else None),
            "ignored_los_prim_paths": list(ignored_los_prim_paths),
            "latency_ms": (delivered_message.latency_ms if delivered_message is not None else 0.0),
            "los_clear": los_clear,
            "los_provider": "isaac_physx",
            "message_id": receipt.message_id,
            "nlos": (delivered_message.nlos if delivered_message is not None else None),
            "packet_count": receipt.packet_count,
            "payload_length": receipt.payload_length,
            "raycast_hit_count": len(raycast_hits),
            "raycast_hits": [self._communication_hit_json(hit) for hit in raycast_hits[:20]],
            "receipt_reason": receipt.reason,
            "receipt_status": receipt.status,
            "source": "RuntimeCommunicationBridge",
            "submitted": True,
        }
        return {"evidence": evidence}

    def _episode_reset(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        ugv_payload = payload.get("ugv")
        if not isinstance(ugv_payload, dict):
            raise RuntimeError("episode_reset payload.ugv must be an object")
        uav_payload = payload.get("uav_on_platform")
        if uav_payload is not None and not isinstance(uav_payload, dict):
            raise RuntimeError("episode_reset payload.uav_on_platform must be an object when provided")
        return self.app.reset_episode_start(
            ugv_x_m=float(ugv_payload.get("x_m")),
            ugv_y_m=float(ugv_payload.get("y_m")),
            ugv_yaw_rad=float(ugv_payload.get("yaw_rad")),
            uav_platform_x_m=float((uav_payload or {}).get("x_m", 0.0)),
            uav_platform_y_m=float((uav_payload or {}).get("y_m", 0.0)),
            uav_platform_z_m=float((uav_payload or {}).get("z_m", 0.45)),
            uav_platform_yaw_rad=float((uav_payload or {}).get("yaw_rad", 0.0)),
            docked=bool(payload.get("docked", True)),
        )

    def _cached_target_annotations(self, path: Path, loader: Any) -> Any:
        """Load the (frozen) target manifest once per file version.

        This runs on the Kit main thread for every confirmation request, so a re-parse stalls
        the physics step of every task in the process.
        """
        resolved = path.expanduser().resolve(strict=True)
        stat = resolved.stat()
        key = (str(resolved), int(stat.st_mtime_ns), int(stat.st_size))
        cache = self.__dict__.setdefault("_target_annotation_cache", {})
        manifest = cache.get(key)
        if manifest is None:
            started = time.perf_counter()
            manifest = loader(resolved)
            cache[key] = manifest
            carb.log_warn(
                f"[AirGround] target annotations loaded for confirmation frames in "
                f"{time.perf_counter() - started:.3f} s: {resolved}"
            )
        return manifest

    def _confirmation_sensor_frames(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        _airground_prepare_benchmark_package_import()
        from airground_benchmark.ground_truth import (  # noqa: WPS433
            confirmation_sensor_frame_records_from_pose,
            load_target_annotations,
        )

        annotations_path = Path(str(payload.get("target_annotations_path") or ""))
        target_id = str(payload.get("target_id") or "")
        frame_count = max(1, int(payload.get("frame_count", 5)))
        frame_interval_s = max(0.0, float(payload.get("frame_interval_s", 0.1)))
        manifest = self._cached_target_annotations(annotations_path, load_target_annotations)
        raycast_fn, _ignored_los_prim_paths = self._raycast_fn()
        ugv_position, ugv_orientation_wxyz = prim_world_pose_wxyz(self.stage, UGV_SENSOR_BODY_PATH)
        camera_position = (
            float(ugv_position[0]),
            float(ugv_position[1]),
            float(ugv_position[2]) + CONFIRMATION_CAMERA_HEIGHT_M,
        )
        yaw_rad = _airground_yaw_from_wxyz(ugv_orientation_wxyz)
        base_time_s = float(self.app._simulation_time_s())
        records: list[dict[str, Any]] = []
        for frame_index in range(frame_count):
            frame_records = confirmation_sensor_frame_records_from_pose(
                manifest,
                raycast_fn,
                camera_position_xyz_m=camera_position,
                camera_yaw_rad=yaw_rad,
                sim_time_s=base_time_s + float(frame_index) * frame_interval_s,
                camera_frame="ugv/confirmation_camera",
                target_id=target_id,
                camera_height_m=CONFIRMATION_CAMERA_HEIGHT_M,
                ignored_prim_prefixes=ROBOT_IGNORED_PRIM_PREFIXES,
            )
            for record in frame_records:
                message = self._String()
                message.data = json.dumps(record, allow_nan=False, sort_keys=True, separators=(",", ":"))
                self.sensor_frame_pub.publish(message)
                records.append(dict(record))
        return {"published_count": len(records), "records": records}

    def _resolve_px4_connection(self, requested: str) -> str:
        if requested and requested != "auto":
            return requested
        return f"udpin:0.0.0.0:{self.app.task.px4_gcs_port}"

    def _step_once_for_uav_control(self) -> None:
        """Advance the sim so the OFFBOARD control window tracks wall time.

        The OFFBOARD runner calls this once per pump iteration and then blocks
        up to 20 ms on MAVLink, so stepping exactly one physics step per call
        advanced the simulation at only ~0.3x real time (measured 4 ms sim per
        ~11 ms wall in the 2026-09-12 mission traces).  PX4 keeps free-running
        on the wall clock, so that mismatch multiplied the flight controller's
        effective loop rate per simulated second by the same ~3x and drove the
        UAV into full-scale bang-bang oscillation right after takeoff
        (`uav_control_actuator_trace.jsonl`: [1.0, 0, 1.0, 0] alternating with
        [0, 0.831, 0, 0.831]).  Step enough physics steps to track the wall
        clock, with a bounded catch-up so a stalled pump cannot burst-step.
        """
        try:
            self.app.ugv.apply_cmd_vel(0.0, 0.0)
        except Exception as exc:
            carb.log_warn(f"AirGround UGV stop command skipped during UAV control step: {exc}")
        try:
            physics_dt = float(self.app.world.get_physics_dt())
        except Exception:
            physics_dt = 0.0
        now = time.time()
        previous_wall_s = getattr(self, "_airground_uav_control_step_wall_s", None)
        self._airground_uav_control_step_wall_s = now
        step_count = 1
        if (
            AIRGROUND_UAV_CONTROL_STEP_CATCHUP
            and physics_dt > 0.0
            and previous_wall_s is not None
        ):
            elapsed_s = max(0.0, now - float(previous_wall_s))
            step_count = int(max(1.0, min(float(AIRGROUND_UAV_CONTROL_MAX_CATCHUP_STEPS), round(elapsed_s / physics_dt))))
        for _ in range(max(1, step_count)):
            self.app.step_world(render=AIRGROUND_UAV_CONTROL_STEP_RENDER)
            self.app._pump_uav_px4_runtime_once("uav_control_step")

    @staticmethod
    def _uav_control_attempt_trace_path(base_path: Path, attempt_index: int) -> Path:
        if attempt_index <= 1:
            return base_path
        suffix = base_path.suffix or ".jsonl"
        return base_path.with_name(f"{base_path.stem}.attempt_{attempt_index:02d}{suffix}")

    @staticmethod
    def _uav_control_attempt_artifact_paths(output_dir: Path, attempt_index: int) -> dict[str, Path]:
        suffix = "" if attempt_index <= 1 else f".attempt_{attempt_index:02d}"
        return {
            "actuator_trace": output_dir / f"uav_control_actuator_trace{suffix}.jsonl",
            "dynamics_trace": output_dir / f"uav_control_dynamics_trace{suffix}.jsonl",
            "force_trace": output_dir / f"uav_control_force_trace{suffix}.jsonl",
        }

    def _configure_uav_control_diagnostics(self, output_dir: Path, attempt_index: int) -> dict[str, Any]:
        paths = self._uav_control_attempt_artifact_paths(output_dir, attempt_index)
        summary: dict[str, Any] = {
            "attempt_index": attempt_index,
            "paths": {key: str(path) for key, path in paths.items()},
            "vehicle_found": False,
            "backends": [],
        }
        vehicle = self.app._uav_vehicle()
        if vehicle is not None:
            summary["vehicle_found"] = True
            setattr(vehicle, "_force_trace_path", str(paths["force_trace"]))
            # Every-N step sampling; 1 gives a per-physics-step trace (needed to
            # resolve control-loop content such as the 15.2 Hz rate oscillation
            # seen in the gyro channel).
            setattr(
                vehicle,
                "_force_trace_sample_period",
                max(1, _multirotor_env_int("AIRGROUND_VEHICLE_FORCE_TRACE_SAMPLE_PERIOD", 25)),
            )
            setattr(vehicle, "_force_trace_count", 0)
            if hasattr(vehicle, "_dynamics_trace_path"):
                setattr(vehicle, "_dynamics_trace_path", str(paths["dynamics_trace"]))
                setattr(
                    vehicle,
                    "_dynamics_trace_sample_period",
                    max(1, _multirotor_env_int("AIRGROUND_MULTIROTOR_DYNAMICS_TRACE_SAMPLE_PERIOD", 25)),
                )
                setattr(vehicle, "_dynamics_trace_count", 0)
        for index, backend in enumerate(self.app._uav_backends()):
            backend_summary: dict[str, Any] = {"backend_index": index, "class": type(backend).__name__}
            config = getattr(backend, "config", None)
            if config is not None:
                setattr(config, "actuator_trace_path", str(paths["actuator_trace"]))
                backend_summary["actuator_trace_path"] = str(paths["actuator_trace"])
            trace_file = getattr(backend, "_actuator_trace_file", None)
            if trace_file is not None:
                try:
                    trace_file.close()
                    backend_summary["previous_actuator_trace_closed"] = True
                except Exception as exc:
                    backend_summary["previous_actuator_trace_close_error"] = f"{type(exc).__name__}: {exc}"
                setattr(backend, "_actuator_trace_file", None)
            if hasattr(backend, "_actuator_trace_count"):
                setattr(backend, "_actuator_trace_count", 0)
            summary["backends"].append(backend_summary)
        return summary

    @staticmethod
    def _uav_control_report_failure_reason(report: Mapping[str, Any]) -> str | None:
        smoke_steps = report.get("smoke")
        if not isinstance(smoke_steps, list):
            return None
        for step in reversed(smoke_steps):
            if not isinstance(step, Mapping):
                continue
            if step.get("step") == "arm" and step.get("status") != "ok":
                reason = step.get("reason")
                return str(reason) if reason is not None else None
        return None

    @classmethod
    def _is_retryable_uav_control_prearm_failure(
        cls,
        report: Mapping[str, Any],
        *,
        dock_release_status: Mapping[str, Any],
    ) -> bool:
        if report.get("status") == "ok" or dock_release_status.get("released") is True:
            return False
        reason = cls._uav_control_report_failure_reason(report)
        if reason not in {"pre_arm_telemetry_unstable", "pre_arm_health_unstable"}:
            return False
        stats = report.get("stats") if isinstance(report.get("stats"), Mapping) else {}
        latest = report.get("latest") if isinstance(report.get("latest"), Mapping) else {}
        status_text = str(latest.get("last_status_text") or "").lower()
        attitude_samples = int(stats.get("attitude_samples") or 0)
        local_position_samples = int(stats.get("samples") or 0)
        telemetry_missing = attitude_samples <= 0 or local_position_samples <= 0
        retryable_status = any(
            marker in status_text
            for marker in (
                "ekf2 missing data",
                "missing data",
                "preflight fail",
                "high accelerometer bias",
                "high gyro bias",
                "attitude failure",
            )
        )
        return telemetry_missing or retryable_status

    def _recover_uav_control_prearm_retry(
        self,
        *,
        attempt_index: int,
        reason: str | None,
        episode_start_reset: Mapping[str, Any] | None,
    ) -> dict[str, Any]:
        summary: dict[str, Any] = {
            "attempt_index": attempt_index,
            "reason": reason,
            "recovery": "episode_reset_before_uav_control_retry",
        }
        if isinstance(episode_start_reset, Mapping):
            summary["episode_reset"] = self._episode_reset(dict(episode_start_reset))
        else:
            summary["recovery"] = "px4_backend_restart_before_uav_control_retry"
            summary["px4_backend_reset"] = self.app._reset_uav_px4_backend_state(
                "uav_control_prearm_retry"
            )
            summary["callback_refresh"] = self.app._refresh_uav_physics_callbacks()
            summary["uav_sensor_reset"] = self.app._reset_uav_sensor_state(
                "uav_control_prearm_retry"
            )
            summary["px4_backend_restart"] = self.app._restart_uav_px4_backend_state(
                "uav_control_prearm_retry"
            )
            try:
                self.app.timeline.play()
                summary["timeline_played"] = True
            except Exception as exc:
                summary["timeline_play_error"] = f"{type(exc).__name__}: {exc}"
        for _ in range(120):
            self.app.step_world(render=AIRGROUND_UAV_CONTROL_STEP_RENDER)
            self.app._pump_uav_px4_runtime_once("uav_control_prearm_retry_recovery")
            self.app.publish_runtime_state(spin_evidence_server=False)
        summary["post_recovery_world_steps"] = 120
        summary["post_recovery_uav_px4_runtime"] = self.app._uav_px4_runtime_snapshot(
            "uav_control_prearm_retry_recovery"
        )
        return summary

    def _uav_force_response_probe(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        body_path = str(payload.get("body_path") or f"{UAV_PRIM}{UAV_MAPPING.body_path}")
        root_path = str(payload.get("root_path") or UAV_PRIM)
        force_n = self._position_tuple(payload.get("force_n") or [0.0, 0.0, 60.0], "force_n")
        position_m = self._position_tuple(payload.get("position_m") or [0.0, 0.0, 0.0], "position_m")
        force_steps = max(1, min(600, int(payload.get("force_steps") or 90)))
        settle_steps = max(0, min(300, int(payload.get("settle_steps") or 15)))
        methods_payload = payload.get("methods")
        if methods_payload is None:
            methods = [
                "dynamic_control_local",
                "dynamic_control_world",
                "vehicle_apply_force",
                "rigid_prim_local",
                "rigid_prim_world",
            ]
        elif isinstance(methods_payload, list | tuple):
            methods = [str(item) for item in methods_payload]
        else:
            raise RuntimeError("methods must be a list of probe method names")
        allowed_methods = {
            "dynamic_control_local",
            "dynamic_control_world",
            "rigid_prim_local",
            "rigid_prim_world",
            "vehicle_apply_force",
        }
        invalid_methods = [method for method in methods if method not in allowed_methods]
        if invalid_methods:
            raise RuntimeError("unsupported force-response probe method(s): " + ", ".join(invalid_methods))

        output_path_text = str(payload.get("output") or "").strip()
        output_path = Path(output_path_text) if output_path_text else None
        stage = omni.usd.get_context().get_stage()
        if stage is None:
            raise RuntimeError("Stage is unavailable for UAV force-response probe")
        root_pose = prim_world_pose_wxyz(stage, root_path)
        body_pose = prim_world_pose_wxyz(stage, body_path)

        def step_world(label: str) -> None:
            try:
                self.app.ugv.apply_cmd_vel(0.0, 0.0)
            except Exception as exc:
                carb.log_warn(f"AirGround UGV stop command skipped during force-response probe {label}: {exc}")
            self.app.step_world(render=AIRGROUND_RENDER)
            self.app.publish_runtime_state(spin_evidence_server=False)

        def snapshot(label: str) -> dict[str, Any]:
            position, orientation = prim_world_pose_wxyz(stage, body_path)
            root_position, root_orientation = prim_world_pose_wxyz(stage, root_path)
            return {
                "body_diagnostics": rigid_body_diagnostic_snapshot(stage, body_path),
                "body_orientation_wxyz": list(orientation),
                "body_position_m": list(position),
                "dynamic_control": dynamic_control_rigid_body_snapshot(body_path, root_path=root_path),
                "label": label,
                "root_orientation_wxyz": list(root_orientation),
                "root_position_m": list(root_position),
                "sim_time_s": float(self.app._simulation_time_s()),
            }

        def reset_probe_pose(method_name: str) -> dict[str, Any]:
            reset_summary: dict[str, Any] = {"method": method_name}
            reset_summary["root_pose_reset"] = {"status": "ok", "prim_path": root_path}
            try:
                set_articulation_root_world_pose(stage, root_path, root_pose[0], root_pose[1])
                reset_summary["root_pose_reset"]["applied"] = True
            except Exception as exc:
                reset_summary["root_pose_reset"] = {
                    "error": f"{type(exc).__name__}: {exc}",
                    "prim_path": root_path,
                    "status": "warning",
                }
            reset_summary["body_pose_reset"] = skip_articulation_child_world_pose_reset(
                stage,
                root_path=root_path,
                child_path=body_path,
                target_position_m=body_pose[0],
                target_orientation_wxyz=body_pose[1],
                label=f"uav_force_response_probe_{method_name}",
            )
            reset_summary["body_velocity_reset"] = zero_rigid_prim_velocities(body_path)
            reset_summary["root_velocity_reset"] = zero_rigid_prim_velocities(root_path)
            for step_index in range(settle_steps):
                step_world(f"{method_name}_settle_{step_index:03d}")
            return reset_summary

        actuator_zero = self.app._zero_uav_actuator_state("uav_force_response_probe")
        callback_refresh = self.app._refresh_uav_physics_callbacks()
        runtime_flags = ensure_rigid_body_runtime_flags(
            stage,
            tuple(f"{UAV_PRIM}{suffix}" for suffix in UAV_RIGID_BODY_PRIM_SUFFIXES),
            label="uav_force_response_probe",
        )
        self.app._suspend_uav_force_application(
            "uav_force_response_probe",
            steps=(force_steps + settle_steps + 5) * max(1, len(methods)),
        )

        results: list[dict[str, Any]] = []
        for method_name in methods:
            method_result: dict[str, Any] = {
                "force_n": list(force_n),
                "force_steps": force_steps,
                "method": method_name,
                "position_m": list(position_m),
                "settle_steps": settle_steps,
            }
            method_result["reset"] = reset_probe_pose(method_name)
            before = snapshot(f"{method_name}_before")
            apply_summaries: list[dict[str, Any]] = []
            for step_index in range(force_steps):
                if method_name == "dynamic_control_local":
                    apply_summary = apply_dynamic_control_probe_force(
                        body_path,
                        root_path=root_path,
                        force_n=force_n,
                        position_m=position_m,
                        is_global=False,
                    )
                elif method_name == "dynamic_control_world":
                    apply_summary = apply_dynamic_control_probe_force(
                        body_path,
                        root_path=root_path,
                        force_n=force_n,
                        position_m=position_m,
                        is_global=True,
                    )
                elif method_name == "rigid_prim_local":
                    apply_summary = apply_rigid_prim_probe_force(
                        body_path,
                        force_n=force_n,
                        position_m=position_m,
                        local_frame=True,
                    )
                elif method_name == "rigid_prim_world":
                    apply_summary = apply_rigid_prim_probe_force(
                        body_path,
                        force_n=force_n,
                        position_m=position_m,
                        local_frame=False,
                    )
                elif method_name == "vehicle_apply_force":
                    vehicle = self.app._uav_vehicle()
                    if vehicle is None:
                        apply_summary = {"applied": False, "backend": "vehicle", "error": "UAV vehicle unavailable"}
                    else:
                        try:
                            vehicle.apply_force(force_n, pos=position_m, body_part=UAV_MAPPING.body_path)
                            apply_summary = {"applied": True, "backend": "vehicle", "body_part": UAV_MAPPING.body_path}
                        except Exception as exc:
                            apply_summary = {"applied": False, "backend": "vehicle", "error": f"{type(exc).__name__}: {exc}"}
                else:  # pragma: no cover - guarded above.
                    raise RuntimeError(f"unsupported force-response probe method: {method_name}")
                if step_index in {0, force_steps - 1}:
                    apply_summaries.append({"step_index": step_index, **apply_summary})
                step_world(f"{method_name}_force_{step_index:03d}")
            after = snapshot(f"{method_name}_after")
            displacement = [
                float(after["body_position_m"][index]) - float(before["body_position_m"][index])
                for index in range(3)
            ]
            method_result.update(
                {
                    "after": after,
                    "apply_summaries": apply_summaries,
                    "before": before,
                    "displacement_m": displacement,
                    "distance_m": math.sqrt(sum(component * component for component in displacement)),
                    "moved": math.sqrt(sum(component * component for component in displacement)) > 0.05,
                }
            )
            results.append(method_result)

        report = {
            "actuator_zero": actuator_zero,
            "body_path": body_path,
            "callback_refresh": callback_refresh,
            "force_n": list(force_n),
            "force_steps": force_steps,
            "initial_body_pose": {"orientation_wxyz": list(body_pose[1]), "position_m": list(body_pose[0])},
            "initial_root_pose": {"orientation_wxyz": list(root_pose[1]), "position_m": list(root_pose[0])},
            "methods": methods,
            "position_m": list(position_m),
            "results": results,
            "root_path": root_path,
            "runtime_flags": runtime_flags,
            "schema_version": "airground-uav-force-response-probe-v1",
            "settle_steps": settle_steps,
            "status": "ok" if any(result.get("moved") for result in results) else "no_motion_detected",
        }
        if output_path is not None:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(
                json.dumps(report, allow_nan=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
        return {"report": report, **({"output": str(output_path)} if output_path is not None else {})}

    def _uav_control_offboard(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        tools_dir = Path(__file__).resolve().parents[1] / "tools"
        tools_text = str(tools_dir)
        if tools_text not in sys.path:
            sys.path.insert(0, tools_text)
        from run_uav_offboard_smoke import OffboardSmokeRunner, SmokeRecorder  # noqa: WPS433

        output_dir = Path(str(payload.get("output_dir") or "/tmp/airground_uav_control"))
        output_dir.mkdir(parents=True, exist_ok=True)
        event_trace = output_dir / str(payload.get("event_trace_filename") or "uav_control_adapter_events.jsonl")
        report_path = output_dir / str(payload.get("report_filename") or "uav_control_adapter_report.json")
        dock_release_status: dict[str, Any] = {"released": False, "policy": "after_arm_ack"}
        attempt_reports: list[dict[str, Any]] = []
        retry_recoveries: list[dict[str, Any]] = []
        final_report: dict[str, Any] | None = None
        final_event_trace = event_trace
        episode_start_reset = payload.get("episode_start_reset")

        def release_after_arm(reason: str) -> None:
            if dock_release_status["released"]:
                return
            if self.app.dock_joint is None:
                dock_release_status.update(
                    {
                        "event": "dock_release_after_arm",
                        "joint_exists_after_release": False,
                        "physical_dock_joint_enabled": False,
                        "reason": reason,
                        "released": True,
                    }
                )
                for _ in range(5):
                    self._step_once_for_uav_control()
                return
            release_status = self.app.dock_joint.release()
            dock_release_status.update(
                {
                    "event": "dock_release_after_arm",
                    "joint_exists_after_release": release_status.exists,
                    "physical_dock_joint_enabled": True,
                    "reason": reason,
                    "released": True,
                }
            )
            for _ in range(5):
                self._step_once_for_uav_control()

        resolved_connection = self._resolve_px4_connection(str(payload.get("connection") or "auto"))
        max_attempts = max(1, min(2, int(payload.get("max_prearm_retry_attempts", 2))))
        for attempt_index in range(1, max_attempts + 1):
            attempt_trace = self._uav_control_attempt_trace_path(event_trace, attempt_index)
            diagnostic_trace_setup = self._configure_uav_control_diagnostics(output_dir, attempt_index)
            recorder = SmokeRecorder(attempt_trace)
            recorder.event(
                {
                    "attempt_index": attempt_index,
                    "event": "uav_control_offboard_attempt_start",
                    "max_attempts": max_attempts,
                }
            )
            recorder.event(
                {
                    "attempt_index": attempt_index,
                    "event": "uav_control_diagnostic_traces_configured",
                    **diagnostic_trace_setup,
                }
            )
            callback_refresh = self.app._refresh_uav_physics_callbacks()
            recorder.event({"attempt_index": attempt_index, "event": "uav_physics_callbacks_refreshed", **callback_refresh})
            before_control_snapshot = self.app._uav_px4_runtime_snapshot(
                f"uav_control_before_attempt_{attempt_index:02d}"
            )

            def release_after_arm_with_record(reason: str) -> None:
                release_after_arm(reason)
                recorder.event(
                    {
                        "attempt_index": attempt_index,
                        "event": "dock_release_after_arm",
                        "joint_exists_after_release": dock_release_status.get("joint_exists_after_release"),
                        "policy": "after_arm_ack",
                        "reason": reason,
                    }
                )

            runner = OffboardSmokeRunner(
                arm_max_attempts=5,
                arm_ready_timeout_s=45.0,
                arm_retry_warmup_s=5.0,
                connection=resolved_connection,
                heartbeat_timeout_s=45.0,
                hover_acceptance_m=0.5,
                hover_max_horizontal_speed_mps=0.3,
                hover_s=float(payload.get("hover_s", 2.0)),
                max_tilt_rad=0.55,
                pre_arm_health_settle_s=10.0,
                pre_arm_health_timeout_s=240.0,
                pre_arm_max_horizontal_speed_mps=0.3,
                pre_arm_max_vertical_speed_mps=0.5,
                pre_arm_stability_timeout_s=20.0,
                pre_arm_warmup_s=20.0,
                recorder=recorder,
                require_pre_arm_attitude=AIRGROUND_UAV_PREARM_STRICT_TELEMETRY,
                require_pre_arm_horizontal_speed=AIRGROUND_UAV_PREARM_STRICT_TELEMETRY,
                target_altitude_m=float(payload.get("target_altitude_m", 1.45)),
                takeoff_timeout_s=float(payload.get("takeoff_timeout_s", 60.0)),
                waypoint_acceptance_m=float(payload.get("waypoint_acceptance_m", 0.75)),
                waypoint_timeout_s=float(payload.get("waypoint_timeout_s", 90.0)),
                waypoint_x_m=float(payload.get("waypoint_x_m", 2.0)),
                waypoint_y_m=float(payload.get("waypoint_y_m", 0.0)),
                waypoint_z_up_m=float(payload.get("waypoint_z_up_m", 0.0)),
                px4_params={
                    str(name): float(value)
                    for name, value in dict(payload.get("px4_params") or {}).items()
                },
                skip_waypoint=bool(payload.get("skip_waypoint", False)),
                step_callback=self._step_once_for_uav_control,
                post_arm_callback=release_after_arm_with_record,
            )
            report = runner.run()
            report["attempt_index"] = attempt_index
            report["diagnostic_trace_setup"] = diagnostic_trace_setup
            report["dock_release_status"] = dict(dock_release_status)
            report["event_trace"] = str(attempt_trace)
            report["uav_px4_runtime_before_control"] = before_control_snapshot
            report["uav_px4_runtime_after_control"] = self.app._uav_px4_runtime_snapshot(
                f"uav_control_after_attempt_{attempt_index:02d}"
            )
            attempt_reports.append(dict(report))
            final_report = dict(report)
            final_event_trace = attempt_trace
            if report.get("status") == "ok":
                break
            failure_reason = self._uav_control_report_failure_reason(report)
            if attempt_index >= max_attempts or not self._is_retryable_uav_control_prearm_failure(
                report,
                dock_release_status=dock_release_status,
            ):
                break
            recovery = self._recover_uav_control_prearm_retry(
                attempt_index=attempt_index + 1,
                reason=failure_reason,
                episode_start_reset=episode_start_reset if isinstance(episode_start_reset, Mapping) else None,
            )
            retry_recoveries.append(recovery)

        if final_report is None:
            raise RuntimeError("UAV-control OFFBOARD attempt did not produce a report")
        final_report["attempt_reports"] = attempt_reports
        final_report["dock_release_status"] = dict(dock_release_status)
        final_report["event_trace"] = str(final_event_trace)
        final_report["retry_recoveries"] = retry_recoveries
        report_path.write_text(
            json.dumps(final_report, allow_nan=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return {
            "dock_release_status": dict(dock_release_status),
            "event_trace": str(final_event_trace),
            "offboard_report": final_report,
            "report": str(report_path),
            "retry_recoveries": retry_recoveries,
        }


class PegasusApp:

    def _trace_dock_settle(self, label: str, index: int = 0) -> None:
        """Multi-task diagnostic: log the live PhysX pose of the UAV chassis and UGV base.

        Only active with more than one task (the single-task flow is unchanged).  It records the
        dynamic-control pose (what PhysX holds) next to the USD pose and whether the dock joint
        prim exists, so a tilted/undocked UAV after a re-dock can be traced to the step it appears.
        """
        if len(TASKS) < 2:
            return
        try:
            stage = omni.usd.get_context().get_stage()
            uav_path = f"{UAV_PRIM}{UAV_MAPPING.body_path}"
            ugv_path = f"{UGV_PRIM}/base_link"

            def _dc_pose(path: str):
                from omni.isaac.dynamic_control import _dynamic_control  # noqa: WPS433

                dc = _dynamic_control.acquire_dynamic_control_interface()
                body = dc.get_rigid_body(path)
                if body == _dynamic_control.INVALID_HANDLE:
                    return None
                pose = dc.get_rigid_body_pose(body)
                return (
                    (float(pose.p.x), float(pose.p.y), float(pose.p.z)),
                    (float(pose.r.w), float(pose.r.x), float(pose.r.y), float(pose.r.z)),
                )

            def _rpy(q):
                w, x, y, z = q
                roll = math.atan2(2 * (w * x + y * z), 1 - 2 * (x * x + y * y))
                pitch = math.asin(max(-1.0, min(1.0, 2 * (w * y - z * x))))
                yaw = math.atan2(2 * (w * z + x * y), 1 - 2 * (y * y + z * z))
                return roll, pitch, yaw

            def _fmt(pose) -> str:
                if pose is None:
                    return "invalid"
                (px, py, pz), q = pose
                r, pi, ya = _rpy(q)
                return f"p=({px:.3f},{py:.3f},{pz:.3f}) rpy=({r:.3f},{pi:.3f},{ya:.3f})"

            usd_uav = prim_world_pose_wxyz(stage, uav_path)
            usd_uav_pose = (tuple(usd_uav[0]), tuple(usd_uav[1]))
            joint = stage.GetPrimAtPath(self.task.dock_joint_path)
            carb.log_warn(
                f"AirGround dock trace task={self.task.task_id} {label}[{index}] "
                f"uav_dc[{_fmt(_dc_pose(uav_path))}] uav_usd[{_fmt(usd_uav_pose)}] "
                f"ugv_dc[{_fmt(_dc_pose(ugv_path))}] "
                f"joint_exists={bool(joint and joint.IsValid())}"
            )
        except Exception as exc:  # diagnostics must never break a reset
            carb.log_warn(f"AirGround dock trace {label}[{index}] failed: {type(exc).__name__}: {exc}")

    def _uav_vehicle(self) -> Any | None:
        try:
            return self.pg.get_vehicle(UAV_PRIM)
        except Exception:
            return None

    def _build_native_vehicle_math(self) -> Any:
        """Build and activate the opt-in fused native vehicle math."""
        tools = str(Path(__file__).resolve().parents[1] / "tools")
        if tools not in sys.path:
            sys.path.insert(0, tools)
        from native_vehicle_math import MathLibrary, NativeVehicleMath, set_stage_timer

        if _STAGE_TIMER is not None:
            set_stage_timer(_STAGE_TIMER)
            from pegasus.simulator.logic.vehicles import multirotor as _multirotor_module  # noqa: WPS433

            _multirotor_module.STAGE_TIMER = _STAGE_TIMER
        runtime = NativeVehicleMath(self, MathLibrary(Path(NATIVE_VEHICLE_MATH_LIBRARY)))
        runtime.activate()
        carb.log_warn(
            "Native vehicle math enabled: "
            f"{NATIVE_VEHICLE_MATH_LIBRARY} (source {runtime.library.manifest['source_sha256'][:12]})"
        )
        return runtime

    def _ensure_native_vehicle_math(self) -> None:
        """Re-assert the opt-in native math after a reset rebuilt the vehicle.

        Activation is per-object, so a reset that replaces the UAV would
        silently drop back to the Python callbacks.  Only runs when the operator
        asked for the native lane.
        """
        runtime = getattr(self, "_native_vehicle_math", None)
        if runtime is None:
            return
        vehicle = self._uav_vehicle()
        if vehicle is None or getattr(vehicle, "_airground_native_math", None) is runtime:
            return
        runtime.close()
        self._native_vehicle_math = self._build_native_vehicle_math()

    def _refresh_uav_physics_callbacks(self) -> dict[str, Any]:
        """Reattach Pegasus multirotor callbacks after Isaac world resets."""
        summary: dict[str, Any] = {"refreshed": [], "vehicle_found": False}
        vehicle = self._uav_vehicle()
        if vehicle is None:
            return summary
        summary["vehicle_found"] = True
        stage_prefix = getattr(vehicle, "_stage_prefix", UAV_PRIM)
        callbacks = {
            f"{stage_prefix}/state": getattr(vehicle, "update_state", None),
            f"{stage_prefix}/update": getattr(vehicle, "update", None),
            f"{stage_prefix}/Sensors": getattr(vehicle, "update_sensors", None),
            f"{stage_prefix}/mav_state": getattr(vehicle, "update_sim_state", None),
        }
        remove_callback = getattr(self.world, "remove_physics_callback", None)
        for callback_name, callback in callbacks.items():
            if not callable(callback):
                continue
            if callable(remove_callback):
                try:
                    remove_callback(callback_name)
                except Exception:
                    pass
            self.world.add_physics_callback(callback_name, callback)
            summary["refreshed"].append(callback_name)
        self._ensure_native_vehicle_math()
        return summary

    def _uav_backends(self) -> list[Any]:
        vehicle = self._uav_vehicle()
        if vehicle is None:
            return []
        backends = getattr(vehicle, "_backends", [])
        if isinstance(backends, list):
            return backends
        return []

    def _reset_uav_sensor_state(self, reason: str) -> dict[str, Any]:
        """Re-prime UAV simulated sensors before PX4 estimator warmup.

        Isaac world resets and direct re-docking can leave sensor wrappers with
        stale update counters or bias caches while the live rigid bodies have
        moved to a new episode start.  Reset only simulator-side sensor state;
        PX4 still receives real Pegasus HIL samples through the normal backend.
        """
        summary: dict[str, Any] = {"reason": reason, "vehicle_found": False, "sensors": []}
        vehicle = self._uav_vehicle()
        if vehicle is None:
            return summary
        summary["vehicle_found"] = True
        state = getattr(vehicle, "_state", None)
        state_linear_velocity = getattr(state, "linear_velocity", None)
        state_position = getattr(state, "position", None)
        zero_velocity = np.zeros(3, dtype=float)
        if state is not None:
            for attr in ("linear_velocity", "linear_body_velocity", "angular_velocity", "linear_acceleration"):
                if hasattr(state, attr):
                    try:
                        setattr(state, attr, zero_velocity.copy())
                        summary[f"state_{attr}_zeroed"] = True
                    except Exception as exc:
                        summary[f"state_{attr}_zero_error"] = f"{type(exc).__name__}: {exc}"
            state_linear_velocity = getattr(state, "linear_velocity", state_linear_velocity)
        for sensor in getattr(vehicle, "_sensors", []) or []:
            sensor_summary: dict[str, Any] = {
                "class": type(sensor).__name__,
                "sensor_type": getattr(sensor, "sensor_type", None),
            }
            for attr, value in (("_first_update", True), ("_total_time", 0.0)):
                try:
                    setattr(sensor, attr, value)
                    sensor_summary[f"{attr}_reset"] = True
                except Exception as exc:
                    sensor_summary[f"{attr}_reset_error"] = f"{type(exc).__name__}: {exc}"
            if hasattr(sensor, "_prev_linear_velocity") and state_linear_velocity is not None:
                try:
                    sensor._prev_linear_velocity = np.asarray(state_linear_velocity, dtype=float).copy()
                    sensor_summary["prev_linear_velocity_reset"] = True
                except Exception as exc:
                    sensor_summary["prev_linear_velocity_reset_error"] = f"{type(exc).__name__}: {exc}"
            if hasattr(sensor, "_z_start"):
                try:
                    sensor._z_start = float(state_position[2]) if state_position is not None else None
                    sensor_summary["z_start_reset"] = True
                except Exception as exc:
                    sensor_summary["z_start_reset_error"] = f"{type(exc).__name__}: {exc}"
            for attr in (
                "_gyroscope_bias",
                "_accelerometer_bias",
                "_random_walk_gps",
                "_noise_gps_pos",
                "_noise_gps_vel",
                "_gps_bias",
                "_bias",
            ):
                value = getattr(sensor, attr, None)
                if value is None:
                    continue
                try:
                    if hasattr(value, "fill"):
                        value.fill(0.0)
                    else:
                        setattr(sensor, attr, np.zeros_like(np.asarray(value, dtype=float)))
                    sensor_summary[f"{attr}_zeroed"] = True
                except Exception as exc:
                    sensor_summary[f"{attr}_zero_error"] = f"{type(exc).__name__}: {exc}"
            reset = getattr(sensor, "reset", None)
            if callable(reset):
                try:
                    reset()
                    sensor_summary["reset_called"] = True
                except Exception as exc:
                    sensor_summary["reset_error"] = f"{type(exc).__name__}: {exc}"
            summary["sensors"].append(sensor_summary)
        return summary

    def _zero_uav_actuator_state(self, reason: str) -> dict[str, Any]:
        """Clear stale PX4 rotor commands before/after episode resets.

        Pegasus' multirotor dynamics asks the first backend for
        ``input_reference()`` every physics tick, even when the PX4 backend has
        been stopped for a reset boundary.  If the previous episode leaves a
        non-zero actuator command in ``_rotor_data.input_reference``, the UAV
        can keep receiving stale thrust during reset/settle steps and enter the
        next arm gate already rolled over.  Clear both backend and thruster
        caches before any reset stepping.
        """
        summary: dict[str, Any] = {"reason": reason, "backends": [], "vehicle_found": False}
        vehicle = self._uav_vehicle()
        if vehicle is None:
            return summary
        summary["vehicle_found"] = True
        for backend in self._uav_backends():
            backend_summary: dict[str, Any] = {"class": type(backend).__name__}
            rotor_data = getattr(backend, "_rotor_data", None)
            zero_input_reference = getattr(rotor_data, "zero_input_reference", None)
            if callable(zero_input_reference):
                try:
                    zero_input_reference()
                    backend_summary["rotor_data_zero_input_reference_called"] = True
                except Exception as exc:
                    backend_summary["rotor_data_zero_input_reference_error"] = f"{type(exc).__name__}: {exc}"
            input_reference = getattr(backend, "_input_reference", None)
            try:
                if hasattr(input_reference, "fill"):
                    input_reference.fill(0.0)
                    backend_summary["backend_input_reference_zeroed"] = True
                elif isinstance(input_reference, list):
                    for index in range(len(input_reference)):
                        input_reference[index] = 0.0
                    backend_summary["backend_input_reference_zeroed"] = True
            except Exception as exc:
                backend_summary["backend_input_reference_zero_error"] = f"{type(exc).__name__}: {exc}"
            for attr, value in (
                ("_armed", False),
                ("_received_actuator", False),
                ("_received_first_actuator", False),
                ("_received_first_hearbeat", False),
                ("_current_utime", 0),
            ):
                try:
                    setattr(backend, attr, value)
                    backend_summary[f"{attr}_reset"] = True
                except Exception:
                    pass
            summary["backends"].append(backend_summary)
        thrusters = getattr(vehicle, "_thrusters", None)
        if thrusters is not None:
            summary["thrusters_zeroed"] = False
            for attr in ("_input_reference", "_velocity", "_force"):
                values = getattr(thrusters, attr, None)
                try:
                    if hasattr(values, "fill"):
                        values.fill(0.0)
                    elif isinstance(values, list):
                        for index in range(len(values)):
                            values[index] = 0.0
                    else:
                        continue
                    summary["thrusters_zeroed"] = True
                except Exception as exc:
                    summary[f"{attr}_zero_error"] = f"{type(exc).__name__}: {exc}"
            try:
                thrusters._rolling_moment = 0.0
                summary["thruster_rolling_moment_zeroed"] = True
            except Exception:
                pass
        return summary

    def _suspend_uav_force_application(self, reason: str, steps: int | None = None) -> dict[str, Any]:
        """Temporarily skip Pegasus multirotor forces after Isaac world reset.

        Isaac 4.5 legacy dynamic_control can leave stale rigid-body handles right
        after ``world.reset()``.  The PX4/backend callbacks still need to run so
        estimator warmup receives HIL samples, but force application should wait
        until the reset boundary has settled.
        """
        requested_steps = AIRGROUND_UAV_RESET_FORCE_SKIP_STEPS if steps is None else int(steps)
        requested_steps = max(0, requested_steps)
        summary: dict[str, Any] = {
            "reason": reason,
            "requested_steps": requested_steps,
            "vehicle_found": False,
        }
        vehicle = self._uav_vehicle()
        if vehicle is None:
            return summary
        summary["vehicle_found"] = True
        previous_steps = int(getattr(vehicle, "_airground_skip_force_steps_remaining", 0) or 0)
        applied_steps = max(previous_steps, requested_steps)
        try:
            setattr(vehicle, "_airground_skip_force_steps_remaining", applied_steps)
            setattr(vehicle, "_airground_skip_force_reason", reason)
            summary.update(
                {
                    "previous_steps_remaining": previous_steps,
                    "applied_steps_remaining": applied_steps,
                    "status": "ok",
                }
            )
        except Exception as exc:
            summary["error"] = f"{type(exc).__name__}: {exc}"
        try:
            vehicle._vehicle_dc_interface = None
            summary["dynamic_control_interface_cleared"] = True
        except Exception:
            pass
        try:
            rigid_cache = getattr(vehicle, "_rigid_prim_cache", None)
            if isinstance(rigid_cache, dict):
                rigid_cache.clear()
                summary["rigid_prim_cache_cleared"] = True
        except Exception:
            pass
        return summary

    def _refresh_uav_body_local_rotation_compensation(self, reason: str) -> dict[str, Any]:
        """Refresh Pegasus attitude compensation after Isaac world resets.

        Pegasus reports PX4 attitude from the UAV body prim and compensates a
        baked-in body local rotation that is sampled during vehicle
        construction.  Repeated ``world.reset()`` calls can leave the live body
        local transform different from that construction-time value; PX4 then
        sees a large roll even when the root pose is visually re-docked.  The
        episode reset must refresh this compensation before PX4 starts again.
        """
        summary: dict[str, Any] = {
            "reason": reason,
            "vehicle_found": False,
            "rotation_available": ScipyRotation is not None,
        }
        vehicle = self._uav_vehicle()
        if vehicle is None:
            return summary
        summary["vehicle_found"] = True
        if ScipyRotation is None:
            summary["error"] = "scipy.spatial.transform.Rotation unavailable"
            return summary
        stage = omni.usd.get_context().get_stage()
        if stage is None:
            summary["error"] = "stage unavailable"
            return summary
        stage_prefix = getattr(vehicle, "_stage_prefix", UAV_PRIM)
        body_path = getattr(vehicle, "_body_path", UAV_MAPPING.body_path)
        body_prim_path = f"{stage_prefix}{body_path}"
        try:
            local_position, local_orientation_wxyz = child_local_pose_wxyz(
                stage,
                str(stage_prefix),
                str(body_prim_path),
            )
            w, x, y, z = local_orientation_wxyz
            vehicle._body_local_rotation_inv = ScipyRotation.from_quat([x, y, z, w]).inv()
            state = getattr(vehicle, "_state", None)
            if state is not None:
                try:
                    vehicle._state = type(state)()
                    summary["state_reset"] = True
                except Exception as exc:
                    summary["state_reset_error"] = f"{type(exc).__name__}: {exc}"
            try:
                vehicle._last_state_position = None
                summary["last_state_position_reset"] = True
            except Exception:
                pass
            try:
                vehicle._last_state_attitude = None
                summary["last_state_attitude_reset"] = True
            except Exception:
                pass
            rigid_cache = getattr(vehicle, "_rigid_prim_cache", None)
            if isinstance(rigid_cache, dict):
                rigid_cache.clear()
                summary["rigid_prim_cache_cleared"] = True
            try:
                vehicle._vehicle_dc_interface = None
                summary["dynamic_control_interface_cleared"] = True
            except Exception:
                pass
            summary.update(
                {
                    "body_local_orientation_wxyz": list(local_orientation_wxyz),
                    "body_local_position_m": list(local_position),
                    "body_prim_path": body_prim_path,
                    "status": "ok",
                }
            )
        except Exception as exc:
            summary["error"] = f"{type(exc).__name__}: {exc}"
        return summary

    def _reset_uav_px4_backend_state(self, reason: str) -> dict[str, Any]:
        """Clear Pegasus/PX4 backend state before a full-mission episode reset."""
        summary: dict[str, Any] = {
            "reason": reason,
            "actuator_zero_before_backend_stop": self._zero_uav_actuator_state(
                f"{reason}_before_backend_stop"
            ),
            "backends": [],
        }
        for backend in self._uav_backends():
            backend_summary: dict[str, Any] = {
                "class": type(backend).__name__,
                "had_connection": bool(getattr(backend, "_connection", None)),
                "had_px4_tool": bool(getattr(backend, "px4_tool", None)),
                "was_running": bool(getattr(backend, "_is_running", False)),
            }
            stop = getattr(backend, "stop", None)
            if callable(stop):
                try:
                    stop()
                    backend_summary["stop_called"] = True
                except Exception as exc:
                    backend_summary["stop_error"] = f"{type(exc).__name__}: {exc}"
            connection = getattr(backend, "_connection", None)
            if connection is not None:
                try:
                    connection.close()
                    backend_summary["connection_closed"] = True
                except Exception as exc:
                    backend_summary["connection_close_error"] = f"{type(exc).__name__}: {exc}"
                try:
                    backend._connection = None
                except Exception:
                    pass
            try:
                backend._is_running = False
            except Exception:
                pass
            try:
                backend.px4_tool = None
            except Exception:
                pass
            summary["backends"].append(backend_summary)
        summary["actuator_zero_after_backend_stop"] = self._zero_uav_actuator_state(
            f"{reason}_after_backend_stop"
        )
        kill_all_px4 = _px4_killer_for_active_task()
        if callable(kill_all_px4):
            try:
                kill_all_px4()
                summary["kill_all_px4_called"] = True
            except Exception as exc:
                summary["kill_all_px4_error"] = f"{type(exc).__name__}: {exc}"
        return summary

    def _restart_uav_px4_backend_state(self, reason: str) -> dict[str, Any]:
        """Restart Pegasus/PX4 backends after a full-mission episode reset.

        ``_reset_uav_px4_backend_state`` intentionally closes the MAVLink
        connection, clears ``px4_tool`` and kills the old PX4 process.  A world
        reset plus callback refresh is not sufficient to reopen that MAVLink
        bridge; PX4 may relaunch independently and emit heartbeats while the
        Pegasus backend remains stopped, which leaves OFFBOARD pre-arm gates
        with zero ATTITUDE/LOCAL_POSITION samples.  Explicitly call backend
        ``start()`` after the vehicle has been re-docked and callbacks are
        refreshed so the next attempt receives real simulated sensor data.
        """
        summary: dict[str, Any] = {"reason": reason, "backends": [], "vehicle_found": False}
        vehicle = self._uav_vehicle()
        if vehicle is None:
            return summary
        summary["vehicle_found"] = True
        for backend in self._uav_backends():
            backend_summary: dict[str, Any] = {
                "class": type(backend).__name__,
                "had_connection_before_start": bool(getattr(backend, "_connection", None)),
                "had_px4_tool_before_start": bool(getattr(backend, "px4_tool", None)),
                "was_running_before_start": bool(getattr(backend, "_is_running", False)),
            }
            stop = getattr(backend, "stop", None)
            if callable(stop):
                try:
                    stop()
                    backend_summary["force_stop_before_start"] = True
                except Exception as exc:
                    backend_summary["force_stop_error"] = f"{type(exc).__name__}: {exc}"
            connection = getattr(backend, "_connection", None)
            if connection is not None:
                try:
                    connection.close()
                    backend_summary["connection_closed_before_start"] = True
                except Exception as exc:
                    backend_summary["connection_close_before_start_error"] = f"{type(exc).__name__}: {exc}"
            kill_all_px4 = _px4_killer_for_active_task()
            if callable(kill_all_px4):
                try:
                    kill_all_px4()
                    backend_summary["kill_all_px4_before_start"] = True
                except Exception as exc:
                    backend_summary["kill_all_px4_before_start_error"] = f"{type(exc).__name__}: {exc}"
            for attr, value in (
                ("_connection", None),
                ("_is_running", False),
                ("px4_tool", None),
                ("_armed", False),
                ("_received_actuator", False),
                ("_received_first_actuator", False),
                ("_received_first_hearbeat", False),
                ("_current_utime", 0),
            ):
                try:
                    setattr(backend, attr, value)
                    backend_summary[f"{attr}_cleared_before_start"] = True
                except Exception:
                    pass
            start = getattr(backend, "start", None)
            if callable(start):
                try:
                    start()
                    backend_summary["start_called"] = True
                except Exception as exc:
                    backend_summary["start_error"] = f"{type(exc).__name__}: {exc}"
            else:
                backend_summary["start_unavailable"] = True
            backend_summary.update(
                {
                    "has_connection_after_start": bool(getattr(backend, "_connection", None)),
                    "has_px4_tool_after_start": bool(getattr(backend, "px4_tool", None)),
                    "is_running_after_start": bool(getattr(backend, "_is_running", False)),
                }
            )
            summary["backends"].append(backend_summary)
        return summary

    def _uav_px4_runtime_snapshot(self, reason: str) -> dict[str, Any]:
        """Return compact UAV/PX4 runtime evidence after reset warmup."""
        summary: dict[str, Any] = {"reason": reason, "vehicle_found": False, "sensors": [], "backends": []}
        vehicle = self._uav_vehicle()
        if vehicle is None:
            return summary
        summary["vehicle_found"] = True
        for attr in (
            "_airground_skip_force_reason",
            "_airground_skip_force_steps_remaining",
            "_aggregate_force_frame_source",
            "_force_on_body_at_rotor_positions",
            "_force_trace_count",
            "_force_trace_path",
            "_force_trace_sample_period",
            "_dynamics_trace_count",
            "_dynamics_trace_path",
            "_dynamics_trace_sample_period",
        ):
            if hasattr(vehicle, attr):
                value = getattr(vehicle, attr)
                if isinstance(value, (str, bool)) or value is None:
                    summary[attr.removeprefix("_")] = value
                else:
                    try:
                        summary[attr.removeprefix("_")] = int(value)
                    except Exception:
                        summary[attr.removeprefix("_")] = str(value)
        thrusters = getattr(vehicle, "_thrusters", None)
        if thrusters is not None:
            summary["thrusters"] = {"class": type(thrusters).__name__}
            for attr in ("_input_reference", "input_reference", "_force", "force", "_velocity", "velocity"):
                value = _compact_float_sequence(getattr(thrusters, attr, None))
                if value is not None:
                    summary["thrusters"][attr.removeprefix("_")] = value
            for attr in ("_num_rotors", "num_rotors"):
                if hasattr(thrusters, attr):
                    try:
                        summary["thrusters"][attr.removeprefix("_")] = int(getattr(thrusters, attr))
                    except Exception:
                        pass
        state = getattr(vehicle, "_state", None)
        if state is not None:
            for attr in ("position", "linear_velocity", "angular_velocity"):
                value = getattr(state, attr, None)
                compact = _compact_float_sequence(value)
                if compact is not None:
                    summary[f"state_{attr}"] = compact
        for sensor in getattr(vehicle, "_sensors", []) or []:
            sensor_summary: dict[str, Any] = {
                "class": type(sensor).__name__,
                "sensor_type": getattr(sensor, "sensor_type", None),
                "first_update": bool(getattr(sensor, "_first_update", False)),
                "total_time_s": float(getattr(sensor, "_total_time", 0.0) or 0.0),
            }
            summary["sensors"].append(sensor_summary)
        for backend in self._uav_backends():
            sensor_data = getattr(backend, "_sensor_data", None)
            backend_summary: dict[str, Any] = {
                "class": type(backend).__name__,
                "has_connection": bool(getattr(backend, "_connection", None)),
                "has_px4_tool": bool(getattr(backend, "px4_tool", None)),
                "is_running": bool(getattr(backend, "_is_running", False)),
                "current_utime": int(getattr(backend, "_current_utime", 0) or 0),
                "received_first_heartbeat": bool(getattr(backend, "_received_first_hearbeat", False)),
            }
            for attr in (
                "_actuator_trace_count",
                "_armed",
                "_num_inputs",
                "_sensor_send_count",
                "_sensor_send_error_count",
                "_gps_send_count",
                "_gps_send_error_count",
                "_groundtruth_send_count",
                "_groundtruth_send_error_count",
                "_last_sensor_fields_updated",
                "_preactuator_gyro_clamp_count",
            ):
                if hasattr(backend, attr):
                    backend_summary[attr.removeprefix("_")] = int(getattr(backend, attr) or 0)
            # MAVLink receive health: the applied actuator command must track the
            # simulator clock (see PX4MavlinkBackend.poll_mavlink_messages).
            diagnostics_reader = getattr(backend, "mavlink_link_diagnostics", None)
            if callable(diagnostics_reader):
                try:
                    backend_summary["mavlink_link"] = diagnostics_reader()
                except Exception as exc:  # pragma: no cover - live diagnostic path.
                    backend_summary["mavlink_link"] = {
                        "status": "failed",
                        "error": f"{type(exc).__name__}: {exc}",
                    }
            config = getattr(backend, "config", None)
            if config is not None:
                actuator_trace_path = getattr(config, "actuator_trace_path", None)
                if actuator_trace_path:
                    backend_summary["actuator_trace_path"] = str(actuator_trace_path)
            for attr in ("_input_reference",):
                value = _compact_float_sequence(getattr(backend, attr, None))
                if value is not None:
                    backend_summary[attr.removeprefix("_")] = value
            rotor_data = getattr(backend, "_rotor_data", None)
            if rotor_data is not None:
                backend_summary["rotor_data"] = {"class": type(rotor_data).__name__}
                for attr in ("input_reference", "_input_reference"):
                    value = _compact_float_sequence(getattr(rotor_data, attr, None))
                    if value is not None:
                        backend_summary["rotor_data"][attr.removeprefix("_")] = value
            if sensor_data is not None:
                backend_summary.update(
                    {
                        "received_first_imu": bool(getattr(sensor_data, "received_first_imu", False)),
                        "new_imu_data": bool(getattr(sensor_data, "new_imu_data", False)),
                        "new_gps_data": bool(getattr(sensor_data, "new_gps_data", False)),
                        "new_sim_state": bool(getattr(sensor_data, "new_sim_state", False)),
                    }
                )
                for attr in (
                    "abs_pressure",
                    "altitude",
                    "eph",
                    "epv",
                    "fix_type",
                    "sim_alt",
                    "sim_lat",
                    "sim_lon",
                    "temperature",
                    "xacc",
                    "xgyro",
                    "xmag",
                    "yacc",
                    "ygyro",
                    "ymag",
                    "zacc",
                    "zgyro",
                    "zmag",
                ):
                    value = getattr(sensor_data, attr, None)
                    if value is not None:
                        try:
                            backend_summary[f"sensor_data_{attr}"] = float(value)
                        except Exception:
                            backend_summary[f"sensor_data_{attr}"] = value
            summary["backends"].append(backend_summary)
        return summary

    def _pump_uav_px4_runtime_once(self, reason: str) -> dict[str, Any]:
        """Explicitly advance UAV state/sensor/backend data after Isaac resets.

        Isaac Sim 6.0.1 world resets can leave the Pegasus physics callback
        chain present but not delivering fresh IMU/GPS/state data soon enough
        for the next PX4 arm gate.  The full-mission UAV-control adapter uses
        this explicit pump only around reset/takeoff control steps; it does not
        apply multirotor dynamics a second time, it only refreshes state,
        sensors, simulated MAVLink state, and backend I/O.
        """
        summary: dict[str, Any] = {"reason": reason, "vehicle_found": False, "steps": []}
        vehicle = self._uav_vehicle()
        if vehicle is None:
            return summary
        summary["vehicle_found"] = True
        try:
            dt = float(self.world.get_physics_dt())
        except Exception:
            dt = 1.0 / 60.0
        native_math = vehicle.__dict__.get("_airground_native_math")
        for name in ("update_state", "update_sensors", "update_sim_state"):
            callback = getattr(vehicle, name, None)
            if name == "update_state" and native_math is not None and hasattr(native_math, "update_state_alone"):
                # A shared vehicle group refreshes this vehicle only (Vehicle.update_state would run a group round).
                callback = native_math.update_state_alone
            step_summary: dict[str, Any] = {"step": name}
            if callable(callback):
                try:
                    callback(dt)
                    step_summary["status"] = "ok"
                except Exception as exc:
                    step_summary["status"] = "failed"
                    step_summary["error"] = f"{type(exc).__name__}: {exc}"
            else:
                step_summary["status"] = "unavailable"
            summary["steps"].append(step_summary)
        for backend in self._uav_backends():
            # A shared PX4 hub exchanges this vehicle alone; ``update`` would step every task's PX4 link.
            update = getattr(backend, "update_alone", None) or getattr(backend, "update", None)
            step_summary = {"step": "backend.update", "class": type(backend).__name__}
            if callable(update):
                try:
                    update(dt)
                    step_summary["status"] = "ok"
                except Exception as exc:
                    step_summary["status"] = "failed"
                    step_summary["error"] = f"{type(exc).__name__}: {exc}"
            else:
                step_summary["status"] = "unavailable"
            summary["steps"].append(step_summary)
        return summary

    def _ensure_ground_support_plane(self, stage, reason: str) -> dict[str, Any]:
        summary: dict[str, Any] = {
            "enabled": bool(AIRGROUND_ENABLE_GROUND_SUPPORT_PLANE),
            "reason": reason,
            "status": "disabled",
        }
        if not AIRGROUND_ENABLE_GROUND_SUPPORT_PLANE:
            return summary
        try:
            summary.update(
                add_ground_support_plane(
                    stage,
                    center_x_m=AIRGROUND_GROUND_SUPPORT_CENTER_X_M,
                    center_y_m=AIRGROUND_GROUND_SUPPORT_CENTER_Y_M,
                    size_x_m=AIRGROUND_GROUND_SUPPORT_SIZE_X_M,
                    size_y_m=AIRGROUND_GROUND_SUPPORT_SIZE_Y_M,
                    top_z_m=AIRGROUND_GROUND_SUPPORT_TOP_Z_M,
                    thickness_m=AIRGROUND_GROUND_SUPPORT_THICKNESS_M,
                    contact_offset_m=AIRGROUND_GROUND_SUPPORT_CONTACT_OFFSET_M,
                    rest_offset_m=AIRGROUND_GROUND_SUPPORT_REST_OFFSET_M,
                )
            )
            prim_path = str(summary.get("prim_path") or "/World/AirGroundGroundSupportPlane")
            prim = stage.GetPrimAtPath(prim_path)
            summary["prim_valid_after_create"] = bool(prim.IsValid())
            summary["has_collision_api_after_create"] = bool(
                prim.IsValid() and prim.HasAPI(UsdPhysics.CollisionAPI)
            )
            if prim.IsValid() and prim.HasAPI(UsdPhysics.CollisionAPI):
                summary["collision_enabled_after_create"] = bool(
                    UsdPhysics.CollisionAPI(prim).GetCollisionEnabledAttr().Get()
                )
            if prim.IsValid():
                summary["visibility_after_create"] = str(UsdGeom.Imageable(prim).ComputeVisibility())
            summary["status"] = "ok"
            carb.log_warn(f"AirGround ground support plane ensured: {summary}")
        except Exception as exc:  # pragma: no cover - live Isaac diagnostic path.
            summary["status"] = "failed"
            summary["error"] = f"{type(exc).__name__}: {exc}"
            summary["traceback"] = traceback.format_exc()
            carb.log_error(f"AirGround ground support plane ensure failed: {summary['error']}\n{summary['traceback']}")
        return summary

    def __init__(
        self,
        *,
        host: "PegasusApp | None" = None,
        defer_reset: bool = False,
        task: Any = None,
    ) -> None:
        """Build one task (UAV + UGV) and, for the first task, the shared world.

        With no ``host`` this creates the world and the environment (the original
        single-task flow).  Additional tasks of a multi-task run pass the first
        app as ``host`` and ``defer_reset=True`` on every task, then call
        ``reset_host_world()`` once and ``finish_task()`` on each app.
        """
        self.host = host if host is not None else self
        self.task = task if task is not None else TASKS[0]
        self.task_apps = [self] if host is None else host.task_apps
        if host is not None:
            host.task_apps.append(self)
        self.activate_task()
        if host is None:
            self._init_host()
        else:
            self._adopt_host(host)
        self._spawn_task()
        if not defer_reset:
            self.reset_host_world()
            self.finish_task()

    def activate_task(self) -> None:
        """Make this app's task the active one (module globals + ROS domain)."""
        self.task.activate(globals())
        from pegasus.simulator.logic import ros_context  # noqa: WPS433

        ros_context.set_active_domain(self.task.ros_domain_id if len(TASKS) > 1 else None)

    def _adopt_host(self, host: "PegasusApp") -> None:
        for name in (
            "timeline",
            "pg",
            "world",
            "ground_support_launch_summary",
            "default_stage_env_hide_summary",
            "rtx_tonemap_settings_summary",
        ):
            setattr(self, name, getattr(host, name))
        self.ugv_proximity_cloud_publisher = None
        self.wheel_contact_offsets_summary = None
        self.ugv_solver_iterations_summary = None
        self.ugv_wheel_traction_summary = None

    def _init_host(self) -> None:
        _trace_startup("before_pegasus_app")
        self.timeline = omni.timeline.get_timeline_interface()
        self.ugv_proximity_cloud_publisher = None
        self.ground_support_launch_summary: dict[str, Any] | None = None
        self.wheel_contact_offsets_summary: dict[str, Any] | None = None
        self.ugv_solver_iterations_summary: dict[str, Any] | None = None
        self.ugv_wheel_traction_summary: dict[str, Any] | None = None
        self.default_stage_env_hide_summary: dict[str, Any] | None = None

        # Pin the onboard camera exposure before any render product exists: the
        # Kit default (f/5) clips the sunlit scene in the mission app.
        self.rtx_tonemap_settings_summary = self._apply_rtx_tonemap_settings()

        omni.client.initialize()

        self.pg = PegasusInterface()
        _trace_startup("after_pegasus_interface")
        world_settings = dict(self.pg._world_settings)
        physics_device = os.environ.get("AIRGROUND_PHYSICS_DEVICE", "").strip()
        if physics_device:
            if physics_device not in {"cpu", "cuda:0"}:
                raise ValueError("AIRGROUND_PHYSICS_DEVICE must be cpu or cuda:0")
            world_settings["device"] = physics_device
        self.pg._world = World(**world_settings)
        self.world = self.pg.world
        if _STAGE_TIMER is not None:
            _instrument_physics_callbacks(self.world)
            _instrument_state_samplers()
            _instrument_tensor_velocity_reads()
            _instrument_update_events()
        physics_threads = os.environ.get("AIRGROUND_PHYSX_THREADS", "").strip()
        if physics_threads:
            count = int(physics_threads)
            if count < 0:
                raise ValueError("AIRGROUND_PHYSX_THREADS must be nonnegative")
            carb.settings.get_settings().set_int("/persistent/physics/numThreads", count)
        if physics_device == "cuda:0":
            # Existing dynamic_control/ROS adapters consume CPU state. Preserve
            # their readback semantics during this GPU dynamics comparison.
            self.world.get_physics_context().enable_fabric(False)
            carb.settings.get_settings().set_bool("/physics/suppressReadback", False)

        self.timeline.stop()

        self.pg.load_environment(ENV_URL)
        _trace_startup("after_load_environment")

        stage = omni.usd.get_context().get_stage()
        if stage is None:
            raise RuntimeError("Stage failed to load")

        if not wait_for_stage(stage):
            carb.log_warn("Stage load timed out — continuing anyway.")
        
        dedupe_physics_scenes(stage)
        reference_root_prims_under_world(stage, ENV_URL)
        _trace_startup("after_reference_stage")
        self.default_stage_env_hide_summary = self._hide_default_stage_environment(stage)

        stage_prim = stage.GetPrimAtPath("/World/stage")
        if stage_prim.IsValid():
            instance_profiles = None
            self.instance_collision_launch_summary = None
            instance_manifest = os.environ.get("AIRGROUND_INSTANCE_COLLIDER_MANIFEST", "").strip()
            if instance_manifest:
                if AIRGROUND_SCENE_COLLIDER_MODE != "profiled":
                    raise ValueError("Instance collision manifests require the profiled scene collider mode")
                from scene_instance_colliders import prepare_static_instance_colliders
                prepared_instances = prepare_static_instance_colliders(
                    stage, manifest_path=Path(instance_manifest).resolve(strict=True),
                    asset_path=Path(ENV_URL).resolve(strict=True), reference_root="/World/stage",
                )
                instance_profiles = prepared_instances.pop("profile_overrides")
                self.instance_collision_launch_summary = prepared_instances
                carb.log_warn(f"Explicit instance collision preparation: {prepared_instances}")
            if AIRGROUND_SCENE_COLLIDER_MODE == "none":
                carb.log_warn("AirGround scene collider mode: none")
            elif AIRGROUND_SCENE_COLLIDER_MODE == "ground_only":
                carb.log_warn("AirGround scene collider mode: ground_only")
                add_profiled_colliders(
                    stage_prim,
                    enabled_profiles={"ground"},
                    disable_other_colliders=True,
                )
            elif AIRGROUND_SCENE_COLLIDER_MODE == "proxy":
                carb.log_warn(
                    "AirGround scene collider mode: proxy "
                    "(diagnostic; static mesh colliders replaced by conservative boxes)"
                )
                add_profiled_colliders(
                    stage_prim,
                    enabled_profiles={"ground"},
                    disable_other_colliders=True,
                )
                add_static_obstacle_box_proxies(stage, stage_prim)
            else:
                carb.log_warn("AirGround scene collider mode: profiled")
                if instance_profiles:
                    add_profiled_colliders(stage_prim, profile_overrides=instance_profiles)
                else:
                    add_profiled_colliders(stage_prim)
            from dataclasses import replace
            from scene_physics_profile import DEFAULT_AIRGROUND_PHYSICS_PROFILE
            profile = DEFAULT_AIRGROUND_PHYSICS_PROFILE
            if physics_device == "cuda:0":
                profile = replace(profile, enable_gpu_dynamics=True, broadphase_type="GPU")
            if instance_profiles:
                configure_airground_physics_profile(stage, root_prim_path="/World/stage", profile=profile,
                                                   profile_overrides=instance_profiles)
            else:
                configure_airground_physics_profile(stage, root_prim_path="/World/stage", profile=profile)
            self.ground_support_launch_summary = self._ensure_ground_support_plane(
                stage,
                "launch_after_physics_profile",
            )
            _trace_startup("after_colliders_before_kit_updates")
            for update_index in range(10):
                _trace_startup("before_scene_kit_update", update_index=update_index)
                omni.kit.app.get_app().update()
                _trace_startup("after_scene_kit_update", update_index=update_index)
            _trace_startup("after_colliders_and_kit_updates")
        else:
            carb.log_warn("/World/stage not found — skipping scale and collision.")

    def _spawn_task(self) -> None:
        stage = omni.usd.get_context().get_stage()
        # Isaac 4.5's WheeledRobot/SingleArticulation wrapper can create a
        # broad PhysX tensor view for Jackal and log a getVelocities shape
        # error every physics step.  Use the narrower USD-backed adapter on
        # 4.5 so Nav2 still drives the real wheel DOFs without registering a
        # scene object that destabilizes the main loop.
        jackal_cls = (
            JackalDirectJointVelocityRobot
            if AIRGROUND_USE_DIRECT_JACKAL_ADAPTER
            else JackalWheeledRobot
        )
        self.ugv = jackal_cls(
            prim_path=UGV_PRIM,
            name=f"{UGV_ROBOT_NAME}{self.task.suffix}",
            usd_path=UGV_USD,
            position=np.array([UGV_X, UGV_Y, UGV_Z]),
            orientation=UGV_ORIENTATION_WXYZ,
            config=JackalDriveConfig(
                wheel_velocity_scale=UGV_WHEEL_VELOCITY_SCALE,
                angular_velocity_scale=AIRGROUND_UGV_CMD_VEL_ANGULAR_GAIN,
                max_angular_radps=AIRGROUND_UGV_CMD_VEL_MAX_ANGULAR_RADPS,
            ),
        )
        self.ugv_cmd_vel_shaping_summary = {
            "angular_velocity_scale": AIRGROUND_UGV_CMD_VEL_ANGULAR_GAIN,
            "max_angular_radps": AIRGROUND_UGV_CMD_VEL_MAX_ANGULAR_RADPS,
            "measured_yaw_gain_before_shaping": 0.40,
            "note": (
                "cmd_vel.angular.z is scaled and clamped before the differential "
                "split so Nav2's command-equals-execution assumption matches the "
                "measured 0.40 in-place yaw gain of this skid-steer"
            ),
            "status": "ok",
        }
        carb.log_warn(
            "AirGround UGV cmd_vel shaping: "
            f"angular_gain={AIRGROUND_UGV_CMD_VEL_ANGULAR_GAIN} "
            f"max_angular_radps={AIRGROUND_UGV_CMD_VEL_MAX_ANGULAR_RADPS} "
            f"wheel_velocity_scale={UGV_WHEEL_VELOCITY_SCALE}"
        )
        for _ in range(10):
            omni.kit.app.get_app().update()
        _trace_startup("after_ugv_and_kit_updates")
        ensure_articulation_root(stage, UGV_PRIM, "UGV")
        # 2026-09-21: pin the wheel side of the wheel/ground contact pair before
        # the first physics step; see ``apply_wheel_contact_offsets``.
        self.wheel_contact_offsets_summary = apply_wheel_contact_offsets(
            stage,
            robot_prim_path=UGV_PRIM,
            contact_offset_m=AIRGROUND_WHEEL_CONTACT_OFFSET_M,
            rest_offset_m=AIRGROUND_WHEEL_REST_OFFSET_M,
        )
        carb.log_warn(
            "AirGround UGV wheel contact offsets: "
            f"contact_offset_m={AIRGROUND_WHEEL_CONTACT_OFFSET_M} "
            f"rest_offset_m={AIRGROUND_WHEEL_REST_OFFSET_M} "
            f"collider_count={self.wheel_contact_offsets_summary.get('collider_count')} "
            f"status={self.wheel_contact_offsets_summary.get('status')}"
        )
        self.ugv_solver_iterations_summary = apply_ugv_solver_iterations(
            stage,
            articulation_prim_path=UGV_PRIM,
            position_iterations=AIRGROUND_UGV_SOLVER_POSITION_ITERATIONS,
            velocity_iterations=AIRGROUND_UGV_SOLVER_VELOCITY_ITERATIONS,
        )
        carb.log_warn(
            "AirGround UGV solver iterations: "
            f"requested={self.ugv_solver_iterations_summary.get('requested')} "
            f"applied={self.ugv_solver_iterations_summary.get('applied')} "
            f"status={self.ugv_solver_iterations_summary.get('status')}"
        )
        self.ugv_wheel_traction_summary = apply_ugv_wheel_traction(
            stage,
            robot_prim_path=UGV_PRIM,
            material_paths=(
                f"{UGV_PRIM}/PhysicsMaterials/wheels",
                "/World/PhysicsMaterials/airground_ground_contact",
            ),
            static_friction=AIRGROUND_UGV_WHEEL_STATIC_FRICTION,
            dynamic_friction=AIRGROUND_UGV_WHEEL_DYNAMIC_FRICTION,
            friction_combine_mode=AIRGROUND_UGV_WHEEL_FRICTION_COMBINE_MODE,
            max_torque_nm=AIRGROUND_UGV_WHEEL_MAX_TORQUE_NM,
        )
        carb.log_warn(
            "AirGround UGV wheel traction: "
            f"materials={self.ugv_wheel_traction_summary.get('materials')} "
            f"max_torque_nm={AIRGROUND_UGV_WHEEL_MAX_TORQUE_NM} "
            f"joints={[entry.get('max_force_after') for entry in self.ugv_wheel_traction_summary.get('wheel_joints', [])]} "
            f"status={self.ugv_wheel_traction_summary.get('status')}"
        )
        if AIRGROUND_USE_DIRECT_JACKAL_ADAPTER:
            carb.log_warn("AirGround UGV using direct dynamic-control Jackal adapter")
        else:
            # Register Jackal with the Isaac World so its articulation view is
            # initialized during world.reset() and wheel velocity actions affect
            # the real PhysX articulation.
            self.ugv = self.world.scene.add(self.ugv)

        ensure_pegasus_ogn_nodes_registered()
        configure_px4_hub_link(len(TASKS))

        # The OmniGraph /clock publisher of this task's PX4 graph (AIRGROUND_SINGLE_CLOCK_PUBLISHER).
        self.og_clock_tick_attrs = (
            f"{UAV_PRIM}/PX4MultirotorGraph/{UAV_ROBOT_NAME}_PlaybackTick.outputs:tick",
            f"{UAV_PRIM}/PX4MultirotorGraph/{UAV_ROBOT_NAME}_ROS2PublishClock.inputs:execIn",
        )
        graph_handle = spawn_px4_multirotor_node(
            pegasus_node_name="PX4Multirotor",
            drone_prim=UAV_PRIM,
            robot_name=UAV_ROBOT_NAME,
            vehicle_id=UAV_VEHICLE_ID,
            domain_id=UAV_DOMAIN_ID,
            usd_file=DRONE_USD,
            init_pos=[DRONE_X, DRONE_Y, DRONE_Z],
            init_orient=[DRONE_QX, DRONE_QY, DRONE_QZ, DRONE_QW],
            px4_autolaunch=UAV_PX4_AUTOLAUNCH,
            px4_vehicle_model=UAV_PX4_MODEL,
            enable_lockstep=UAV_PX4_ENABLE_LOCKSTEP,
            prim_paths=UAV_MAPPING,
        )
        for _ in range(10):
            omni.kit.app.get_app().update()
        self.uav_rigid_body_runtime_flags = ensure_rigid_body_runtime_flags(
            stage,
            tuple(f"{UAV_PRIM}{suffix}" for suffix in UAV_RIGID_BODY_PRIM_SUFFIXES),
            label="launch_after_uav_spawn",
        )
        carb.log_warn(
            "AirGround UAV rigid-body runtime flags enforced: "
            f"{self.uav_rigid_body_runtime_flags}"
        )

        self.rgbd_camera_surfaces: list[RgbdCameraSurfaceConfig] = []
        self.legacy_camera_surfaces: list[Mapping[str, Any]] = []
        self.replicator_camera_surfaces: list[Mapping[str, Any]] = []

        if ENABLE_UAV_RGBD_SENSOR_GRAPH:
            uav_rgbd_surface = add_zed_stereo_camera_subgraph(
                parent_graph_handle=graph_handle,
                drone_prim=UAV_PRIM,
                robot_name=UAV_ROBOT_NAME,
                camera_name="ZEDCamera",
                camera_usd=ZED_USD,
                camera_offset=[0.2, 0.0, -0.05],
                camera_rotation_offset=[0.0, 0.0, 0.0],
                frame_width=UAV_CAMERA_WIDTH,
                frame_height=UAV_CAMERA_HEIGHT,
                rigid_body_prim_path=UAV_PRIM + UAV_MAPPING.sensor_mount_body_path,
            )
            self.rgbd_camera_surfaces.extend(_rgbd_surface_configs(uav_rgbd_surface))
            if isinstance(uav_rgbd_surface, Mapping) and uav_rgbd_surface.get("mode") == "replicator":
                self.replicator_camera_surfaces.append(uav_rgbd_surface)
            if (
                isinstance(uav_rgbd_surface, Mapping)
                and uav_rgbd_surface.get("mode") == "legacy_omnigraph"
                and uav_rgbd_surface.get("legacy_graph_attach_timing") == "post_reset"
            ):
                self.legacy_camera_surfaces.append(uav_rgbd_surface)
        elif ENABLE_UAV_SENSOR_GRAPHS:
            carb.log_warn("AirGround UAV RGB-D sensor graph disabled by AIRGROUND_ENABLE_UAV_RGBD_SENSOR_GRAPH=false")

        if ENABLE_UAV_LIDAR_SENSOR_GRAPH:
            add_ouster_lidar_subgraph(
                parent_graph_handle=graph_handle,
                drone_prim=UAV_PRIM,
                robot_name=UAV_ROBOT_NAME,
                lidar_name="OS1_REV6_128_10hz___512_resolution",
                lidar_usd=OUSTER_USD,
                lidar_offset=[0.0, 0.0, 0.025],
                lidar_rotation_offset=[0.0, 0.0, 0.0],
                lidar_min_range=3.5,
                rigid_body_prim_path=UAV_PRIM + UAV_MAPPING.sensor_mount_body_path,
            )
        elif ENABLE_UAV_SENSOR_GRAPHS:
            carb.log_warn("AirGround UAV LiDAR sensor graph disabled by AIRGROUND_ENABLE_UAV_LIDAR_SENSOR_GRAPH=false")
        elif ENABLE_SENSOR_GRAPHS:
            carb.log_warn("AirGround UAV sensor graphs disabled by AIRGROUND_ENABLE_UAV_SENSOR_GRAPHS=false")

        if ENABLE_UGV_RGBD_SENSOR_GRAPH:
            ugv_rgbd_surface = add_zed_stereo_camera_subgraph(
                parent_graph_handle=graph_handle,
                drone_prim=UGV_PRIM,
                robot_name=UGV_ROBOT_NAME,
                camera_name="UGVZEDCamera",
                camera_usd=ZED_USD,
                camera_offset=[0.34, 0.0, 0.28],
                camera_rotation_offset=[0.0, 0.0, 0.0],
                left_frame_id="ugv_camera_left",
                right_frame_id="ugv_camera_right",
                ros2_context_node=f"{UAV_ROBOT_NAME}_ROS2Context",
                rigid_body_prim_path=UGV_SENSOR_BODY_PATH,
            )
            self.rgbd_camera_surfaces.extend(_rgbd_surface_configs(ugv_rgbd_surface))
            if isinstance(ugv_rgbd_surface, Mapping) and ugv_rgbd_surface.get("mode") == "replicator":
                self.replicator_camera_surfaces.append(ugv_rgbd_surface)
            if (
                isinstance(ugv_rgbd_surface, Mapping)
                and ugv_rgbd_surface.get("mode") == "legacy_omnigraph"
                and ugv_rgbd_surface.get("legacy_graph_attach_timing") == "post_reset"
            ):
                self.legacy_camera_surfaces.append(ugv_rgbd_surface)
        elif ENABLE_UGV_SENSOR_GRAPHS:
            carb.log_warn("AirGround UGV RGB-D sensor graph disabled by AIRGROUND_ENABLE_UGV_RGBD_SENSOR_GRAPH=false")

        if ENABLE_UGV_LIDAR_SENSOR_GRAPH:
            if UGV_LIDAR_SOURCE == "physx_raycast":
                # Isaac Sim 4.5's RTX LiDAR Replicator writer publishes empty
                # clouds, so the same topic/frame is served by the CPU PhysX
                # elevation fan instead of the RTX sensor graph.
                self.ugv_proximity_cloud_publisher = JackalProximityCloudPublisher(
                    _shared_gpu_cloud() if UGV_CLOUD_BACKEND == "gpu" else _airground_lazy_physx_segment_raycast_fn(),
                    JackalProximityCloudConfig(
                        namespace=UGV_ROBOT_NAME,
                        frame_id=UGV_LIDAR_FRAME_ID,
                        mount_offset_m=UGV_LIDAR_MOUNT_OFFSET_M,
                        frame_yaw_rad=UGV_LIDAR_FRAME_YAW_RAD,
                        ray_count=UGV_CLOUD_RAY_COUNT,
                        elevation_deg=UGV_CLOUD_ELEVATION_DEG,
                        max_range_m=UGV_CLOUD_MAX_RANGE_M,
                        min_range_m=UGV_CLOUD_MIN_RANGE_M,
                        publish_period_s=UGV_CLOUD_PERIOD_S,
                        ignored_prim_prefixes=ROBOT_IGNORED_PRIM_PREFIXES,
                    ),
                )
                carb.log_warn(
                    f"UGV 3D obstacle cloud source: physx_raycast/{UGV_CLOUD_BACKEND} "
                    f"(topic /{UGV_ROBOT_NAME}/sensors/ouster/point_cloud, frame {UGV_LIDAR_FRAME_ID}, "
                    f"{len(UGV_CLOUD_ELEVATION_DEG)} elevations x {UGV_CLOUD_RAY_COUNT} rays, "
                    f"{UGV_CLOUD_MAX_RANGE_M:.1f}m, {1.0 / UGV_CLOUD_PERIOD_S:.1f}Hz). "
                    "The RTX LiDAR Replicator writer publishes empty clouds on Isaac 4.5."
                )
            else:
                self.ugv_lidar_sensor_prim_path = add_ouster_lidar_subgraph(
                    parent_graph_handle=graph_handle,
                    drone_prim=UGV_PRIM,
                    robot_name=UGV_ROBOT_NAME,
                    lidar_name="OS1_REV6_128_10hz___512_resolution",
                    lidar_topic_namespace="sensors/ouster",
                    lidar_topic_name="point_cloud",
                    lidar_usd=OUSTER_USD,
                    lidar_offset=list(UGV_LIDAR_MOUNT_OFFSET_M),
                    lidar_rotation_offset=[0.0, 0.0, 0.0],
                    lidar_min_range=0.75,
                    lidar_frame_id=UGV_LIDAR_FRAME_ID,
                    ros2_context_node=f"{UAV_ROBOT_NAME}_ROS2Context",
                    rigid_body_prim_path=UGV_SENSOR_BODY_PATH,
                )
                carb.log_warn(
                    "UGV Ouster OS1 3D lidar enabled: "
                    f"/{UGV_ROBOT_NAME}/sensors/ouster/point_cloud "
                    f"(frame {UGV_LIDAR_FRAME_ID}, mount z+0.42m, min_range 0.75m)"
                )
        elif ENABLE_UGV_SENSOR_GRAPHS:
            carb.log_warn("AirGround UGV LiDAR sensor graph disabled by AIRGROUND_ENABLE_UGV_LIDAR_SENSOR_GRAPH=false")
        elif ENABLE_SENSOR_GRAPHS:
            carb.log_warn("AirGround UGV sensor graphs disabled by AIRGROUND_ENABLE_UGV_SENSOR_GRAPHS=false")

        if not ENABLE_SENSOR_GRAPHS:
            carb.log_warn("AirGround sensor graphs disabled by AIRGROUND_ENABLE_SENSOR_GRAPHS=false")

    def reset_host_world(self) -> None:
        """Reset the shared world once every task has been spawned."""
        stage = omni.usd.get_context().get_stage()
        from task_isolation import (  # noqa: WPS433
            apply_collision_groups,
            make_invisible_to_sensors,
            plan_collision_groups,
            sensor_invisibility_paths,
        )

        robot_roots = [[task.values["UAV_PRIM"], task.values["UGV_PRIM"]] for task in TASKS]
        applied_groups = apply_collision_groups(stage, plan_collision_groups(robot_roots))
        if applied_groups:
            carb.log_warn(f"AirGround per-task collision groups applied: {applied_groups}")
        if AIRGROUND_ROBOTS_INVISIBLE_TO_SENSORS:
            hidden = make_invisible_to_sensors(
                stage,
                sensor_invisibility_paths(
                    [path for roots in robot_roots for path in roots],
                    lambda path: stage.GetPrimAtPath(path).IsValid(),
                ),
            )
            carb.log_warn(f"AirGround robots hidden from RTX sensors: {hidden}")
        for _ in range(30):
            omni.kit.app.get_app().update()

        carb.log_warn("AirGround world.reset starting")
        _trace_startup("before_world_reset")
        self.world.reset()
        _trace_startup("after_world_reset")
        carb.log_warn("AirGround world.reset complete")
        if AIRGROUND_DUMP_RTX_EXPOSURE_SETTINGS:
            self._dump_rtx_exposure_settings()
        callback_refresh = self._refresh_uav_physics_callbacks()
        carb.log_warn(f"AirGround UAV physics callbacks refreshed: {callback_refresh}")
        # Every task's canonical body pose is taken here, before any task's finish_task steps the
        # shared world (see _capture_uav_body_canonical_local_pose).
        for task_app in getattr(self, "task_apps", None) or [self]:
            task_app.activate_task()
            task_app._capture_uav_body_canonical_local_pose()
        self.activate_task()

    def _capture_uav_body_canonical_local_pose(self) -> None:
        """Record the UAV chassis pose relative to its root prim (this task must be active).

        The re-dock restores this local pose and derives the root pose from it, and the
        articulation teleport then places the *chassis* at that root pose.  It is therefore only
        correct when taken straight after ``world.reset()``, before the world steps: a free UAV
        falls onto the platform within a few steps, and a pose captured afterwards carries the
        fall (measured 14.5 cm for the second task of a shared world, which then re-docked the
        chassis that far above the platform and let the dock joint pull it into a 36 degree tilt).
        """
        stage = omni.usd.get_context().get_stage()
        self.uav_body_canonical_local_pose = None
        try:
            self.uav_body_canonical_local_pose = child_local_pose_wxyz(
                stage,
                UAV_PRIM,
                f"{UAV_PRIM}{UAV_MAPPING.body_path}",
            )
            carb.log_warn(
                "AirGround UAV canonical body local pose captured: "
                f"position={self.uav_body_canonical_local_pose[0]}, "
                f"orientation_wxyz={self.uav_body_canonical_local_pose[1]}"
            )
        except Exception as exc:
            carb.log_error(f"AirGround UAV canonical body local pose capture failed: {exc}")

    def _align_and_dock(self, stage: Any, *, settle_updates: bool) -> None:
        """Startup dock: align this task's UAV on its UGV and create the dock joint.

        ``settle_updates=False`` (AIRGROUND_DOCK_ALL_BEFORE_STEP) skips the Kit updates in between, so
        every task can be docked before the shared world advances (SimMT-2d diagnosis).
        """
        # Isaac Sim 6.0.1 / PhysX can fail to create the Jackal articulation
        # view if a fixed joint already connects the UGV and UAV articulations
        # before world.reset().  Create the dock joint after articulation
        # initialization but before the timeline starts so the UAV is still
        # physically docked for the run.
        self.dock_joint = None
        self.soft_dock_hold_active = False
        self.soft_dock_hold_pose = None
        self.soft_dock_hold_correction_count = 0
        self.soft_dock_hold_settle_remaining = 0
        self.soft_dock_hold_latched = False
        dock_config = AirGroundDockJointConfig(
            break_force_n=float(DOCK_BREAK_FORCE_N),
            break_torque_nm=float(DOCK_BREAK_TORQUE_NM),
            joint_path=self.task.dock_joint_path,
            ugv_body_path=f"{UGV_PRIM}/base_link",
            uav_body_path=f"{UAV_PRIM}{UAV_MAPPING.body_path}",
        )
        if ALIGN_UAV_TO_DOCK:
            try:
                ugv_position, ugv_orientation_wxyz = prim_world_pose_wxyz(
                    stage,
                    dock_config.ugv_body_path,
                )
                if self.uav_body_canonical_local_pose is not None:
                    uav_body_local_pos, uav_body_local_orientation_wxyz = self.uav_body_canonical_local_pose
                    set_local_prim_pose(
                        stage,
                        f"{UAV_PRIM}{UAV_MAPPING.body_path}",
                        uav_body_local_pos,
                        uav_body_local_orientation_wxyz,
                    )
                else:
                    uav_body_local_pos, uav_body_local_orientation_wxyz = child_local_pose_wxyz(
                        stage,
                        UAV_PRIM,
                        f"{UAV_PRIM}{UAV_MAPPING.body_path}",
                    )
                # ``DRONE_Q*`` is populated from the episode manifest before
                # Isaac starts.  Preserve that world orientation when the
                # startup dock alignment recomputes the root pose; otherwise
                # the platform yaw is silently replaced by the UGV yaw before
                # the mission runner gets a chance to reset the episode.
                initial_uav_orientation_wxyz = (
                    float(DRONE_QW),
                    float(DRONE_QX),
                    float(DRONE_QY),
                    float(DRONE_QZ),
                )
                dock_root_position, dock_orientation_wxyz = docked_uav_root_world_pose(
                    tuple(float(value) for value in ugv_position),
                    tuple(float(value) for value in ugv_orientation_wxyz),
                    uav_body_local_pos,
                    dock_config,
                    clearance_m=(0.0 if CREATE_DOCK_JOINT else SOFT_DOCK_CLEARANCE_M),
                    uav_orientation_wxyz=initial_uav_orientation_wxyz,
                )
                self.soft_dock_hold_pose = (
                    (
                        tuple(float(value) for value in dock_root_position),
                        tuple(float(value) for value in dock_orientation_wxyz),
                    ),
                    None,
                )
                self.soft_dock_hold_active = bool(
                    SOFT_DOCK_HOLD_ENABLED and not CREATE_DOCK_JOINT
                )
                self.soft_dock_hold_settle_remaining = SOFT_DOCK_HOLD_SETTLE_STEPS
                self.soft_dock_hold_latched = False
                set_articulation_root_world_pose(
                    stage,
                    UAV_PRIM,
                    dock_root_position,
                    dock_orientation_wxyz,
                )
                for _ in range(5 if settle_updates else 0):
                    omni.kit.app.get_app().update()
                carb.log_warn(
                    "AirGround UAV aligned to post-reset UGV dock pose: "
                    f"root_position={dock_root_position}, "
                    f"soft_dock_clearance_m={0.0 if CREATE_DOCK_JOINT else SOFT_DOCK_CLEARANCE_M}, "
                    f"body_local_pos={uav_body_local_pos}, "
                    f"body_local_orientation_wxyz={uav_body_local_orientation_wxyz}, "
                    f"orientation_wxyz={dock_orientation_wxyz}"
                )
            except Exception as exc:
                carb.log_error(f"AirGround UAV dock pose alignment failed: {exc}")
        if CREATE_DOCK_JOINT:
            self.dock_joint = AirGroundDockJointController(
                stage,
                dock_config,
            )
            dock_status = self.dock_joint.create()
            for _ in range(5 if settle_updates else 0):
                omni.kit.app.get_app().update()
            carb.log_warn(
                "AirGround dock joint created after world.reset: "
                f"{dock_status.joint_path} ({dock_status.ugv_body_path} -> {dock_status.uav_body_path})"
            )
        else:
            carb.log_warn("AirGround physical dock joint disabled; UAV starts from dock-aligned pose")

    def finish_task(self) -> None:
        """Post-reset initialisation, publishers and servers of this task."""
        stage = omni.usd.get_context().get_stage()
        if getattr(self, "uav_body_canonical_local_pose", None) is None:
            self._capture_uav_body_canonical_local_pose()
        try:
            if not getattr(self, "_ugv_initialized_before_dock", False):
                self.ugv.initialize()
                self.ugv.post_reset()
            is_valid = getattr(self.ugv, "is_physics_handle_valid", None)
            valid_msg = bool(is_valid()) if callable(is_valid) else "unknown"
            carb.log_warn(
                "AirGround UGV articulation initialized and velocity control armed: "
                f"{valid_msg}"
            )
        except Exception as exc:
            carb.log_error(f"AirGround UGV articulation initialize failed: {exc}")

        if not getattr(self, "_dock_prepared", False):
            self._align_and_dock(stage, settle_updates=True)
        else:
            carb.log_warn("AirGround dock already prepared before the shared world advanced (multi-task)")

        self.ugv_state_publisher = None
        self.ugv_contact_publisher = None
        self.ugv_proximity_scan_publisher = None
        self.uav_state_publisher = None
        self.rgbd_camera_publisher = None
        self.clock_pre_tick = None
        # Later tasks get no working OmniGraph /clock (the bridge publishes only the
        # first ROS domain's), so their Python publisher emits both per-step stamps.
        self.clock_posts_step_end = False
        self.session_scheduler = None
        if AIRGROUND_COOPERATIVE_SESSIONS and self.host is not self and self.host.session_scheduler is not None:
            self.session_scheduler = self.host.session_scheduler
        elif AIRGROUND_COOPERATIVE_SESSIONS:
            _vendor_dir = os.path.normpath(
                os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "vendor", "greenlet-3.0.3")
            )
            if _vendor_dir not in sys.path:
                sys.path.insert(0, _vendor_dir)
            _sidecar_dir = os.path.normpath(
                os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "airground_sidecar")
            )
            if _sidecar_dir not in sys.path:
                sys.path.insert(0, _sidecar_dir)
            from session_scheduler import SessionScheduler  # noqa: WPS433

            self.session_scheduler = SessionScheduler()
            if not self.session_scheduler.available:
                raise RuntimeError("AIRGROUND_COOPERATIVE_SESSIONS=true needs the vendored greenlet module")
            carb.log_warn("AirGround cooperative evidence sessions enabled")
        if self.legacy_camera_surfaces:
            attached_count = 0
            for camera_surface in self.legacy_camera_surfaces:
                if attach_zed_legacy_omnigraph_writers(camera_surface):
                    attached_count += 1
            carb.log_warn(
                "AirGround post-reset legacy RGB-D camera graphs attached: "
                f"{attached_count}/{len(self.legacy_camera_surfaces)} stereo surfaces"
            )
        # The detached (non-fixed-joint) camera mounts follow the vehicle through
        # a dynamic-control handle plus an app update subscription; world.reset()
        # invalidates both, so they must be re-bound here or the camera silently
        # stays at a stale world pose while the UAV flies (2026-09-15: second run
        # in every container reported 110-150 m depth at 4 m altitude and never
        # produced a plan).
        try:
            rebind_detached_camera_mounts()
        except Exception as exc:
            carb.log_error(f"AirGround post-reset camera mount rebind failed: {exc}")
        if self.task.task_id > 0:
            from clock_pre_tick import ClockPreTickPublisher  # noqa: WPS433

            self.clock_pre_tick = ClockPreTickPublisher.create()
            self.clock_posts_step_end = True
        if self.rgbd_camera_surfaces:
            if AIRGROUND_RGBD_PUBLISHER_SURFACES is not None:
                carb.log_warn(
                    "AirGround manual RGB-D publisher surface filter selected: "
                    f"requested={sorted(AIRGROUND_RGBD_PUBLISHER_SURFACES)}, "
                    f"topics={[surface.rgb_topic for surface in self.rgbd_camera_surfaces]}"
                )
            rgbd_config = RgbdCameraPublisherConfig(
                surfaces=tuple(self.rgbd_camera_surfaces),
                publish_hz=AIRGROUND_RGBD_PUBLISHER_HZ,
            )
            if AIRGROUND_RGBD_BACKEND == "tiled_sidecar":
                _sidecar_dir = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "airground_sidecar"))
                if _sidecar_dir not in sys.path:
                    sys.path.insert(0, _sidecar_dir)
                import tiled_rgbd_publisher as _tiled_module  # noqa: WPS433
                from tiled_rgbd_publisher import TiledRgbdSidecarPublisher  # noqa: WPS433

                if _STAGE_TIMER is not None:
                    _tiled_module.STAGE_TIMER = _STAGE_TIMER

                from pegasus.simulator.logic import ros_context  # noqa: WPS433

                # Multi-task: the sidecar publishes in this task's domain (None = container default).
                self.rgbd_camera_publisher = TiledRgbdSidecarPublisher(
                    rgbd_config, log=carb.log_warn, domain_id=ros_context.active_domain()
                )
                # The manual publisher's Camera objects cause a second, start-of-step
                # /clock message per render step; replay it so ROS timers keep the
                # validated cadence (see clock_pre_tick.py for the measurement).
                from clock_pre_tick import ClockPreTickPublisher  # noqa: WPS433

                if self.clock_pre_tick is None:
                    self.clock_pre_tick = ClockPreTickPublisher.create()
                if AIRGROUND_SINGLE_CLOCK_PUBLISHER and not self.clock_posts_step_end:
                    self._retire_omnigraph_clock()
            else:
                self.rgbd_camera_publisher = AirGroundRgbdCameraPublisher(rgbd_config)
            carb.log_warn(
                "Manual RGB-D camera publishers enabled: "
                + ", ".join(surface.rgb_topic or "" for surface in self.rgbd_camera_surfaces)
            )
        if ENABLE_UAV_STATE_PUBLISHERS:
            self.uav_state_publisher = MultirotorStatePublisher(
                MultirotorStatePublisherConfig(
                    namespace=UAV_ROBOT_NAME,
                    prim_path=f"{UAV_PRIM}{UAV_MAPPING.body_path}",
                    base_frame=f"{UAV_ROBOT_NAME}/base_link",
                )
            )
            carb.log_warn(
                "UAV state publishers enabled: "
                f"/{UAV_ROBOT_NAME}/odom, /{UAV_ROBOT_NAME}/ground_truth/pose and /tf"
            )
        if ENABLE_UGV_STATE_PUBLISHERS:
            # Nav2 consumes the Ouster point cloud through tf2, so the sensor
            # frame has to exist below the Jackal body.  Read the mount from the
            # live stage instead of re-hardcoding the offset plus the Ouster
            # asset's baked-in corrective rotation.
            ugv_lidar_frame = None
            if getattr(self, "ugv_proximity_cloud_publisher", None) is not None:
                # The CPU cloud publisher owns the mount contract itself; its
                # configured offset/rotation has to be the published TF.
                ugv_lidar_frame = JackalSensorFrame(
                    frame_id=UGV_LIDAR_FRAME_ID,
                    translation_m=UGV_LIDAR_MOUNT_OFFSET_M,
                    rotation_xyzw=(
                        0.0,
                        0.0,
                        math.sin(UGV_LIDAR_FRAME_YAW_RAD / 2.0),
                        math.cos(UGV_LIDAR_FRAME_YAW_RAD / 2.0),
                    ),
                )
            ugv_sensor_frames = tuple(
                frame
                for frame in (
                    ugv_lidar_frame
                    if ugv_lidar_frame is not None
                    else airground_sensor_frame_from_usd(
                        stage,
                        root_path=UGV_SENSOR_BODY_PATH,
                        sensor_prim_path=getattr(self, "ugv_lidar_sensor_prim_path", None),
                        frame_id=UGV_LIDAR_FRAME_ID,
                    ),
                )
                if frame is not None
            )
            self.ugv_state_publisher = JackalStatePublisher(
                JackalStatePublisherConfig(
                    namespace=UGV_ROBOT_NAME,
                    sensor_frames=ugv_sensor_frames,
                )
            )
            self.ugv_state_publisher.bind_robot(self.ugv)
            carb.log_warn(
                "UGV state publishers enabled: "
                f"/{UGV_ROBOT_NAME}/odom, /{UGV_ROBOT_NAME}/joint_states, "
                f"/{UGV_ROBOT_NAME}/ground_truth/pose, "
                f"/{UGV_ROBOT_NAME}/control/status, /{UGV_ROBOT_NAME}/cmd_vel and /tf "
                f"(sensor frames: {[frame.frame_id for frame in ugv_sensor_frames]})"
            )
        if ENABLE_UGV_CONTACT_PUBLISHER:
            self.ugv_contact_publisher = JackalContactPublisher(
                JackalContactPublisherConfig(
                    namespace=UGV_ROBOT_NAME,
                    prim_root=UGV_PRIM,
                )
            )
            carb.log_warn(f"UGV contact publisher enabled: /{UGV_ROBOT_NAME}/contact_state")

        self.native_state_bridge = None
        if STATE_BRIDGE == "native":
            tools = str(Path(__file__).resolve().parents[1] / "tools")
            if tools not in sys.path:
                sys.path.insert(0, tools)
            from native_state_bridge import attach
            self.native_state_bridge, _ = attach(self, domain_id=UAV_DOMAIN_ID if len(TASKS) > 1 else None)
            carb.log_warn("Native Isaac4.5/Humble state and contact bridge enabled")
        if self.ugv_proximity_cloud_publisher is not None:
            # AIRGROUND_UGV_CLOUD_NATIVE_PUBLISH: this task's cloud goes out through its own bridge (no-op when off).
            self.ugv_proximity_cloud_publisher.bind_native_bridge(self.native_state_bridge)

        self.ugv_proximity_scan_publisher = None
        if ENABLE_UGV_PROXIMITY_SCAN:
            try:
                self.ugv_proximity_scan_publisher = JackalProximityScanPublisher(
                    _airground_lazy_physx_segment_raycast_fn(),
                    JackalProximityScanConfig(
                        namespace=UGV_ROBOT_NAME,
                        ray_count=UGV_PROXIMITY_SCAN_RAY_COUNT,
                        max_range_m=UGV_PROXIMITY_SCAN_MAX_RANGE_M,
                        min_range_m=UGV_PROXIMITY_SCAN_MIN_RANGE_M,
                        height_offset_m=UGV_PROXIMITY_SCAN_HEIGHT_OFFSET_M,
                        publish_period_s=UGV_PROXIMITY_SCAN_PERIOD_S,
                        ignored_prim_prefixes=ROBOT_IGNORED_PRIM_PREFIXES,
                    ),
                )
                carb.log_warn(
                    "UGV proximity scan enabled: "
                    f"/{UGV_ROBOT_NAME}/scan "
                    f"({UGV_PROXIMITY_SCAN_RAY_COUNT} rays, "
                    f"{UGV_PROXIMITY_SCAN_MAX_RANGE_M:.2f}m, "
                    f"z+{UGV_PROXIMITY_SCAN_HEIGHT_OFFSET_M:.2f}m, "
                    f"{1.0 / UGV_PROXIMITY_SCAN_PERIOD_S:.1f}Hz, frame {UGV_ROBOT_NAME}/base_link)"
                )
            except Exception as exc:
                carb.log_error(f"UGV proximity scan failed to start: {exc}")

        self.full_mission_evidence_server = None
        if ENABLE_FULL_MISSION_EVIDENCE_SERVER:
            try:
                self.full_mission_evidence_server = AirGroundFullMissionEvidenceServer(self)
                carb.log_warn(
                    "AirGround full-mission evidence server enabled: "
                    f"{FULL_MISSION_EVIDENCE_REQUEST_TOPIC} -> {FULL_MISSION_EVIDENCE_RESPONSE_TOPIC}"
                )
            except Exception as exc:
                carb.log_error(f"AirGround full-mission evidence server failed to start: {exc}")
                raise

        if self.replicator_camera_surfaces:
            attached_count = 0
            for camera_surface in self.replicator_camera_surfaces:
                if attach_zed_replicator_writers(camera_surface):
                    attached_count += 1
            carb.log_warn(
                "AirGround post-reset Replicator RGB-D writers attached: "
                f"{attached_count}/{len(self.replicator_camera_surfaces)} stereo surfaces"
            )

        self.play_on_start = os.environ.get("PLAY_SIM_ON_START", "true").lower() == "true"
        self.stop_sim = False
        self._runtime_state_publish_count = 0

    def _simulation_time_s(self) -> float:
        if hasattr(self.world, "current_time"):
            current_time = self.world.current_time
            return float(current_time() if callable(current_time) else current_time)
        if hasattr(self.world, "current_time_step_index"):
            step_index = self.world.current_time_step_index
            step_value = step_index() if callable(step_index) else step_index
            return float(step_value) * float(self.world.get_physics_dt())
        return time.time()

    @_usd_during_episode_reset
    def reset_episode_start(
        self,
        *,
        ugv_x_m: float,
        ugv_y_m: float,
        ugv_yaw_rad: float,
        uav_platform_x_m: float,
        uav_platform_y_m: float,
        uav_platform_z_m: float,
        uav_platform_yaw_rad: float,
        docked: bool,
    ) -> dict[str, Any]:
        values = {
            "ugv_x_m": ugv_x_m,
            "ugv_y_m": ugv_y_m,
            "ugv_yaw_rad": ugv_yaw_rad,
            "uav_platform_x_m": uav_platform_x_m,
            "uav_platform_y_m": uav_platform_y_m,
            "uav_platform_z_m": uav_platform_z_m,
            "uav_platform_yaw_rad": uav_platform_yaw_rad,
        }
        for label, value in values.items():
            if not math.isfinite(float(value)):
                raise RuntimeError(f"{label} must be finite")
        stage = omni.usd.get_context().get_stage()
        if stage is None:
            raise RuntimeError("Stage is unavailable for episode reset")

        if self.native_state_bridge is not None:
            self.native_state_bridge.clear_commands()

        actuator_zero_before_settle = self._zero_uav_actuator_state("episode_reset_before_settle")
        ugv_stop_before_settle = {"status": "ok"}
        try:
            self.ugv.apply_cmd_vel(0.0, 0.0)
            ugv_stop_before_settle["applied"] = True
        except Exception as exc:
            ugv_stop_before_settle = {
                "status": "warning",
                "error": f"{type(exc).__name__}: {exc}",
            }
            carb.log_warn(f"AirGround UGV stop command skipped before episode reset settle: {exc}")
        for _ in range(5):
            self.step_world(render=AIRGROUND_RENDER)
            self.publish_runtime_state(spin_evidence_server=False)

        dock_release_status: dict[str, Any] | None = None
        if self.dock_joint is not None:
            released = self.dock_joint.release()
            dock_release_status = {
                "exists_after_release": released.exists,
                "joint_path": released.joint_path,
            }
            self.dock_joint = None

        # Isaac 6.x tolerates a fresh world reset between full-mission episodes.
        # Isaac 4.5 on LFT-W02 invalidates PhysX/dynamic_control views and
        # regresses /clock after world.reset(), so that route uses an explicit
        # soft reset: stop PX4, zero/teleport live bodies, re-dock, and restart.
        world_reset_called = False
        reset_mode = "world_reset" if AIRGROUND_EPISODE_WORLD_RESET else "soft_reset"
        # On Isaac 4.5, stopping the timeline without a matching world.reset()
        # leaves the PhysX tensor simulation view unavailable after restart.
        # Keep soft resets live so dock joints and Pegasus thrust targets stay
        # visible to PhysX; full world-reset mode retains the old stop/reset path.
        timeline_stopped_before_episode_reset = False
        if AIRGROUND_EPISODE_WORLD_RESET:
            self.timeline.stop()
            timeline_stopped_before_episode_reset = True
        force_suspend_before_episode_reset = self._suspend_uav_force_application(
            "episode_reset_before_world_reset"
            if AIRGROUND_EPISODE_WORLD_RESET
            else "episode_reset_before_soft_reset"
        )
        px4_backend_reset = self._reset_uav_px4_backend_state("episode_reset")
        ground_support_after_episode_reset: dict[str, Any] | None = None
        ground_support_after_world_reset: dict[str, Any] | None = None
        callback_refresh_after_world_reset: dict[str, Any] | None = None
        body_rotation_compensation_after_world_reset: dict[str, Any] | None = None
        body_rotation_compensation_after_episode_reset: dict[str, Any] | None = None
        if AIRGROUND_EPISODE_WORLD_RESET:
            self.world.reset()
            world_reset_called = True
            stage = omni.usd.get_context().get_stage()
            if stage is None:
                raise RuntimeError("Stage is unavailable after episode world reset")
            ground_support_after_world_reset = self._ensure_ground_support_plane(
                stage,
                "episode_reset_after_world_reset",
            )
            ground_support_after_episode_reset = ground_support_after_world_reset
            callback_refresh_after_world_reset = self._refresh_uav_physics_callbacks()
            body_rotation_compensation_after_world_reset = self._refresh_uav_body_local_rotation_compensation(
                "episode_reset_after_world_reset"
            )
            body_rotation_compensation_after_episode_reset = body_rotation_compensation_after_world_reset
        else:
            ground_support_after_episode_reset = self._ensure_ground_support_plane(
                stage,
                "episode_reset_after_soft_reset",
            )
            body_rotation_compensation_after_episode_reset = self._refresh_uav_body_local_rotation_compensation(
                "episode_reset_after_soft_reset"
            )
        stage = omni.usd.get_context().get_stage()
        if stage is None:
            raise RuntimeError("Stage is unavailable after episode reset")
        for _ in range(3):
            omni.kit.app.get_app().update()
        if self.rgbd_camera_publisher is not None:
            self.rgbd_camera_publisher.post_reset()
        if not AIRGROUND_EPISODE_WORLD_RESET:
            callback_refresh_after_world_reset = None
        ground_support_after_pre_dock_settle = self._ensure_ground_support_plane(
            stage,
            "episode_reset_pre_dock_settle",
        )
        self._trace_dock_settle("pre_dock_settle", 0)
        for pre_index in range(10):
            self.step_world(render=AIRGROUND_RENDER)
            self.publish_runtime_state(spin_evidence_server=False)
            self._trace_dock_settle("pre_dock_settle", pre_index + 1)

        ugv_reinitialize_status: dict[str, Any] = {"status": "ok"}
        if AIRGROUND_EPISODE_WORLD_RESET:
            try:
                self.ugv.initialize()
                ugv_reinitialize_status["initialize_called"] = True
            except Exception as exc:
                ugv_reinitialize_status["initialize_error"] = f"{type(exc).__name__}: {exc}"
            try:
                self.ugv.post_reset()
                ugv_reinitialize_status["post_reset_called"] = True
            except Exception as exc:
                ugv_reinitialize_status["post_reset_error"] = f"{type(exc).__name__}: {exc}"
            if any(key.endswith("_error") for key in ugv_reinitialize_status):
                ugv_reinitialize_status["status"] = "warning"
        else:
            ugv_reinitialize_status.update(
                {
                    "status": "skipped",
                    "reason": "soft_reset_reuses_live_articulation",
                    "initialize_called": False,
                    "post_reset_called": False,
                }
            )

        ugv_root_position = (float(ugv_x_m), float(ugv_y_m), float(UGV_Z))
        ugv_orientation_wxyz = _airground_wxyz_from_yaw(float(ugv_yaw_rad))
        ugv_root_pose_reset_status: dict[str, Any] = {"status": "ok", "prim_path": UGV_PRIM}
        try:
            set_articulation_root_world_pose(stage, UGV_PRIM, ugv_root_position, ugv_orientation_wxyz)
            ugv_root_pose_reset_status["applied"] = True
        except Exception as exc:
            ugv_root_pose_reset_status = {
                "status": "warning",
                "prim_path": UGV_PRIM,
                "error": f"{type(exc).__name__}: {exc}",
                "usd_pose_authored_before_error": True,
            }
            carb.log_warn(f"AirGround UGV articulation root reset kept USD pose after live-view error: {exc}")
        ugv_robot_pose_reset_status = set_robot_world_pose_and_zero_velocity(
            self.ugv,
            ugv_root_position,
            ugv_orientation_wxyz,
            label="ugv_robot_wrapper",
        )
        ugv_body_pose_reset_status = set_rigid_prim_world_pose_and_zero_velocity(
            stage,
            UGV_SENSOR_BODY_PATH,
            ugv_root_position,
            ugv_orientation_wxyz,
            author_usd_xform=False,
        )
        for _ in range(10):
            self.step_world(render=AIRGROUND_RENDER)
            self.publish_runtime_state(spin_evidence_server=False)

        dock_create_status: dict[str, Any] | None = None
        uav_root_position: tuple[float, float, float] | None = None
        uav_orientation_wxyz: tuple[float, float, float, float] | None = None
        uav_body_target_position: tuple[float, float, float] | None = None
        uav_body_target_orientation_wxyz: tuple[float, float, float, float] | None = None
        uav_body_pose_reset_status: dict[str, Any] | None = None
        uav_body_local_restore_status: dict[str, Any] | None = None
        uav_body_local_pos: tuple[float, float, float] | None = None
        uav_body_local_orientation_wxyz: tuple[float, float, float, float] | None = None
        uav_root_pose_reset_status: dict[str, Any] | None = None
        if docked:
            dock_config = AirGroundDockJointConfig(
                break_force_n=float(DOCK_BREAK_FORCE_N),
                break_torque_nm=float(DOCK_BREAK_TORQUE_NM),
                joint_path=self.task.dock_joint_path,
                ugv_body_path=f"{UGV_PRIM}/base_link",
                uav_body_path=f"{UAV_PRIM}{UAV_MAPPING.body_path}",
            )
            ugv_body_position, ugv_body_orientation_wxyz = prim_world_pose_wxyz(
                stage,
                dock_config.ugv_body_path,
            )
            if self.uav_body_canonical_local_pose is not None:
                uav_body_local_pos, uav_body_local_orientation_wxyz = self.uav_body_canonical_local_pose
                set_local_prim_pose(
                    stage,
                    dock_config.uav_body_path,
                    uav_body_local_pos,
                    uav_body_local_orientation_wxyz,
                )
                uav_body_local_restore_status = {
                    "prim_path": dock_config.uav_body_path,
                    "source": "canonical_body_local_pose",
                    "status": "ok",
                }
            else:
                uav_body_local_pos, uav_body_local_orientation_wxyz = child_local_pose_wxyz(
                    stage,
                    UAV_PRIM,
                    f"{UAV_PRIM}{UAV_MAPPING.body_path}",
                )
                uav_body_local_restore_status = {
                    "prim_path": dock_config.uav_body_path,
                    "source": "current_child_local_pose",
                    "status": "warning",
                }
            uav_root_position, uav_orientation_wxyz = docked_uav_root_world_pose(
                tuple(float(value) for value in ugv_body_position),
                tuple(float(value) for value in ugv_body_orientation_wxyz),
                uav_body_local_pos,
                dock_config,
                clearance_m=(0.0 if CREATE_DOCK_JOINT else SOFT_DOCK_CLEARANCE_M),
                uav_orientation_wxyz=_multiply_quaternions_wxyz(
                    tuple(float(value) for value in ugv_body_orientation_wxyz),
                    _airground_wxyz_from_yaw(float(uav_platform_yaw_rad)),
                ),
            )
            uav_body_target_position, uav_body_target_orientation_wxyz = docked_uav_world_pose(
                tuple(float(value) for value in ugv_body_position),
                tuple(float(value) for value in ugv_body_orientation_wxyz),
                dock_config,
                clearance_m=(0.0 if CREATE_DOCK_JOINT else SOFT_DOCK_CLEARANCE_M),
            )
            # The body target is the UGV platform anchor, but its orientation
            # must follow the UAV's requested relative platform yaw.  Keeping
            # the UGV orientation here would make the child-body correction
            # undo the root yaw on every episode reset.
            assert uav_orientation_wxyz is not None
            uav_body_target_orientation_wxyz = uav_orientation_wxyz
            self.soft_dock_hold_pose = (
                (
                    tuple(float(value) for value in uav_root_position),
                    tuple(float(value) for value in uav_orientation_wxyz),
                ),
                None,
            )
            self.soft_dock_hold_active = bool(
                SOFT_DOCK_HOLD_ENABLED and not CREATE_DOCK_JOINT
            )
            self.soft_dock_hold_settle_remaining = SOFT_DOCK_HOLD_SETTLE_STEPS
            self.soft_dock_hold_latched = False
            uav_root_pose_reset_status = {"status": "ok", "prim_path": UAV_PRIM}
            try:
                set_articulation_root_world_pose(
                    stage,
                    UAV_PRIM,
                    uav_root_position,
                    uav_orientation_wxyz,
                )
                uav_root_pose_reset_status["applied"] = True
            except Exception as exc:
                uav_root_pose_reset_status = {
                    "status": "warning",
                    "prim_path": UAV_PRIM,
                    "error": f"{type(exc).__name__}: {exc}",
                    "usd_pose_authored_before_error": True,
                }
                carb.log_warn(f"AirGround UAV articulation root reset kept USD pose after live-view error: {exc}")
            uav_body_pose_reset_status = skip_articulation_child_world_pose_reset(
                stage,
                root_path=UAV_PRIM,
                child_path=dock_config.uav_body_path,
                target_position_m=uav_body_target_position,
                target_orientation_wxyz=uav_body_target_orientation_wxyz,
                label="episode_reset_redock_uav_chassis",
            )
            if CREATE_DOCK_JOINT:
                self.dock_joint = AirGroundDockJointController(stage, dock_config)
                created = self.dock_joint.create()
                dock_create_status = {
                    "exists_after_create": created.exists,
                    "joint_path": created.joint_path,
                    "physical_dock_joint_enabled": True,
                    "uav_body_path": created.uav_body_path,
                    "ugv_body_path": created.ugv_body_path,
                }
            else:
                self.dock_joint = None
                dock_create_status = {
                    "exists_after_create": False,
                    "joint_path": dock_config.joint_path,
                    "physical_dock_joint_enabled": False,
                    "status": "semantic_dock_pose_only",
                    "uav_body_path": dock_config.uav_body_path,
                    "ugv_body_path": dock_config.ugv_body_path,
                }
        body_rotation_compensation_after_redock = self._refresh_uav_body_local_rotation_compensation(
            "episode_reset_after_redock"
        )
        self._trace_dock_settle("after_joint_create", 0)
        for settle_index in range(15):
            self.step_world(render=AIRGROUND_RENDER)
            self.publish_runtime_state(spin_evidence_server=False)
            self._trace_dock_settle("dock_settle", settle_index + 1)
        # The dock constraint can reintroduce contact angular velocity during
        # settling even after the initial teleport. Clear it immediately
        # before restarting PX4 so EKF2 receives a stationary HIL sample.
        ugv_root_velocity_reset_after_dock_settle = zero_rigid_prim_velocities(UGV_PRIM)
        ugv_velocity_reset_after_dock_settle = zero_rigid_prim_velocities(
            UGV_SENSOR_BODY_PATH
        )
        uav_velocity_reset_after_dock_settle: dict[str, Any] | None = None
        uav_root_velocity_reset_after_dock_settle: dict[str, Any] | None = None
        if docked:
            uav_root_velocity_reset_after_dock_settle = zero_rigid_prim_velocities(UAV_PRIM)
            uav_velocity_reset_after_dock_settle = zero_rigid_prim_velocities(
                f"{UAV_PRIM}{UAV_MAPPING.body_path}"
            )
        callback_refresh = self._refresh_uav_physics_callbacks()
        force_suspend_after_redock = self._suspend_uav_force_application(
            "episode_reset_after_redock"
        )
        uav_sensor_reset_after_dock_settle = self._reset_uav_sensor_state(
            "episode_reset_after_dock_settle"
        )
        px4_backend_restart_after_reset = self._restart_uav_px4_backend_state(
            "episode_reset_after_redock"
        )
        self.timeline.play()
        for warm_index in range(10):
            self.step_world(render=AIRGROUND_RENDER)
            self._pump_uav_px4_runtime_once("episode_reset_post_restart_warmup")
            self.publish_runtime_state(spin_evidence_server=False)
            self._trace_dock_settle("post_restart_warmup", warm_index + 1)
        # Dock constraints can transfer an articulation-root impulse back into
        # the chassis during the warmup itself.  Send one final zero-velocity
        # HIL sample after clearing both live bodies, before evaluating EKF2.
        uav_root_velocity_reset_after_warmup: dict[str, Any] | None = None
        uav_velocity_reset_after_warmup: dict[str, Any] | None = None
        if docked:
            uav_root_velocity_reset_after_warmup = zero_rigid_prim_velocities(UAV_PRIM)
            uav_velocity_reset_after_warmup = zero_rigid_prim_velocities(
                f"{UAV_PRIM}{UAV_MAPPING.body_path}"
            )
            self._pump_uav_px4_runtime_once("episode_reset_post_restart_zero_velocity")
            self.publish_runtime_state(spin_evidence_server=False)
        px4_backend_post_restart_warmup = self._uav_px4_runtime_snapshot(
            "episode_reset_post_restart_warmup"
        )
        ugv_root_applied_position, ugv_root_applied_orientation = prim_world_pose_wxyz(stage, UGV_PRIM)
        ugv_body_applied_position, ugv_body_applied_orientation = prim_world_pose_wxyz(stage, UGV_SENSOR_BODY_PATH)
        uav_root_applied_position, uav_root_applied_orientation = prim_world_pose_wxyz(stage, UAV_PRIM)
        uav_body_applied_position, uav_body_applied_orientation = prim_world_pose_wxyz(
            stage,
            f"{UAV_PRIM}{UAV_MAPPING.body_path}",
        )
        return {
            "callback_refresh_after_world_reset": callback_refresh_after_world_reset,
            "callback_refresh": callback_refresh,
            "episode_reset_mode": reset_mode,
            "episode_world_reset_enabled": AIRGROUND_EPISODE_WORLD_RESET,
            "body_rotation_compensation_after_episode_reset": body_rotation_compensation_after_episode_reset,
            "body_rotation_compensation_after_world_reset": body_rotation_compensation_after_world_reset,
            "body_rotation_compensation_after_redock": body_rotation_compensation_after_redock,
            "dock_create_status": dock_create_status,
            "dock_release_status": dock_release_status,
            "docked": bool(docked),
            "force_suspend_before_episode_reset": force_suspend_before_episode_reset,
            "force_suspend_before_world_reset": (
                force_suspend_before_episode_reset if AIRGROUND_EPISODE_WORLD_RESET else None
            ),
            "force_suspend_after_redock": force_suspend_after_redock,
            "ground_support_after_episode_reset": ground_support_after_episode_reset,
            "ground_support_after_pre_dock_settle": ground_support_after_pre_dock_settle,
            "ground_support_after_world_reset": ground_support_after_world_reset,
            "ground_support_launch_summary": self.ground_support_launch_summary,
            "wheel_contact_offsets_summary": self.wheel_contact_offsets_summary,
            "ugv_solver_iterations_summary": self.ugv_solver_iterations_summary,
            "ugv_wheel_traction_summary": self.ugv_wheel_traction_summary,
            "ugv_cmd_vel_shaping_summary": self.ugv_cmd_vel_shaping_summary,
            "uav_actuator_zero_before_settle": actuator_zero_before_settle,
            "px4_backend_reset": px4_backend_reset,
            "px4_backend_restart_after_reset": px4_backend_restart_after_reset,
            "px4_backend_post_restart_warmup": px4_backend_post_restart_warmup,
            "requested": {
                "uav_on_platform": {
                    "x_m": float(uav_platform_x_m),
                    "y_m": float(uav_platform_y_m),
                    "z_m": float(uav_platform_z_m),
                    "yaw_rad": float(uav_platform_yaw_rad),
                },
                "ugv": {
                    "x_m": float(ugv_x_m),
                    "y_m": float(ugv_y_m),
                    "z_m": float(UGV_Z),
                    "yaw_rad": float(ugv_yaw_rad),
                },
            },
            "status": "ok",
            "uav_root_applied_orientation_wxyz": list(uav_root_applied_orientation),
            "uav_root_applied_position_m": list(uav_root_applied_position),
            "uav_body_applied_orientation_wxyz": list(uav_body_applied_orientation),
            "uav_body_applied_position_m": list(uav_body_applied_position),
            "uav_body_local_restore_status": uav_body_local_restore_status,
            "uav_body_pose_reset_status": uav_body_pose_reset_status,
            "uav_body_target_orientation_wxyz": list(uav_body_target_orientation_wxyz or ()),
            "uav_body_target_position_m": list(uav_body_target_position or ()),
            "uav_body_local_orientation_wxyz": list(uav_body_local_orientation_wxyz or ()),
            "uav_body_local_position_m": list(uav_body_local_pos or ()),
            "uav_root_pose_reset_status": uav_root_pose_reset_status,
            "uav_velocity_reset_after_dock_settle": uav_velocity_reset_after_dock_settle,
            "uav_root_velocity_reset_after_dock_settle": uav_root_velocity_reset_after_dock_settle,
            "uav_root_velocity_reset_after_warmup": uav_root_velocity_reset_after_warmup,
            "uav_sensor_reset_after_dock_settle": uav_sensor_reset_after_dock_settle,
            "uav_velocity_reset_after_warmup": uav_velocity_reset_after_warmup,
            "uav_root_dock_target_orientation_wxyz": list(uav_orientation_wxyz or ()),
            "uav_root_dock_target_position_m": list(uav_root_position or ()),
            "ugv_body_applied_orientation_wxyz": list(ugv_body_applied_orientation),
            "ugv_body_applied_position_m": list(ugv_body_applied_position),
            "ugv_body_pose_reset_status": ugv_body_pose_reset_status,
            "ugv_stop_before_settle": ugv_stop_before_settle,
            "ugv_velocity_reset_after_dock_settle": ugv_velocity_reset_after_dock_settle,
            "ugv_root_velocity_reset_after_dock_settle": ugv_root_velocity_reset_after_dock_settle,
            "ugv_root_pose_reset_status": ugv_root_pose_reset_status,
            "ugv_reinitialize_status": ugv_reinitialize_status,
            "ugv_robot_pose_reset_status": ugv_robot_pose_reset_status,
            "ugv_root_applied_orientation_wxyz": list(ugv_root_applied_orientation),
            "ugv_root_applied_position_m": list(ugv_root_applied_position),
            "timeline_played_after_reset": True,
            "timeline_stopped_before_episode_reset": timeline_stopped_before_episode_reset,
            "timeline_stopped_before_world_reset": (
                timeline_stopped_before_episode_reset if AIRGROUND_EPISODE_WORLD_RESET else False
            ),
            "world_reset_called": world_reset_called,
        }

    def _dump_rtx_exposure_settings(self) -> None:
        """Log the RTX exposure/tonemap settings used by this launch app.

        2026-09-12: onboard ZED frames are washed out while the replay renderer
        is correctly exposed; this dump lets the two apps be compared from run
        evidence (AIRGROUND_DUMP_RTX_EXPOSURE_SETTINGS=1).
        """
        try:
            import carb

            settings = carb.settings.get_settings()
            # 2026-09-13: this build's ISettings has no ``get_keys``; dump the
            # API surface plus a curated key list so the comparison with the
            # replay app does not depend on a missing enumeration call.
            carb.log_warn(
                "AirGround carb settings API: "
                f"{[name for name in dir(settings) if not name.startswith('_')]}"
            )
            query = getattr(settings, "get_keys", None)
            keys: list[str] = list(
                query() if callable(query) else ()
            )
            if not keys:
                keys = [
                    "/rtx/rendermode",
                    "/rtx/post/tonemap/enabled",
                    "/rtx/post/tonemap/mode",
                    "/rtx/post/tonemap/exposureBias",
                    "/rtx/post/histogram/enabled",
                    "/rtx/post/histogram/autoExposure/enabled",
                    "/rtx/post/histogram/normalization",
                    "/rtx/post/histogram/evMax",
                    "/rtx/post/histogram/evMin",
                    "/rtx/exposure/enabled",
                    "/rtx/exposure/ev",
                    "/rtx/exposure/mode",
                    "/rtx/camera/exposure/mode",
                    "/rtx/post/aa/enabled",
                    "/rtx/ambientOcclusion/enabled",
                    "/rtx/indirectDiffuse/enabled",
                    "/rtx/reflections/enabled",
                    "/rtx/domeLight/enabled",
                    "/rtx/background/source/type",
                    "/persistent/app/viewport/displayOptions",
                ]
            filtered_keys = [
                key
                for key in keys
                if any(
                    token in str(key).lower()
                    for token in ("exposure", "tonemap", "histogram", "/rtx/")
                )
            ]
            for key in sorted(str(item) for item in filtered_keys):
                try:
                    value = settings.get(key)
                except Exception:
                    value = "<unreadable>"
                carb.log_warn(f"AirGround RTX exposure setting: {key}={value}")
            carb.log_warn(
                "AirGround RTX exposure settings dumped: "
                f"count={len(filtered_keys)}, viewport="
                f"{AIRGROUND_RENDER_WIDTH}x{AIRGROUND_RENDER_HEIGHT}, "
                f"renderer={AIRGROUND_RENDERER}, "
                f"minimal_shading_mode={AIRGROUND_MINIMAL_SHADING_MODE}"
            )
            self._dump_scene_lights()
            self._dump_scene_materials()
            self._dump_scene_visibility_probe()
        except Exception as exc:
            carb.log_warn(f"AirGround RTX exposure settings dump failed: {exc}")

    @staticmethod
    def _apply_rtx_tonemap_settings() -> dict[str, Any]:
        """Pin the RTX camera exposure settings used by the onboard cameras.

        ``AIRGROUND_RTX_TONEMAP_SETTINGS`` accepts ``key=value`` pairs separated
        by ``;`` (for example ``fNumber=11`` or ``fNumber=11;filmIso=100``) and
        writes them to ``/rtx/post/tonemap/<key>``; ``none`` keeps the Kit
        defaults.  Measured on the local Isaac Sim 4.5 lane (UGV onboard frames,
        clipped-pixel fraction): f/5 (Kit default) 56.6%, f/8 3.2%, f/11 0.0%.
        """
        import carb

        summary: dict[str, Any] = {"requested": AIRGROUND_RTX_TONEMAP_SETTINGS, "applied": {}}
        raw = (AIRGROUND_RTX_TONEMAP_SETTINGS or "").strip()
        if not raw or raw.lower() in {"none", "off", "default"}:
            carb.log_warn(f"AirGround RTX tonemap settings kept: {summary}")
            return summary
        settings = carb.settings.get_settings()
        for entry in raw.split(";"):
            entry = entry.strip()
            if not entry:
                continue
            key, separator, value = entry.partition("=")
            key = key.strip()
            value = value.strip()
            if not separator or not key or not value:
                summary["applied"][entry] = "invalid (expected key=value)"
                continue
            setting_path = f"/rtx/post/tonemap/{key}"
            try:
                numeric = float(value)
            except ValueError:
                summary["applied"][setting_path] = f"invalid float: {value!r}"
                continue
            try:
                previous = settings.get(setting_path)
            except Exception:
                previous = "<unreadable>"
            settings.set(setting_path, numeric)
            try:
                current = settings.get(setting_path)
            except Exception:
                current = "<unreadable>"
            summary["applied"][setting_path] = {
                "previous": previous,
                "requested": numeric,
                "current": current,
            }
        carb.log_warn(f"AirGround RTX tonemap settings applied: {summary}")
        return summary

    def _hide_default_stage_environment(self, stage) -> dict[str, Any]:
        """Hide the Kit default stage's environment helpers in the mission app.

        2026-09-13: the mission stage carries the Kit default stage's
        ``/Environment/defaultLight`` DistantLight (intensity 3000) *in addition*
        to the scene's own sun (DistantLight intensity 5000) and sky dome, while
        the replay app only references the scene's default prim.  The onboard RGB
        renders the same street with mean 241-246 and 55-62% of the lower half
        clipped at 255, while a replay render of the same camera spec renders
        mean ~131 with ~0.5% clipped.  This knob hides the app-level defaults so
        the mission uses the scene's own lighting only.
        """
        import carb

        tokens = [
            token.strip()
            for token in (
                os.environ.get("AIRGROUND_HIDE_DEFAULT_STAGE_ENV_PRIMS")
                or "/Environment/defaultLight,/Environment/defaultGroundPlane"
            ).split(",")
            if token.strip()
        ]
        summary: dict[str, Any] = {
            "enabled": AIRGROUND_HIDE_DEFAULT_STAGE_ENV,
            "hidden": [],
            "missing": [],
            "tokens": tokens,
        }
        if not AIRGROUND_HIDE_DEFAULT_STAGE_ENV:
            carb.log_warn(f"AirGround default stage environment kept: {summary}")
            return summary
        for token in tokens:
            prim = stage.GetPrimAtPath(token)
            if prim is None or not prim.IsValid():
                summary["missing"].append(token)
                continue
            # 2026-09-13: ``visibility`` does not stop RTX from drawing sensor
            # schema prims or lights (the Jackal lidar fan persisted with
            # ``visibility=invisible``), so deactivate the prim instead.
            deactivated = False
            try:
                deactivated = bool(prim.SetActive(False))
            except Exception as error:  # pragma: no cover - live USD edge case.
                summary["missing"].append(f"{token}: {type(error).__name__}: {error}")
                continue
            if not deactivated:
                summary["missing"].append(f"{token} (SetActive(False) returned false)")
                continue
            summary["hidden"].append(token)
        carb.log_warn(f"AirGround default stage environment hidden: {summary}")
        return summary

    def _dump_scene_materials(self, limit: int = 8) -> None:
        """Report the live material bindings of sampled scene meshes.

        2026-09-13: the mission app renders the scene's surfaces as flat white
        (the "white model" reviewers reported) while the replay app shows the
        textures, although the USD file binds materials to 4279/4280 meshes and
        the referenced MDLs resolve.  This dump records what the *live* stage
        sees so the binding and the RTX material path can be told apart.
        """
        import carb
        from pxr import UsdGeom, UsdShade

        stage = omni.usd.get_context().get_stage()
        if stage is None:
            return
        root = stage.GetPrimAtPath("/World/stage")
        if root is None or not root.IsValid():
            return
        reports: list[dict[str, Any]] = []
        meshes = bound = 0
        for prim in Usd.PrimRange(root):
            if not prim.IsA(UsdGeom.Mesh):
                continue
            meshes += 1
            material = UsdShade.MaterialBindingAPI(prim).ComputeBoundMaterial()[0]
            if not material:
                continue
            bound += 1
            if len(reports) >= max(1, int(limit)):
                continue
            mdl = None
            for child in material.GetPrim().GetChildren():
                if child.IsA(UsdShade.Shader):
                    asset = UsdShade.Shader(child).GetSourceAsset("mdl")
                    if asset is not None:
                        mdl = asset.resolvedPath or asset.path
                    break
            reports.append(
                {
                    "mesh": str(prim.GetPath()),
                    "material": str(material.GetPath()),
                    "mdl": mdl,
                }
            )
        carb.log_warn(
            f"AirGround scene material probe: meshes={meshes}, bound={bound}, samples={reports}"
        )

    def _dump_scene_lights(self) -> None:
        """Log every light prim so duplicated scene/app lights are visible."""
        import carb

        light_types = {
            "DomeLight",
            "DistantLight",
            "SphereLight",
            "RectLight",
            "DiskLight",
            "CylinderLight",
            "Light",
        }
        stage = omni.usd.get_context().get_stage()
        if stage is None:
            return
        lights: list[dict[str, Any]] = []
        for prim in stage.Traverse():
            if str(prim.GetTypeName()) not in light_types:
                continue
            entry: dict[str, Any] = {"path": str(prim.GetPath()), "type": str(prim.GetTypeName())}
            for attribute_name in ("inputs:intensity", "intensity", "inputs:exposure", "exposure",
                                   "visibility", "inputs:color"):
                attribute = prim.GetAttribute(attribute_name)
                if attribute is None:
                    continue
                try:
                    entry[attribute_name] = str(attribute.Get())
                except Exception:
                    entry[attribute_name] = "<unreadable>"
            lights.append(entry)
        carb.log_warn(f"AirGround scene light probe: count={len(lights)}, lights={lights}")

    def _dump_scene_visibility_probe(self) -> None:
        """Log computed visibility for the scene helpers that can wash out RGB.

        2026-09-13: the onboard ZED frames are high-key while the replay app
        (same scene, own camera) is not, so the scene-side sky/ground helpers
        are part of the comparison.  ``AIRGROUND_SCENE_VISIBILITY_TOKENS``
        overrides the probed path tokens.
        """
        from pxr import UsdGeom

        tokens = [
            token.strip()
            for token in (
                os.environ.get("AIRGROUND_SCENE_VISIBILITY_TOKENS")
                or "/World/Environment/sky,/World/AirGroundGroundSupportPlane,"
                "/World/AirGroundSensors,airground_dock_platform"
            ).split(",")
            if token.strip()
        ]
        stage = omni.usd.get_context().get_stage()
        if stage is None:
            return
        matches: list[dict[str, Any]] = []
        for prim in stage.Traverse():
            prim_path = str(prim.GetPath())
            if not any(token in prim_path for token in tokens):
                continue
            matches.append(
                {
                    "path": prim_path,
                    "purpose": str(UsdGeom.Imageable(prim).GetPurposeAttr().Get() or ""),
                    "type": str(prim.GetTypeName()),
                    "visibility": str(UsdGeom.Imageable(prim).ComputeVisibility()),
                }
            )
        carb.log_warn(
            "AirGround scene visibility probe: "
            f"matched={len(matches)}, tokens={tokens}, prims={matches[:40]}"
        )

    def _release_dock_on_arm(self) -> None:
        """``AIRGROUND_DOCK_RELEASE_ON_ARM``: remove this task's dock joint once its PX4 reports armed.

        The Isaac-side OFFBOARD lane (``_uav_control_offboard``) releases the joint after the arm ACK
        (policy ``after_arm_ack``); the planner lane's runner arms PX4 over its own MAVLink link and never
        asked for that release.  Most runtime-created joints did not hold in PhysX, so this went unseen
        until N=10: two UAVs per process whose joint did hold armed, saturated their rotors and never
        left the deck (gpd71 s7c1/s7g1 dock diagnostics: pose frozen, relative z 0.171/0.2145 m).
        """
        backends = self._uav_backends() if hasattr(self, "_uav_backends") else []

        def armed(backend: Any) -> bool:
            hub_armed = getattr(backend, "hub_armed", None)  # PX4 hub: the actuator message's armed flag
            return bool(hub_armed()) if callable(hub_armed) else bool(getattr(backend, "_armed", False))

        if not any(armed(backend) for backend in backends):
            return
        status = self.dock_joint.release()
        carb.log_warn(
            f"AirGround dock joint released on arm: {status.joint_path} (exists after release: {status.exists})"
        )
        self.dock_joint = None

    def _maintain_soft_dock_hold(self) -> None:
        """Keep the UAV on the Jackal deck until PX4 reports armed.

        2026-09-12: the Isaac 4.5 local route runs with the physical dock joint
        disabled.  The Quadcopter can then slide off the small deck during the
        long pre-arm dwell, which the UAV smoke's pre-arm gate correctly
        rejected.  The first latch implementation monitored only the
        articulation *root* while the chassis body slid off underneath it, so
        the hold now monitors and restores the real chassis body: restore the
        canonical body local pose and teleport the articulation root back to
        the settled dock pose (the same sequence used by episode reset).
        """
        if DOCK_RELEASE_ON_ARM and getattr(self, "dock_joint", None) is not None:
            self._release_dock_on_arm()
        if not getattr(self, "soft_dock_hold_active", False) or getattr(
            self, "soft_dock_hold_pose", None
        ) is None:
            return
        backends = self._uav_backends() if hasattr(self, "_uav_backends") else []
        if any(bool(getattr(backend, "_armed", False)) for backend in backends):
            self.soft_dock_hold_active = False
            carb.log_warn(
                "AirGround soft dock hold released: PX4 armed "
                f"(corrections={getattr(self, 'soft_dock_hold_correction_count', 0)})"
            )
            return
        stage = omni.usd.get_context().get_stage()
        body_path = f"{UAV_PRIM}{UAV_MAPPING.body_path}"
        try:
            body_position, body_orientation = prim_world_pose_wxyz(stage, body_path)
            root_position, root_orientation = prim_world_pose_wxyz(stage, UAV_PRIM)
        except Exception:
            return
        target_root, target_body = self.soft_dock_hold_pose
        reference_body = target_body if target_body is not None else (body_position, body_orientation)
        drift_m = math.dist(body_position, reference_body[0])
        dot = abs(
            sum(
                float(actual) * float(target)
                for actual, target in zip(body_orientation, reference_body[1])
            )
        )
        tilt_rad = 2.0 * math.acos(max(-1.0, min(1.0, dot)))
        # Let the vehicle settle onto the deck (the soft-dock clearance drop is
        # ~8cm) before latching the hold target.  Only intervene immediately if
        # the UAV is already falling off the deck.
        if getattr(self, "soft_dock_hold_settle_remaining", 0) > 0:
            self.soft_dock_hold_settle_remaining -= 1
            if drift_m <= 0.5 and tilt_rad <= 0.5:
                return
        elif not getattr(self, "soft_dock_hold_latched", False):
            # Do not latch a physically nonsensical dock pose (the default
            # (0,0) spawn lets the Jackal settle tilted ~50deg, which would then
            # be frozen into the soft dock and fail the PX4 attitude gate).
            world_up_tilt_rad = math.acos(
                max(
                    -1.0,
                    min(
                        1.0,
                        1.0
                        - 2.0
                        * (
                            float(body_orientation[1]) ** 2
                            + float(body_orientation[2]) ** 2
                        ),
                    ),
                )
            )
            if world_up_tilt_rad > SOFT_DOCK_HOLD_MAX_TILT_RAD:
                carb.log_warn(
                    "AirGround soft dock hold refuses to latch tilted pose: "
                    f"world_up_tilt_rad={world_up_tilt_rad:.4f} "
                    f"limit_rad={SOFT_DOCK_HOLD_MAX_TILT_RAD:.4f}"
                )
                self.soft_dock_hold_settle_remaining = SOFT_DOCK_HOLD_SETTLE_STEPS
                return
            self.soft_dock_hold_pose = (
                (
                    tuple(float(value) for value in root_position),
                    tuple(float(value) for value in root_orientation),
                ),
                (
                    tuple(float(value) for value in body_position),
                    tuple(float(value) for value in body_orientation),
                ),
            )
            self.soft_dock_hold_latched = True
            carb.log_warn(
                "AirGround soft dock hold latched settled pose: "
                f"body_drift_from_alignment_m={drift_m:.4f} body_tilt_rad={tilt_rad:.4f}"
            )
            return
        if (
            drift_m <= SOFT_DOCK_HOLD_TOLERANCE_M
            and tilt_rad <= SOFT_DOCK_HOLD_MAX_TILT_RAD
        ):
            return
        if not SOFT_DOCK_HOLD_CORRECT_ENABLED:
            if not getattr(self, "soft_dock_hold_correction_disabled_logged", False):
                self.soft_dock_hold_correction_disabled_logged = True
                carb.log_warn(
                    "AirGround soft dock hold detected body drift but corrections "
                    "are disabled (diagnostic-only): "
                    f"body_drift_m={drift_m:.4f} body_tilt_rad={tilt_rad:.4f}; "
                    "use the physical dock joint to hold the UAV"
                )
            return
        try:
            if self.uav_body_canonical_local_pose is not None:
                body_local_position, body_local_orientation = self.uav_body_canonical_local_pose
                set_local_prim_pose(
                    stage,
                    body_path,
                    body_local_position,
                    body_local_orientation,
                )
            set_articulation_root_world_pose(
                stage,
                UAV_PRIM,
                target_root[0],
                target_root[1],
            )
            self.soft_dock_hold_correction_count = (
                getattr(self, "soft_dock_hold_correction_count", 0) + 1
            )
            if (
                self.soft_dock_hold_correction_count <= 3
                or self.soft_dock_hold_correction_count % 100 == 0
            ):
                carb.log_warn(
                    "AirGround soft dock hold corrected UAV: "
                    f"body_drift_m={drift_m:.4f} body_tilt_rad={tilt_rad:.4f} "
                    f"corrections={self.soft_dock_hold_correction_count}"
                )
        except Exception as exc:
            carb.log_warn(f"AirGround soft dock hold correction failed: {exc}")

    def step_world(self, *, render: bool) -> None:
        """Advance the world one step; evidence sessions park here to share it."""
        scheduler = self.session_scheduler
        if scheduler is not None and scheduler.in_session():
            scheduler.park_for_step(bool(render))
            return
        self.world.step(render=render)

    def _run_session_step(self) -> None:
        """One shared step for every parked evidence session (main loop only)."""
        scheduler = self.session_scheduler
        render = scheduler.next_step_render()
        if render:
            self._tick_task_clocks(post=False)
        self.world.step(render=render)
        if render:
            self._tick_task_clocks(post=True)
        waiting = scheduler.take_parked()
        # Tasks without a session of their own still publish and accept requests;
        # a session they start here waits for the next step.
        busy = scheduler.active_owners()
        for app in self.task_apps:
            if app not in busy:
                app.activate_task()
                app.publish_runtime_state()
        scheduler.resume(waiting)

    def _retire_omnigraph_clock(self) -> None:
        """Leave this task's /clock to its Python publisher alone (AIRGROUND_SINGLE_CLOCK_PUBLISHER).

        Disconnects the PX4 graph's playback tick from its ROS2PublishClock node and makes the Python
        publisher emit the end-of-step stamp too, the scheme every later task runs. If the disconnect fails,
        both publishers stay as before and the failure is logged.
        """
        source, target = self.og_clock_tick_attrs
        try:
            og.Controller.disconnect(source, target)
        except Exception as exc:  # noqa: BLE001 - keep the original two-publisher clock
            carb.log_error(f"AirGround single /clock publisher: FALLBACK, disconnect {source} -> {target} failed: {exc}")
            return
        self.clock_posts_step_end = True
        carb.log_warn(f"AirGround single /clock publisher: OmniGraph clock tick disconnected ({target}); "
                      "the Python publisher emits both per-step stamps")

    def _tick_task_clocks(self, *, post: bool) -> None:
        """Replay the start-of-step /clock stamp (and, for later tasks, the end-of-step one)."""
        for app in self.task_apps:
            if app.clock_pre_tick is None or (post and not app.clock_posts_step_end):
                continue
            app.activate_task()
            app.clock_pre_tick.tick(self._simulation_time_s())

    def _log_dock_diagnostics(self, step_count: int) -> None:
        """Diagnostic only (AIRGROUND_DOCK_DIAG): per-task UGV base / UAV chassis poses and the dock joint prim."""
        from omni.isaac.dynamic_control import _dynamic_control
        from pxr import UsdPhysics

        dc = _dynamic_control.acquire_dynamic_control_interface()
        stage = omni.usd.get_context().get_stage()
        rows = []
        for app in self.task_apps:
            values = getattr(getattr(app, "task", None), "values", None) or {}
            ugv_body = f"{values.get('UGV_PRIM', UGV_PRIM)}/base_link"
            uav_body = f"{values.get('UAV_PRIM', UAV_PRIM)}{UAV_MAPPING.body_path}"
            row: dict[str, Any] = {"task": getattr(app.task, "task_id", None), "ugv": ugv_body, "uav": uav_body}
            for key, path in (("ugv_pose", ugv_body), ("uav_pose", uav_body)):
                handle = dc.get_rigid_body(path)
                if handle:
                    pose = dc.get_rigid_body_pose(handle)
                    row[key] = [round(float(v), 4) for v in (pose.p.x, pose.p.y, pose.p.z, pose.r.x, pose.r.y, pose.r.z, pose.r.w)]
                    if key == "uav_pose":
                        w = dc.get_rigid_body_angular_velocity(handle)
                        row["uav_angular_velocity"] = [round(float(v), 4) for v in (w.x, w.y, w.z)]
            if "ugv_pose" in row and "uav_pose" in row:
                row["relative_z_m"] = round(row["uav_pose"][2] - row["ugv_pose"][2], 4)
            joint_path = getattr(getattr(app, "task", None), "dock_joint_path", None)
            prim = stage.GetPrimAtPath(joint_path) if joint_path else None
            if prim is not None and prim.IsValid():
                joint = UsdPhysics.Joint(prim)
                row["joint"] = {
                    "path": joint_path,
                    "enabled": bool(joint.GetJointEnabledAttr().Get()),
                    "body0": [str(t) for t in joint.GetBody0Rel().GetTargets()],
                    "body1": [str(t) for t in joint.GetBody1Rel().GetTargets()],
                    "local_pos0": [float(v) for v in (joint.GetLocalPos0Attr().Get() or (0, 0, 0))],
                    "exclude_from_articulation": bool(joint.GetExcludeFromArticulationAttr().Get()),
                    "collision_enabled": bool(joint.GetCollisionEnabledAttr().Get()),
                }
            else:
                row["joint"] = {"path": joint_path, "valid": False}
            rows.append(row)
        carb.log_warn("AirGround dock diagnostics: " + json.dumps({"step": int(step_count), "tasks": rows}, sort_keys=True))

    def _prefetch_ugv_clouds(self) -> None:
        """SimMT-5 opt-in (AIRGROUND_UGV_CLOUD_BATCH): one GPU query for every task's due UGV cloud.

        Each task's publisher still publishes its own cloud in its own turn; it takes the prefetched hits
        only when its pose is exactly the one queried here (same stage pose read), else queries alone.
        """
        wrapper = _SHARED_GPU_CLOUD
        backend = getattr(wrapper, "backend", None) if wrapper is not None else None
        if backend is None or not callable(getattr(backend, "prefetch", None)):
            return
        sim_time_s = self._simulation_time_s()
        stage = omni.usd.get_context().get_stage()
        poses = []
        config = None
        for app in self.task_apps:
            publisher = getattr(app, "ugv_proximity_cloud_publisher", None)
            if publisher is None or getattr(publisher, "raycast_fn", None) is not wrapper:
                continue
            if not publisher.due(sim_time_s):
                continue
            task = getattr(app, "task", None)
            values = getattr(task, "values", None)
            body_path = values["UGV_SENSOR_BODY_PATH"] if values is not None else UGV_SENSOR_BODY_PATH
            try:
                poses.append(prim_world_pose_wxyz(stage, body_path))
            except Exception:
                continue
            config = publisher.config
        if len(poses) >= 2:
            backend.prefetch(poses, config)

    def _publish_all_tasks(self) -> None:
        """Publish every task's state (one task in the single-task flow)."""
        if AIRGROUND_UGV_CLOUD_BATCH and len(self.task_apps) > 1:
            try:
                self._prefetch_ugv_clouds()
            except Exception as exc:  # the per-task path still publishes every cloud
                carb.log_warn(f"AirGround batched UGV cloud prefetch failed: {exc}")
        fleet = self._fleet_state_publisher()
        if fleet is None:
            for app in self.task_apps:
                app.activate_task()
                app.publish_runtime_state()
            return
        # SimMT-5f: the per-task order is dock hold, UAV state, UGV state, then the rest; the dock hold
        # may move the UAV, so every hold runs before the fleet publication reads the poses.
        for app in self.task_apps:
            app.activate_task()
            app._maintain_soft_dock_hold()
        if _STAGE_TIMER is not None:
            _STAGE_TIMER.begin("publish.fleet_state")
        # True also for a state-cadence skip (AIRGROUND_STATE_PUBLISH_EVERY_STEPS > 1): nothing to publish
        # per task on that step, so the per-task publishers below must stay off.
        try:
            state_published = fleet.publish()
        finally:
            if _STAGE_TIMER is not None:
                _STAGE_TIMER.end("publish.fleet_state")
        for app in self.task_apps:
            app.activate_task()
            app.publish_runtime_state(dock_hold_done=True, state_published=state_published)

    def _fleet_state_publisher(self) -> Any:
        """The SimMT-5f fleet state publisher (``AIRGROUND_STATE_PUBLISH_FLEET``), created on first use."""
        fleet = getattr(self, "_fleet_state", None)
        if fleet is None:
            from fleet_state_publish import ENABLED, FleetStatePublisher
            if not ENABLED or len(self.task_apps) < 2:
                self._fleet_state = False
                return None
            import physics_pose_reader
            fleet = self._fleet_state = FleetStatePublisher(
                self.task_apps, pose_reader_fast=physics_pose_reader.FAST_BOUND_POSE)
            carb.log_warn(f"AirGround fleet state publish enabled: {fleet.summary()}")
        return fleet or None

    def publish_runtime_state(self, *, spin_evidence_server: bool = True, dock_hold_done: bool = False,
                              state_published: bool = False) -> None:
        if not dock_hold_done:
            self._maintain_soft_dock_hold()
        sim_time_s = self._simulation_time_s()
        publish_count = self._runtime_state_publish_count + 1

        def _trace(stage: str) -> None:
            if _STAGE_TIMER is not None:
                _STAGE_TIMER.mark("publish." + stage)
            if not AIRGROUND_STATE_PUBLISH_TRACE_STAGES:
                return
            if AIRGROUND_STATE_PUBLISH_DEBUG_EVERY_N > 0 and publish_count % AIRGROUND_STATE_PUBLISH_DEBUG_EVERY_N != 0:
                return
            payload = {
                "count": publish_count,
                "monotonic_s": time.monotonic(),
                "wall_time_s": time.time(),
                "sim_time_s": round(float(sim_time_s), 6),
                "stage": stage,
            }
            if AIRGROUND_MAIN_LOOP_TRACE_EVERY_N > 0:
                # Trace-only: which publish stage a /clock message arrives in.
                payload["clock_msgs"] = self._clock_message_probe().get("msgs")
            if not AIRGROUND_STATE_PUBLISH_DEBUG_FILE:
                carb.log_warn(
                    "AirGround runtime state publish stage: "
                    f"count={publish_count}, sim_time_s={payload['sim_time_s']:.3f}, stage={stage}"
                )
            if AIRGROUND_STATE_PUBLISH_DEBUG_FILE:
                try:
                    with open(AIRGROUND_STATE_PUBLISH_DEBUG_FILE, "a", encoding="utf-8") as stream:
                        stream.write(json.dumps(payload, sort_keys=True) + "\n")
                except Exception as exc:
                    carb.log_warn(f"AirGround state publish debug file write failed: {exc}")

        _trace("begin")
        if _STAGE_TIMER is not None and not getattr(self, "_airground_pubs_timed", False):
            # Diagnostic only: time each rclpy ``publish`` call of the state publishers.
            self._airground_pubs_timed = True
            for _owner, _label in ((self.uav_state_publisher, "uav"), (self.ugv_state_publisher, "ugv")):
                for _attr in ("odom_pub", "pose_pub", "tf_pub", "joint_pub", "status_pub", "clock_pub"):
                    _publisher = getattr(_owner, _attr, None) if _owner is not None else None
                    if _publisher is None:
                        continue

                    def _make(publisher: Any, kind: str) -> Any:
                        original_publish = publisher.publish

                        def _timed_publish(message: Any) -> Any:
                            _STAGE_TIMER.begin(kind)
                            try:
                                return original_publish(message)
                            finally:
                                _STAGE_TIMER.end(kind)

                        return _timed_publish

                    try:
                        _publisher.publish = _make(_publisher, f"pub.{_label}.{_attr[:-4]}")
                    except Exception as exc:  # pragma: no cover - diagnostic only
                        carb.log_warn(f"AirGround publish timing skipped for {_label}.{_attr}: {exc}")
        if self.uav_state_publisher is not None and not state_published:
            _trace("before_uav_state")
            self.uav_state_publisher.publish(sim_time_s)
            _trace("after_uav_state")
        if self.ugv_state_publisher is not None and not state_published:
            _trace("before_ugv_state")
            self.ugv_state_publisher.publish(self.ugv, sim_time_s)
            _trace("after_ugv_state")
        if self.ugv_contact_publisher is not None:
            _trace("before_ugv_contact")
            self.ugv_contact_publisher.publish(sim_time_s)
            _trace("after_ugv_contact")
        pose_stage = None
        # One USD pose read per step shared by the scan and the cloud (both sample the same body prim, and
        # neither writes USD in between), so a step where both are due reads it once.
        ugv_body_pose = None
        if self.ugv_proximity_scan_publisher is not None:
            _trace("before_ugv_scan")
            _scan_due = getattr(self.ugv_proximity_scan_publisher, "due", None)
            if _scan_due is None or _scan_due(sim_time_s):
                try:
                    pose_stage = omni.usd.get_context().get_stage()
                    position, orientation_wxyz = prim_world_pose_wxyz(pose_stage, UGV_SENSOR_BODY_PATH)
                    ugv_body_pose = (position, orientation_wxyz)
                    self.ugv_proximity_scan_publisher.publish(
                        position,
                        _airground_yaw_from_wxyz(orientation_wxyz),
                        sim_time_s,
                    )
                except Exception as exc:
                    carb.log_warn(f"UGV proximity scan publish failed: {exc}")
            _trace("after_ugv_scan")
        if self.ugv_proximity_cloud_publisher is not None:
            _trace("before_ugv_cloud")
            _cloud_due = getattr(self.ugv_proximity_cloud_publisher, "due", None)
            if _cloud_due is None or _cloud_due(sim_time_s):
                try:
                    if ugv_body_pose is None:
                        if pose_stage is None:
                            pose_stage = omni.usd.get_context().get_stage()
                        ugv_body_pose = prim_world_pose_wxyz(pose_stage, UGV_SENSOR_BODY_PATH)
                    position, orientation_wxyz = ugv_body_pose
                    # 2026-09-19: the 3D fan is cast with the body's *full* attitude.
                    # Passing only the yaw left the ground returns level while the
                    # tf2 chain rotated them by the real pitch/roll, so a pitching
                    # chassis manufactured phantom lethal rings in both costmaps
                    # (measured live on ``smoke_20260919_105956_type-i``).
                    self.ugv_proximity_cloud_publisher.publish(
                        position,
                        orientation_wxyz,
                        sim_time_s,
                    )
                except Exception as exc:
                    carb.log_warn(f"UGV 3D proximity cloud publish failed: {exc}")
            _trace("after_ugv_cloud")
        if self.rgbd_camera_publisher is not None:
            _trace("before_rgbd")
            self.rgbd_camera_publisher.publish(sim_time_s)
            _trace("after_rgbd")
        if spin_evidence_server and self.full_mission_evidence_server is not None:
            _trace("before_evidence")
            self.full_mission_evidence_server.spin_once()
            _trace("after_evidence")
        self._runtime_state_publish_count = publish_count
        if _STAGE_TIMER is not None:
            _STAGE_TIMER.break_chain()
        if (
            AIRGROUND_STATE_PUBLISH_DEBUG_EVERY_N > 0
            and self._runtime_state_publish_count % AIRGROUND_STATE_PUBLISH_DEBUG_EVERY_N == 0
        ):
            heartbeat_payload = {
                "count": self._runtime_state_publish_count,
                "rgbd_pub": self.rgbd_camera_publisher is not None,
                "sim_time_s": round(float(sim_time_s), 6),
                "uav_pub": self.uav_state_publisher is not None,
                "ugv_pub": self.ugv_state_publisher is not None,
            }
            rgbd_rate: dict[str, Any] = {}
            if self.rgbd_camera_publisher is not None:
                # Camera topic rate in simulated vs wall time: the benchmark
                # rate contract is in simulated seconds, so this ratio is the
                # run's real-time factor as an observer sees it.
                rgbd_rate = self.rgbd_camera_publisher.rate_diagnostics()
                heartbeat_payload["rgbd_rate"] = rgbd_rate
            heartbeat_payload["render_schedule"] = {
                "render_every_n_steps": int(AIRGROUND_RENDER_PULSE_EVERY_N),
                "render_hz": round(float(AIRGROUND_RENDER_HZ), 3),
                "rgbd_publish_hz": round(float(AIRGROUND_RGBD_PUBLISHER_HZ), 3),
                # Camera-aligned rendering: renders should track the camera
                # publishes instead of the fixed cadence's surplus.
                "render_on_camera_due": bool(AIRGROUND_RENDER_ON_CAMERA_DUE),
                "render_steps": int(getattr(self, "_render_step_count", 0)),
            }
            render_schedule = heartbeat_payload.get("render_schedule", {})
            carb.log_warn(
                "AirGround runtime state publish heartbeat: "
                f"count={heartbeat_payload['count']}, sim_time_s={heartbeat_payload['sim_time_s']:.3f}, "
                f"uav_pub={heartbeat_payload['uav_pub']}, "
                f"ugv_pub={heartbeat_payload['ugv_pub']}, "
                f"rgbd_pub={heartbeat_payload['rgbd_pub']}, "
                # Render steps should track the camera publishes once the
                # camera-aligned gate is on (this line is the alignment check).
                f"render_steps={render_schedule.get('render_steps')}, "
                f"render_on_camera_due={render_schedule.get('render_on_camera_due')}, "
                # Contract check: the camera must keep its simulated-time rate
                # even when renders are aligned to its publishes.
                f"rgbd_sim_hz={rgbd_rate.get('sim_hz')}, rgbd_wall_hz={rgbd_rate.get('wall_hz')}, "
                f"rgbd_publishes={rgbd_rate.get('publish_count')}"
            )
            if AIRGROUND_STATE_PUBLISH_DEBUG_FILE:
                try:
                    with open(AIRGROUND_STATE_PUBLISH_DEBUG_FILE, "a", encoding="utf-8") as stream:
                        stream.write(json.dumps(heartbeat_payload, sort_keys=True) + "\n")
                except Exception as exc:
                    carb.log_warn(f"AirGround state publish debug file write failed: {exc}")

    def _camera_frame_due(self) -> bool | None:
        """True when this iteration should render for a due camera publish.

        ``world.step(render=True)`` advances the timeline by the rendering dt and
        runs the whole Kit update; ``render=False`` only advances physics.  A
        render therefore both refreshes the camera render product and moves the
        simulated clock further, so the gate asks whether the publish the camera
        publisher will make *after* this iteration is already due.  Returning
        None keeps the caller on the fixed cadence (no publisher available).
        """
        publishers = [
            publisher
            for app in self.task_apps
            if (publisher := getattr(app, "rgbd_camera_publisher", None)) is not None
            and hasattr(publisher, "would_publish")
        ]
        if not publishers:
            return None
        try:
            current_s = float(self._simulation_time_s())
            rendering_dt = float(self.world.get_rendering_dt())
        except Exception as exc:
            carb.log_warn(f"AirGround camera-aligned render gate unavailable: {exc}")
            return None
        return any(bool(publisher.would_publish(current_s + rendering_dt)) for publisher in publishers)

    def _render_for_main_loop_step(self, step_count: int) -> bool:
        if not (
            AIRGROUND_RENDER
            and AIRGROUND_RENDER_MAIN_LOOP_MODE == "world_step"
            and int(step_count) >= max(0, AIRGROUND_RENDER_STARTUP_WARMUP_STEPS)
        ):
            return False
        if AIRGROUND_RENDER_ON_CAMERA_DUE:
            due = self._camera_frame_due()
            if due is not None:
                return bool(due)
        return int(step_count) % AIRGROUND_RENDER_PULSE_EVERY_N == 0

    def _render_pulse_for_main_loop_step(self, step_count: int) -> bool:
        return bool(
            AIRGROUND_RENDER
            and AIRGROUND_RENDER_MAIN_LOOP_MODE == "replicator_pulse"
            and int(step_count) >= max(0, AIRGROUND_RENDER_STARTUP_WARMUP_STEPS)
            and int(step_count) % AIRGROUND_RENDER_PULSE_EVERY_N == 0
        )

    def _replicator_render_pulse(self) -> None:
        import omni.replicator.core as rep

        rep.orchestrator.step(rt_subframes=1, delta_time=0.0, pause_timeline=False)

    def _app_update_counter(self) -> int | None:
        counter = getattr(self, "_app_update_counter_state", None)
        if counter is None:
            counter = {"count": 0, "subscription": None}
            try:
                import omni.kit.app

                def _on_update(_event: Any) -> None:
                    counter["count"] += 1

                counter["subscription"] = (
                    omni.kit.app.get_app()
                    .get_update_event_stream()
                    .create_subscription_to_pop(_on_update, name="airground_main_loop_trace_update_counter")
                )
            except Exception as exc:
                carb.log_warn(f"AirGround app update counter unavailable: {exc}")
                counter["count"] = None
            self._app_update_counter_state = counter
        return counter["count"]

    def _clock_message_probe(self) -> dict[str, Any]:
        """In-process /clock subscriber (trace only): message vs distinct-stamp counts."""
        state = getattr(self, "_clock_probe_state", None)
        if state is None:
            state = {"msgs": 0, "stamps": set(), "node": None, "sub": None}
            try:
                import rclpy
                from rosgraph_msgs.msg import Clock
                from rclpy.qos import QoSProfile, ReliabilityPolicy

                if not rclpy.ok():
                    rclpy.init(args=None)
                state["rclpy"] = rclpy
                state["node"] = rclpy.create_node("airground_clock_cadence_probe")

                stamp_log = None
                if AIRGROUND_MAIN_LOOP_TRACE_FILE:
                    stamp_path = Path(AIRGROUND_MAIN_LOOP_TRACE_FILE + ".clock")
                    stamp_path.parent.mkdir(parents=True, exist_ok=True)
                    stamp_log = open(stamp_path, "a", encoding="utf-8", buffering=1)

                def _on_clock(msg: Any) -> None:
                    state["msgs"] += 1
                    stamp = (int(msg.clock.sec), int(msg.clock.nanosec))
                    state["stamps"].add(stamp)
                    if stamp_log is not None:
                        # received_monotonic_s aligns the stamp with the main-loop trace rows.
                        stamp_log.write(f"{stamp[0]}.{stamp[1]:09d} {time.monotonic():.6f}\n")

                state["sub"] = state["node"].create_subscription(
                    Clock,
                    "/clock",
                    _on_clock,
                    QoSProfile(depth=2000, reliability=ReliabilityPolicy.RELIABLE),
                )
            except Exception as exc:
                carb.log_warn(f"AirGround clock cadence probe unavailable: {exc}")
                state["node"] = None
            self._clock_probe_state = state
        node = state.get("node")
        if node is None:
            return {}
        self._instrument_camera_reads_for_clock_probe(state)
        try:
            state["rclpy"].spin_once(node, timeout_sec=0.0)
            publishers = node.count_publishers("/clock")
        except Exception:
            publishers = None
        return {
            "msgs": state["msgs"],
            "distinct": len(state["stamps"]),
            "publishers": publishers,
            "by_call": dict(state.get("by_call") or {}) or None,
        }

    def _instrument_camera_reads_for_clock_probe(self, state: dict[str, Any]) -> None:
        """Trace only: attribute extra /clock messages to individual camera read calls."""
        if state.get("instrumented") or state.get("instrumenting"):
            return
        publisher = getattr(self, "rgbd_camera_publisher", None)
        streams = getattr(publisher, "_streams", None)
        if not streams:
            return
        state["instrumenting"] = True
        by_call: dict[str, int] = {}
        state["by_call"] = by_call
        node = state["node"]
        rclpy = state["rclpy"]

        def wrap(owner: Any, name: str, label: str) -> None:
            original = getattr(owner, name, None)
            if not callable(original):
                return

            def wrapper(*args: Any, **kwargs: Any) -> Any:
                rclpy.spin_once(node, timeout_sec=0.002)
                before = state["msgs"]
                try:
                    return original(*args, **kwargs)
                finally:
                    rclpy.spin_once(node, timeout_sec=0.01)
                    by_call[label] = by_call.get(label, 0) + (state["msgs"] - before)

            setattr(owner, name, wrapper)

        for index, stream in enumerate(streams):
            camera = stream.get("camera")
            for method in ("get_rgb", "get_rgba", "get_depth", "get_current_frame"):
                wrap(camera, method, f"cam{index}.{method}")
        for method in ("_maybe_apply_camera_stage", "_camera_info_message", "_image_message"):
            wrap(publisher, method, f"publisher.{method}")
        state["instrumented"] = True

    def _trace_main_loop(
        self,
        stage: str,
        *,
        step_count: int,
        render: bool,
        render_pulse: bool = False,
    ) -> None:
        if AIRGROUND_MAIN_LOOP_TRACE_EVERY_N <= 0:
            return
        if step_count % AIRGROUND_MAIN_LOOP_TRACE_EVERY_N != 0:
            return
        try:
            sim_time_s: float | None = round(float(self._simulation_time_s()), 6)
        except Exception as exc:
            carb.log_warn(f"AirGround main loop trace sim_time read failed: {exc}")
            sim_time_s = None
        # Kit app-update counter: tells an extra app update per render step
        # (which publishes an extra /clock tick) apart from a graph that runs
        # twice per update.  Only active while tracing, so default runs are
        # unchanged.
        app_update_count = self._app_update_counter()
        clock_probe = self._clock_message_probe()
        payload = {
            "app_update_count": app_update_count,
            "clock_msgs": clock_probe.get("msgs"),
            "clock_distinct_stamps": clock_probe.get("distinct"),
            "clock_publishers": clock_probe.get("publishers"),
            "clock_by_call": clock_probe.get("by_call"),
            "monotonic_s": round(time.monotonic(), 6),
            "render": bool(render),
            "render_main_loop_mode": AIRGROUND_RENDER_MAIN_LOOP_MODE,
            "render_pulse": bool(render_pulse),
            "sim_time_s": sim_time_s,
            "stage": stage,
            "step_count": int(step_count),
            "startup_warmup_steps": int(AIRGROUND_RENDER_STARTUP_WARMUP_STEPS),
            "wall_time_s": round(time.time(), 6),
        }
        sim_time_display = "n/a" if sim_time_s is None else f"{sim_time_s:.3f}"
        if not AIRGROUND_MAIN_LOOP_TRACE_FILE:
            carb.log_warn(
                "AirGround main loop trace: "
                f"step={payload['step_count']}, sim_time_s={sim_time_display}, "
                f"render={payload['render']}, render_pulse={payload['render_pulse']}, "
                f"render_mode={payload['render_main_loop_mode']}, stage={stage}"
            )
        if AIRGROUND_MAIN_LOOP_TRACE_FILE:
            try:
                trace_path = Path(AIRGROUND_MAIN_LOOP_TRACE_FILE)
                trace_path.parent.mkdir(parents=True, exist_ok=True)
                with open(trace_path, "a", encoding="utf-8") as stream:
                    stream.write(json.dumps(payload, sort_keys=True) + "\n")
            except Exception as exc:
                carb.log_warn(f"AirGround main loop trace file write failed: {exc}")

    def run(self):
        if _STAGE_TIMER is not None:
            _log_python_speed_probe()
        self._fabric_state = None
        self._native_vehicle_math = None
        if USE_FABRIC_STATE:
            tools = str(Path(__file__).resolve().parents[1] / "tools")
            if tools not in sys.path:
                sys.path.insert(0, tools)
            from physics_pose_reader import FabricRuntime
            self._fabric_state = FabricRuntime(self)
            self._fabric_state.activate()
            for task_app in self.task_apps:
                # One runtime serves every task of the shared world (per-task reset flows and
                # the native vehicle math look it up on their own app).
                if task_app is not self:
                    task_app._fabric_state = self._fabric_state
        if NATIVE_VEHICLE_MATH_LIBRARY:
            for task_app in self.task_apps:
                task_app.activate_task()
                task_app._native_vehicle_math = task_app._build_native_vehicle_math()
            self.activate_task()
        if _env_bool("AIRGROUND_RUNTIME_HOTPATH_TUNING", False):
            from runtime_hotpath_tuning import RuntimeHotpathTuning
            nodes = [publisher.node for name in ("uav_state_publisher", "ugv_state_publisher",
                     "ugv_contact_publisher", "rgbd_camera_publisher", "full_mission_evidence_server")
                     if (publisher := getattr(self, name, None)) is not None]
            self._runtime_hotpath_tuning = RuntimeHotpathTuning(nodes=nodes)
            self._runtime_hotpath_tuning.activate()
        _trace_startup("before_main_loop", physics_dt_s=self.world.get_physics_dt(),
                       rendering_dt_s=self.world.get_rendering_dt())
        if self.play_on_start:
            self.timeline.play()
        else:
            self.timeline.stop()

        # Optional sim-side UAV-control diagnostics (HIL actuator reception rate,
        # per-step RX depth and ``command_lag_s`` from the PX4 MAVLink backend).
        # The evidence-server lane configures these per attempt, but the external
        # OFFBOARD runner never does, so lockstep/real-time questions had no
        # sim-side counters to read.
        if _env_bool("AIRGROUND_UAV_CONTROL_DIAGNOSTICS", False):
            try:
                diagnostics_dir = Path(
                    os.environ.get(
                        "AIRGROUND_UAV_CONTROL_DIAGNOSTICS_DIR",
                        "/tmp/airground_uav_control_diag",
                    )
                )
                diagnostics_owner = self.full_mission_evidence_server
                if diagnostics_owner is None or not hasattr(
                    diagnostics_owner, "_configure_uav_control_diagnostics"
                ):
                    raise RuntimeError(
                        "full-mission evidence server is unavailable; cannot enable "
                        "sim-side UAV control diagnostics"
                    )
                diagnostics_summary = diagnostics_owner._configure_uav_control_diagnostics(
                    diagnostics_dir, 0
                )
                carb.log_warn(
                    "AirGround UAV control diagnostics enabled: "
                    f"{json.dumps(diagnostics_summary, sort_keys=True)[:500]}"
                )
            except Exception as exc:  # pragma: no cover - diagnostic only
                carb.log_warn(f"AirGround UAV control diagnostics setup failed: {exc}")

        step_count = 0
        self._render_step_count = 0
        profile_steps = int(os.environ.get("AIRGROUND_RUNTIME_PROFILE_STEPS") or "0")
        runtime_profile = None
        if profile_steps > 0:
            import cProfile
            runtime_profile = cProfile.Profile()
            runtime_profile.enable()
        while simulation_app.is_running() and not self.stop_sim:
            try:
                if self.session_scheduler is not None and self.session_scheduler.has_parked():
                    # An evidence session is waiting for a step: take it for all of them.
                    if _MAIN_LOOP_WATCHDOG is not None:
                        _MAIN_LOOP_WATCHDOG.beat(step_count, "session_step")
                    self._run_session_step()
                    continue
                render_step = self._render_for_main_loop_step(step_count)
                if render_step:
                    self._render_step_count += 1
                render_pulse = self._render_pulse_for_main_loop_step(step_count)
                self._trace_main_loop(
                    "before_world_step",
                    step_count=step_count,
                    render=render_step,
                    render_pulse=render_pulse,
                )
                if render_step:
                    self._tick_task_clocks(post=False)
                _step_stage = "world_step.render" if render_step else "world_step.physics"
                if _MAIN_LOOP_WATCHDOG is not None:
                    _MAIN_LOOP_WATCHDOG.beat(step_count, _step_stage)
                if _STAGE_TIMER is not None:
                    _STAGE_TIMER.begin(_step_stage)
                    _world_step_split_begin()
                self.world.step(render=render_step)
                if _MAIN_LOOP_WATCHDOG is not None:
                    _MAIN_LOOP_WATCHDOG.beat(step_count, "after_world_step")
                if _STAGE_TIMER is not None:
                    _world_step_split_end("render" if render_step else "physics")
                    _STAGE_TIMER.end(_step_stage)
                if render_step:
                    self._tick_task_clocks(post=True)
                self._trace_main_loop(
                    "after_world_step",
                    step_count=step_count,
                    render=render_step,
                    render_pulse=render_pulse,
                )
                if render_pulse:
                    self._trace_main_loop(
                        "before_render_pulse",
                        step_count=step_count,
                        render=render_step,
                        render_pulse=True,
                    )
                    self._replicator_render_pulse()
                    self._trace_main_loop(
                        "after_render_pulse",
                        step_count=step_count,
                        render=render_step,
                        render_pulse=True,
                    )
                step_count += 1
                self._trace_main_loop(
                    "before_publish",
                    step_count=step_count,
                    render=render_step,
                    render_pulse=render_pulse,
                )
                self._publish_all_tasks()
                if AIRGROUND_DOCK_DIAG and step_count % 1000 == 0:
                    self._log_dock_diagnostics(step_count)
                if _STAGE_TIMER is not None and step_count % max(1, AIRGROUND_STAGE_TIMING_EVERY_N) == 0:
                    _now = time.perf_counter()
                    _last = getattr(self, "_stage_timing_last", None)
                    _wall = None if _last is None else round(_now - _last[0], 3)
                    _steps = None if _last is None else step_count - _last[1]
                    self._stage_timing_last = (_now, step_count)
                    if _wall is not None and _steps:
                        carb.log_warn(
                            "AirGround stage timing: "
                            + json.dumps(
                                {
                                    "tasks": len(self.task_apps),
                                    "steps": _steps,
                                    "wall_s": _wall,
                                    "loop_ms_per_step": round(1000.0 * _wall / _steps, 3),
                                    "stages": _STAGE_TIMER.snapshot(reset=True),
                                    **({"usd_changes": _usd_change_probe_snapshot()} if AIRGROUND_USD_CHANGE_PROBE else {}),
                                    **({"physx_profile": _physx_profile_snapshot(),
                                        "physx_scene_stats": _physx_scene_stats()} if AIRGROUND_PHYSX_PROFILE else {}),
                                },
                                sort_keys=True,
                            )
                        )
                self._trace_main_loop(
                    "after_publish",
                    step_count=step_count,
                    render=render_step,
                    render_pulse=render_pulse,
                )
                if runtime_profile is not None and step_count >= profile_steps:
                    runtime_profile.disable()
                    profile_path = os.environ.get("AIRGROUND_RUNTIME_PROFILE_FILE")
                    if not profile_path:
                        raise ValueError("AIRGROUND_RUNTIME_PROFILE_FILE required when profiling")
                    Path(profile_path).parent.mkdir(parents=True, exist_ok=True)
                    runtime_profile.dump_stats(profile_path)
                    runtime_profile = None
                    carb.log_warn(f"AirGround runtime CPU profile saved: {profile_path}")
                if MAX_STEPS > 0 and step_count >= MAX_STEPS:
                    carb.log_warn(f"AIRGROUND_MAX_STEPS reached: {MAX_STEPS}")
                    break
            except Exception as e:
                carb.log_error(f"Error during simulation step: {e}")
                break

        carb.log_warn("Closing simulation.")
        capture = getattr(self,'_main_loop_capture',None)
        if capture is not None and not capture.closed:
            capture.finish(error='simulation stopped before the requested capture completed')
        for task_app in self.task_apps:
            if getattr(task_app, "_native_vehicle_math", None) is not None:
                task_app._native_vehicle_math.close()
        if self._fabric_state is not None:
            self._fabric_state.close()
        tuning = getattr(self, "_runtime_hotpath_tuning", None)
        if tuning is not None:
            tuning.close()
        self.timeline.stop()
        for _ in range(AIRGROUND_POST_STOP_UPDATES):
            omni.kit.app.get_app().update()
        if self.uav_state_publisher is not None:
            self.uav_state_publisher.close()
        if self.ugv_state_publisher is not None:
            self.ugv_state_publisher.close()
        if self.ugv_contact_publisher is not None:
            self.ugv_contact_publisher.close()
        if self.native_state_bridge is not None:
            self.native_state_bridge.close()
        if self.ugv_proximity_scan_publisher is not None:
            self.ugv_proximity_scan_publisher.close()
        if self.ugv_proximity_cloud_publisher is not None:
            self.ugv_proximity_cloud_publisher.close()
        if self.rgbd_camera_publisher is not None:
            self.rgbd_camera_publisher.close()
        if self.clock_pre_tick is not None:
            self.clock_pre_tick.close()
        if self.full_mission_evidence_server is not None:
            self.full_mission_evidence_server.close()
        stop_px4_autolaunch_processes()
        if AIRGROUND_SKIP_CLEANUP_ON_CLOSE:
            carb.log_warn("AirGround fast headless exit.")
            sys.stdout.flush()
            sys.stderr.flush()
            os._exit(0)
        simulation_app.close(
            wait_for_replicator=not AIRGROUND_HEADLESS,
            skip_cleanup=AIRGROUND_SKIP_CLEANUP_ON_CLOSE,
        )


def build_apps() -> "PegasusApp":
    """Build the single legacy task, or every task of ``AIRGROUND_TASKS_JSON`` in one world."""
    if len(TASKS) == 1:
        return PegasusApp()
    if not AIRGROUND_COOPERATIVE_SESSIONS:
        raise RuntimeError("AIRGROUND_TASKS_JSON with several tasks needs AIRGROUND_COOPERATIVE_SESSIONS=true")
    # The native state bridge (one rclcpp context per task, ROS domain from the task), the Fabric
    # pose lane (root bindings for every task) and the native vehicle math (per vehicle) are all
    # per-task now; the math still needs the Fabric lane, as in a single task.
    if NATIVE_VEHICLE_MATH_LIBRARY and not USE_FABRIC_STATE:
        raise RuntimeError("native vehicle math needs AIRGROUND_USE_FABRIC_STATE=true (the live Fabric pose lane)")
    host: PegasusApp | None = None
    for task in TASKS:
        app = PegasusApp(host=host, defer_reset=True, task=task)
        host = host or app
    assert host is not None
    host.reset_host_world()
    if _env_bool("AIRGROUND_DOCK_ALL_BEFORE_STEP", True):
        # SimMT-2d fix (default for several tasks): dock every task before any finish_task advances the
        # shared world.  Docking task k>=1 after earlier tasks' Kit updates had stepped PhysX left its
        # UAV resting 7 cm low on its UGV when the joint was created; the joint was then not enforced
        # (or, excluded from the articulation, snapped the pair over) and PX4 EKF2 never initialised.
        # Evidence: runs/simmt/d14_{excl,first} (docs/development/simmt/evidence-03-px4hub-physics-n4.md).
        stage = omni.usd.get_context().get_stage()
        if _env_bool("AIRGROUND_UGV_INIT_BEFORE_DOCK", False):
            # SimMT-7: the single-task order (finish_task: UGV initialize/post_reset, then align + dock) for
            # every task before any docks.  Docking all first left each UGV's initialize/post_reset to its
            # finish_task, after earlier tasks' finish_task had advanced Kit: at N=10 two UAVs per process
            # sat 7 cm low on their UGV with the joint not enforced (the d11 failure of SimMT-2d) and never
            # left the deck (gpd71 s7c1/s7g1/s7h1; evidence-08).
            for app in host.task_apps:
                app.activate_task()
                try:
                    app.ugv.initialize()
                    app.ugv.post_reset()
                    app._ugv_initialized_before_dock = True
                except Exception as exc:  # finish_task retries and logs as before
                    carb.log_error(f"AirGround UGV initialize before dock failed: {exc}")
        for app in host.task_apps:
            app.activate_task()
            if getattr(app, "uav_body_canonical_local_pose", None) is None:
                app._capture_uav_body_canonical_local_pose()
            app._align_and_dock(stage, settle_updates=False)
            app._dock_prepared = True
    for app in host.task_apps:
        app.activate_task()
        app.finish_task()
    host.activate_task()
    return host


def main():
    if os.environ.get("AIRGROUND_PY_STACK_SAMPLE", "").strip():  # SimMT CPU attribution (default off)
        import sys as _sys  # noqa: PLC0415

        # Scripts may run from a copy (the mission runner runs as /tmp/run_rayfronts_full_mission_t<k>.py).
        for _candidate in (os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "airground_sidecar"),
                           "/isaac-sim/AirStack/simulation/isaac-sim/airground_sidecar"):
            if os.path.isfile(os.path.join(_candidate, "stack_sampler.py")):
                _sys.path.insert(0, _candidate)
                break
        try:
            import stack_sampler  # noqa: PLC0415

            stack_sampler.start_from_env("kit")
        except Exception as _exc:  # noqa: BLE001 - a diagnostic must never stop the run
            print(f"AirGround stack sampler unavailable: {_exc}", file=_sys.stderr, flush=True)
    pg_app = build_apps()
    switch_interval = os.environ.get("AIRGROUND_PY_SWITCH_INTERVAL_S", "").strip()
    if switch_interval:  # SimMT diagnostic: GIL hand-over interval (CPython default 0.005 s)
        sys.setswitchinterval(float(switch_interval))
        carb.log_warn(f"AirGround Python switch interval set to {sys.getswitchinterval()} s")
    global _MAIN_LOOP_WATCHDOG
    watchdog_s = float(os.environ.get("AIRGROUND_MAIN_LOOP_WATCHDOG_S") or "0")
    if watchdog_s > 0:  # SimMT diagnostic: dump every thread when the main loop stops advancing
        import main_loop_watchdog  # noqa: PLC0415 - airground_sidecar is on sys.path

        out = os.environ.get("AIRGROUND_MAIN_SAMPLER_OUT") or "/isaac-sim/AirGroundRuns/main_thread_sampler.json"
        main_loop_watchdog.start(watchdog_s, os.environ.get("AIRGROUND_MAIN_LOOP_WATCHDOG_DIR") or os.path.dirname(out))
        _MAIN_LOOP_WATCHDOG = main_loop_watchdog
        carb.log_warn(f"AirGround main-loop watchdog on: stall after {watchdog_s} s")
    sampler_s = float(os.environ.get("AIRGROUND_MAIN_SAMPLER_S") or "0")
    if sampler_s > 0:  # SimMT diagnostic: Python stack sampling of the main thread (default off)
        import main_thread_sampler  # noqa: PLC0415 - airground_sidecar is on sys.path

        main_thread_sampler.start(
            delay_s=float(os.environ.get("AIRGROUND_MAIN_SAMPLER_DELAY_S") or "150"),
            duration_s=sampler_s,
            out_path=os.environ.get("AIRGROUND_MAIN_SAMPLER_OUT") or "/isaac-sim/AirGroundRuns/main_thread_sampler.json",
            every_s=float(os.environ.get("AIRGROUND_MAIN_SAMPLER_EVERY_S") or "0"),
            windows=int(os.environ.get("AIRGROUND_MAIN_SAMPLER_WINDOWS") or "1"),
        )
    pg_app.run()


if __name__ == "__main__":
    main()
