#!/usr/bin/env python3
"""Run a real ROS 2 Nav2 smoke against the live AirGround Jackal topics.

The script starts a minimal namespaced Nav2 stack for `/ugv`, using the live
Isaac `/ugv/odom` and `/tf` publishers and a generated free-space map.  It
writes the JSONL evidence consumed by `airground smoke check-nav2`.

Obstacle perception is the UGV Ouster OS1 3D point cloud
(``/ugv/sensors/ouster/point_cloud``).  Both costmaps use
``nav2_costmap_2d::VoxelLayer`` with ``min_obstacle_height`` 0.05 m in the map
frame (the scene ground sits at z ~= 0), so any geometry 5 cm or more above the
ground - curbs, tire stacks, fence footings - is lethal while the drivable
surface itself is not.  The earlier 2D ``/<ns>/scan`` proximity scan is no
longer an observation source.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import math
import os
from pathlib import Path
import signal
import shutil
import subprocess
import textwrap
import time
from typing import Any

from builtin_interfaces.msg import Duration
from geometry_msgs.msg import PoseStamped, Twist
from lifecycle_msgs.srv import GetState
from nav2_msgs.action import BackUp, NavigateToPose
from nav_msgs.msg import OccupancyGrid, Odometry, Path as NavPath
import rclpy
from rclpy.action import ActionClient
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy
from tf2_msgs.msg import TFMessage


NAV2_NODE_NAMES: tuple[str, ...] = (
    "map_server",
    "controller_server",
    "smoother_server",
    "planner_server",
    "behavior_server",
    "velocity_smoother",
    "bt_navigator",
)
# 2026-09-18: the managed nodes are started first and the lifecycle manager is
# appended after this settle delay.  One second was enough for the light 0.25 m
# stack, but with the 0.05 m map (2M cells) the map_server's very first
# ``change_state`` response can be lost in DDS discovery, which leaves the
# manager blocked forever on ``Configuring map_server`` (measured
# ``smoke_20260918_173406_type-i``: rmw_response.cpp:154 "failed to send
# response to /ugv/map_server/change_state (timeout)").  Give the discovery a
# wider window before the bring-up starts.
NAV2_LIFECYCLE_MANAGER_START_DELAY_S = 3.0
NAV2_SMOKE_STEP_NAMES: tuple[str, ...] = (
    "lifecycle_active",
    "map_received",
    "global_costmap_active",
    "local_costmap_active",
    "goal_accepted",
    "path_received",
    "local_planner_active",
    "cancel_accepted",
    "stuck_recovery_triggered",
)
NAV2_STARTUP_ONLY_STEP_NAMES: tuple[str, ...] = (
    "lifecycle_active",
    "map_received",
    "global_costmap_active",
    "local_costmap_active",
    "action_server_ready",
)


def _env_switch(name: str) -> bool:
    """Opt-in boolean switch: only ``1``/``true``/``yes``/``on`` enable it."""

    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


# AIRGROUND_LEAN_SUBSCRIPTIONS (default off).  The map and costmap subscriptions
# above only count messages for the readiness waits.  With the switch on, each
# one is destroyed as soon as its wait has succeeded, so the global costmap
# (7792x4137 cells on the scene, 2 Hz) is no longer deserialised in Python for
# the rest of the run.  The recorded step counts are read before the destroy,
# so the evidence is unchanged.
LEAN_SUBSCRIPTIONS = _env_switch("AIRGROUND_LEAN_SUBSCRIPTIONS")

# 2026-09-18 UGV drivetrain/stability fix.  Three Type I runs showed the same
# physical failure: the Jackal stalls a few metres into its first goal, the
# behaviour tree spends the window on spin/back-up recoveries that abort against
# the same blocked cells, and the chassis ends up rolled onto its back
# (``smoke_20260918_142310_type-i`` and ``..._154502_type-i`` both measured
# ``roll=180 deg`` on ``map -> ugv/base_link``, which pushes the lidar frame
# below the map floor).  The commands were also far more aggressive than the
# drivetrain can track (0.6 m/s commanded, ~0.1-0.4 m/s achieved), so the
# vehicle keeps pressing and climbing while the wheels slip.  The defaults below
# slow every axis down and cap accelerations; the collision guard is re-enabled
# with a short horizon so it acts as a bumper instead of wedging the robot at
# the goal.
#: 2026-09-22 (user request: "移动速度和旋转速度均翻倍，要真的翻倍"): the two
#: speed axes were doubled from the long-standing 0.4 m/s / 0.6 rad/s pair, and
#: the doubling was *measured on the live rig* before the lane re-run (probe
#: container, the bus-stop pocket pose, plane ground-support surface):
#: * linear: command 0.4 -> 0.8 m/s realized 0.382 -> **0.797 m/s (2.09x)**
#:   (wheel speed 4.08 -> 8.16 rad/s, 8 N*m cap unchanged, roll 0.0 deg);
#: * in-place yaw: the drive-layer clamp had to be raised with it
#:   (``AIRGROUND_UGV_CMD_VEL_MAX_ANGULAR_RADPS`` 1.2 -> 2.4, see
#:   ``docker/docker-compose.yaml``), because the old clamp pinned every
#:   rotation command above 0.48 rad/s to 1.2 and the realized yaw to ~0.2 rad/s.
#:   With the clamp at 2.4 the same command realizes **+0.942 rad/s at cmd 1.2**
#:   and +0.362 rad/s at cmd 0.6, i.e. the lane's rotate command (0.75 x 1.2 =
#:   0.9 rad/s) is realized ~4x faster than before, with roll <= 0.25 deg and the
#:   nominal ride height (no wheelie, no instability).
DEFAULT_NAV2_DESIRED_LINEAR_VEL_MPS = 0.8
DEFAULT_NAV2_MAX_LINEAR_VEL_MPS = 1.0
#: 2026-09-20: angular-velocity ceiling.  History (live rig + real runs):
#: * 0.25 rad/s *looked* right in the isolated A/B - with a goal behind the
#:   robot the chassis followed a slip-free 1.6 m arc - but the *injected-lane*
#:   regression run ``smoke_20260920_172252`` shows what it does to RPP's path
#:   tracking: the controller asks for omega up to 1.33 rad/s (a 0.30 m radius
#:   at 0.4 m/s), the clamp cut it to 0.25 (1.6 m radius) and the UGV simply
#:   orbited - 51 m of path, never closer than 17 m to a goal 6 m away.
#: * With the ceiling at 0.6 rad/s the same goal was reached
#:   (``smoke_20260920_000947`` K==2).  Curvature distortion is worse than wheel
#:   slip for this benchmark, so the ceiling stays at the pre-2026-09-20 value.
#: ``rotate_to_heading`` remains disabled: the drivetrain cannot spin in place
#: (measured 2-4% of the commanded yaw rate even with a 6 N*m wheel cap).
#
#: 2026-09-22: that history is superseded.  In-place rotation works once the
#: ground support surface is a plane collider (CHANGELOG §73) and the drive-layer
#: yaw clamp is 2.4 rad/s; the ceiling is doubled with the linear speed so both
#: axes of this lane are 2x.  ``rotate_to_heading_angular_vel`` therefore becomes
#: 0.75 x 1.2 = 0.9 rad/s.
DEFAULT_NAV2_MAX_ANGULAR_VEL_RADPS = 1.2
#: 2026-09-22 (speed doubling): the linear acceleration doubles with the speed
#: (0.5 -> 1.0 m/s^2) so the vehicle still reaches the new ceiling in the same
#: time.
DEFAULT_NAV2_LINEAR_ACCEL_MPS2 = 1.0
#: ``max_angular_accel`` doubles as RPP's rotate-to-heading feasibility window
#: ``[omega_odom - a*dt, omega_odom + a*dt]``.  The window is *relative to the
#: measured* yaw rate, so a **parked** robot (omega_odom = 0) gets a window of
#: +-a*dt around zero: with the old a = 0.8 that is +-0.08 rad/s per 10 Hz cycle,
#: the commanded yaw is pinned at ~0.1 rad/s, the skid's static friction is never
#: broken, the measured rate stays 0 and the window never opens - measured in the
#: probe container on 2026-09-22: a parked UGV deadlocked for ~16 s at ~0.1 rad/s
#: of commanded rotation and eventually had to be disturbed before it would turn.
#: With the doubled speed ceiling (rotate command 0.9 rad/s) that deadlock is
#: *more* likely, so the accel limit is raised out of the way: this drivetrain
#: reaches 0.94 rad/s of body yaw within a few 100 ms when the command is applied
#: (measured spin step response), i.e. its real yaw acceleration is far above the
#: 20 rad/s^2 used here.  The value only widens the command window; the speed
#: ceiling (1.2 rad/s -> 0.9 rotate command -> 2.4 clamped shaping) still bounds
#: the commanded rate, and RPP's anti-overshoot cap ``sqrt(2*a*|angle|)`` stays
#: above that ceiling (sqrt(2*20*2.55) = 10 rad/s), so it is inert.
DEFAULT_NAV2_ANGULAR_ACCEL_RADPS2 = 20.0
#: 2026-09-20: RPP's forward/reverse choice.  Both values have a measured
#: failure mode on this drivetrain, so the value is a first-class option (the
#: live A/B experiment flips it without touching the rest of the stack):
#: * ``True``  - the controller *reverses* when the path/ carrot is behind the
#:   robot, which is the only way this base can execute a ~180 deg turnaround
#:   (it cannot spin in place: 5.6 N*m/wheel needed vs 3 N*m available), but the
#:   forward/reverse decision flips at |angle| ~ 90 deg and produced a +-0.13 m/s
#:   ping-pong limit cycle (measured at the RetroNeighborhood fence,
#:   ``smoke_20260919_225512``).
#: * ``False`` - steering-only forward following never ping-pongs, but pure
#:   pursuit has a *stable* singularity with the carrot directly behind
#:   (``sin(angle) ~ 0`` -> zero steering): the UGV drives straight *away* from
#:   the goal and the target times out (measured ``smoke_20260920_014912``,
#:   where the dispatch goal sat 153 deg behind the spawn heading).
DEFAULT_NAV2_ALLOW_REVERSING = False
#: 2026-09-20: RPP scales the *linear* velocity down when the path curvature is
#: high (``regulated_linear_scaling_min_radius``).  On a skid-steer that is
#: counter-productive: the turn radius is ``v / omega``, so slowing down while
#: the turn rate saturates makes the commanded arc *tighter* than the wheels can
#: execute.  Measured live at ``(-21.8, -15.0)`` with an 82 deg heading error:
#: RPP commanded ``v = 0.13, omega = 0.44`` (a 0.30 m radius arc), the wheels
#: slipped, and the chassis crawled ~6 mm/s.  Disable the scaling so the arc
#: radius is set by ``max_angular_vel`` instead of by the speed reduction.
DEFAULT_NAV2_REGULATED_LINEAR_SCALING = True
# UGV 3D obstacle source.  The static traversability map is a vertical-raycast
# prior: it misses thin runtime geometry (fences) and, at 0.25 m, most of the
# 5-10 cm steps the Jackal can climb.  The Ouster OS1 sensor graph publishes a
# map-frame-height cloud that both costmaps voxelize.
DEFAULT_NAV2_POINT_CLOUD_TOPIC = "/ugv/sensors/ouster/point_cloud"
# 2026-09-19: back to the 5 cm contract.  The "5-6 cm return ring" that forced
# the temporary 0.10 m dead band was *not* raycast noise: the PhysX fan was cast
# with the body yaw only while tf2 re-rotated the points by the real attitude,
# so ground returns were lifted by ``range * sin(pitch)`` whenever the chassis
# pitched (measured live on ``smoke_20260919_105956_type-i``: cloud points in
# the band swung 14 -> 689 as the chassis pitched +-15..40 deg).  The driver now
# casts with the full attitude *and* segments the ground itself
# (``JackalProximityCloudConfig.min_obstacle_height_m``, applied with the exact
# attitude the ray was cast with), so this gate only has to mirror the
# traversability GT's 0.05 m step contract: any geometry 5 cm or more above the
# map-frame ground (z ~= 0) is lethal.  CLI/env remain overridable for A/B runs.
DEFAULT_NAV2_POINT_CLOUD_MIN_OBSTACLE_HEIGHT_M = 0.05
DEFAULT_NAV2_POINT_CLOUD_MAX_OBSTACLE_HEIGHT_M = 1.00
# Managed Nav2 bringup attempts before the smoke fails.  Two attempts were not
# enough on 2026-09-18: the first one can lose the map_server ``change_state``
# response in DDS discovery, and the old retry path crashed on the invalid rcl
# context it left behind (see ``DEFAULT_NAV2_LIFECYCLE_RETRY_ATTEMPTS`` usage in
# ``main``).
DEFAULT_NAV2_LIFECYCLE_RETRY_ATTEMPTS = 3
# Marking range is kept short on purpose: the 0.05 m static map already carries
# everything beyond it, and every point inside the raytrace range costs a voxel
# ray clear in the layer's update loop.
DEFAULT_NAV2_POINT_CLOUD_OBSTACLE_RANGE_M = 4.5
DEFAULT_NAV2_POINT_CLOUD_RAYTRACE_RANGE_M = 6.0
# 0.05 m costmap resolution matches the traversability GT grid, so a lethal
# static cell and a lethal voxel cell describe the same physical footprint.
DEFAULT_NAV2_COSTMAP_RESOLUTION_M = 0.05
DEFAULT_NAV2_LOCAL_COSTMAP_SIZE_M = 8.0
DEFAULT_NAV2_VOXEL_Z_RESOLUTION_M = 0.05
#: Inflation cost decay: ``cost = (INSCRIBED-1) * exp(-factor * (d - r_inscribed))``.
#: 2026-10-03 measurement (``20261003_p4probe`` live trace + an offline
#: NavFn-cost model on the same live map): at the previous 2.5 the planner routed
#: the tour's ``red_car -> house.0015`` leg through the (57.5,-30.6) pinch
#: corridor, whose 0.1 m-resampled cells sit at internal cost 229-253 (the Nav2
#: abort pose had a 253 cell 0.25 m behind the robot, so the reverse recovery was
#: impassable), even though a ~121 m southern loop whose cells are all free
#: (worst internal cost 0) exists at the price of ~12 m.  The weighted-Dijkstra
#: model flips to that loop between factor 1.5 and 1.4 and keeps it down to 0.5;
#: at 2.5 the model reproduced the driven corridor (109 m model vs the 103.3 m
#: NavFn probe).  1.0 is chosen with margin below the measured flip and is
#: validated live by the two-target probe re-run.
DEFAULT_NAV2_INFLATION_COST_SCALING_FACTOR = 1.0
#: Planar Jackal footprint (half-length x half-width) used by the traversability
#: sweep (0.508 m x 0.430 m).  ``robot_radius`` is the *circumscribed* radius,
#: and Nav2 feeds it to the inflation layer as the *inscribed* radius, so every
#: cell within 0.33 m of an obstacle becomes INSCRIBED (253) - and NavFn treats
#: 253 as blocked (``nav2_navfn_planner`` ``setCostmap``: ``v >= COST_OBS_ROS``
#: -> ``COST_OBS``).  With the circumscribed radius the planner therefore needs
#: 0.66 m of clearance everywhere, and a robot that ends up in a slightly
#: tighter pocket can no longer be re-planned *at all*: measured 2026-09-19
#: (``smoke_20260919_122659_type-i``) the UGV stopped inside the bus-stop
#: pocket at (-9.711,-28.423), whose static clearance is 0.300 m, with
#: ``GridBased: failed to create plan`` x18 and both goals lost.  Declaring the
#: real polygon makes the inscribed radius 0.215 m (the robot's half width), so
#: the planner regains every cell the chassis genuinely fits in while the
#: inflation cost field still steers paths away from walls.
DEFAULT_NAV2_ROBOT_FOOTPRINT_M = (
    (0.254, 0.215),
    (0.254, -0.215),
    (-0.254, -0.215),
    (-0.254, 0.215),
)
DEFAULT_NAV2_VOXEL_Z_VOXELS = 16


@dataclass
class StepRecorder:
    output: Path
    start_wall: float

    def __post_init__(self) -> None:
        self.output.parent.mkdir(parents=True, exist_ok=True)
        self._stream = self.output.open("w", encoding="utf-8")
        self._last_time_s = 0.0

    def close(self) -> None:
        self._stream.close()

    def step(self, name: str, status: str = "ok", **details: Any) -> None:
        elapsed = max(0.0, time.monotonic() - self.start_wall)
        elapsed = max(elapsed, self._last_time_s)
        self._last_time_s = elapsed
        payload = {
            "agent": "ugv",
            "event": "nav2_smoke_step",
            "status": status,
            "step": name,
            "time_s": round(elapsed, 6),
        }
        if details:
            payload["details"] = details
        self._stream.write(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n")
        self._stream.flush()


def _write_free_space_map(
    map_yaml: Path,
    *,
    width: int,
    height: int,
    resolution: float,
    origin_x_m: float,
    origin_y_m: float,
) -> None:
    image_path = map_yaml.with_suffix(".pgm")
    rows = [" ".join(["254"] * width) for _ in range(height)]
    image_path.write_text(
        "P2\n"
        f"{width} {height}\n"
        "255\n"
        + "\n".join(rows)
        + "\n",
        encoding="ascii",
    )
    map_yaml.write_text(
        textwrap.dedent(
            f"""\
            image: {image_path.name}
            mode: trinary
            resolution: {resolution}
            origin: [{origin_x_m}, {origin_y_m}, 0.0]
            negate: 0
            occupied_thresh: 0.65
            free_thresh: 0.25
            """
        ),
        encoding="utf-8",
    )


def _copy_nav2_map_yaml(source_yaml: Path, work_dir: Path) -> Path:
    source_yaml = source_yaml.expanduser().resolve(strict=True)
    yaml_text = source_yaml.read_text(encoding="utf-8")
    image_name = None
    for line in yaml_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("image:"):
            image_name = stripped.split(":", 1)[1].strip().strip('"\'')
            break
    if not image_name:
        raise RuntimeError(f"Nav2 map yaml missing image field: {source_yaml}")
    source_image = (source_yaml.parent / image_name).resolve(strict=True)
    target_yaml = work_dir / source_yaml.name
    target_image = work_dir / source_image.name
    shutil.copyfile(source_image, target_image)
    rewritten_lines: list[str] = []
    for line in yaml_text.splitlines():
        if line.strip().startswith("image:"):
            indent = line[: len(line) - len(line.lstrip())]
            rewritten_lines.append(f"{indent}image: {target_image.name}")
        else:
            rewritten_lines.append(line)
    target_yaml.write_text("\n".join(rewritten_lines) + "\n", encoding="utf-8")
    return target_yaml


def _write_nav2_params(
    path: Path,
    namespace: str,
    *,
    desired_linear_vel_mps: float = DEFAULT_NAV2_DESIRED_LINEAR_VEL_MPS,
    max_linear_vel_mps: float = DEFAULT_NAV2_MAX_LINEAR_VEL_MPS,
    max_angular_vel_radps: float = DEFAULT_NAV2_MAX_ANGULAR_VEL_RADPS,
    linear_accel_mps2: float = DEFAULT_NAV2_LINEAR_ACCEL_MPS2,
    angular_accel_radps2: float = DEFAULT_NAV2_ANGULAR_ACCEL_RADPS2,
    point_cloud_topic: str | None = None,
    point_cloud_min_obstacle_height_m: float = DEFAULT_NAV2_POINT_CLOUD_MIN_OBSTACLE_HEIGHT_M,
    point_cloud_max_obstacle_height_m: float = DEFAULT_NAV2_POINT_CLOUD_MAX_OBSTACLE_HEIGHT_M,
    point_cloud_obstacle_range_m: float = DEFAULT_NAV2_POINT_CLOUD_OBSTACLE_RANGE_M,
    point_cloud_raytrace_range_m: float = DEFAULT_NAV2_POINT_CLOUD_RAYTRACE_RANGE_M,
    costmap_resolution_m: float = DEFAULT_NAV2_COSTMAP_RESOLUTION_M,
    local_costmap_size_m: float = DEFAULT_NAV2_LOCAL_COSTMAP_SIZE_M,
    inflation_cost_scaling_factor: float = DEFAULT_NAV2_INFLATION_COST_SCALING_FACTOR,
    allow_reversing: bool = DEFAULT_NAV2_ALLOW_REVERSING,
    regulated_linear_velocity_scaling: bool = DEFAULT_NAV2_REGULATED_LINEAR_SCALING,
) -> None:
    for label, value in {
        "desired_linear_vel_mps": desired_linear_vel_mps,
        "max_linear_vel_mps": max_linear_vel_mps,
        "max_angular_vel_radps": max_angular_vel_radps,
        "linear_accel_mps2": linear_accel_mps2,
        "angular_accel_radps2": angular_accel_radps2,
        "point_cloud_obstacle_range_m": point_cloud_obstacle_range_m,
        "point_cloud_raytrace_range_m": point_cloud_raytrace_range_m,
        "costmap_resolution_m": costmap_resolution_m,
        "local_costmap_size_m": local_costmap_size_m,
    }.items():
        if not math.isfinite(float(value)) or float(value) <= 0.0:
            raise ValueError(f"{label} must be finite and positive")
    for label, value in {
        "point_cloud_min_obstacle_height_m": point_cloud_min_obstacle_height_m,
        "point_cloud_max_obstacle_height_m": point_cloud_max_obstacle_height_m,
    }.items():
        if not math.isfinite(float(value)) or float(value) < 0.0:
            raise ValueError(f"{label} must be finite and non-negative")
    if float(point_cloud_max_obstacle_height_m) <= float(point_cloud_min_obstacle_height_m):
        raise ValueError(
            "point_cloud_max_obstacle_height_m must be greater than "
            "point_cloud_min_obstacle_height_m"
        )
    ns = namespace.strip("/")
    point_cloud_topic = point_cloud_topic or f"/{ns}/sensors/ouster/point_cloud"
    point_cloud_obstacle_range_m = min(
        float(point_cloud_obstacle_range_m), float(point_cloud_raytrace_range_m)
    )
    prefix = f"/{ns}"
    lifecycle_nodes_yaml = "\n".join(f"                  - {name}" for name in NAV2_NODE_NAMES)
    # AIRGROUND_LEAN_SUBSCRIPTIONS: the smoother's costmap is read only by a SmoothPath
    # request, and no Humble navigate_to_pose BT (ours is the default
    # navigate_to_pose_w_replanning_and_recovery.xml) nor any AirGround code sends one.
    # Its default subscription is the full global costmap_raw (7792x4137 cells, 2 Hz);
    # pointing it at the 8 m local costmap keeps the server and its lifecycle unchanged.
    smoother_costmap_yaml = (
        "                costmap_topic: local_costmap/costmap_raw\n"
        "                footprint_topic: local_costmap/published_footprint\n"
        if LEAN_SUBSCRIPTIONS
        else ""
    )
    # ``footprint_padding`` grows the collision outline used for the costmap's
    # inscribed radius without changing the declared footprint.  NavFn only
    # refuses a cell that is at least INSCRIBED, so with the bare 0.508 x 0.43 m
    # outline a 0.75 m gap between two obstacles still reads as drivable (the
    # centre line is 0.375 m from either side, the inscribed radius only
    # 0.215 m) while the Jackal physically wedges in it: measured 2026-10-01,
    # the 480 s ladder pinned the UGV at (-39.7, -28.9) there twice.
    # ``AIRGROUND_NAV2_FOOTPRINT_PADDING_M`` keeps the value a run parameter
    # until an experiment picks the default.
    try:
        footprint_padding_m = float(
            os.environ.get("AIRGROUND_NAV2_FOOTPRINT_PADDING_M", "0.0") or 0.0
        )
    except ValueError:
        footprint_padding_m = 0.0
    if footprint_padding_m < 0.0:
        raise ValueError("AIRGROUND_NAV2_FOOTPRINT_PADDING_M must be non-negative")
    footprint_yaml = (
        "                footprint: \"[["
        + "], [".join(
            f"{float(x):.3f}, {float(y):.3f}" for x, y in DEFAULT_NAV2_ROBOT_FOOTPRINT_M
        )
        + "]]\"\n"
        + f"                footprint_padding: {footprint_padding_m:.3f}"
    )
    # NOTE: this block is interpolated into the dedented parameter template
    # below, so it keeps the template's own indentation and must not be
    # dedented on its own.
    voxel_layer_yaml = (
        f"""\
                  plugin: "nav2_costmap_2d::VoxelLayer"
                  enabled: true
                  # Footprint clearing must stay enabled.  With it disabled the
                  # cells the sensor cannot see (its own occluded footprint)
                  # keep whatever the vehicle marked while driving over them, so
                  # the robot ends up standing inside a lethal island: measured
                  # 2026-09-19 02:14 (``smoke_20260919_021234``) the robot's own
                  # cell was INSCRIBED (99) and every cell within +-0.5 m was
                  # 99/100 in both costmaps, while the live cloud had *zero*
                  # points within 1 m in the [0.05, 0.6) m band -- i.e. the
                  # marks were stale, not live.  The planner then failed to
                  # create a plan from a lethal start cell and RPP's collision
                  # check fired continuously ("detected collision ahead!" x756),
                  # pinning the UGV ~2 m from its start.  A real 5 cm step is
                  # still carried by the 0.05 m static layer, which footprint
                  # clearing does not touch.
                  footprint_clearing_enabled: true
                  combination_method: 1
                  z_resolution: {float(DEFAULT_NAV2_VOXEL_Z_RESOLUTION_M)}
                  z_voxels: {int(DEFAULT_NAV2_VOXEL_Z_VOXELS)}
                  mark_threshold: 0
                  publish_voxel_map: false
                  observation_sources: ugv_point_cloud
                  ugv_point_cloud:
                    topic: {point_cloud_topic}
                    data_type: "PointCloud2"
                    clearing: true
                    marking: true
                    inf_is_valid: false
                    min_obstacle_height: {float(point_cloud_min_obstacle_height_m)}
                    max_obstacle_height: {float(point_cloud_max_obstacle_height_m)}
                    raytrace_max_range: {float(point_cloud_raytrace_range_m)}
                    raytrace_min_range: 0.0
                    obstacle_max_range: {float(point_cloud_obstacle_range_m)}
                    obstacle_min_range: 0.0"""
    )
    path.write_text(
        textwrap.dedent(
            f"""\
            {prefix}/lifecycle_manager_navigation:
              ros__parameters:
                use_sim_time: true
                autostart: true
                node_names:
{lifecycle_nodes_yaml}

            {prefix}/map_server:
              ros__parameters:
                use_sim_time: true

            {prefix}/controller_server:
              ros__parameters:
                use_sim_time: true
                controller_frequency: 10.0
                costmap_update_timeout: 1.0
                min_x_velocity_threshold: 0.001
                min_y_velocity_threshold: 0.5
                min_theta_velocity_threshold: 0.001
                failure_tolerance: 1.0
                progress_checker_plugins: ["progress_checker"]
                goal_checker_plugins: ["general_goal_checker"]
                controller_plugins: ["FollowPath"]
                progress_checker:
                  plugin: "nav2_controller::SimpleProgressChecker"
                  required_movement_radius: 0.05
                  movement_time_allowance: 25.0
                general_goal_checker:
                  plugin: "nav2_controller::SimpleGoalChecker"
                  stateful: false
                  xy_goal_tolerance: 0.25
                  # 2026-10-04 (user rule): the arrival must face the point the
                  # goal was sent for; the resolver already commands the goal
                  # yaw toward the injected point, so the goal checker enforces
                  # it.  The 2026-09-19 "any heading" relaxation predates the
                  # drivetrain fix - ``smoke_20260919_193841`` could not rotate
                  # in place (5.6 N*m/wheel needed vs the 5.0 N*m wheelie
                  # bound), but the 2026-09-21 reconfiguration (tyre friction
                  # pair + 8 N*m cap) re-enabled rotate-to-heading and measured
                  # 0.19-0.41 rad/s in place, so a 0.30 rad gate is executable.
                  # The stateful checker keeps the 0.25 m xy contract first and
                  # rotates afterwards.
                  yaw_goal_tolerance: 0.30
                FollowPath:
                  plugin: "nav2_regulated_pure_pursuit_controller::RegulatedPurePursuitController"
                  desired_linear_vel: {float(desired_linear_vel_mps)}
                  lookahead_dist: 0.6
                  min_lookahead_dist: 0.3
                  max_lookahead_dist: 0.9
                  lookahead_time: 1.5
                  rotate_to_heading_angular_vel: {float(max_angular_vel_radps) * 0.75}
                  transform_tolerance: 0.2
                  use_velocity_scaled_lookahead_dist: false
                  min_approach_linear_velocity: 0.1
                  approach_velocity_scaling_dist: 1.0
                  # The collision pre-check is kept as a *bumper*, with the
                  # shortest horizon RPP accepts.  History: the 1 s default
                  # horizon wedged the robot on every bus-stop approach
                  # (2026-09-18 13:10 Type I -> patience -> abort), disabling it
                  # let the robot press in and roll onto its back (14:23/15:45),
                  # and 0.5 s still fired on the *carrot* while the goal itself
                  # was in free space (2026-09-18 23:30 Type I: goal
                  # (-23.875,-13.425) and the straight line to it are all free
                  # in the static map, yet 740 "detected collision ahead!" plus
                  # 5 patience aborted the goal 1.7 m short, while the reach set
                  # had already been entered).  0.1 s at 0.4 m/s checks only
                  # ~4 cm ahead of the robot, so a lethal cell the robot is
                  # about to touch still stops it, and a structure under the
                  # look-ahead carrot no longer does.
                  # 2026-09-19: restored once the phantom lethal rings were fixed (§32).  The
                  # 0.1 s value was introduced on 2026-09-18 to stop the *phantom* rings from
                  # firing "detected collision ahead" - but it also shrinks the bumper to
                  # 1-4 cm at 0.1-0.4 m/s, and `smoke_20260919_200800` shows the result: the
                  # UGV pressed itself 0.04 m into the bus-shelter wall with **zero**
                  # collision warnings (the fan's 0.30 m min_range is blind that close and
                  # the 0.1 s horizon never reaches it), then spun its wheels until the goal
                  # timed out.  0.75 s at 0.4 m/s gives a ~30 cm bumper - outside the lidar
                  # blind spot, still far short of the goal-approach behaviour that the
                  # 1.0 s horizon broke.
                  use_collision_detection: true
                  max_allowed_time_to_collision_up_to_carrot: 0.75
                  use_regulated_linear_velocity_scaling: {str(bool(regulated_linear_velocity_scaling)).lower()}
                  use_cost_regulated_linear_velocity_scaling: false
                  regulated_linear_scaling_min_radius: 0.9
                  regulated_linear_scaling_min_speed: 0.1
              # The Jackal could not rotate in place on this drivetrain when
              # this lane was tuned: with a
                  # pure-rotation command (linear.x = 0) the wheels slip and the
                  # chassis turns ~1% of the commanded rate, so RPP's
                  # rotate-to-heading phase wedged the UGV 2.5 m short of the
                  # 2026-09-17 injected goal until "Controller patience
                  # exceeded" aborted it.  Steering-only forward following keeps
                  # the robot moving; allowing reverse as well made it ping-pong
                  # (measured 2026-09-18: -23.3 -> -24.0 -> -23.3 m with the goal
                  # still 2.3 m away).
                  #
                  # 2026-09-19 (second measurement, ``smoke_20260919_165233``):
                  # rotate-to-heading was re-enabled after the wheel-torque
                  # bound and *failed*: the controller commanded its 0.45 rad/s
                  # rotation for 15 simulated seconds while the chassis yaw
                  # stayed at 171 deg and the wheel targets stayed inside
                  # +-0.1 rad/s - the robot never left the start.  Rotating in
                  # place needs a yaw moment above the skid-steer scrub
                  # resistance (~43 N*m with the benchmark tyre friction 1.0/1.2)
                  # = 5.6 N*m per wheel, i.e. *above* the 5.0 N*m wheelie
                  # threshold, so this drivetrain genuinely cannot spin in
                  # place.  Steering-only forward following stays enabled; the
                  # nose-in deadlock it can cause is handled by allowing reverse
                  # (below) and by the plan probe.
                  # 2026-09-20: rotate-to-heading also failed with a 6 N*m cap.
                  # Commanded pure rotation (linear 0, angular 0.07-0.16 rad/s)
                  # moved the yaw only ~0.15 deg per simulated second (~2-4 % of
                  # the command) over 480 wall seconds: the yaw moment was eaten
                  # by the skid-steer scrub.
                  #
                  # 2026-09-21 (this turn, measured): that conclusion is
                  # obsolete.  With the tyre friction lowered to 0.7/0.6 on a
                  # ``min``-combined pair, the drive cap raised to 8 N*m and the
                  # measured 0.40 yaw gain shaped into the command
                  # (``AIRGROUND_UGV_CMD_VEL_ANGULAR_GAIN=2.5``), the spin probe
                  # measures 0.189 rad/s at 0.5 and 0.407 rad/s at 1.0 rad/s
                  # commanded, i.e. in-place rotation works and scales.  The
                  # formal injected run ``smoke_20260921_203844`` still failed
                  # *because* this flag was false: after reaching the first
                  # dispatched goal the UGV had the next goal behind it, RPP had
                  # no rotate-to-heading phase, so it drew a forward-left arc
                  # into the pocket next to the 0002 bus stop (x -26.9 -> -29.4
                  # while the goal was 23 m east), then aborted on the collision
                  # pre-check.  Rotate-to-heading is therefore re-enabled.
                  # ``allow_reversing`` must stay false: RPP disables reversing
                  # whenever rotate-to-heading is on (its constructor warns and
                  # forces the pair), and reversing was the ping-pong source.
                  use_rotate_to_heading: true
                  # 2026-09-19 (third measurement, ``smoke_20260919_225512``):
                  # reversing was re-enabled to escape the nose-in deadlock, and
                  # that made the controller *ping-pong* instead: with the
                  # heading roughly across the path the forward/reverse decision
                  # flips every cycle.  Measured directly on ``/ugv/control/status``
                  # for 24 + simulated seconds at the RetroNeighborhood fence
                  # (``(-20.99, -14.80)``): cmd linear +0.13 -> -0.13 m/s and
                  # angular -0.44 -> +0.44 rad/s every ~0.5-1 s while the chassis
                  # oscillated within +-2 mm, so ``follow_path`` ended in
                  # "Failed to make progress" and the target timed out.  That is
                  # the same limit cycle the 2026-09-18 runs saw; it is *not* a
                  # phantom-costmap artefact (the costmap in front of the robot
                  # was free here).  Steering-only forward following is therefore
                  # restored.
                  allow_reversing: {str(bool(allow_reversing)).lower()}
                  rotate_to_heading_min_angle: 0.5
                  max_angular_accel: {float(angular_accel_radps2)}
                  max_robot_pose_search_dist: 10.0
                  use_interpolation: true

            {prefix}/local_costmap/local_costmap:
              ros__parameters:
                use_sim_time: true
                update_frequency: 10.0
                publish_frequency: 2.0
                global_frame: map
                robot_base_frame: {ns}/base_link
                initial_transform_timeout: 10.0
                rolling_window: true
                width: {int(round(local_costmap_size_m))}
                height: {int(round(local_costmap_size_m))}
                resolution: {float(costmap_resolution_m)}
{footprint_yaml}
                # 2026-09-19: the local costmap MUST also carry the static
                # prior.  The traversability prior marks every cell under a
                # bus-shelter roof as blocked (its vertical ray hits the roof),
                # and NavFn seeds its potential field at the *robot's* cell:
                # ``smoke_20260919_153113`` measured the UGV physically driving
                # *under* the shelter, after which the robot's cell was a
                # one-cell hole inside the lethal footprint and the planner
                # answered ``GridBased: failed to create plan`` for every goal
                # (14x for the east bus stop, 4/4 probes for the west one) until
                # a recovery shoved it out.  The controller now refuses that
                # region in the first place, while the voxel layer keeps adding
                # live 3D geometry and the global costmap keeps planning around
                # both.
                static_layer:
                  plugin: "nav2_costmap_2d::StaticLayer"
                  map_subscribe_transient_local: true
                # ``track_unknown_space: true`` (the Nav2 default) leaves the
                # not-yet-observed cells of the rolling window at NO_INFORMATION
                # (255), and RPP's collision check treats >= INSCRIBED (253) as a
                # collision - measured 2026-09-18: the UGV stopped every ~2 m
                # with "RegulatedPurePursuitController detected collision ahead"
                # followed by "Controller patience exceeded" while the local
                # costmap around the robot was free.
                track_unknown_space: false
                plugins: ["static_layer", "voxel_layer", "inflation_layer"]
                voxel_layer:
{voxel_layer_yaml}
                inflation_layer:
                  plugin: "nav2_costmap_2d::InflationLayer"
                  cost_scaling_factor: {float(inflation_cost_scaling_factor)}
                  inflation_radius: 0.65
                always_send_full_costmap: true

            {prefix}/global_costmap/global_costmap:
              ros__parameters:
                use_sim_time: true
                # 2026-09-19: 2 Hz lagged the 10 Hz local costmap badly enough
                # that fresh fan returns appeared in the *local* layer while the
                # global plan still routed through them (4095 "collision ahead"
                # in ``smoke_20260919_160240``).  5 Hz keeps the two surfaces in
                # step at ~4 % of the wall-time budget.
                update_frequency: 5.0
                publish_frequency: 2.0
                global_frame: map
                robot_base_frame: {ns}/base_link
                initial_transform_timeout: 10.0
{footprint_yaml}
                resolution: {float(costmap_resolution_m)}
                track_unknown_space: false
                # 2026-09-19: the *live* 3D cloud feeds the local costmap only.
                # With the voxel layer in the global costmap, the fan's returns
                # extend the instance structures by 0.1-0.3 m, and the dispatch
                # pose (nearest reachable cell to the structural anchor, 0.35 m
                # from the bus-stop shelter) then falls inside the inscribed
                # ring.  ``nav2_navfn_planner`` feeds the *goal* to
                # ``NavFn::setStart`` and ``NavFn::setStart`` refuses a cell with
                # cost >= INSCRIBED, so the planner produced **no plan at all**
                # (``GridBased: failed to create plan`` x18 in
                # ``smoke_20260919_122659``/``142336``) until the recovery
                # cleared the marks.  The global plan now runs on the published
                # 0.05 m traversability prior (same runtime PhysX source as the
                # GT), while the local costmap still blocks live geometry 5 cm or
                # more above the ground within its 8 m window.
                plugins: ["static_layer", "voxel_layer", "inflation_layer"]
                static_layer:
                  plugin: "nav2_costmap_2d::StaticLayer"
                  map_subscribe_transient_local: true
                voxel_layer:
{voxel_layer_yaml}
                inflation_layer:
                  plugin: "nav2_costmap_2d::InflationLayer"
                  cost_scaling_factor: {float(inflation_cost_scaling_factor)}
                  inflation_radius: 0.65
                always_send_full_costmap: true

            {prefix}/planner_server:
              ros__parameters:
                use_sim_time: true
                expected_planner_frequency: 5.0
                costmap_update_timeout: 1.0
                planner_plugins: ["GridBased"]
                GridBased:
                  plugin: "nav2_navfn_planner/NavfnPlanner"
                  tolerance: 0.5
                  use_astar: false
                  allow_unknown: true

            {prefix}/smoother_server:
              ros__parameters:
                use_sim_time: true
{smoother_costmap_yaml}                smoother_plugins: ["simple_smoother"]
                simple_smoother:
                  plugin: "nav2_smoother::SimpleSmoother"
                  tolerance: 1.0e-10
                  max_its: 1000
                  do_refinement: true

            {prefix}/behavior_server:
              ros__parameters:
                use_sim_time: true
                local_costmap_topic: local_costmap/costmap_raw
                global_costmap_topic: global_costmap/costmap_raw
                local_footprint_topic: local_costmap/published_footprint
                global_footprint_topic: global_costmap/published_footprint
                cycle_frequency: 10.0
                behavior_plugins: ["spin", "backup", "wait"]
                spin:
                  plugin: "nav2_behaviors/Spin"
                backup:
                  plugin: "nav2_behaviors/BackUp"
                  backup_dist: 0.4
                  backup_speed: 0.1
                wait:
                  plugin: "nav2_behaviors/Wait"
                local_frame: map
                global_frame: map
                robot_base_frame: {ns}/base_link
                transform_tolerance: 0.2
                simulate_ahead_time: 1.0
                # 2026-09-18: the recovery spin is the only motion commanded
                # while the UGV is stalled against blocked cells, and the
                # drivetrain cannot rotate in place (measured: ~1-4 % of the
                # commanded yaw).  The original 0.9/0.45 rad/s spin ran
                # straight into the roll-over, so the recovery torque is now
                # bounded to roughly a third of it.
                max_rotational_vel: 0.35
                min_rotational_vel: 0.15
                rotational_acc_lim: 0.8

            {prefix}/bt_navigator:
              ros__parameters:
                use_sim_time: true
                global_frame: map
                robot_base_frame: {ns}/base_link
                odom_topic: /{ns}/odom
                bt_loop_duration: 20
                default_server_timeout: 20
                wait_for_service_timeout: 2000
                action_server_result_timeout: 120.0
                navigators: ["navigate_to_pose"]
                navigate_to_pose:
                  plugin: "nav2_bt_navigator::NavigateToPoseNavigator"
                error_code_names:
                  - compute_path_error_code
                  - follow_path_error_code

            {prefix}/velocity_smoother:
              ros__parameters:
                use_sim_time: true
                smoothing_frequency: 10.0
                stamp_smoothed_velocity_with_smoothing_time: false
                scale_velocities: false
                feedback: "OPEN_LOOP"
                max_velocity: [{float(max_linear_vel_mps)}, 0.0, {float(max_angular_vel_radps)}]
                min_velocity: [{-float(max_linear_vel_mps) * 0.5}, 0.0, {-float(max_angular_vel_radps)}]
                max_accel: [{float(linear_accel_mps2)}, 0.0, {float(angular_accel_radps2)}]
                max_decel: [{-float(linear_accel_mps2)}, 0.0, {-float(angular_accel_radps2)}]
                odom_topic: /{ns}/odom
                odom_duration: 0.1
                deadband_velocity: [0.0, 0.0, 0.0]
                velocity_timeout: 1.0
            """
        ),
        encoding="utf-8",
    )


def _indent_follow_path(text: str) -> str:
    """Place a dedented ``FollowPath`` template at the file's 4-space depth."""
    return "\n".join(
        ("    " + line) if line.strip() else line
        for line in textwrap.dedent(text).splitlines()
    )


def _follow_path_block(
    planner: str,
    *,
    max_linear_vel_mps: float,
    max_angular_vel_radps: float,
    linear_accel_mps2: float,
    angular_accel_radps2: float,
) -> str:
    """Return the ``FollowPath`` YAML body (4-space key indentation) for a planner.

    2026-09-21 (controller A/B).  The two alternatives to RPP are the ones the
    image actually ships and that fit this drivetrain's measured capability
    (in-place yaw = 0.40 * command after the shaping layer, ~0.5-0.9 m practical
    turn radius, short reverse available):

    * ``mppi`` - sampling controller over (v, omega) with a differential model;
      reverse and pure rotation are ordinary actions and obstacles are costs, so
      it can back out of a nose-in instead of aborting;
    * ``dwb`` - trajectory-scoring controller whose ``Oscillation`` critic
      directly suppresses the measured +-cmd ping-pong limit cycle.
    """
    if planner == "mppi":
        return _indent_follow_path(
            f"""\
                FollowPath:
                  plugin: nav2_mppi_controller::MPPIController
                  motion_model: DiffDrive
                  time_steps: 30
                  # MPPI requires model_dt >= the controller period (10 Hz lane).
                  model_dt: 0.1
                  batch_size: 1500
                  iteration_count: 1
                  vx_std: 0.15
                  vy_std: 0.0
                  wz_std: 0.4
                  vx_max: {float(max_linear_vel_mps)}
                  vx_min: -0.15
                  vy_max: 0.0
                  wz_max: {float(max_angular_vel_radps)}
                  temperature: 0.3
                  gamma: 0.015
                  prune_distance: 1.5
                  transform_tolerance: 0.2
                  visualize: false
                  TrajectoryVisualizer:
                    time_step: 3
                    trajectory_step: 3
                  critics: ["ConstraintCritic", "CostCritic", "GoalCritic", "GoalAngleCritic", "PathAlignCritic", "PathFollowCritic", "PathAngleCritic", "PreferForwardCritic", "VelocityDeadbandCritic"]
                  ConstraintCritic:
                    enabled: true
                    cost_weight: 4.0
                    cost_power: 1
                  CostCritic:
                    enabled: true
                    cost_weight: 3.81
                    cost_power: 1
                    # 2026-09-21: with ``consider_footprint: true`` every rollout
                    # was rejected next to the bus-stop structure ("Optimizer
                    # fail to compute path", 3 follow_path aborts in the first
                    # MPPI round) because the injected ring poses sit inside the
                    # 0.65 m inflation band.  Keep the point-based collision cost
                    # for the comparison and rely on the footprint check in the
                    # local costmap for safety.
                    critical_cost: 500.0
                    consider_footprint: false
                    collision_cost: 1000000.0
                    near_goal_distance: 0.3
                  GoalCritic:
                    enabled: true
                    cost_weight: 5.0
                    threshold_to_consider: 1.4
                  GoalAngleCritic:
                    enabled: true
                    cost_weight: 3.0
                    threshold_to_consider: 0.5
                  PathAlignCritic:
                    enabled: true
                    cost_weight: 2.0
                    threshold_to_consider: 0.5
                  PathFollowCritic:
                    enabled: true
                    cost_weight: 5.0
                    offset_from_furthest: 5
                    threshold_to_consider: 1.4
                  PathAngleCritic:
                    enabled: true
                    cost_weight: 2.0
                    offset_from_furthest: 4
                    threshold_to_consider: 0.5
                    max_angle_to_furthest: 1.0
                  PreferForwardCritic:
                    enabled: true
                    cost_weight: 5.0
                    threshold_to_consider: 0.5
                  VelocityDeadbandCritic:
                    enabled: true
                    cost_weight: 35.0
                    deadband_velocities: [0.05, 0.05, 0.05]
            """
        )
    if planner == "dwb":
        return _indent_follow_path(
            f"""\
                FollowPath:
                  plugin: "dwb_core::DWBLocalPlanner"
                  debug_trajectory_details: false
                  min_vel_x: -0.15
                  min_vel_y: 0.0
                  max_vel_x: {float(max_linear_vel_mps)}
                  max_vel_y: 0.0
                  max_vel_theta: {float(max_angular_vel_radps)}
                  min_speed_xy: 0.0
                  max_speed_xy: {float(max_linear_vel_mps)}
                  min_speed_theta: 0.0
                  acc_lim_x: {float(linear_accel_mps2)}
                  acc_lim_y: 0.0
                  acc_lim_theta: {float(angular_accel_radps2)}
                  decel_lim_x: {-float(linear_accel_mps2)}
                  decel_lim_y: 0.0
                  decel_lim_theta: {-float(angular_accel_radps2)}
                  vx_samples: 20
                  vy_samples: 5
                  vtheta_samples: 40
                  sim_time: 1.7
                  linear_granularity: 0.05
                  angular_granularity: 0.025
                  transform_tolerance: 0.2
                  xy_goal_tolerance: 0.10
                  trans_stopped_velocity: 0.25
                  short_circuit_trajectory_evaluation: true
                  stateful: true
                  critics: ["RotateToGoal", "Oscillation", "BaseObstacle", "GoalAlign", "PathAlign", "PathDist", "GoalDist"]
                  BaseObstacle.scale: 0.02
                  PathAlign.scale: 32.0
                  PathAlign.forward_point_distance: 0.1
                  GoalAlign.scale: 24.0
                  GoalAlign.forward_point_distance: 0.1
                  PathDist.scale: 32.0
                  GoalDist.scale: 24.0
                  RotateToGoal.scale: 32.0
                  RotateToGoal.slowing_factor: 5.0
                  RotateToGoal.lookahead_time: -1.0
                  Oscillation.scale: 1.0
                  Oscillation.oscillation_reset_dist: 0.05
                  Oscillation.oscillation_reset_angle: 0.2
            """
        )
    raise ValueError(f"unknown local planner profile: {planner}")


def apply_local_planner_profile(
    params_path: Path,
    planner: str,
    *,
    max_linear_vel_mps: float,
    max_angular_vel_radps: float,
    linear_accel_mps2: float,
    angular_accel_radps2: float,
) -> None:
    """Replace the generated ``FollowPath`` block with the selected planner."""
    if planner == "rpp":
        return
    block = _follow_path_block(
        planner,
        max_linear_vel_mps=max_linear_vel_mps,
        max_angular_vel_radps=max_angular_vel_radps,
        linear_accel_mps2=linear_accel_mps2,
        angular_accel_radps2=angular_accel_radps2,
    ).rstrip("\n").splitlines()
    lines = params_path.read_text(encoding="utf-8").splitlines()
    start: int | None = None
    for index, line in enumerate(lines):
        if line.startswith("    FollowPath:") and line.strip() == "FollowPath:":
            start = index
            break
    if start is None:
        raise RuntimeError("generated Nav2 params have no FollowPath block to replace")
    end = len(lines)
    for index in range(start + 1, len(lines)):
        line = lines[index]
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip())
        if indent < 6:
            end = index
            break
    params_path.write_text("\n".join(lines[:start] + block + lines[end:]) + "\n", encoding="utf-8")


def _source_ros_prefix() -> str:
    distro = os.environ.get("ROS_DISTRO", "jazzy").strip() or "jazzy"
    workspace = os.environ.get("ISAAC_ROS_WORKSPACE", f"{distro}_ws").strip() or f"{distro}_ws"
    return (
        f"source /opt/ros/{distro}/setup.bash; "
        f"if [ -f /isaac-sim/{workspace}/install/setup.bash ]; "
        f"then source /isaac-sim/{workspace}/install/setup.bash; fi"
    )


def _start_process(command: str, log_stream: Any) -> subprocess.Popen[str]:
    return subprocess.Popen(
        ["bash", "-lc", f"{_source_ros_prefix()}; exec {command}"],
        stdout=log_stream,
        stderr=subprocess.STDOUT,
        text=True,
        start_new_session=True,
    )


def _start_nav2_processes(
    *,
    namespace: str,
    map_yaml: Path,
    params_file: Path,
    log_path: Path,
) -> tuple[list[subprocess.Popen[str]], Any]:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_stream = log_path.open("w", encoding="utf-8")
    ns = namespace.strip("/")
    managed_commands = [
        (
            "ros2 run nav2_map_server map_server "
            f"--ros-args -r __ns:=/{ns} -p yaml_filename:={map_yaml} "
            "-p use_sim_time:=true"
        ),
        f"ros2 run nav2_planner planner_server --ros-args -r __ns:=/{ns} --params-file {params_file}",
        f"ros2 run nav2_smoother smoother_server --ros-args -r __ns:=/{ns} --params-file {params_file}",
        (
            "ros2 run nav2_controller controller_server "
            f"--ros-args -r __ns:=/{ns} --params-file {params_file} -r cmd_vel:=cmd_vel_nav"
        ),
        (
            "ros2 run nav2_behaviors behavior_server "
            f"--ros-args -r __ns:=/{ns} --params-file {params_file} -r cmd_vel:=cmd_vel_nav"
        ),
        f"ros2 run nav2_bt_navigator bt_navigator --ros-args -r __ns:=/{ns} --params-file {params_file}",
        (
            "ros2 run nav2_velocity_smoother velocity_smoother "
            f"--ros-args -r __ns:=/{ns} --params-file {params_file} -r cmd_vel:=cmd_vel_nav"
        ),
    ]
    lifecycle_command = (
        "ros2 run nav2_lifecycle_manager lifecycle_manager "
        f"--ros-args -r __ns:=/{ns} -r __node:=lifecycle_manager_navigation "
        f"--params-file {params_file}"
    )
    processes = [_start_process(command, log_stream) for command in managed_commands]
    time.sleep(NAV2_LIFECYCLE_MANAGER_START_DELAY_S)
    processes.append(_start_process(lifecycle_command, log_stream))
    return processes, log_stream


def _stop_processes(processes: list[subprocess.Popen[str]], log_stream: Any) -> None:
    for process in processes:
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGINT)
    deadline = time.monotonic() + 8.0
    for process in processes:
        remaining = max(0.1, deadline - time.monotonic())
        try:
            process.wait(timeout=remaining)
        except subprocess.TimeoutExpired:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
    for process in processes:
        try:
            process.wait(timeout=1.0)
        except subprocess.TimeoutExpired:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGKILL)
    log_stream.close()


def _destroy_node_safely(node: Node) -> None:
    try:
        node.destroy_node()
    except Exception:
        pass


def _shutdown_safely() -> None:
    if not rclpy.ok():
        return
    try:
        rclpy.shutdown()
    except Exception:
        pass


def _stamp_s(message: Odometry) -> float:
    return float(message.header.stamp.sec) + float(message.header.stamp.nanosec) / 1_000_000_000.0


class TfPreflightNode(Node):
    def __init__(self, namespace: str) -> None:
        super().__init__("airground_nav2_tf_preflight")
        self.namespace = namespace.strip("/")
        self.map_to_base_link_seen = False
        self.create_subscription(TFMessage, "/tf", self._on_tf, 50)

    def _on_tf(self, message: TFMessage) -> None:
        expected_child = f"{self.namespace}/base_link"
        for transform in message.transforms:
            if transform.header.frame_id == "map" and transform.child_frame_id == expected_child:
                self.map_to_base_link_seen = True
                return


def _wait_for_map_to_base_link_tf(namespace: str, timeout_s: float) -> None:
    rclpy.init(args=None)
    node = TfPreflightNode(namespace)
    try:
        _spin_until(
            node,
            lambda: node.map_to_base_link_seen,
            timeout_s,
            f"timed out waiting for map -> {namespace.strip('/')}/base_link TF",
        )
    finally:
        _destroy_node_safely(node)
        _shutdown_safely()


class Nav2SmokeNode(Node):
    def __init__(self, namespace: str) -> None:
        super().__init__("airground_nav2_smoke_runner")
        self.namespace = namespace.strip("/")
        # 2026-09-21 (probe tour).  In the mission lane the RayFronts runner
        # relays the controller's raw output ``/ugv/cmd_vel_nav`` onto
        # ``/ugv/cmd_vel`` (deliberately *not* the velocity smoother's
        # ``cmd_vel_smoothed``: its omega ceiling distorts RPP's curvature badly
        # enough that the UGV orbits instead of converging).  A bare probe
        # container has no runner, so without this relay Nav2 accepts goals,
        # plans, runs the controller and the UGV never moves - measured
        # 2026-09-21 on ``probe_rpp`` (174 planned paths, 4 "Failed to make
        # progress", 0 m travelled).
        self.relay_cmd_vel = True
        self.cmd_vel_pub = self.create_publisher(Twist, f"/{self.namespace}/cmd_vel", 20)
        self.latest_odom: Odometry | None = None
        self.map_messages = 0
        self.global_costmap_messages = 0
        self.local_costmap_messages = 0
        self.plan_messages = 0
        self.cmd_vel_nav_messages = 0
        self.cmd_vel_messages = 0
        self.odom_history: list[tuple[float, float, float]] = []
        self.cmd_vel_history: list[tuple[float, float, float]] = []
        # Handles kept so ``retire_smoke_subscriptions`` can drop them for the startup-only hold.
        self._smoke_subscriptions: dict[str, Any] = {
            "odom": self.create_subscription(Odometry, f"/{self.namespace}/odom", self._on_odom, 20),
        }
        map_qos = QoSProfile(
            depth=1,
            durability=DurabilityPolicy.TRANSIENT_LOCAL,
            history=HistoryPolicy.KEEP_LAST,
            reliability=ReliabilityPolicy.RELIABLE,
        )
        # Handles are kept so a readiness subscription can be retired once its wait
        # has succeeded (``retire_readiness_subscription``, switch-gated).
        self._readiness_subscriptions: dict[str, Any] = {
            "map": self.create_subscription(
                OccupancyGrid, f"/{self.namespace}/map", self._on_map, map_qos
            ),
            "global_costmap": self.create_subscription(
                OccupancyGrid,
                f"/{self.namespace}/global_costmap/costmap",
                self._on_global_costmap,
                map_qos,
            ),
            "local_costmap": self.create_subscription(
                OccupancyGrid,
                f"/{self.namespace}/local_costmap/costmap",
                self._on_local_costmap,
                map_qos,
            ),
        }
        self._smoke_subscriptions["plan"] = self.create_subscription(
            NavPath, f"/{self.namespace}/plan", self._on_plan, 10
        )
        self._smoke_subscriptions["cmd_vel_nav"] = self.create_subscription(
            Twist, f"/{self.namespace}/cmd_vel_nav", self._on_cmd_vel_nav, 20
        )
        self._smoke_subscriptions["cmd_vel"] = self.create_subscription(
            Twist, f"/{self.namespace}/cmd_vel", self._on_cmd_vel, 20
        )
        self.navigate_client: ActionClient[NavigateToPose] = ActionClient(
            self,
            NavigateToPose,
            f"/{self.namespace}/navigate_to_pose",
        )
        self.backup_client: ActionClient[BackUp] = ActionClient(
            self,
            BackUp,
            f"/{self.namespace}/backup",
        )

    def retire_readiness_subscription(self, name: str) -> None:
        """Destroy a readiness-only subscription after its wait succeeded.

        No-op unless ``AIRGROUND_LEAN_SUBSCRIPTIONS`` is on.  Called only after
        the step with that wait's count has been recorded, so the counter keeps
        its value and nothing reads it afterwards.
        """

        if not LEAN_SUBSCRIPTIONS:
            return
        subscription = self._readiness_subscriptions.pop(name, None)
        if subscription is not None:
            self.destroy_subscription(subscription)

    def retire_smoke_subscriptions(self) -> None:
        """Destroy the odom/plan/cmd_vel subscriptions before the startup-only hold.

        No-op unless ``AIRGROUND_LEAN_SUBSCRIPTIONS`` is on.  In ``--startup-only`` mode another
        runner owns the navigation goal; this process only keeps Nav2 alive until the hold ends
        and returns without reading ``latest_odom``, the pose/command histories or the plan and
        command counters again, so those callbacks (``/ugv/odom`` arrives every physics step)
        were pure overhead for the whole mission.
        """

        if not LEAN_SUBSCRIPTIONS:
            return
        for name in list(self._smoke_subscriptions):
            self.destroy_subscription(self._smoke_subscriptions.pop(name))

    def _on_odom(self, message: Odometry) -> None:
        self.latest_odom = message
        # 2026-09-21 (controller A/B tour): keep a bounded pose history so a goal
        # window can be scored on distance travelled, and a command history so
        # the ping-pong limit cycle shows up as a sign-flip rate.
        stamp = _odom_stamp_s(message)
        self.odom_history.append(
            (
                stamp,
                float(message.pose.pose.position.x),
                float(message.pose.pose.position.y),
            )
        )
        if len(self.odom_history) > 200000:
            del self.odom_history[:100000]

    def _on_map(self, _: OccupancyGrid) -> None:
        self.map_messages += 1

    def _on_global_costmap(self, _: OccupancyGrid) -> None:
        self.global_costmap_messages += 1

    def _on_local_costmap(self, _: OccupancyGrid) -> None:
        self.local_costmap_messages += 1

    def _on_plan(self, message: NavPath) -> None:
        if message.poses:
            self.plan_messages += 1

    def _on_cmd_vel_nav(self, message: Twist) -> None:
        if abs(message.linear.x) > 1.0e-4 or abs(message.angular.z) > 1.0e-4:
            self.cmd_vel_nav_messages += 1
        if self.relay_cmd_vel:
            self.cmd_vel_pub.publish(message)

    def _on_cmd_vel(self, message: Twist) -> None:
        if abs(message.linear.x) > 1.0e-4 or abs(message.angular.z) > 1.0e-4:
            self.cmd_vel_messages += 1
        stamp = self.latest_odom is not None and _odom_stamp_s(self.latest_odom) or 0.0
        self.cmd_vel_history.append((stamp, float(message.linear.x), float(message.angular.z)))
        if len(self.cmd_vel_history) > 200000:
            del self.cmd_vel_history[:100000]

    def lifecycle_state_client(self, node_name: str) -> Any:
        return self.create_client(GetState, f"/{self.namespace}/{node_name}/get_state")


def _spin_until(node: Node, predicate: Any, timeout_s: float, failure: str) -> None:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        rclpy.spin_once(node, timeout_sec=0.1)
        if predicate():
            return
    raise RuntimeError(failure)


def _wait_lifecycle_active(node: Nav2SmokeNode, node_names: tuple[str, ...], timeout_s: float) -> None:
    deadline = time.monotonic() + timeout_s
    clients = {name: node.lifecycle_state_client(name) for name in node_names}
    states = {name: "service_pending" for name in node_names}
    for name, client in clients.items():
        while time.monotonic() < deadline and not client.wait_for_service(timeout_sec=0.2):
            rclpy.spin_once(node, timeout_sec=0.05)
        if not client.service_is_ready():
            raise RuntimeError(f"lifecycle service not ready for {name}")
        states[name] = "service_ready"

    remaining = set(node_names)
    while time.monotonic() < deadline and remaining:
        for name in tuple(remaining):
            future = clients[name].call_async(GetState.Request())
            while time.monotonic() < deadline and not future.done():
                rclpy.spin_once(node, timeout_sec=0.05)
            if not future.done():
                continue
            try:
                response = future.result()
            except Exception as exc:
                states[name] = f"state_error:{type(exc).__name__}"
                continue
            if response is not None and response.current_state.label == "active":
                states[name] = "active"
                remaining.remove(name)
            elif response is not None:
                states[name] = response.current_state.label or f"state_id:{response.current_state.id}"
            else:
                states[name] = "state_response_none"
        if remaining:
            time.sleep(0.1)
    if remaining:
        state_summary = ", ".join(f"{name}={states.get(name, 'unknown')}" for name in sorted(node_names))
        raise RuntimeError(
            "Nav2 lifecycle nodes not active: "
            + ", ".join(sorted(remaining))
            + "; states: "
            + state_summary
        )


def _make_goal_from_odom(message: Odometry, distance_m: float) -> PoseStamped:
    pose = message.pose.pose
    qz = float(pose.orientation.z)
    qw = float(pose.orientation.w)
    yaw = math.atan2(2.0 * qw * qz, 1.0 - 2.0 * qz * qz)
    goal = PoseStamped()
    goal.header.frame_id = "map"
    goal.header.stamp = message.header.stamp
    goal.pose.position.x = float(pose.position.x) + distance_m * math.cos(yaw)
    goal.pose.position.y = float(pose.position.y) + distance_m * math.sin(yaw)
    goal.pose.position.z = 0.0
    goal.pose.orientation = pose.orientation
    return goal


def _odom_stamp_s(message: Odometry) -> float:
    """Simulation timestamp of an odometry sample."""
    return float(message.header.stamp.sec) + float(message.header.stamp.nanosec) / 1_000_000_000.0


def parse_tour_goals(text: str) -> list[tuple[float, float]]:
    """Parse ``"x,y;x,y"`` into a list of map-frame goals for the probe tour."""
    goals: list[tuple[float, float]] = []
    for chunk in str(text).split(";"):
        chunk = chunk.strip()
        if not chunk:
            continue
        parts = [part for part in chunk.replace(" ", "").split(",") if part]
        if len(parts) != 2:
            raise ValueError(f"tour goal must be written as 'x,y': {chunk!r}")
        goals.append((float(parts[0]), float(parts[1])))
    if not goals:
        raise ValueError("no tour goals parsed")
    return goals


@dataclass(frozen=True)
class StaticLethalMap:
    """Clearance field of the generated Nav2 map's lethal cells."""

    clearance_field_m: Any
    resolution_m: float
    origin_x_m: float
    origin_y_m: float

    def clearance_at(self, x_m: float, y_m: float) -> float:
        height, width = self.clearance_field_m.shape
        column = int((x_m - self.origin_x_m) / self.resolution_m)
        row = height - 1 - int((y_m - self.origin_y_m) / self.resolution_m)
        if 0 <= row < height and 0 <= column < width:
            return float(self.clearance_field_m[row, column])
        return 0.0


def load_static_lethal_map(map_yaml: Path, *, occupied_thresh: float = 0.65) -> StaticLethalMap | None:
    """Load the PGM next to a Nav2 map YAML and precompute a clearance field.

    2026-09-21 (controller A/B tour): the injected goals sit 0.35-0.70 m from
    structure in the static map, so "how close did the controller bring the
    robot to a lethal cell" is part of the comparison, not an afterthought.
    """
    try:
        import numpy as np
        from scipy import ndimage
    except Exception:  # pragma: no cover - optional diagnostics dependency.
        return None
    if not map_yaml.is_file():
        return None
    image_name: str | None = None
    resolution = 0.05
    negate = 0
    origin = [0.0, 0.0]
    lines = map_yaml.read_text(encoding="utf-8").splitlines()
    for index, raw_line in enumerate(lines):
        line = raw_line.strip()
        if line.startswith("image:"):
            image_name = line.split(":", 1)[1].strip()
        elif line.startswith("resolution:"):
            resolution = float(line.split(":", 1)[1].strip())
        elif line.startswith("negate:"):
            negate = int(float(line.split(":", 1)[1].strip()))
        elif line.startswith("origin:"):
            tail = line.split(":", 1)[1].strip()
            if tail.startswith("["):
                values = [value for value in tail.strip("[]").split(",") if value.strip()]
                origin = [float(values[0]), float(values[1])]
            else:
                following = []
                for extra in lines[index + 1 :]:
                    extra = extra.strip()
                    if not extra.startswith("-"):
                        break
                    # YAML list items look like "- -64.0": the numeric token is
                    # the *last* one, and stripping "-" would silently drop the
                    # sign of the origin (measured 2026-09-21: origin parsed as
                    # +64/+32, which made every clearance query land outside the
                    # map and report 0.00 m).
                    following.append(float(extra.split()[-1]))
                if len(following) >= 2:
                    origin = [following[0], following[1]]
    if image_name is None:
        return None
    pgm_path = (map_yaml.parent / image_name).resolve()
    if not pgm_path.is_file():
        return None
    raw = pgm_path.read_bytes()
    tokens: list[bytes] = []
    cursor = 0
    while len(tokens) < 4 and cursor < len(raw):
        while cursor < len(raw) and chr(raw[cursor]).isspace():
            cursor += 1
        if raw[cursor : cursor + 1] == b"#":
            while cursor < len(raw) and raw[cursor : cursor + 1] != b"\n":
                cursor += 1
            continue
        end = cursor
        while end < len(raw) and not chr(raw[end]).isspace():
            end += 1
        tokens.append(raw[cursor:end])
        cursor = end
    if len(tokens) < 4 or tokens[0] != b"P5":
        return None
    width, height = int(tokens[1]), int(tokens[2])
    while cursor < len(raw) and chr(raw[cursor]).isspace():
        cursor += 1
    pixels = np.frombuffer(raw[cursor : cursor + width * height], dtype=np.uint8)
    if pixels.size != width * height:
        return None
    image = pixels.reshape(height, width).astype(np.float32)
    normalized = image if negate else (255.0 - image)
    lethal = normalized > occupied_thresh * 255.0
    if not lethal.any():
        lethal = image < 128.0
    clearance = ndimage.distance_transform_edt(~lethal) * float(resolution)
    return StaticLethalMap(
        clearance_field_m=clearance,
        resolution_m=float(resolution),
        origin_x_m=float(origin[0]),
        origin_y_m=float(origin[1]),
    )


def run_goal_tour(
    node: Nav2SmokeNode,
    *,
    goals: list[tuple[float, float]],
    goal_timeout_s: float,
    settle_s: float,
    lethal_map: StaticLethalMap | None,
    recorder: StepRecorder,
) -> dict[str, Any]:
    """Drive a fixed list of map-frame goals and score each one.

    This is the cheap replacement for the 45-minute mission when the probe
    container runs headless (measured RTF ~0.95): ~2 minutes of wall time for the
    same injected tour.  Per goal it records the outcome, simulated time, path
    length, command sign-flip rate (the RPP ping-pong signature), the closest
    approach to the goal (the K ring criterion proxy) and the minimum clearance
    to a lethal cell of the static map.
    """
    if not node.navigate_client.wait_for_server(timeout_sec=20.0):
        raise RuntimeError("navigate_to_pose action server not ready")
    results: list[dict[str, Any]] = []
    for index, (goal_x, goal_y) in enumerate(goals):
        _spin_until(
            node, lambda: node.latest_odom is not None, 20.0, "timed out waiting for /ugv/odom"
        )
        assert node.latest_odom is not None
        start_stamp_s = _odom_stamp_s(node.latest_odom)
        odom_start = len(node.odom_history)
        cmd_start = len(node.cmd_vel_history)
        message = NavigateToPose.Goal()
        message.pose.header.frame_id = "map"
        message.pose.header.stamp = node.latest_odom.header.stamp
        message.pose.pose.position.x = float(goal_x)
        message.pose.pose.position.y = float(goal_y)
        message.pose.pose.position.z = 0.0
        message.pose.pose.orientation.w = 1.0
        future = node.navigate_client.send_goal_async(message)
        goal_handle = _wait_future(
            node, future, 20.0, "navigate_to_pose goal response timed out"
        )
        accepted = bool(goal_handle.accepted)
        outcome = "rejected"
        result_status: int | None = None
        if accepted:
            result_future = goal_handle.get_result_async()
            wall_deadline = time.monotonic() + max(60.0, goal_timeout_s * 8.0)
            while True:
                rclpy.spin_once(node, timeout_sec=0.05)
                if result_future.done():
                    result = result_future.result()
                    status = getattr(result, "status", None)
                    result_status = int(getattr(status, "value", status) or 0)
                    outcome = "reached" if result_status == 4 else f"aborted_status_{result_status}"
                    break
                latest = node.latest_odom
                if latest is not None and _odom_stamp_s(latest) - start_stamp_s >= goal_timeout_s:
                    goal_handle.cancel_goal_async()
                    outcome = "timeout"
                    for _ in range(60):
                        rclpy.spin_once(node, timeout_sec=0.02)
                    break
                if time.monotonic() > wall_deadline:
                    goal_handle.cancel_goal_async()
                    outcome = "wall_timeout"
                    break
        end_stamp_s = (
            _odom_stamp_s(node.latest_odom) if node.latest_odom is not None else start_stamp_s
        )
        window = node.odom_history[odom_start:]
        path_m = sum(
            math.hypot(second[1] - first[1], second[2] - first[2])
            for first, second in zip(window, window[1:])
        )
        closest = min(
            (math.hypot(x_m - goal_x, y_m - goal_y) for _, x_m, y_m in window),
            default=float("nan"),
        )
        clearance = (
            min((lethal_map.clearance_at(x_m, y_m) for _, x_m, y_m in window), default=float("nan"))
            if lethal_map is not None
            else float("nan")
        )
        commands = node.cmd_vel_history[cmd_start:]
        flips = 0
        previous_sign = 0
        for _, linear_x, _ in commands:
            if abs(linear_x) < 0.02:
                continue
            sign = 1 if linear_x > 0.0 else -1
            if previous_sign and sign != previous_sign:
                flips += 1
            previous_sign = sign
        duration_s = max(1.0e-6, end_stamp_s - start_stamp_s)
        entry = {
            "accepted": accepted,
            "closest_approach_m": round(closest, 3) if closest == closest else None,
            "cmd_sign_flip_rate_per_s": round(flips / duration_s, 3),
            "cmd_sign_flips": flips,
            "goal_xy_m": [round(goal_x, 3), round(goal_y, 3)],
            "index": index,
            "min_lethal_clearance_m": round(clearance, 3) if clearance == clearance else None,
            "outcome": outcome,
            "path_m": round(path_m, 3),
            "result_status": result_status,
            "ring_hit": bool(closest == closest and closest <= 0.5),
            "sim_time_s": round(duration_s, 3),
        }
        results.append(entry)
        recorder.step("tour_goal", **entry)
        settle_until = (
            _odom_stamp_s(node.latest_odom) + float(settle_s)
            if node.latest_odom is not None
            else 0.0
        )
        while node.latest_odom is not None and _odom_stamp_s(node.latest_odom) < settle_until:
            rclpy.spin_once(node, timeout_sec=0.05)
    clearances = [
        entry["min_lethal_clearance_m"]
        for entry in results
        if entry["min_lethal_clearance_m"] is not None
    ]
    summary = {
        "event": "nav2_tour_summary",
        "goal_count": len(goals),
        "max_cmd_sign_flip_rate_per_s": max(
            (entry["cmd_sign_flip_rate_per_s"] for entry in results), default=0.0
        ),
        "min_lethal_clearance_m": min(clearances) if clearances else None,
        "reached_count": sum(1 for entry in results if entry["outcome"] == "reached"),
        "ring_hit_count": sum(1 for entry in results if entry["ring_hit"]),
        "goals": results,
    }
    recorder.step("tour_summary", **{key: value for key, value in summary.items() if key != "event"})
    return summary


def _wait_future(node: Node, future: Any, timeout_s: float, failure: str) -> Any:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline and not future.done():
        rclpy.spin_once(node, timeout_sec=0.1)
    if not future.done():
        raise RuntimeError(failure)
    result = future.result()
    if result is None:
        raise RuntimeError(failure)
    return result


def _run_navigation_goal(
    node: Nav2SmokeNode,
    *,
    goal_distance_m: float,
    timeout_s: float,
) -> Any:
    _spin_until(node, lambda: node.latest_odom is not None, timeout_s, "timed out waiting for /ugv/odom")
    if not node.navigate_client.wait_for_server(timeout_sec=timeout_s):
        raise RuntimeError("navigate_to_pose action server not ready")
    goal_message = NavigateToPose.Goal()
    assert node.latest_odom is not None
    goal_message.pose = _make_goal_from_odom(node.latest_odom, goal_distance_m)
    future = node.navigate_client.send_goal_async(goal_message)
    goal_handle = _wait_future(node, future, timeout_s, "navigate_to_pose goal response timed out")
    if not goal_handle.accepted:
        raise RuntimeError("navigate_to_pose goal was rejected")
    return goal_handle


def _trigger_backup_recovery(node: Nav2SmokeNode, timeout_s: float) -> None:
    if not node.backup_client.wait_for_server(timeout_sec=timeout_s):
        raise RuntimeError("backup action server not ready")
    goal = BackUp.Goal()
    goal.target.x = -0.05
    goal.speed = 0.03
    goal.time_allowance = Duration(sec=2, nanosec=0)
    future = node.backup_client.send_goal_async(goal)
    goal_handle = _wait_future(node, future, timeout_s, "backup goal response timed out")
    if not goal_handle.accepted:
        raise RuntimeError("backup recovery goal was rejected")
    cancel_future = goal_handle.cancel_goal_async()
    _wait_future(node, cancel_future, timeout_s, "backup cancel response timed out")


def _completed_smoke_steps(output: Path) -> set[str]:
    completed_steps: set[str] = set()
    if not output.exists():
        return completed_steps
    with output.open("r", encoding="utf-8") as stream:
        for line in stream:
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            step = payload.get("step")
            status = payload.get("status")
            if isinstance(step, str) and status == "ok":
                completed_steps.add(step)
    return completed_steps


def main() -> int:
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

            stack_sampler.start_from_env_for_script(__file__)
        except Exception as _exc:  # noqa: BLE001 - a diagnostic must never stop the run
            print(f"AirGround stack sampler unavailable: {_exc}", file=_sys.stderr, flush=True)
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, help="JSONL output path")
    parser.add_argument("--namespace", default="ugv")
    parser.add_argument("--work-dir", default=None)
    parser.add_argument(
        "--map-yaml",
        help=(
            "Existing Nav2 map_server YAML derived from traversability GT. "
            "If omitted, a diagnostic free-space map is generated."
        ),
    )
    parser.add_argument("--startup-timeout-s", type=float, default=90.0)
    parser.add_argument(
        "--lifecycle-retry-attempts",
        type=int,
        default=DEFAULT_NAV2_LIFECYCLE_RETRY_ATTEMPTS,
        help="managed Nav2 node bringup attempts before failing the smoke",
    )
    parser.add_argument("--goal-distance-m", type=float, default=0.8)
    parser.add_argument(
        "--local-planner",
        choices=("rpp", "mppi", "dwb"),
        default="rpp",
        help=(
            "FollowPath plugin to test: rpp (RegulatedPurePursuit, the lane default), "
            "mppi (nav2_mppi_controller, DifferentialMotionModel) or dwb "
            "(dwb_core::DWBLocalPlanner with the Oscillation critic)."
        ),
    )
    parser.add_argument(
        "--tour-goals",
        help=(
            "semicolon-separated map-frame goals 'x,y;x,y' to drive in sequence; "
            "replaces the single --goal-distance-m probe with a scored tour "
            "(outcome, sim time, path length, command sign-flip rate, closest "
            "approach, lethal clearance)."
        ),
    )
    parser.add_argument(
        "--tour-goal-timeout-s",
        type=float,
        default=90.0,
        help="simulated seconds allowed per tour goal (default 90)",
    )
    parser.add_argument(
        "--tour-settle-s",
        type=float,
        default=2.0,
        help="simulated seconds of settle between tour goals (default 2)",
    )
    parser.add_argument(
        "--tour-output",
        help="optional JSON path for the tour summary (also written to --output as steps)",
    )
    parser.add_argument(
        "--rpp-regulated-linear-scaling",
        action=argparse.BooleanOptionalAction,
        default=DEFAULT_NAV2_REGULATED_LINEAR_SCALING,
        help=(
            "RPP use_regulated_linear_velocity_scaling (see "
            "DEFAULT_NAV2_REGULATED_LINEAR_SCALING): '--no-rpp-regulated-linear-scaling' "
            "keeps the linear velocity at the requested value in tight turns so the "
            "commanded arc stays executable for the skid-steer"
        ),
    )
    parser.add_argument(
        "--rpp-allow-reversing",
        action=argparse.BooleanOptionalAction,
        default=DEFAULT_NAV2_ALLOW_REVERSING,
        help=(
            "RegulatedPurePursuitController allow_reversing (see "
            "DEFAULT_NAV2_ALLOW_REVERSING for the measured trade-off). "
            "'--no-rpp-allow-reversing' keeps steering-only forward following"
        ),
    )
    parser.add_argument("--desired-linear-vel-mps", type=float, default=DEFAULT_NAV2_DESIRED_LINEAR_VEL_MPS)
    parser.add_argument("--max-linear-vel-mps", type=float, default=DEFAULT_NAV2_MAX_LINEAR_VEL_MPS)
    parser.add_argument("--max-angular-vel-radps", type=float, default=DEFAULT_NAV2_MAX_ANGULAR_VEL_RADPS)
    parser.add_argument("--linear-accel-mps2", type=float, default=DEFAULT_NAV2_LINEAR_ACCEL_MPS2)
    parser.add_argument("--angular-accel-radps2", type=float, default=DEFAULT_NAV2_ANGULAR_ACCEL_RADPS2)
    parser.add_argument(
        "--point-cloud-topic",
        default=None,
        help=(
            "3D obstacle source consumed by both VoxelLayers; defaults to "
            "/<ns>/sensors/ouster/point_cloud"
        ),
    )
    parser.add_argument(
        "--pointcloud-min-obstacle-height-m",
        type=float,
        default=DEFAULT_NAV2_POINT_CLOUD_MIN_OBSTACLE_HEIGHT_M,
        help=(
            "Map-frame height (m) at which a point cloud return counts as an "
            "obstacle; the RetroNeighborhood ground sits at z ~= 0, so 0.05 "
            "means 'anything 5 cm or more above the drivable surface'"
        ),
    )
    parser.add_argument(
        "--pointcloud-max-obstacle-height-m",
        type=float,
        default=DEFAULT_NAV2_POINT_CLOUD_MAX_OBSTACLE_HEIGHT_M,
        help="Map-frame height (m) above which returns are ignored by the voxel layers",
    )
    parser.add_argument(
        "--pointcloud-obstacle-range-m",
        type=float,
        default=DEFAULT_NAV2_POINT_CLOUD_OBSTACLE_RANGE_M,
        help="Voxel-layer marking range for the 3D point cloud",
    )
    parser.add_argument(
        "--pointcloud-raytrace-range-m",
        type=float,
        default=DEFAULT_NAV2_POINT_CLOUD_RAYTRACE_RANGE_M,
        help="Voxel-layer clearing range for the 3D point cloud",
    )
    parser.add_argument(
        "--costmap-resolution-m",
        type=float,
        default=DEFAULT_NAV2_COSTMAP_RESOLUTION_M,
        help="Local and global costmap resolution (must match the Nav2 map YAML)",
    )
    parser.add_argument(
        "--local-costmap-size-m",
        type=float,
        default=DEFAULT_NAV2_LOCAL_COSTMAP_SIZE_M,
        help="Local rolling window edge length in metres",
    )
    parser.add_argument(
        "--inflation-cost-scaling-factor",
        type=float,
        default=DEFAULT_NAV2_INFLATION_COST_SCALING_FACTOR,
        help=(
            "Global+local inflation decay; see "
            "DEFAULT_NAV2_INFLATION_COST_SCALING_FACTOR for the 2026-10-03 "
            "route-choice measurement that lowered it from 2.5"
        ),
    )
    parser.add_argument("--tf-startup-timeout-s", type=float, default=15.0)
    parser.add_argument(
        "--startup-only",
        action="store_true",
        help=(
            "Start Nav2, verify lifecycle/map/costmap/action readiness, then hold. "
            "Use this when another runner owns the real NavigateToPose goal."
        ),
    )
    parser.add_argument(
        "--hold-after-success-s",
        type=float,
        default=0.0,
        help="Keep Nav2 processes alive for this many seconds after all smoke steps pass.",
    )
    args = parser.parse_args()

    output = Path(args.output)
    work_dir = Path(args.work_dir) if args.work_dir else output.parent / "nav2_runtime"
    work_dir.mkdir(parents=True, exist_ok=True)
    map_yaml = work_dir / "airground_nav2_free_map.yaml"
    params_file = work_dir / "airground_nav2_params.yaml"
    log_path = work_dir / "nav2_processes.log"
    if args.map_yaml:
        map_yaml = _copy_nav2_map_yaml(Path(args.map_yaml), work_dir)
    else:
        _write_free_space_map(
            map_yaml,
            width=600,
            height=500,
            resolution=0.2,
            origin_x_m=-80.0,
            origin_y_m=-50.0,
        )
    _write_nav2_params(
        params_file,
        args.namespace,
        desired_linear_vel_mps=args.desired_linear_vel_mps,
        max_linear_vel_mps=args.max_linear_vel_mps,
        max_angular_vel_radps=args.max_angular_vel_radps,
        linear_accel_mps2=args.linear_accel_mps2,
        angular_accel_radps2=args.angular_accel_radps2,
        point_cloud_topic=args.point_cloud_topic,
        point_cloud_min_obstacle_height_m=args.pointcloud_min_obstacle_height_m,
        point_cloud_max_obstacle_height_m=args.pointcloud_max_obstacle_height_m,
        point_cloud_obstacle_range_m=args.pointcloud_obstacle_range_m,
        point_cloud_raytrace_range_m=args.pointcloud_raytrace_range_m,
        costmap_resolution_m=args.costmap_resolution_m,
        local_costmap_size_m=args.local_costmap_size_m,
        inflation_cost_scaling_factor=args.inflation_cost_scaling_factor,
        allow_reversing=bool(args.rpp_allow_reversing),
        regulated_linear_velocity_scaling=bool(args.rpp_regulated_linear_scaling),
    )
    if args.local_planner != "rpp":
        apply_local_planner_profile(
            params_file,
            args.local_planner,
            max_linear_vel_mps=args.max_linear_vel_mps,
            max_angular_vel_radps=args.max_angular_vel_radps,
            linear_accel_mps2=args.linear_accel_mps2,
            angular_accel_radps2=args.angular_accel_radps2,
        )
        print(
            json.dumps(
                {
                    "local_planner_profile": args.local_planner,
                    "params_file": str(params_file),
                },
                sort_keys=True,
            ),
            flush=True,
        )
    _wait_for_map_to_base_link_tf(args.namespace, args.tf_startup_timeout_s)

    recorder = StepRecorder(output=output, start_wall=time.monotonic())

    rclpy.init(args=None)
    node = Nav2SmokeNode(args.namespace)
    exit_code = 0
    processes: list[subprocess.Popen[str]] = []
    log_stream: Any = None
    try:
        # Nav2 bringup through the lifecycle manager can lose a single
        # change_state response (rmw reports "failed to send response ... client
        # will not receive response" and the manager then blocks until the smoke
        # timeout).  Retrying the whole managed-node group once turns that
        # transient discovery race into a non-event instead of an episode
        # failure.
        lifecycle_attempts = max(1, int(args.lifecycle_retry_attempts))
        for lifecycle_attempt in range(1, lifecycle_attempts + 1):
            attempt_log_path = log_path
            if lifecycle_attempt > 1:
                attempt_log_path = log_path.with_name(
                    f"{log_path.stem}.attempt{lifecycle_attempt}{log_path.suffix}"
                )
            processes, log_stream = _start_nav2_processes(
                namespace=args.namespace,
                map_yaml=map_yaml,
                params_file=params_file,
                log_path=attempt_log_path,
            )
            try:
                _wait_lifecycle_active(node, NAV2_NODE_NAMES, args.startup_timeout_s)
            except Exception as exc:
                if lifecycle_attempt >= lifecycle_attempts:
                    raise
                recorder.step(
                    "lifecycle_retry",
                    "ok",
                    attempt=lifecycle_attempt + 1,
                    error=str(exc)[:300],
                    exception_type=type(exc).__name__,
                )
                _stop_processes(processes, log_stream)
                processes, log_stream = [], None
                # 2026-09-18: the failed attempt can leave the process-level rcl
                # context unusable.  Measured in ``smoke_20260918_173406_type-i``:
                # attempt 2 died with "failed to create timer: the given context
                # is not valid, either rcl_init() was not called or rcl_shutdown()
                # was called" while it was building the lifecycle state clients,
                # so the built-in retry could never recover from the transient
                # map_server change_state race.  Rebuild the node (and the
                # context when rclpy reports it shut down) before retrying.
                _destroy_node_safely(node)
                if not rclpy.ok():
                    rclpy.init(args=None)
                node = Nav2SmokeNode(args.namespace)
                continue
            recorder.step("lifecycle_active", nodes=list(NAV2_NODE_NAMES), attempt=lifecycle_attempt)
            break
        _spin_until(node, lambda: node.map_messages > 0, 20.0, "timed out waiting for /ugv/map")
        recorder.step("map_received", count=node.map_messages)
        node.retire_readiness_subscription("map")
        _spin_until(
            node,
            lambda: node.global_costmap_messages > 0,
            25.0,
            "timed out waiting for /ugv/global_costmap/costmap",
        )
        recorder.step("global_costmap_active", count=node.global_costmap_messages)
        node.retire_readiness_subscription("global_costmap")
        _spin_until(
            node,
            lambda: node.local_costmap_messages > 0,
            25.0,
            "timed out waiting for /ugv/local_costmap/costmap",
        )
        recorder.step("local_costmap_active", count=node.local_costmap_messages)
        node.retire_readiness_subscription("local_costmap")
        if args.startup_only:
            if not node.navigate_client.wait_for_server(timeout_sec=min(args.startup_timeout_s, 15.0)):
                raise RuntimeError("navigate_to_pose action server not ready")
            recorder.step("action_server_ready")
            if args.hold_after_success_s > 0:
                node.retire_smoke_subscriptions()
                hold_until = time.monotonic() + args.hold_after_success_s
                while time.monotonic() < hold_until:
                    rclpy.spin_once(node, timeout_sec=0.2)
            return 0
        if args.tour_goals:
            tour_summary = run_goal_tour(
                node,
                goals=parse_tour_goals(args.tour_goals),
                goal_timeout_s=float(args.tour_goal_timeout_s),
                settle_s=float(args.tour_settle_s),
                lethal_map=load_static_lethal_map(map_yaml),
                recorder=recorder,
            )
            if args.tour_output:
                Path(args.tour_output).write_text(
                    json.dumps(tour_summary, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8",
                )
            print(
                json.dumps(
                    {key: value for key, value in tour_summary.items() if key != "goals"},
                    sort_keys=True,
                ),
                flush=True,
            )
            if args.hold_after_success_s > 0:
                hold_until = time.monotonic() + args.hold_after_success_s
                while time.monotonic() < hold_until:
                    rclpy.spin_once(node, timeout_sec=0.2)
            tour_ok = tour_summary["ring_hit_count"] == tour_summary["goal_count"]
            return 0 if tour_ok else 2
        goal_handle = _run_navigation_goal(
            node,
            goal_distance_m=args.goal_distance_m,
            timeout_s=25.0,
        )
        recorder.step("goal_accepted")
        _spin_until(node, lambda: node.plan_messages > 0, 25.0, "timed out waiting for /ugv/plan")
        recorder.step("path_received", count=node.plan_messages)
        _spin_until(
            node,
            lambda: node.cmd_vel_nav_messages > 0 or node.cmd_vel_messages > 0,
            25.0,
            "timed out waiting for Nav2 cmd_vel output",
        )
        recorder.step(
            "local_planner_active",
            cmd_vel_nav_count=node.cmd_vel_nav_messages,
            cmd_vel_count=node.cmd_vel_messages,
        )
        cancel_future = goal_handle.cancel_goal_async()
        _wait_future(node, cancel_future, 10.0, "navigate_to_pose cancel response timed out")
        recorder.step("cancel_accepted")
        _trigger_backup_recovery(node, timeout_s=15.0)
        recorder.step("stuck_recovery_triggered", recovery_action="backup")
        if args.hold_after_success_s > 0:
            hold_until = time.monotonic() + args.hold_after_success_s
            while time.monotonic() < hold_until:
                rclpy.spin_once(node, timeout_sec=0.2)
    except (Exception, KeyboardInterrupt) as exc:
        completed_steps = _completed_smoke_steps(output)
        if (
            args.startup_only
            and args.hold_after_success_s > 0.0
            and all(step in completed_steps for step in NAV2_STARTUP_ONLY_STEP_NAMES)
        ):
            recorder.step(
                "hold_interrupted_after_startup",
                "ok",
                exception_type=type(exc).__name__,
            )
        elif args.hold_after_success_s > 0.0 and all(step in completed_steps for step in NAV2_SMOKE_STEP_NAMES):
            recorder.step(
                "hold_interrupted_after_success",
                "ok",
                exception_type=type(exc).__name__,
            )
        else:
            exit_code = 2
            for step in NAV2_SMOKE_STEP_NAMES:
                if step not in completed_steps:
                    recorder.step(step, "failed", error=str(exc), exception_type=type(exc).__name__)
                    break
            print(
                json.dumps(
                    {
                        "error": str(exc),
                        "exception_type": type(exc).__name__,
                        "log": str(log_path),
                        "status": "failed",
                    },
                    sort_keys=True,
                )
            )
    finally:
        recorder.close()
        _destroy_node_safely(node)
        _shutdown_safely()
        _stop_processes(processes, log_stream)

    if exit_code == 0:
        print(
            json.dumps(
                {
                    "log": str(log_path),
                    "output": str(output),
                    "params": str(params_file),
                    "status": "ok",
                },
                sort_keys=True,
            )
        )
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
