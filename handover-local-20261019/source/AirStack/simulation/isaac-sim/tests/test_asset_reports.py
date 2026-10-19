"""Regression checks for the checked-in official USD asset reports."""

import importlib.util
import json
from pathlib import Path
import sys
import types

import pytest


REPORTS = Path(__file__).parents[1] / "assets/reports_verified"
ROBOTS = Path(__file__).parents[1] / "assets/robots"
LAUNCH_SCRIPTS = Path(__file__).parents[1] / "launch_scripts"
DOCKER = Path(__file__).parents[1] / "docker"
TOOLS = Path(__file__).parents[1] / "tools"
SCENES = Path(__file__).parents[3] / "scenes"
REPO_ROOT = Path(__file__).parents[4]
AIR_STACK_ROOT = Path(__file__).parents[3]
PX4_AIRFRAMES = Path(__file__).parents[1] / "px4/airframes"
PEGASUS_API = (
    Path(__file__).parents[1]
    / "extensions/PegasusSimulator/extensions/pegasus.simulator/pegasus/simulator/ogn/api"
)
PEGASUS_PACKAGE = (
    Path(__file__).parents[1]
    / "extensions/PegasusSimulator/extensions/pegasus.simulator/pegasus/simulator"
)


def _load(name: str) -> dict:
    with (REPORTS / name).open(encoding="utf-8") as stream:
        return json.load(stream)


def _load_tool_module(name: str):
    path = TOOLS / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_scene_prep_for_usd_test(monkeypatch):
    """Load scene_prep without requiring an Isaac Kit runtime."""
    utils = Path(__file__).parents[1] / "utils"
    monkeypatch.syspath_prepend(str(utils))
    omni = types.ModuleType("omni")
    omni.__path__ = []
    kit = types.ModuleType("omni.kit")
    kit.__path__ = []
    kit_app = types.ModuleType("omni.kit.app")
    omni_usd = types.ModuleType("omni.usd")
    omni.kit = kit
    kit.app = kit_app
    omni.usd = omni_usd
    monkeypatch.setitem(sys.modules, "omni", omni)
    monkeypatch.setitem(sys.modules, "omni.kit", kit)
    monkeypatch.setitem(sys.modules, "omni.kit.app", kit_app)
    monkeypatch.setitem(sys.modules, "omni.usd", omni_usd)

    path = utils / "scene_prep.py"
    spec = importlib.util.spec_from_file_location("airground_scene_prep_proxy_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_quadcopter_report_contract():
    report = _load("quadcopter_5_1.json")
    assert report["schema_version"] == "1.0.0"
    assert report["stage"]["default_prim"] == "/Quadcopter"
    assert report["counts"] == {
        "articulations": 1,
        "collisions": 9,
        "dofs": 8,
        "joints": 8,
        "mass_prims": 9,
        "physics_materials": 0,
        "prims": 63,
        "rigid_bodies": 9,
        "sensors": 0,
    }
    assert report["source"]["sha256"] == (
        "24199bf09fc37963119fb08a9aa1d1b08e711df324c884d01fbb76ad7ce826e7"
    )


def test_jackal_report_contract():
    report = _load("jackal_5_1.json")
    assert report["stage"]["default_prim"] == "/jackal"
    assert "/Environment" in report["stage"]["root_prims"]
    assert report["counts"]["joints"] == 4
    assert report["counts"]["rigid_bodies"] == 5
    assert report["counts"]["physics_materials"] == 1
    wheel = next(
        collision
        for collision in report["collisions"]
        if collision["path"] == "/jackal/front_left_wheel_link/collisions"
    )
    assert abs(wheel["attributes"]["radius"] - 0.098) < 1e-6
    material = report["physics_materials"][0]
    assert abs(material["attributes"]["physics:staticFriction"] - 0.2) < 1e-6
    assert abs(material["attributes"]["physics:dynamicFriction"] - 0.2) < 1e-6
    assert report["source"]["sha256"] == (
        "be499d8ed3c83deff8a1ce43dc2976ba2b1a8cc66eae80360a19f6d8bb8720ec"
    )


def test_isaac_6_0_1_quadcopter_report_matches_migration_contract():
    report_5 = _load("quadcopter_5_1.json")
    report_6 = _load("quadcopter_6_0_1.json")

    assert report_6["schema_version"] == "1.0.0"
    assert report_6["asset_id"] == "isaac_sim.quadcopter"
    assert report_6["simulator_version"] == "6.0.1"
    assert report_6["source"] == report_5["source"]
    assert report_6["stage"] == report_5["stage"]
    assert report_6["counts"] == report_5["counts"]
    assert report_6["stage"]["default_prim"] == "/Quadcopter"
    assert report_6["counts"] == {
        "articulations": 1,
        "collisions": 9,
        "dofs": 8,
        "joints": 8,
        "mass_prims": 9,
        "physics_materials": 0,
        "prims": 63,
        "rigid_bodies": 9,
        "sensors": 0,
    }

    joints = {joint["path"]: joint for joint in report_6["joints"]}
    for index in range(4):
        assert joints[f"/Quadcopter/joints/rotor{index}"]["body0"] == [
            f"/Quadcopter/rotor_arm{index}"
        ]
        assert joints[f"/Quadcopter/joints/rotor{index}"]["body1"] == [
            f"/Quadcopter/rotor{index}"
        ]
        assert joints[f"/Quadcopter/joints/rotor{index}"]["attributes"]["physics:axis"] == "X"


def test_isaac_6_0_1_jackal_report_matches_migration_contract():
    report_5 = _load("jackal_5_1.json")
    report_6 = _load("jackal_6_0_1.json")

    assert report_6["schema_version"] == "1.0.0"
    assert report_6["asset_id"] == "isaac_sim.clearpath_jackal"
    assert report_6["simulator_version"] == "6.0.1"
    assert report_6["source"] == report_5["source"]
    assert report_6["stage"] == report_5["stage"]
    assert report_6["counts"] == report_5["counts"]
    assert report_6["stage"]["default_prim"] == "/jackal"
    assert report_6["counts"] == {
        "articulations": 1,
        "collisions": 8,
        "dofs": 4,
        "joints": 4,
        "mass_prims": 6,
        "physics_materials": 1,
        "prims": 66,
        "rigid_bodies": 5,
        "sensors": 4,
    }

    wheel = next(
        collision
        for collision in report_6["collisions"]
        if collision["path"] == "/jackal/front_left_wheel_link/collisions"
    )
    assert abs(wheel["attributes"]["radius"] - 0.098) < 1e-6
    material = report_6["physics_materials"][0]
    assert abs(material["attributes"]["physics:staticFriction"] - 0.2) < 1e-6
    assert abs(material["attributes"]["physics:dynamicFriction"] - 0.2) < 1e-6


def test_target_prim_candidate_exporter_reads_retro_neighborhood_usd():
    exporter = _load_tool_module("export_target_prim_candidates")
    stage = SCENES / "RetroNeighborhood/RetroNeighborhood_Export.usd"

    manifest = exporter.export_candidates(
        stage,
        classes=("bus stop", "billboard"),
        min_volume_m3=0.1,
    )

    assert manifest["generator"] == "airground-usd-prim-candidate-exporter-v1"
    assert manifest["scene_id"] == "RetroNeighborhood"
    candidates = manifest["candidates"]
    assert candidates
    assert any("BP_BusStop" in item["prim_path"] for item in candidates)
    assert any("BP_Billboard" in item["prim_path"] for item in candidates)
    assert all(item["prim_path"].startswith("/World/stage") for item in candidates)
    assert all(len(item["center_xyz_m"]) == 3 for item in candidates)


def test_confirmation_visibility_raycast_runner_binds_physx_to_validator():
    text = (TOOLS / "validate_confirmation_visibility_raycast.py").read_text(encoding="utf-8")

    assert "make_isaac_physx_raycast_fn(scene_query)" in text
    assert "validate_confirmation_visibility_with_raycast(" in text
    assert "validate_confirmation_visibility_sensor_trace(" in text
    assert "canonical_raycast_confirmation_visibility_report_json(report)" in text
    assert "canonical_sensor_frame_confirmation_visibility_report_json(sensor_report)" in text
    assert "--sensor-trace-output" in text
    assert "--publish-sensor-topic" in text
    assert "--sensor-topic-report-output" in text
    assert "--sensor-camera-frame" in text
    assert "create_publisher(String" in text
    assert '"/ugv/confirmation_visibility_sensor_frames"' in text
    assert '"publisher_source": "isaac_physx_confirmation_visibility_raycast"' in text
    assert '"event": "confirmation_visibility_sensor_frame"' in text
    assert "DEFAULT_IGNORED_PRIM_PREFIXES" in text
    assert "AIRGROUND_SCENE_COLLIDER_MODE" in text


def test_runtime_barrier_trace_runner_uses_real_ros_topics_and_hold_action():
    text = (TOOLS / "collect_runtime_barrier_trace.py").read_text(encoding="utf-8")

    assert '"/clock"' in text
    assert '"/uav/odom"' in text
    assert '"/ugv/odom"' in text
    assert '"/ugv/cmd_vel"' in text
    assert "--require-sensor-timing" in text
    assert "--emit-full-surface" in text
    assert "--require-sensor-payloads" in text
    assert '"sensor_payloads"' in text
    assert '"data_sha256"' in text
    assert '"byte_count"' in text
    assert '"public_infos"' in text
    assert '"mission"' in text
    assert '"inbox"' in text
    assert '"last_action_status"' in text
    assert '"detection_report"' in text
    assert '"confirmation"' in text
    assert "/uav/sensors/front_stereo/left/camera_info" in text
    assert "/uav/sensors/lidar/point_cloud" in text
    assert "/ugv/sensors/front_stereo/left/camera_info" in text
    assert "/ugv/sensors/ouster/point_cloud" in text
    assert '"sensor_timing"' in text
    assert '"rgbd_stamp_s"' in text
    assert '"lidar_point_count"' in text
    assert '"runtime_barrier_step"' in text
    assert "PHASES = (" in text
    assert '"actions_applied"' in text
    assert '"physics_advanced"' in text
    assert '"observations_validated"' in text
    assert '"infos_validated"' in text
    assert "cmd_vel_publisher.publish(Twist())" in text


def test_reset_readiness_trace_runner_uses_real_ros_topics_and_reset_contract():
    pytest.importorskip("rclpy")  # the runner imports rclpy at module level (ROS environment only)
    module = _load_tool_module("collect_reset_readiness_trace")
    text = (TOOLS / "collect_reset_readiness_trace.py").read_text(encoding="utf-8")

    assert ("pause_physics", "physics") in module.SOFT_RESET_STEPS
    assert ("wait_health_handshake", "orchestrator") in module.SOFT_RESET_STEPS
    assert ("resume_physics", "physics") in module.SOFT_RESET_STEPS
    assert module.REQUIRED_HEALTH_COMPONENTS == (
        "simulator",
        "px4",
        "airstack",
        "nav2",
        "rayfronts",
        "sensors",
        "agent_adapter",
    )
    assert '"/clock"' in text
    assert '"/uav/odom"' in text
    assert '"/ugv/odom"' in text
    assert '"/ugv/cmd_vel"' in text
    assert '"/ugv/control/status"' in text
    assert "--require-sensor-payloads" in text
    assert '"sensor_payloads"' in text
    assert '"data_sha256"' in text
    assert '"byte_count"' in text
    assert "/uav/sensors/front_stereo/left/image_rect" in text
    assert "/uav/sensors/lidar/point_cloud" in text
    assert "/ugv/sensors/front_stereo/left/image_rect" in text
    assert "/ugv/sensors/ouster/point_cloud" in text
    assert '"reset_readiness_trace"' in text
    assert '"airground-real-reset-readiness-v1"' in text
    assert "def publish_twist" in text
    assert "cmd_vel_publisher.publish(twist)" in text
    assert "--probe-control-hold" in text
    assert '"control_hold_evidence"' in text
    assert '"after_dirty_status"' in text
    assert '"after_hold_status"' in text
    assert "--probe-adapter-state-clear" in text
    assert "--benchmark-package-root" in text
    assert '"adapter_state_clear_evidence"' in text
    assert "RuntimeCommunicationBridge.reset_episode_state" in text
    assert "from airground_benchmark.runtime_communication import RuntimeCommunicationBridge" in text
    assert "bridge.reset_episode_state(" in text
    assert '"communication_queue"' in text
    assert '"metric_accumulators"' in text
    assert '"late_delivery_count_after_reset"' in text
    assert "--probe-ros-queue-clear" in text
    assert '"ros_queue_clear_evidence"' in text
    assert "adapter_ros_queue_clear" in text
    assert "adapter_ros_subscription_queue" in text
    assert '"late_message_count_after_clear"' in text
    assert "ros_queue_probe_ok" in text
    assert "--probe-airstack-trajectory-clear" in text
    assert '"airstack_trajectory_clear_evidence"' in text
    assert "adapter_airstack_trajectory_buffer" in text
    assert "airstack_trajectory_probe_ok" in text
    assert "late_trajectory_count_after_clear" in text
    assert "def _probe_airstack_trajectory_clear" in text
    assert "node.count_subscribers(node.cmd_vel_topic) > 0" in text
    assert "wheel_speeds_rad_s" in text
    assert "def _control_status_dirty" in text
    assert "def _control_status_zeroed" in text
    assert "control_probe_ok" in text
    assert "from pymavlink import mavutil" in text
    assert "--probe-uav-px4-cancel" in text
    assert '"uav_cancel_evidence"' in text
    assert "MAV_CMD_DO_SET_MODE" in text
    assert "set_position_target_local_ned_send" in text
    assert "MAV_FRAME_LOCAL_NED" in text
    assert "uav_probe_ok" in text
    assert "OFFBOARD" in text
    assert "LOITER" in text
    assert "health_output.write_text" in text
    assert "create_client(Empty, rayfronts_reset_service)" in text
    assert "ActionClient" in text
    assert "NavigateToPose" in text
    assert "--probe-nav2-cancel" in text
    assert '"nav2_cancel_evidence"' in text
    assert "goals_canceling_count" in text
    assert "cancel_goal_async" in text
    assert "settle_deadline = time.monotonic() + 0.2" in text
    assert "--probe-rayfronts-reset" in text
    assert "publish_rayfronts_query" in text
    assert "publish_rayfronts_map_probe" in text
    assert "--rayfronts-map-probe-topic" in text
    assert "map_probe_subscriber_seen" in text
    assert "map_state_empty_after_reset" in text
    assert '_int_field(node.latest_rayfronts_health, "map_entry_count") == 0' in text
    assert '_int_field(node.latest_rayfronts_health, "frontier_count") == 0' in text
    assert '"rayfronts_reset_evidence"' in text
    assert "hypotheses_empty_after_reset" in text
    assert "def _int_field" in text
    assert '_int_field(node.latest_rayfronts_health, "query_count") == 0' in text
    assert "node.count_subscribers(node.rayfronts_input_topic) > 0" in text
    assert "rayfronts_probe_ok" in text
    assert 'rayfronts_reset_evidence.get("status") == "ok"' in text
    assert "node.rayfronts_health_topic in topics" in text
    assert "def _collect_stable_health_handshake" in text
    assert "--require-stable-health-handshake" in text
    assert "--stable-health-samples" in text
    assert "--stable-health-period-s" in text
    assert "--stable-health-timeout-s" in text
    assert '"stable_health_handshake_evidence"' in text
    assert "stable_health_probe_ok" in text
    assert "failed_components_by_sample" in text


def test_runtime_metrics_smoke_runner_writes_real_backend_artifact():
    text = (TOOLS / "collect_runtime_metrics_smoke.py").read_text(encoding="utf-8")

    assert '"/clock"' in text
    assert '"/uav/odom"' in text
    assert '"/ugv/odom"' in text
    assert '"/ugv/cmd_vel"' in text
    assert '"run_manifest.json"' in text
    assert '"run_summary.json"' in text
    assert '"termination_report.json"' in text
    assert '"reset_trace.json"' in text
    assert '"reset_health.json"' in text
    assert '"events.jsonl"' in text
    assert '"mode": "isaac_ros"' in text
    assert '"runtime_backend"' in text
    assert '"simulator": "isaac_sim"' in text
    assert '"ros": "ros2"' in text
    assert '"mission_start"' in text
    assert '"pose"' in text
    assert '"detection"' in text
    assert '"confirmation"' in text
    assert '"energy"' in text
    assert '"communication"' in text
    assert '"safety"' in text
    assert "sensor_payloads" in text
    assert "data_sha256" in text
    assert "--require-reset-sensor-payloads" in text
    assert "--require-airstack-trajectory-clear" in text
    assert "--airstack-trajectory-probe-topic" in text
    assert "adapter_airstack_trajectory_buffer" in text
    assert "airstack_trajectory_clear_evidence" in text
    assert "late_trajectory_count_after_clear" in text
    assert "def _probe_airstack_trajectory_clear" in text
    assert "--require-stable-health-handshake" in text
    assert "--stable-health-samples" in text
    assert '"stable_health_handshake_evidence"' in text
    assert "def _collect_stable_health_handshake" in text
    assert "full-health handshake did not reach a stable window before timeout" in text
    assert "unstable_attempts" in text
    assert "attempt_count" in text
    assert "def _health_sample" in text
    assert "last_sample_clock_s" in text
    assert "advancing /clock odometry metric samples" in text
    assert "/uav/sensors/front_stereo/left/image_rect" in text
    assert "/ugv/sensors/ouster/point_cloud" in text
    assert "--require-rayfronts-mapper-derived-hypothesis" in text
    assert "require_rayfronts_mapper_derived_hypothesis" in text
    assert "mapper_derived_required" in text
    assert "surface_hypothesis_count" in text
    assert "timed out waiting for RayFronts mapper-derived hypothesis" in text


def test_runtime_fault_smoke_runner_writes_real_termination_surface():
    text = (TOOLS / "collect_runtime_fault_smoke.py").read_text(encoding="utf-8")

    assert '"/clock"' in text
    assert '"/uav/odom"' in text
    assert '"/ugv/odom"' in text
    assert '"/ugv/cmd_vel"' in text
    assert '"runtime_fault"' in text
    assert '"run_manifest.json"' in text
    assert '"run_summary.json"' in text
    assert '"termination_report.json"' in text
    assert '"reset_trace.json"' in text
    assert '"reset_health.json"' in text
    assert '"events.jsonl"' in text
    assert '"mode": "isaac_ros"' in text
    assert '"runtime_backend"' in text
    assert '"simulator": "isaac_sim"' in text
    assert '"ros": "ros2"' in text
    assert '"event_tail"' in text
    assert '"final_health"' in text
    assert '"watchdog_evidence"' in text
    assert '"action_watchdog_timeout"' in text
    assert '"action_timeout_watchdog"' in text
    assert '"action_timeout"' in text
    assert '"agent_failure"' in text
    assert "--fault-code" in text
    assert "--fault-category" in text
    assert "--fault-agent" in text
    assert "--no-fault-agent" in text
    assert "--fault-scenario-id" in text
    assert "--fault-trigger-mode" in text
    assert "phase15_fault_injector" in text
    assert "PHASE15_FAULT_INJECTION_SURFACES" in text
    assert "--phase15-injection-timeout-s" in text
    assert "fault_injection_evidence" in text
    assert "phase15_fault_injected" in text
    assert "--action-timeout-s" in text
    assert "--action-heartbeat-topic" in text
    assert "--agent-process-command" in text
    assert "--agent-process-timeout-s" in text
    assert '"agent_process_watchdog"' in text
    assert '"agent_process_exit"' in text
    assert '"crash_evidence"' in text
    assert "subprocess.Popen" in text
    assert '"non_finite_action"' in text
    assert '"non_finite_action_validator"' in text
    assert '"action_validation_rejected"' in text
    assert '"action_validation_evidence"' in text
    assert '"too_many_invalid_actions"' in text
    assert '"invalid_action_streak_validator"' in text
    assert '"max_consecutive_invalid_actions"' in text
    assert "--max-consecutive-invalid-actions" in text
    assert '"ugv_rollover"' in text
    assert '"ugv_rollover_watchdog"' in text
    assert '"safety_threshold_exceeded"' in text
    assert '"safety_evidence"' in text
    assert "--rollover-linear-x-mps" in text
    assert "--rollover-angular-z-radps" in text
    assert "--rollover-tilt-threshold-rad" in text
    assert "--rollover-command-timeout-s" in text
    assert "_odom_tilt_rad" in text
    assert '"severe_collision"' in text
    assert '"severe_collision_watchdog"' in text
    assert '"trigger_contact_state"' in text
    assert '"unsafe_contact_threshold"' in text
    assert '"/ugv/contact_state"' in text
    assert "--collision-target-x-m" in text
    assert "--collision-command-timeout-s" in text
    assert "_wait_for_severe_collision_watchdog" in text
    assert '"pre_publish_action_gate"' in text
    assert '"status_code": 3' in text
    assert "allow_nan=False" in text
    assert "--require-sensor-payloads" in text
    assert "sensor_payloads" in text
    assert "data_sha256" in text
    assert "byte_count" in text
    assert "/uav/sensors/front_stereo/left/image_rect" in text
    assert "/ugv/sensors/ouster/point_cloud" in text


def test_runtime_api_trace_runner_uses_real_ros_topics_for_public_api_sample():
    text = (TOOLS / "collect_runtime_api_trace.py").read_text(encoding="utf-8")

    assert '"/clock"' in text
    assert '"/uav/odom"' in text
    assert '"/ugv/odom"' in text
    assert '"/ugv/cmd_vel"' in text
    assert '"/ugv/contact_state"' in text
    assert '"/ugv/control/status"' in text
    assert "--require-sensor-timing" in text
    assert "--emit-full-surface" in text
    assert "--require-sensor-payloads" in text
    assert '"sensor_payloads"' in text
    assert '"data_sha256"' in text
    assert '"byte_count"' in text
    assert '"public_infos"' in text
    assert '"mission"' in text
    assert '"inbox"' in text
    assert '"last_action_status"' in text
    assert '"detection_report"' in text
    assert '"confirmation"' in text
    assert "/uav/sensors/front_stereo/left/camera_info" in text
    assert "/uav/sensors/lidar/point_cloud" in text
    assert "/ugv/sensors/front_stereo/left/camera_info" in text
    assert "/ugv/sensors/ouster/point_cloud" in text
    assert "sensor_timing_ready" in text
    assert '"sensor_timing"' in text
    assert '"rgbd_stamp_s"' in text
    assert '"lidar_point_count"' in text
    assert '"runtime_api_observation_sample"' in text
    assert '"airground-real-runtime-api-v1"' in text
    assert '"action_batch"' in text
    assert '"motion_mode"' in text
    assert "cmd_vel_publisher.publish(Twist())" in text
    assert "self.ugv_contact_state" in text
    assert "self.ugv_control_status" in text
    assert "orientation_quat_xyzw" in text
    assert "linear_velocity_mps" in text


def test_jackal_airground_layer_contains_uav_dock_platform():
    text = (ROBOTS / "jackal_airground.usda").read_text(encoding="utf-8")

    assert 'prepend apiSchemas = ["PhysxArticulationAPI"]' in text
    assert text.count('prepend apiSchemas = ["PhysxRigidBodyAPI"]') >= 5
    assert 'custom string airground:dockPlatformPath = "/base_link/airground_dock_platform"' in text
    assert 'custom string airground:dockPlatformSource = "isaac-sim-4.5.0-compat-quadcopter-footprint-v1"' in text
    assert "custom double3 airground:dockPlatformSizeM = (0.56, 0.38, 0.04)" in text
    assert 'custom string airground:uavMountPath = "/base_link/airground_uav_mount"' in text
    assert "custom double3 airground:uavFootprintEnvelopeM = (0.48, 0.30, 0.16)" in text
    assert 'def Cube "airground_dock_platform"' in text
    assert 'prepend apiSchemas = ["PhysicsCollisionAPI"]' in text
    assert 'def Material "airground_dock_rubber"' in text
    assert "float physics:staticFriction = 1.3" in text
    assert "float physics:dynamicFriction = 1.1" in text
    assert 'def Xform "airground_uav_mount"' in text
    assert 'custom string airground:mountFrame = "ugv/platform"' in text


def test_jackal_airground_layer_overrides_wheel_friction_for_retro_ground_contact():
    text = (ROBOTS / "jackal_airground.usda").read_text(encoding="utf-8")

    assert 'over "PhysicsMaterials"' in text
    assert 'over "wheels"' in text
    # 909cc5ac (2026-09-21) retuned the wheels for real in-place turning (was 1.2 / 1.0).
    assert "float physics:staticFriction = 0.7" in text
    assert "float physics:dynamicFriction = 0.6" in text
    assert "float physics:restitution = 0" in text


def test_retro_neighborhood_launch_mounts_ugv_rgbd_and_ouster():
    text = (LAUNCH_SCRIPTS / "RetroNeighborhood_Launch.py").read_text(encoding="utf-8")
    zed_helper = (
        Path(__file__).parents[1]
        / "extensions/PegasusSimulator/extensions/pegasus.simulator/pegasus/simulator/ogn/api/spawn_zed_camera.py"
    ).read_text(encoding="utf-8")
    ouster_helper = (
        Path(__file__).parents[1]
        / "extensions/PegasusSimulator/extensions/pegasus.simulator/pegasus/simulator/ogn/api/spawn_ouster_lidar.py"
    ).read_text(encoding="utf-8")

    assert 'UGV_SENSOR_BODY_PATH = os.environ.get("AIRGROUND_UGV_SENSOR_BODY_PRIM")' in text
    assert "drone_prim=UGV_PRIM" in text
    assert "robot_name=UGV_ROBOT_NAME" in text
    assert 'camera_name="UGVZEDCamera"' in text
    assert 'left_frame_id="ugv_camera_left"' in text
    assert 'right_frame_id="ugv_camera_right"' in text
    assert 'lidar_topic_namespace="sensors/ouster"' in text
    assert 'lidar_topic_name="point_cloud"' in text
    assert 'UGV_LIDAR_FRAME_ID = os.environ.get("AIRGROUND_UGV_LIDAR_FRAME_ID") or "ugv_os1_lidar"' in text
    assert "lidar_frame_id=UGV_LIDAR_FRAME_ID" in text
    # Isaac Sim 4.5's RTX LiDAR writer publishes empty clouds, so the local lane
    # serves the same topic/frame from a CPU PhysX elevation fan.
    assert 'UGV_LIDAR_SOURCE = (os.environ.get("AIRGROUND_UGV_LIDAR_SOURCE") or "rtx")' in text
    assert "JackalProximityCloudPublisher(" in text
    assert "JackalProximityCloudConfig(" in text
    assert 'if UGV_LIDAR_SOURCE == "physx_raycast":' in text
    assert "UGV_LIDAR_FRAME_YAW_RAD = math.pi / 2.0" in text
    assert "self.ugv_proximity_cloud_publisher.publish(" in text
    assert "self.ugv_proximity_cloud_publisher.close()" in text
    assert "rigid_body_prim_path=UGV_SENSOR_BODY_PATH" in text
    assert 'ENABLE_UAV_SENSOR_GRAPHS = ENABLE_SENSOR_GRAPHS and _env_bool(' in text
    assert '"AIRGROUND_ENABLE_UAV_SENSOR_GRAPHS", True' in text
    assert 'ENABLE_UGV_SENSOR_GRAPHS = ENABLE_SENSOR_GRAPHS and _env_bool(' in text
    assert '"AIRGROUND_ENABLE_UGV_SENSOR_GRAPHS", True' in text
    assert 'ENABLE_UAV_RGBD_SENSOR_GRAPH = ENABLE_UAV_SENSOR_GRAPHS and _env_bool(' in text
    assert '"AIRGROUND_ENABLE_UAV_RGBD_SENSOR_GRAPH", True' in text
    assert 'ENABLE_UAV_LIDAR_SENSOR_GRAPH = ENABLE_UAV_SENSOR_GRAPHS and _env_bool(' in text
    assert '"AIRGROUND_ENABLE_UAV_LIDAR_SENSOR_GRAPH", True' in text
    assert 'UAV_CAMERA_WIDTH = int(os.environ.get("AIRGROUND_UAV_CAMERA_WIDTH") or "480")' in text
    assert 'UAV_CAMERA_HEIGHT = int(os.environ.get("AIRGROUND_UAV_CAMERA_HEIGHT") or "300")' in text
    assert 'AIRGROUND_RGBD_PUBLISHER_HZ = float(os.environ.get("AIRGROUND_RGBD_PUBLISHER_HZ") or "10.0")' in text
    assert 'AIRGROUND_RGBD_PUBLISHER_SURFACES = _env_csv_tokens("AIRGROUND_RGBD_PUBLISHER_SURFACES")' in text
    assert 'surface_token = f"{robot_token}_{side}"' in text
    assert 'AirGround manual RGB-D publisher surface filter selected' in text
    assert "AirGroundRgbdCameraPublisher" in text
    assert "_rgbd_surface_configs" in text
    assert 'frame_width=UAV_CAMERA_WIDTH' in text
    assert 'frame_height=UAV_CAMERA_HEIGHT' in text
    assert 'ENABLE_UGV_RGBD_SENSOR_GRAPH = ENABLE_UGV_SENSOR_GRAPHS and _env_bool(' in text
    assert '"AIRGROUND_ENABLE_UGV_RGBD_SENSOR_GRAPH", True' in text
    assert 'ENABLE_UGV_LIDAR_SENSOR_GRAPH = ENABLE_UGV_SENSOR_GRAPHS and _env_bool(' in text
    assert '"AIRGROUND_ENABLE_UGV_LIDAR_SENSOR_GRAPH", True' in text
    assert "if ENABLE_UAV_SENSOR_GRAPHS:" in text
    assert "if ENABLE_UGV_SENSOR_GRAPHS:" in text
    assert "if ENABLE_UAV_RGBD_SENSOR_GRAPH:" in text
    assert "if ENABLE_UAV_LIDAR_SENSOR_GRAPH:" in text
    assert "if ENABLE_UGV_RGBD_SENSOR_GRAPH:" in text
    assert "if ENABLE_UGV_LIDAR_SENSOR_GRAPH:" in text
    assert "AirGround UAV sensor graphs disabled by AIRGROUND_ENABLE_UAV_SENSOR_GRAPHS=false" in text
    assert "AirGround UGV sensor graphs disabled by AIRGROUND_ENABLE_UGV_SENSOR_GRAPHS=false" in text
    assert "AirGround UAV RGB-D sensor graph disabled by AIRGROUND_ENABLE_UAV_RGBD_SENSOR_GRAPH=false" in text
    assert "AirGround UAV LiDAR sensor graph disabled by AIRGROUND_ENABLE_UAV_LIDAR_SENSOR_GRAPH=false" in text
    assert "IsaacSetCameraOnRenderProduct" in zed_helper
    assert "set_targets(" in zed_helper
    assert 'attribute="inputs:cameraPrim"' in zed_helper
    assert '(("inputs:cameraPrim", left_nodes["create_rp"]), [Sdf.Path(left_camera_prim)])' in zed_helper
    assert '(("inputs:cameraPrim", right_nodes["create_rp"]), [Sdf.Path(right_camera_prim)])' in zed_helper
    assert '(("inputs:cameraPrim", left_nodes["set_camera"]), [Sdf.Path(left_camera_prim)])' in zed_helper
    assert '(("inputs:cameraPrim", right_nodes["set_camera"]), [Sdf.Path(right_camera_prim)])' in zed_helper
    assert "og.Controller.evaluate_sync(parent_graph_handle)" in zed_helper
    assert 'rep.writers.get("LdrColorSDROS2PublishImage")' in zed_helper
    assert 'rep.writers.get("DistanceToImagePlaneSDROS2PublishImage")' in zed_helper
    assert 'rep.writers.get("ROS2PublishCameraInfo")' in zed_helper
    assert "render_product_path = render_product.path" in zed_helper
    assert 'projectionType="pinhole"' in zed_helper
    assert "AIRGROUND_ZED_CAMERA_FX" in zed_helper
    assert "def _isaac_version_uses_legacy_camera_graph()" in zed_helper
    assert 'version.startswith("4.5")' in zed_helper
    assert "def _detached_camera_mount_enabled()" in zed_helper
    assert 'AIRGROUND_DETACH_GRAPHICAL_CAMERA_PRIMS' in zed_helper
    assert '"/World/AirGroundSensors"' in zed_helper
    assert "Registered detached ZED camera mount follower" in zed_helper
    assert "def _camera_publisher_mode()" in zed_helper
    assert 'AIRGROUND_CAMERA_PUBLISHER_MODE' in zed_helper
    assert 'return "manual" if _isaac_version_uses_legacy_camera_graph() else "replicator"' in zed_helper
    assert "AIRGROUND_CAMERA_PUBLISHER_MODE must be 'manual' or 'replicator'" in zed_helper
    assert "AIRGROUND_REPLICATOR_CAMERA_ATTACH_TIMING" in zed_helper
    assert 'return "post_reset" if _isaac_version_uses_legacy_camera_graph() else "spawn"' in zed_helper
    assert "def attach_zed_replicator_writers" in zed_helper
    assert "AIRGROUND_LEGACY_CAMERA_GRAPH_ATTACH_TIMING" in zed_helper
    assert "def attach_zed_legacy_omnigraph_writers" in zed_helper
    assert 'camera_surface["legacy_graph_attach_timing"] = attach_timing' in zed_helper
    assert "Deferring legacy" in zed_helper
    assert "AirGround manual RGB-D publisher selected" in zed_helper
    assert 'AIRGROUND_USE_LEGACY_SENSOR_OMNIGRAPH' in zed_helper
    assert 'AIRGROUND_LEGACY_CAMERA_GRAPH_MODE' in zed_helper
    assert '_isaac_version_uses_legacy_camera_graph(),' in zed_helper
    assert 'default_legacy_mode = "flat" if _isaac_version_uses_legacy_camera_graph() else "viewport"' in zed_helper
    assert "AIRGROUND_LEGACY_CAMERA_GRAPH_MODE must be 'flat' or 'viewport'" in zed_helper
    assert 'legacy OmniGraph camera publishers are disabled for this run' in zed_helper
    assert 'Created legacy flat ZED ROS2 camera graph' in zed_helper
    assert 'Created legacy viewport ZED ROS2 camera graph' in zed_helper
    assert 'camera_surface["mode"] = "legacy_omnigraph"' in zed_helper
    assert 'camera_surface["legacy_graph_mode"] = legacy_mode' in zed_helper
    assert 'IsaacCreateViewport' in zed_helper
    assert 'IsaacGetViewportRenderProduct' in zed_helper
    assert 'IsaacSetViewportResolution' in zed_helper
    assert 'Created Replicator ROS2 ZED camera writers' in zed_helper
    assert 'topicName="image_rect"' in zed_helper
    assert 'topicName="depth_ground_truth"' in zed_helper
    assert 'topicName="camera_info"' in zed_helper
    assert "set_targets(" in ouster_helper
    assert '(("inputs:cameraPrim", create_render), [Sdf.Path(lidar_sensor_prim)])' in ouster_helper
    assert "og.Controller.evaluate_sync(parent_graph_handle)" in ouster_helper
    assert 'rep.writers.get("RtxLidarROS2PublishPointCloud")' in ouster_helper
    assert 'AIRGROUND_USE_LEGACY_SENSOR_OMNIGRAPH' in ouster_helper
    assert 'Created Replicator ROS2 LiDAR writer' in ouster_helper
    assert "nodeNamespace=f\"{robot_name}/{lidar_topic_namespace}\"" in ouster_helper

    compose = (DOCKER / "docker-compose.yaml").read_text(encoding="utf-8")
    assert "AIRGROUND_USE_LEGACY_SENSOR_OMNIGRAPH=${AIRGROUND_USE_LEGACY_SENSOR_OMNIGRAPH:-}" in compose
    assert "AIRGROUND_LEGACY_CAMERA_GRAPH_MODE=${AIRGROUND_LEGACY_CAMERA_GRAPH_MODE:-}" in compose
    assert "AIRGROUND_DETACH_GRAPHICAL_CAMERA_PRIMS=${AIRGROUND_DETACH_GRAPHICAL_CAMERA_PRIMS:-}" in compose
    assert "AIRGROUND_CAMERA_PUBLISHER_MODE=${AIRGROUND_CAMERA_PUBLISHER_MODE:-}" in compose
    assert "AIRGROUND_REPLICATOR_CAMERA_ATTACH_TIMING=${AIRGROUND_REPLICATOR_CAMERA_ATTACH_TIMING:-}" in compose
    assert "AIRGROUND_RGBD_PUBLISHER_HZ=${AIRGROUND_RGBD_PUBLISHER_HZ:-10}" in compose
    assert "AIRGROUND_RGBD_PUBLISHER_SURFACES=${AIRGROUND_RGBD_PUBLISHER_SURFACES:-}" in compose
    assert "AIRGROUND_DOCKER_HOME=${AIRGROUND_DOCKER_HOME:-${HOME}/docker}" in compose
    assert "${AIRGROUND_DOCKER_HOME:-${HOME}/docker}/isaac-sim/cache/main:/isaac-sim/.cache" in compose


def test_graphical_uav_sensors_default_to_xform_attachment():
    zed_helper = (PEGASUS_API / "spawn_zed_camera.py").read_text(encoding="utf-8")
    ouster_helper = (PEGASUS_API / "spawn_ouster_lidar.py").read_text(encoding="utf-8")

    for helper in (zed_helper, ouster_helper):
        assert "AIRGROUND_USE_SENSOR_FIXED_JOINTS" in helper
        assert "def _graphical_sensor_fixed_joints_enabled()" in helper
        assert "def _strip_graphical_sensor_physics(root_prim)" in helper
        assert 'return _env_bool("AIRGROUND_USE_SENSOR_FIXED_JOINTS", False)' in helper
        assert "attach_with_fixed_joint = _graphical_sensor_fixed_joints_enabled()" in helper
        assert "not attach_with_fixed_joint" in helper
        assert "if attach_with_fixed_joint:" in helper
        assert "stack = [root_prim]" in helper
        assert "physx_utils.removeCollider(prim)" in helper
        assert "UsdPhysics.RigidBodyAPI" in helper
        assert "UsdPhysics.CollisionAPI" in helper
        assert "UsdPhysics.MeshCollisionAPI" in helper
        assert "UsdPhysics.MassAPI" in helper
        assert helper.index("if attach_with_fixed_joint:") < helper.index(
            "physx_utils.createJoint("
        )

    assert "return camera_prim_path" in zed_helper
    assert "Stripped physics APIs from graphical camera subtree" in zed_helper
    assert "def _make_graphical_sensor_physics_kinematic(root_prim)" in zed_helper
    assert "CreateKinematicEnabledAttr().Set(True)" in zed_helper
    assert "Configured graphical camera rigid bodies as kinematic" in zed_helper
    reference_index = zed_helper.index("prim.GetReferences().AddReference(camera_usd)")
    strip_index = zed_helper.index("stripped_physics_api_count = _strip_graphical_sensor_physics(prim)")
    first_update_after_reference = zed_helper.index("app.update()", reference_index)
    assert reference_index < strip_index < first_update_after_reference
    assert (
        "# Apply RigidBody API only for the legacy fixed-joint attachment mode."
        in ouster_helper
    )
    assert "Stripped physics APIs from graphical LiDAR subtree" in ouster_helper
    assert "adding extra rigid bodies to the Quadcopter articulation perturbs PX4" in ouster_helper
    assert "UsdPhysics.RigidBodyAPI.Apply(lidar_prim)" in ouster_helper
    assert ouster_helper.index("if attach_with_fixed_joint:\n        try:") < ouster_helper.index(
        "UsdPhysics.RigidBodyAPI.Apply(lidar_prim)"
    )


def test_retro_neighborhood_launch_supports_headless_smoke_env():
    text = (LAUNCH_SCRIPTS / "RetroNeighborhood_Launch.py").read_text(encoding="utf-8")

    assert "from isaacsim.core.api.world import World" in text
    assert "from omni.isaac.core.world import World" not in text
    assert 'AIRGROUND_HEADLESS = _env_bool("AIRGROUND_HEADLESS", False)' in text
    assert 'AIRGROUND_RENDER = _env_bool("AIRGROUND_RENDER", not AIRGROUND_HEADLESS)' in text
    assert 'AIRGROUND_RENDERER = os.environ.get("AIRGROUND_RENDERER")' in text
    assert '"MinimalRendering" if AIRGROUND_HEADLESS and not AIRGROUND_RENDER else "RayTracedLighting"' in text
    assert "AIRGROUND_RENDER_WIDTH" in text
    assert "AIRGROUND_RENDER_HEIGHT" in text
    assert 'AIRGROUND_DISABLE_VIEWPORT_UPDATES = _env_bool(' in text
    assert '"AIRGROUND_DISABLE_VIEWPORT_UPDATES"' in text
    assert "AIRGROUND_HEADLESS and not AIRGROUND_RENDER" in text
    assert 'AIRGROUND_RENDER_STARTUP_WARMUP_STEPS = int(os.environ.get("AIRGROUND_RENDER_STARTUP_WARMUP_STEPS") or "0")' in text
    assert 'AIRGROUND_MAIN_LOOP_TRACE_EVERY_N = int(os.environ.get("AIRGROUND_MAIN_LOOP_TRACE_EVERY_N") or "0")' in text
    assert 'AIRGROUND_MAIN_LOOP_TRACE_FILE = os.environ.get("AIRGROUND_MAIN_LOOP_TRACE_FILE") or ""' in text
    assert 'AIRGROUND_UAV_CONTROL_STEP_RENDER = _env_bool(' in text
    assert '"AIRGROUND_UAV_CONTROL_STEP_RENDER"' in text
    assert 'AIRGROUND_USE_DIRECT_JACKAL_ADAPTER = _env_bool(' in text
    assert '"AIRGROUND_USE_DIRECT_JACKAL_ADAPTER"' in text
    assert 'UGV_YAW = float(os.environ.get("UGV_YAW") or "0.0")' in text
    assert 'raise ValueError("UGV_YAW must be finite")' in text
    assert "UGV_ORIENTATION_WXYZ = np.asarray(" in text
    assert "orientation=UGV_ORIENTATION_WXYZ" in text
    assert '"status": "skipped_articulation_root"' in text
    assert '"articulation_root_velocity_reset_uses_multi_body_tensor_view"' in text
    assert '"isaac45_articulation_root_velocity_tensor_shape_guard"' in text
    assert '"headless": AIRGROUND_HEADLESS' in text
    assert '"hide_gui": AIRGROUND_HEADLESS' in text
    assert '"renderer": AIRGROUND_RENDERER' in text
    assert '"disable_viewport_updates": AIRGROUND_DISABLE_VIEWPORT_UPDATES' in text
    assert '"width": AIRGROUND_RENDER_WIDTH' in text
    assert '"height": AIRGROUND_RENDER_HEIGHT' in text
    assert '"extra_args": _APP_EXTRA_ARGS' in text
    assert '_APP_EXTRA_ARGS = ["--ext-folder", PEGASUS_EXT_FOLDER]' in text
    assert "def _render_for_main_loop_step(self, step_count: int) -> bool:" in text
    assert "AIRGROUND_RENDER_STARTUP_WARMUP_STEPS" in text
    assert 'AIRGROUND_RENDER_ON_CAMERA_DUE = _env_bool("AIRGROUND_RENDER_ON_CAMERA_DUE", False)' in text
    assert "def _camera_frame_due(self) -> bool | None:" in text
    assert "publisher.would_publish(current_s + rendering_dt)" in text
    assert "def _trace_main_loop(" in text
    assert "trace_path.parent.mkdir(parents=True, exist_ok=True)" in text
    assert "self.world.step(render=render_step)" in text
    assert "self.app.step_world(render=AIRGROUND_UAV_CONTROL_STEP_RENDER)" in text
    assert 'MAX_STEPS = int(os.environ.get("AIRGROUND_MAX_STEPS") or "0")' in text
    assert "AIRGROUND_MAX_STEPS reached" in text
    assert "AIRGROUND_PEGASUS_EXT_FOLDER" in text
    assert "ext_manager.add_path(PEGASUS_EXT_FOLDER)" in text
    assert '"pegasus.simulator"' in text
    assert '"airlab.pegasus"' not in text
    assert "PLAY_SIM_ON_START" in text


def test_isaac_compose_uses_airground_healthcheck():
    compose = (DOCKER / "docker-compose.yaml").read_text(encoding="utf-8")
    healthcheck = (DOCKER / "airground-healthcheck.sh").read_text(encoding="utf-8")

    assert "healthcheck:" in compose
    assert "AIRGROUND_ENABLE_UGV_SENSOR_GRAPHS=${AIRGROUND_ENABLE_UGV_SENSOR_GRAPHS:-true}" in compose
    assert "AIRGROUND_ENABLE_UAV_SENSOR_GRAPHS=${AIRGROUND_ENABLE_UAV_SENSOR_GRAPHS:-true}" in compose
    assert "AIRGROUND_ENABLE_UAV_RGBD_SENSOR_GRAPH=${AIRGROUND_ENABLE_UAV_RGBD_SENSOR_GRAPH:-true}" in compose
    assert "AIRGROUND_ENABLE_UAV_LIDAR_SENSOR_GRAPH=${AIRGROUND_ENABLE_UAV_LIDAR_SENSOR_GRAPH:-true}" in compose
    assert "AIRGROUND_UAV_CAMERA_WIDTH=${AIRGROUND_UAV_CAMERA_WIDTH:-480}" in compose
    assert "AIRGROUND_UAV_CAMERA_HEIGHT=${AIRGROUND_UAV_CAMERA_HEIGHT:-300}" in compose
    assert "ROS_UBUNTU_CODENAME=${AIRGROUND_ROS_UBUNTU_CODENAME:-${ROS_UBUNTU_CODENAME:-jammy}}" in compose
    assert "ISAAC_SIM_KIT_VERSION=${AIRGROUND_ISAAC_SIM_KIT_VERSION:-${ISAAC_SIM_KIT_VERSION:-4.5}}" in compose
    assert "AIRGROUND_RENDER_WIDTH=${AIRGROUND_RENDER_WIDTH:-}" in compose
    assert "AIRGROUND_RENDER_HEIGHT=${AIRGROUND_RENDER_HEIGHT:-}" in compose
    assert "AIRGROUND_UAV_CONTROL_STEP_RENDER=${AIRGROUND_UAV_CONTROL_STEP_RENDER:-}" in compose
    assert "AIRGROUND_DISABLE_VIEWPORT_UPDATES=${AIRGROUND_DISABLE_VIEWPORT_UPDATES:-}" in compose
    assert "AIRGROUND_RENDER_STARTUP_WARMUP_STEPS=${AIRGROUND_RENDER_STARTUP_WARMUP_STEPS:-0}" in compose
    assert "AIRGROUND_MAIN_LOOP_TRACE_EVERY_N=${AIRGROUND_MAIN_LOOP_TRACE_EVERY_N:-0}" in compose
    assert "AIRGROUND_MAIN_LOOP_TRACE_FILE=${AIRGROUND_MAIN_LOOP_TRACE_FILE:-}" in compose
    assert "UGV_YAW=${UGV_YAW:-0.0}" in compose
    assert "AIRGROUND_ENABLE_UGV_RGBD_SENSOR_GRAPH=${AIRGROUND_ENABLE_UGV_RGBD_SENSOR_GRAPH:-true}" in compose
    assert "AIRGROUND_ENABLE_UGV_LIDAR_SENSOR_GRAPH=${AIRGROUND_ENABLE_UGV_LIDAR_SENSOR_GRAPH:-true}" in compose
    assert "privileged: ${AIRGROUND_ISAAC_PRIVILEGED:-true}" in compose
    assert "/isaac-sim/AirStack/simulation/isaac-sim/docker/airground-healthcheck.sh" in compose
    assert "AIRGROUND_MAX_STEPS reached" in healthcheck
    assert "AirGround fast headless exit." in healthcheck
    assert "Closing simulation." in healthcheck
    assert "compact_log=" in healthcheck
    assert 'grep -q "AppReady"' not in healthcheck


def test_pegasus_headless_imports_do_not_eager_load_legacy_dynamic_control():
    package_init = (PEGASUS_PACKAGE / "__init__.py").read_text(encoding="utf-8")
    vehicles_init = (PEGASUS_PACKAGE / "logic/vehicles/__init__.py").read_text(
        encoding="utf-8"
    )
    extension_toml = (
        Path(__file__).parents[1]
        / "extensions/PegasusSimulator/extensions/pegasus.simulator/config/extension.toml"
    ).read_text(encoding="utf-8")
    px4_database = (
        PEGASUS_PACKAGE / "ogn/OgnPegasusMultirotorPX4NodeDatabase.py"
    ).read_text(encoding="utf-8")
    node_base = (
        PEGASUS_PACKAGE / "ogn/python/nodes/OgnPegasusMultirotorNodeBase.py"
    ).read_text(encoding="utf-8")
    vehicle = (PEGASUS_PACKAGE / "logic/vehicles/vehicle.py").read_text(
        encoding="utf-8"
    )

    assert "from .extension import Pegasus_SimulatorExtension" not in package_init
    assert "from .vehicle import Vehicle" not in vehicles_init
    assert "from .multirotor import Multirotor" not in vehicles_init
    assert '"omni.isaac.core" = {}' not in extension_toml
    assert '"isaacsim.core.api" = {}' in extension_toml
    assert '"isaacsim.core.prims" = {}' in extension_toml
    assert '"isaacsim.core.utils" = {}' in extension_toml
    assert "from isaacsim.core.utils.stage import get_current_stage" in px4_database
    assert "from isaacsim.core.prims import GeometryPrim, RigidPrim, XFormPrim" in node_base
    assert "from isaacsim.core.api.world import World" in node_base
    assert "omni.isaac.dynamic_control is unavailable" in vehicle
    assert "import omni.isaac.dynamic_control" not in package_init
    assert "from omni.isaac.dynamic_control" not in package_init
    assert "import omni.isaac.dynamic_control" not in vehicles_init
    assert "from omni.isaac.dynamic_control" not in vehicles_init


def test_isaac_4_5_docker_compose_and_launch_defaults():
    dockerfile = (DOCKER / "Dockerfile.isaac-ros").read_text(encoding="utf-8")
    compose = (DOCKER / "docker-compose.yaml").read_text(encoding="utf-8")
    launch = (LAUNCH_SCRIPTS / "RetroNeighborhood_Launch.py").read_text(encoding="utf-8")
    omni_template = (DOCKER / "omni_pass_TEMPLATE.env").read_text(encoding="utf-8")
    air_stack_env = (AIR_STACK_ROOT / ".env").read_text(encoding="utf-8")
    root_launcher = (REPO_ROOT / "launch_raven.sh").read_text(encoding="utf-8")

    assert 'ARG ISAAC_VERSION="4.5.0"' in dockerfile
    assert 'ARG ROS_DISTRO="humble"' in dockerfile
    assert 'ARG ROS_UBUNTU_CODENAME="jammy"' in dockerfile
    assert 'ARG ISAAC_ROS_WORKSPACE="humble_ws"' in dockerfile
    assert "FROM nvcr.io/nvidia/isaac-sim:${ISAAC_VERSION}" in dockerfile
    assert "isaacsim_bringup" in dockerfile
    assert "elif [ -d \"${isaac_dir_name}/${ISAAC_ROS_WORKSPACE}/src/isaacsim\" ]" in dockerfile
    assert "ENV LD_LIBRARY_PATH=/opt/ros/${ROS_DISTRO}/lib:/${ROS_DISTRO}/lib" in dockerfile
    assert "ENV LD_LIBRARY_PATH=$LD_LIBRARY_PATH" not in dockerfile
    assert "ENV LD_LIBRARY_PATH=${LD_LIBRARY_PATH" not in dockerfile
    assert "COPY extensions/PegasusSimulator/extensions/pegasus.simulator" in dockerfile
    assert "PegasusSimulator-AirStack-Integration.git" not in dockerfile
    assert "git clone --depth 1 https://github.com/castacks/PegasusSimulator" not in dockerfile
    assert "-e /isaac-sim/.local/share/ov/data/documents/Kit/shared/exts/pegasus.simulator" in dockerfile

    assert "v${DOCKER_IMAGE_TAG}_isaac-sim-${ISAAC_VERSION:-4.5.0}" in compose
    assert "ISAAC_VERSION: ${ISAAC_VERSION:-4.5.0}" in compose
    assert "PX4_VERSION: ${PX4_VERSION:-v1.16.1}" in compose
    assert "ROS_DISTRO: ${AIRGROUND_ROS_DISTRO:-${ROS_DISTRO:-humble}}" in compose
    assert "ROS_UBUNTU_CODENAME: ${AIRGROUND_ROS_UBUNTU_CODENAME:-${ROS_UBUNTU_CODENAME:-jammy}}" in compose
    assert "ISAAC_ROS_WORKSPACE: ${AIRGROUND_ISAAC_ROS_WORKSPACE:-${ISAAC_ROS_WORKSPACE:-humble_ws}}" in compose
    assert "ros2 launch ${AIRGROUND_ISAAC_SIM_ROS_PACKAGE:-${ISAAC_SIM_ROS_PACKAGE:-isaacsim}}" in compose
    assert "${ISAAC_SIM_ROS_LAUNCH:-run_isaacsim.launch.py}" in compose
    assert "ISAAC_SIM_FOREGROUND=${ISAAC_SIM_FOREGROUND:-false}" in compose
    assert "ISAAC_SIM_USE_STANDALONE=${ISAAC_SIM_USE_STANDALONE:-false}" in compose
    assert "ISAAC_SIM_SCRIPT_NAME=${ISAAC_SIM_SCRIPT_NAME:-RetroNeighborhood_Launch.py}" in compose
    assert "ISAAC_ROS_BRIDGE_PYTHONPATH=/isaac-sim/exts/isaacsim.ros2.bridge/$${ROS_DISTRO:-humble}/rclpy" in compose
    # AIRGROUND_FASTDDS_PATCHED_LIB_DIR (default empty) may go first; the bundled bridge libraries always follow.
    assert ("ISAAC_ROS_BRIDGE_LD_LIBRARY_PATH=$${AIRGROUND_FASTDDS_PATCHED_LIB_DIR:+$${AIRGROUND_FASTDDS_PATCHED_LIB_DIR}:}"
            "/isaac-sim/exts/isaacsim.ros2.bridge/$${ROS_DISTRO:-humble}/lib") in compose
    assert 'if [ \\"$${ISAAC_SIM_FOREGROUND}\\" = ' in compose
    assert "exec env PYTHONPATH=" in compose
    assert "/isaac-sim/python.sh /isaac-sim/AirStack/simulation/isaac-sim/launch_scripts/$${ISAAC_SIM_SCRIPT_NAME}" in compose
    assert "ISAAC_SIM_ROS_PACKAGE=${AIRGROUND_ISAAC_SIM_ROS_PACKAGE:-${ISAAC_SIM_ROS_PACKAGE:-isaacsim}}" in compose
    assert "ROS_DISTRO=${AIRGROUND_ROS_DISTRO:-${ROS_DISTRO:-humble}}" in compose
    assert "ISAAC_ROS_WORKSPACE=${AIRGROUND_ISAAC_ROS_WORKSPACE:-${ISAAC_ROS_WORKSPACE:-humble_ws}}" in compose
    assert "AIRGROUND_HEADLESS=${AIRGROUND_HEADLESS:-false}" in compose
    assert "AIRGROUND_RENDER=${AIRGROUND_RENDER:-true}" in compose
    assert "AIRGROUND_DISABLE_VIEWPORT_UPDATES=${AIRGROUND_DISABLE_VIEWPORT_UPDATES:-}" in compose
    assert "AIRGROUND_RENDER_STARTUP_WARMUP_STEPS=${AIRGROUND_RENDER_STARTUP_WARMUP_STEPS:-0}" in compose
    assert "AIRGROUND_RENDER_MAIN_LOOP_MODE=${AIRGROUND_RENDER_MAIN_LOOP_MODE:-world_step}" in compose
    assert "AIRGROUND_RENDER_PULSE_EVERY_N=${AIRGROUND_RENDER_PULSE_EVERY_N:-0}" in compose
    assert "AIRGROUND_RGBD_PUBLISHER_SURFACES=${AIRGROUND_RGBD_PUBLISHER_SURFACES:-}" in compose
    assert "AIRGROUND_ASSET_ROOT=${AIRGROUND_ASSET_ROOT:-/isaac-sim/AirGroundAssets/4.5.0}" in compose
    assert "AIRGROUND_UAV_MODEL=${AIRGROUND_UAV_MODEL:-quadcopter}" in compose
    assert "AIRGROUND_ENV_URL=${AIRGROUND_ENV_URL:-}" in compose
    assert "AIRGROUND_ENABLE_SENSOR_GRAPHS=${AIRGROUND_ENABLE_SENSOR_GRAPHS:-true}" in compose
    assert "AIRGROUND_CREATE_DOCK_JOINT=${AIRGROUND_CREATE_DOCK_JOINT:-true}" in compose
    assert "UGV_Z=${UGV_Z:-0.20}" in compose
    assert "AIRGROUND_JACKAL_CMD_VEL_BACKEND=${AIRGROUND_JACKAL_CMD_VEL_BACKEND:-}" in compose
    assert "AIRGROUND_USE_DIRECT_JACKAL_ADAPTER=${AIRGROUND_USE_DIRECT_JACKAL_ADAPTER:-}" in compose
    assert (
        "AIRGROUND_JACKAL_WHEEL_VELOCITY_SCALE="
        "${AIRGROUND_JACKAL_WHEEL_VELOCITY_SCALE:-1.0}"
    ) in compose
    assert (
        "AIRGROUND_ENABLE_UGV_PROXIMITY_SCAN=${AIRGROUND_ENABLE_UGV_PROXIMITY_SCAN:-false}"
    ) in compose
    assert (
        "AIRGROUND_UGV_PROXIMITY_SCAN_RAY_COUNT=${AIRGROUND_UGV_PROXIMITY_SCAN_RAY_COUNT:-240}"
    ) in compose
    assert (
        "AIRGROUND_UGV_PROXIMITY_SCAN_MAX_RANGE_M=${AIRGROUND_UGV_PROXIMITY_SCAN_MAX_RANGE_M:-12.0}"
    ) in compose
    assert "../../../../RayFronts:/isaac-sim/RayFronts:rw" in compose
    assert "Isaac-Sim Full/${AIRGROUND_ISAAC_SIM_KIT_VERSION:-${ISAAC_SIM_KIT_VERSION:-4.5}}/user.config.json" in compose
    assert "airground assets fetch --simulator-version 4.5.0 --cache assets/cache" in compose

    assert 'ENV_URL = os.environ.get("AIRGROUND_ENV_URL") or DEFAULT_ENV_URL' in launch
    assert 'ASSET_ROOT = os.environ.get("AIRGROUND_ASSET_ROOT") or "/isaac-sim/AirGroundAssets/4.5.0"' in launch
    assert 'UGV_Z = float(os.environ.get("UGV_Z") or "0.20")' in launch
    assert "UGV_WHEEL_VELOCITY_SCALE = float(" in launch
    assert 'AIRGROUND_RENDER_MAIN_LOOP_MODE = os.environ.get("AIRGROUND_RENDER_MAIN_LOOP_MODE", "world_step")' in launch
    assert 'AIRGROUND_UAV_CONTROL_STEP_RENDER = _env_bool(' in launch
    assert 'AIRGROUND_USE_DIRECT_JACKAL_ADAPTER = _env_bool(' in launch
    assert 'AIRGROUND_RENDER_MAIN_LOOP_MODE == "replicator_pulse"' in launch
    assert 'rep.orchestrator.step(rt_subframes=1, delta_time=0.0, pause_timeline=False)' in launch
    assert "attach_zed_replicator_writers" in launch
    assert "AirGround post-reset Replicator RGB-D writers attached" in launch
    assert "attach_zed_legacy_omnigraph_writers" in launch
    assert "AirGround post-reset legacy RGB-D camera graphs attached" in launch
    assert "JackalDriveConfig(" in launch
    assert "JackalDirectJointVelocityRobot" in launch
    assert "AirGround UGV using direct dynamic-control Jackal adapter" in launch
    assert "wheel_velocity_scale=UGV_WHEEL_VELOCITY_SCALE" in launch
    assert 'OMNI_SERVER="omniverse://airlab-nucleus.andrew.cmu.edu/NVIDIA/Assets/Isaac/6.0"' in omni_template
    assert "UGV_Z=0.20" in air_stack_env
    assert "AIRGROUND_UAV_CONTROL_STEP_RENDER=\"false\"" in air_stack_env
    assert "AIRGROUND_USE_DIRECT_JACKAL_ADAPTER=\"true\"" in air_stack_env
    assert "AIRGROUND_JACKAL_WHEEL_VELOCITY_SCALE=1.0" in air_stack_env
    assert "UGV_X=0.13" in air_stack_env
    assert "UGV_Y=-18.96" in air_stack_env
    assert "DRONE_X=0.13" in air_stack_env
    assert "DRONE_Y=-18.96" in air_stack_env
    assert "DRONE_Z=0.45" in air_stack_env
    assert "UGV_X=$UGV_X UGV_Y=$UGV_Y UGV_Z=$UGV_Z" in root_launcher
    assert "-e UGV_X=$UGV_X -e UGV_Y=$UGV_Y -e UGV_Z=$UGV_Z" in root_launcher


def test_jackal_route_smoke_runner_uses_real_ros_topics():
    runner = (Path(__file__).parents[1] / "tools/run_jackal_route_smoke.py").read_text(
        encoding="utf-8"
    )

    assert "STANDARD_ROUTES" in runner
    assert "node.create_publisher(Twist, f\"/{args.namespace}/cmd_vel\", 10)" in runner
    assert "node.create_subscription(Odometry, f\"/{args.namespace}/odom\"" in runner
    assert "node.create_subscription(" in runner
    assert "f\"/{args.namespace}/contact_state\"" in runner
    assert '"event": "jackal_ground_route"' in runner
    assert "--settle-time-s" in runner
    assert "_settle_before_routes(" in runner
    assert '"contact_log_available": bool(route_contact_samples)' in runner
    assert '"normal_wheel_ground_contact_count": int(normal_contact_count)' in runner
    assert "PhysX contact-stream evidence" in runner
    assert 'parser.add_argument(\n        "--cycles"' in runner
    assert "cycle_index * len(STANDARD_ROUTES) + base_index" in runner
    assert '"cycle_index": route_index // len(STANDARD_ROUTES)' in runner
    assert '"route_base_index": route_index % len(STANDARD_ROUTES)' in runner
    assert '"event": "jackal_precision"' in runner
    assert "--precision-output" in runner
    assert "--precision-only" in runner
    assert '"static_drift_m": float(static["drift_m"])' in runner
    assert '"static_duration_s": float(static["duration_s"])' in runner
    assert '"static_jitter": static["jitter"]' in runner
    assert '"straight_target_distance_m": float(straight["target_distance_m"])' in runner
    assert '"straight_endpoint_error_m": float(straight["endpoint_error_m"])' in runner
    assert '"straight_distance_m": float(straight["straight_distance_m"])' in runner
    assert '"straight_jitter": straight["jitter"]' in runner
    assert '"contact_sample_count": int(summary["contact_sample_count"])' in runner
    # Flat-ground ride quality (2026-09-21 contact-offset fix) is measured on
    # every route and on the static/straight precision segments.
    assert "DEFAULT_JITTER_THRESHOLD_M" in runner
    assert '"jitter": _jitter_metrics(route_samples)' in runner
    assert "def _jitter_metrics(" in runner
    assert '"threshold_exceedance_fraction": round(exceedance_fraction, 6)' in runner


def test_nav2_smoke_runner_uses_real_nav2_stack():
    runner = (Path(__file__).parents[1] / "tools/run_nav2_smoke.py").read_text(
        encoding="utf-8"
    )
    dockerfile = (Path(__file__).parents[1] / "docker/Dockerfile.isaac-ros").read_text(
        encoding="utf-8"
    )

    assert "ros2 run nav2_map_server map_server" in runner
    assert "ros2 run nav2_planner planner_server" in runner
    assert "ros2 run nav2_controller controller_server" in runner
    assert "ros2 run nav2_bt_navigator bt_navigator" in runner
    assert "ros2 run nav2_lifecycle_manager lifecycle_manager" in runner
    assert 'plugin: "nav2_navfn_planner/NavfnPlanner"' in runner
    assert 'nav2_navfn_planner::NavfnPlanner' not in runner
    assert 'ActionClient[NavigateToPose]' in runner
    assert 'ActionClient[BackUp]' in runner
    assert 'f"/{self.namespace}/odom"' in runner
    assert 'f"/{self.namespace}/cmd_vel_nav"' in runner
    assert 'f"/{self.namespace}/navigate_to_pose"' in runner
    assert 'f"/{self.namespace}/backup"' in runner
    assert '"event": "nav2_smoke_step"' in runner
    assert "width=600" in runner
    assert "height=500" in runner
    assert "origin_x_m=-80.0" in runner
    assert "origin_y_m=-50.0" in runner
    assert "--map-yaml" in runner
    assert "_copy_nav2_map_yaml" in runner
    # 2026-09-22: both speed axes doubled (0.4/0.5 -> 0.8/1.0 m/s) with the
    # doubling measured on the live rig; see tests/test_nav2_params_generation.py.
    assert "DEFAULT_NAV2_DESIRED_LINEAR_VEL_MPS = 0.8" in runner
    assert "DEFAULT_NAV2_MAX_LINEAR_VEL_MPS = 1.0" in runner
    assert "--desired-linear-vel-mps" in runner
    assert "--max-linear-vel-mps" in runner
    assert "--startup-only" in runner
    assert "NAV2_STARTUP_ONLY_STEP_NAMES" in runner
    assert '"action_server_ready"' in runner
    assert "hold_interrupted_after_startup" in runner
    assert "--hold-after-success-s" in runner
    assert "args.hold_after_success_s > 0" in runner
    assert "NAV2_SMOKE_STEP_NAMES" in runner
    assert "hold_interrupted_after_success" in runner
    assert "_completed_smoke_steps(output)" in runner
    assert "--tf-startup-timeout-s" in runner
    assert "TfPreflightNode" in runner
    assert "map_to_base_link_seen" in runner
    assert "NAV2_LIFECYCLE_MANAGER_START_DELAY_S = 3.0" in runner
    assert "managed_commands" in runner
    assert "time.sleep(NAV2_LIFECYCLE_MANAGER_START_DELAY_S)" in runner
    assert "lifecycle_manager_navigation:" in runner
    assert "lifecycle_nodes_yaml" in runner
    assert 'f"--params-file {params_file}"' in runner
    assert "f'-p node_names" not in runner
    assert "state_summary" in runner
    assert "def _destroy_node_safely" in runner
    assert "def _shutdown_safely" in runner
    assert "if not rclpy.ok():" in runner
    assert "initial_transform_timeout: 10.0" in runner
    assert "DurabilityPolicy.TRANSIENT_LOCAL" in runner
    assert "nav2_regulated_pure_pursuit_controller::RegulatedPurePursuitController" in runner
    assert "nav2_navfn_planner/NavfnPlanner" in runner
    assert "nav2_behaviors/Spin" in runner
    assert "nav2_behaviors/BackUp" in runner
    assert "nav2_behaviors/Wait" in runner
    assert "nav2_behaviors::Spin" not in runner
    # Live 3D obstacle layer: the UGV static map is a vertical-raycast
    # traversability prior and misses thin vertical geometry (fences) and 5-10 cm
    # steps.  Both costmaps must voxelize the Ouster OS1 point cloud with a
    # 0.05 m map-frame obstacle height floor.
    assert 'plugin: "nav2_costmap_2d::VoxelLayer"' in runner
    assert "nav2_costmap_2d::ObstacleLayer" not in runner
    # 42328e25 (2026-09-21): the local costmap also carries the 0.05 m static prior (5 cm steps).
    assert runner.count('plugins: ["static_layer", "voxel_layer", "inflation_layer"]') == 2
    assert "observation_sources: ugv_point_cloud" in runner
    assert 'data_type: "PointCloud2"' in runner
    assert "DEFAULT_NAV2_POINT_CLOUD_TOPIC = \"/ugv/sensors/ouster/point_cloud\"" in runner
    assert "point_cloud_topic or f\"/{ns}/sensors/ouster/point_cloud\"" in runner
    assert "/{ns}/scan" not in runner
    assert "DEFAULT_NAV2_POINT_CLOUD_MIN_OBSTACLE_HEIGHT_M = 0.05" in runner
    assert "DEFAULT_NAV2_POINT_CLOUD_MAX_OBSTACLE_HEIGHT_M = 1.00" in runner
    assert "min_obstacle_height: {float(point_cloud_min_obstacle_height_m)}" in runner
    assert "max_obstacle_height: {float(point_cloud_max_obstacle_height_m)}" in runner
    assert "z_resolution: {float(DEFAULT_NAV2_VOXEL_Z_RESOLUTION_M)}" in runner
    assert "z_voxels: {int(DEFAULT_NAV2_VOXEL_Z_VOXELS)}" in runner
    assert "mark_threshold: 0" in runner
    assert "publish_voxel_map: false" in runner
    assert "footprint_clearing_enabled: true" in runner  # stale marks pinned the UGV (2026-09-19)
    assert "DEFAULT_NAV2_COSTMAP_RESOLUTION_M = 0.05" in runner
    assert "resolution: {float(costmap_resolution_m)}" in runner
    assert "--pointcloud-min-obstacle-height-m" in runner
    assert "--pointcloud-max-obstacle-height-m" in runner
    assert "point_cloud_min_obstacle_height_m=args.pointcloud_min_obstacle_height_m" in runner
    assert "point_cloud_max_obstacle_height_m=args.pointcloud_max_obstacle_height_m" in runner
    assert "inf_is_valid: false" in runner
    assert "ros-${ROS_DISTRO}-nav2-regulated-pure-pursuit-controller" in dockerfile
    assert "PIP_SYSTEM_ARGS=\"--break-system-packages\"" in dockerfile
    assert "python3 -m pip install ${PIP_SYSTEM_ARGS} --no-cache-dir" in dockerfile
    assert "pydantic==2.13.4" in dockerfile
    assert "gymnasium==1.3.0" in dockerfile
    assert "pyarrow==25.0.0" in dockerfile
    assert "PyYAML==6.0.3" in dockerfile
    assert "libopenvdb-dev" in dockerfile
    assert "python3-openvdb" in dockerfile
    assert "Keep OpenVDB in its own layer" in dockerfile
    assert dockerfile.index("python3-openvdb") > dockerfile.index("PyYAML==6.0.3")
    assert "pip dependency" in dockerfile
    assert dockerfile.index("pip dependency") > dockerfile.index("make px4_sitl")
    assert "airground-rayfronts-pip-cache" in dockerfile
    assert "--mount=type=cache" in dockerfile
    assert "docker/assets/rayfronts_wheels" in dockerfile
    assert "--no-index" in dockerfile
    assert "--find-links /tmp/rayfronts_wheels" in dockerfile
    assert "PIP_LOCAL_ARGS" in dockerfile
    assert dockerfile.index("${PIP_LOCAL_ARGS}") < dockerfile.index("antlr4-python3-runtime==4.9.3")
    assert '4.5.0) \\' in dockerfile
    assert 'TORCH_VERSION="2.5.1"' in dockerfile
    assert 'TORCHVISION_VERSION="0.20.1"' in dockerfile
    assert 'TORCH_CUDA_INDEX="cu118"' in dockerfile
    assert 'torch-2.5.1+cu118.html' in dockerfile
    assert 'TORCH_VERSION="2.6.0"' in dockerfile
    assert 'TORCHVISION_VERSION="0.21.0"' in dockerfile
    assert 'TORCH_CUDA_INDEX="cu124"' in dockerfile
    assert 'torch-2.6.0+cu124.html' in dockerfile
    assert "--no-deps \\\n      --index-url https://download.pytorch.org/whl/${TORCH_CUDA_INDEX}" in dockerfile
    assert "--ignore-installed \\\n    --retries 20" in dockerfile
    assert "torch==${TORCH_VERSION}" in dockerfile
    assert "torchvision==${TORCHVISION_VERSION}" in dockerfile
    assert "NumPy 1.x ABI" in dockerfile
    assert "numpy==1.26.4" in dockerfile
    assert "scipy==1.15.3" in dockerfile
    assert "requests==2.32.5" in dockerfile
    assert "attrs==25.4.0" in dockerfile
    assert "sympy==1.13.1" in dockerfile
    assert "filelock==3.32.2" in dockerfile
    assert "torch-scatter==2.1.2" in dockerfile
    assert "omni.isaac.ml_archive/pip_prebundle/nvidia/cublas/lib" in dockerfile
    assert "omni.isaac.ml_archive/pip_prebundle/nvidia/cudnn/lib" in dockerfile
    assert "omni.isaac.ml_archive/pip_prebundle/cusparselt/lib" in dockerfile
    assert "hydra-core==1.3.2" in dockerfile
    assert "open_clip_torch==3.2.0" in dockerfile
    assert "nanobind==2.9.2" in dockerfile


def test_rayfronts_mapper_runtime_preflight_checks_real_dependencies():
    preflight = (
        Path(__file__).parents[1] / "tools/preflight_rayfronts_mapper_runtime.py"
    ).read_text(encoding="utf-8")

    assert "airground-rayfronts-mapper-runtime-preflight-v1" in preflight
    assert '"torch_scatter"' in preflight
    assert '"pyopenvdb"' in preflight
    assert '"rayfronts.mapping_server_rosnode"' in preflight
    assert '"rayfronts.mapping_server_vlfm"' in preflight
    assert "cmake" in preflight
    assert "build_" in preflight
    assert "rayfronts_cpp*.so" in preflight
    assert "runtime_reuse_ok" in preflight
    assert "pyopenvdb_fallback_ok" in preflight
    assert "shared_objects" in preflight
    assert "vdb_ok" in preflight
    assert "create_occupancy_grid()" in preflight
    assert "occ_pc2vdb" in preflight
    assert "query_occ" in preflight


def test_rayfronts_semantic_encoder_preflight_checks_real_weights():
    preflight = (
        Path(__file__).parents[1] / "tools/preflight_rayfronts_semantic_encoder.py"
    ).read_text(encoding="utf-8")
    dockerfile = (DOCKER / "Dockerfile.isaac-ros").read_text(encoding="utf-8")

    assert "airground-rayfronts-semantic-encoder-preflight-v1" in preflight
    assert "NARadioEncoder" in preflight
    assert "RadioEncoder" in preflight
    assert "NACLIPEncoder" in preflight
    assert "torch.hub" not in preflight
    assert "encode_labels" in preflight
    assert "encode_image_to_feat_map" in preflight
    assert "encode_image_to_vector" in preflight
    assert "align_global_features_with_language" in preflight
    assert "align_spatial_features_with_language" in preflight
    assert "cache_summary" in preflight
    assert "sha256" in preflight
    assert "TORCH_HOME" in preflight
    assert "HF_HOME" in preflight
    assert "HUGGINGFACE_HUB_CACHE" in preflight
    assert "TRANSFORMERS_CACHE" in preflight
    naradio = (REPO_ROOT / "RayFronts/rayfronts/image_encoders/naradio.py").read_text(
        encoding="utf-8"
    )
    assert "trust_repo=True" in naradio
    assert "attn_mask=None" in naradio
    assert naradio.count("@torch.no_grad()") >= 7
    assert "parameter.requires_grad_(False)" in naradio
    assert "trust_repo=True" in (
        REPO_ROOT / "RayFronts/rayfronts/image_encoders/radio.py"
    ).read_text(encoding="utf-8")

    assert "ENV XDG_CACHE_HOME=/isaac-sim/.cache" in dockerfile
    assert "ENV TORCH_HOME=/isaac-sim/.cache/torch" in dockerfile
    assert "ENV HF_HOME=/isaac-sim/.cache/huggingface" in dockerfile
    assert "ENV HUGGINGFACE_HUB_CACHE=/isaac-sim/.cache/huggingface/hub" in dockerfile


def test_reset_health_detects_real_nav2_topic_surface():
    readiness = (
        Path(__file__).parents[1] / "tools/collect_reset_readiness_trace.py"
    ).read_text(encoding="utf-8")
    metrics = (
        Path(__file__).parents[1] / "tools/collect_runtime_metrics_smoke.py"
    ).read_text(encoding="utf-8")

    for text in (readiness, metrics):
        assert "NAV2_HEALTH_TOPIC_SURFACE" in text
        assert '"/ugv/map"' in text
        assert '"/ugv/global_costmap/costmap"' in text
        assert '"/ugv/local_costmap/costmap"' in text
        assert '"/ugv/plan"' in text
        assert '"/ugv/cmd_vel_nav"' in text
        assert '"/ugv/navigate_to_pose/_action/status"' in text
        assert "NAV2_HEALTH_MIN_OBSERVED_TOPICS" in text
        assert "_nav2_health_from_topics(topics)" in text


def test_retro_neighborhood_launch_enables_ugv_state_publishers():
    text = (LAUNCH_SCRIPTS / "RetroNeighborhood_Launch.py").read_text(encoding="utf-8")

    assert "JackalStatePublisher" in text
    assert "JackalStatePublisherConfig(" in text
    assert "namespace=UGV_ROBOT_NAME," in text
    # Nav2 transforms the Ouster cloud with tf2, so the UGV state publisher has
    # to publish the sensor frame below the Jackal body.  The mount is read back
    # from the live USD stage (offset + the asset's corrective rotation) instead
    # of being duplicated by hand.
    assert "JackalSensorFrame" in text
    assert "airground_sensor_frame_from_usd(" in text
    assert "sensor_frames=ugv_sensor_frames" in text
    assert "frame_id=UGV_LIDAR_FRAME_ID" in text
    assert "JackalContactPublisher" in text
    assert "JackalContactPublisherConfig(" in text
    assert "AIRGROUND_ENABLE_UGV_STATE_PUBLISHERS" in text
    assert "AIRGROUND_ENABLE_UGV_CONTACT_PUBLISHER" in text
    assert f"/{{UGV_ROBOT_NAME}}/odom" in text
    assert f"/{{UGV_ROBOT_NAME}}/joint_states" in text
    assert f"/{{UGV_ROBOT_NAME}}/ground_truth/pose" in text
    assert f"/{{UGV_ROBOT_NAME}}/control/status" in text
    assert f"/{{UGV_ROBOT_NAME}}/cmd_vel" in text
    assert f"/{{UGV_ROBOT_NAME}}/contact_state" in text
    assert "self.ugv_state_publisher.bind_robot(self.ugv)" in text
    assert "def publish_runtime_state" in text
    assert "self.ugv_state_publisher.publish(self.ugv, sim_time_s)" in text
    assert "self.ugv_contact_publisher.publish(sim_time_s)" in text


def test_retro_neighborhood_launch_enables_ugv_proximity_scan():
    text = (LAUNCH_SCRIPTS / "RetroNeighborhood_Launch.py").read_text(encoding="utf-8")

    assert "JackalProximityScanPublisher" in text
    assert "JackalProximityScanConfig(" in text
    assert 'AIRGROUND_ENABLE_UGV_PROXIMITY_SCAN' in text
    assert 'AIRGROUND_UGV_PROXIMITY_SCAN_RAY_COUNT' in text
    assert 'AIRGROUND_UGV_PROXIMITY_SCAN_MAX_RANGE_M' in text
    assert 'AIRGROUND_UGV_PROXIMITY_SCAN_HEIGHT_OFFSET_M' in text
    assert "self.ugv_proximity_scan_publisher = None" in text
    assert "self.ugv_proximity_scan_publisher.publish(" in text
    assert "self.ugv_proximity_scan_publisher.close()" in text
    assert "def _airground_physx_segment_raycast_fn" in text
    assert "def _airground_lazy_physx_segment_raycast_fn" in text
    assert "_airground_lazy_physx_segment_raycast_fn()" in text
    assert "UGV proximity scan enabled:" in text


def test_retro_neighborhood_launch_enables_uav_state_publishers():
    text = (LAUNCH_SCRIPTS / "RetroNeighborhood_Launch.py").read_text(encoding="utf-8")

    assert "MultirotorStatePublisher" in text
    assert "MultirotorStatePublisherConfig(" in text
    assert "AIRGROUND_ENABLE_UAV_STATE_PUBLISHERS" in text
    assert 'prim_path=f"{UAV_PRIM}{UAV_MAPPING.body_path}"' in text
    assert f"/{{UAV_ROBOT_NAME}}/odom" in text
    assert f"/{{UAV_ROBOT_NAME}}/ground_truth/pose" in text
    assert "self.uav_state_publisher.publish(sim_time_s)" in text


def test_retro_neighborhood_launch_uses_single_world_clock_for_airground_stack():
    text = (LAUNCH_SCRIPTS / "RetroNeighborhood_Launch.py").read_text(encoding="utf-8")

    assert text.count("World(**world_settings)") == 1
    assert "world_settings = dict(self.pg._world_settings)" in text
    assert "self.world = self.pg.world" in text
    assert "self.ugv = self.world.scene.add(" in text
    assert "JackalWheeledRobot" in text
    assert "self.ugv = jackal_cls(" in text
    assert "JackalDriveConfig(" in text
    assert "wheel velocity actions affect" in text
    assert "ensure_articulation_root(stage, UGV_PRIM, \"UGV\")" in text
    assert "self.ugv.initialize()" in text
    assert "self.ugv.post_reset()" in text
    assert "AirGround UGV articulation initialized and velocity control armed" in text
    assert "DOCK_PRE_ALIGN_SETTLE_STEPS" not in text
    assert "AirGround dock pre-align UGV settle complete" not in text
    assert "fixed joint already connects the UGV and UAV articulations" in text
    assert "prim_world_pose_wxyz(" in text
    assert "dock_config.ugv_body_path" in text
    assert "self.ugv.get_world_pose()" not in text
    assert "child_local_pose_wxyz(" in text
    assert "self.uav_body_canonical_local_pose" in text
    assert "set_local_prim_pose(" in text
    assert "docked_uav_root_world_pose(" in text
    assert "uav_body_local_orientation_wxyz" in text
    assert "body_local_orientation_wxyz={uav_body_local_orientation_wxyz}" in text
    assert "docked_uav_world_pose(" in text
    assert "def set_articulation_root_world_pose" in text
    assert "from isaacsim.core.experimental.prims import Articulation, RigidPrim" in text
    assert "from isaacsim.core.prims import Articulation, RigidPrim" in text
    assert "def make_isaac_prim_view" in text
    assert 'exact_expr = f"^{re.escape(prim_path)}$"' in text
    assert '"prim_paths_expr": exact_expr' in text
    assert "make_isaac_prim_view(Articulation, prim_path)" in text
    assert "falling back to USD-authored articulation root pose" in text
    assert "articulation.set_world_poses(positions=position, orientations=orientation)" in text
    assert "zero_rigid_prim_velocities(prim_path, rigid_prim=articulation)" in text
    assert 'prim_path.rstrip("/") in {UAV_PRIM.rstrip("/"), UGV_PRIM.rstrip("/")}' in text
    assert "prim.HasAPI(UsdPhysics.ArticulationRootAPI)" in text
    assert '"status": "skipped_articulation_root"' in text
    assert "set_articulation_root_world_pose(" in text
    assert "def set_rigid_prim_world_pose_and_zero_velocity" in text
    assert "author_usd_xform: bool = True" in text
    assert "make_isaac_prim_view(RigidPrim, prim_path)" in text
    assert 'summary["view_error"]' in text
    assert 'summary["status"] = "view_unavailable"' in text
    assert '"usd_pose_only_after_view_error"' in text
    assert "rigid_prim.set_world_poses(positions=position, orientations=orientation)" in text
    assert 'getattr(rigid_prim, "set_velocities", None)' in text
    assert 'summary["velocity_zero_method"] = "set_velocities"' in text
    assert 'getattr(rigid_prim, "set_linear_velocities", None)' in text
    assert 'getattr(rigid_prim, "set_angular_velocities", None)' in text
    assert 'getattr(rigid_prim, "set_linear_velocity", None)' in text
    assert 'getattr(rigid_prim, "set_angular_velocity", None)' in text
    assert "def zero_rigid_prim_velocities" in text
    assert "uav_root_velocity_reset_after_dock_settle" in text
    assert "uav_root_velocity_reset_after_warmup" in text
    assert "def _reset_uav_sensor_state" in text
    assert "uav_sensor_reset_after_dock_settle" in text
    assert "episode_reset_post_restart_zero_velocity" in text
    assert "body_position={dock_body_position}" not in text
    assert "body_local_pos={uav_body_local_pos}" in text
    assert "AirGround dock joint created after world.reset" in text
    assert text.index("AirGround world.reset complete") < text.index(
        "AirGround dock joint created after world.reset"
    )
    assert "graph_handle = spawn_px4_multirotor_node(" in text
    assert text.count("parent_graph_handle=graph_handle") == 4
    assert 'ros2_context_node=f"{UAV_ROBOT_NAME}_ROS2Context"' in text
    assert "self.world.step(render=render_step)" in text
    assert "def _render_for_main_loop_step(self, step_count: int) -> bool:" in text
    assert "self._simulation_time_s()" in text
    assert "float(step_value) * float(self.world.get_physics_dt())" in text
    assert "AIRGROUND_ENABLE_SENSOR_GRAPHS" in text
    assert "AirGround sensor graphs disabled" in text


def test_retro_neighborhood_launch_uses_profiled_colliders_not_blanket_mesh_sweep():
    launch = (LAUNCH_SCRIPTS / "RetroNeighborhood_Launch.py").read_text(encoding="utf-8")
    scene_prep = (Path(__file__).parents[1] / "utils/scene_prep.py").read_text(encoding="utf-8")

    assert "from scene_audit import classify_scene_mesh" in scene_prep
    assert "collision_approximation_for_profile" in scene_prep
    assert "from scene_physics_profile import configure_airground_physics_profile" in scene_prep
    assert "def add_profiled_colliders(prim, enabled_profiles=None, disable_other_colliders: bool = False," in scene_prep
    assert "def add_static_obstacle_box_proxies(" in scene_prep
    assert "airground:collisionProxyVersion" in scene_prep
    assert "enabled_profiles = {\"ground\", \"static_obstacle\"}" in scene_prep
    assert "disable_other_colliders: bool = False" in scene_prep
    assert 'AIRGROUND_SCENE_COLLIDER_MODE = os.environ.get("AIRGROUND_SCENE_COLLIDER_MODE", "profiled")' in launch
    assert '{"profiled", "ground_only", "proxy", "none"}' in launch
    assert 'if AIRGROUND_SCENE_COLLIDER_MODE == "none":' in launch
    assert 'elif AIRGROUND_SCENE_COLLIDER_MODE == "ground_only":' in launch
    assert 'elif AIRGROUND_SCENE_COLLIDER_MODE == "proxy":' in launch
    assert "add_static_obstacle_box_proxies(stage, stage_prim)" in launch
    assert 'enabled_profiles={"ground"}' in launch
    assert "disable_other_colliders=True" in launch
    assert "UsdPhysics.MeshCollisionAPI.Apply(current)" in scene_prep
    assert "current.RemoveAPI(UsdPhysics.CollisionAPI)" in scene_prep
    assert "removed_collision_api_count" in scene_prep
    assert "CreateApproximationAttr().Set(approximation)" in scene_prep
    assert 'summary["skipped"] += 1' in scene_prep
    assert "add_profiled_colliders(stage_prim)" in launch
    assert 'configure_airground_physics_profile(stage, root_prim_path="/World/stage", profile=profile)' in launch
    assert "AIRGROUND_ENABLE_GROUND_SUPPORT_PLANE" in launch
    assert "add_ground_support_plane(" in launch
    assert "def _ensure_ground_support_plane(self, stage, reason: str)" in launch
    assert "AirGround ground support plane ensured" in launch
    assert '"episode_reset_after_world_reset"' in launch
    assert '"ground_support_after_world_reset"' in launch
    assert "AirGround world.reset starting" in launch
    assert "AirGround world.reset complete" in launch
    assert "AIRGROUND_SKIP_CLEANUP_ON_CLOSE" in launch
    assert "AIRGROUND_POST_STOP_UPDATES" in launch
    assert "PX4LaunchTool.kill_all_px4()" in launch
    assert "AirGround fast headless exit." in launch
    assert "os._exit(0)" in launch
    assert "wait_for_replicator=not AIRGROUND_HEADLESS" in launch
    assert "skip_cleanup=AIRGROUND_SKIP_CLEANUP_ON_CLOSE" in launch
    assert "add_colliders(stage_prim)" not in launch


def test_static_obstacle_proxy_removes_source_collision_apis(monkeypatch):
    from pxr import Usd, UsdGeom, UsdPhysics

    scene_prep = _load_scene_prep_for_usd_test(monkeypatch)
    stage = Usd.Stage.Open(str(SCENES / "RetroNeighborhood" / "RetroNeighborhood_Export.usd"))
    assert stage is not None
    root = stage.GetPrimAtPath("/World/stage")
    assert root.IsValid()

    source_paths = [
        str(prim.GetPath())
        for prim in Usd.PrimRange(root)
        if prim.IsA(UsdGeom.Mesh)
        and scene_prep.classify_scene_mesh(
            str(prim.GetPath()),
            has_collision=prim.HasAPI(UsdPhysics.CollisionAPI),
            has_rigid_body=prim.HasAPI(UsdPhysics.RigidBodyAPI),
        )
        == "static_obstacle"
    ]
    ground_collision_count = sum(
        1
        for prim in Usd.PrimRange(root)
        if prim.IsA(UsdGeom.Mesh)
        and scene_prep.classify_scene_mesh(
            str(prim.GetPath()),
            has_collision=prim.HasAPI(UsdPhysics.CollisionAPI),
            has_rigid_body=prim.HasAPI(UsdPhysics.RigidBodyAPI),
        )
        == "ground"
        and prim.HasAPI(UsdPhysics.CollisionAPI)
    )

    summary = scene_prep.add_static_obstacle_box_proxies(stage, root)

    assert len(source_paths) == 3733
    assert ground_collision_count == 545
    assert summary["source_mesh_count"] == len(source_paths)
    assert summary["removed_collision_api_count"] == len(source_paths)
    assert summary["proxy_group_count"] == 1324
    assert summary["proxy_count"] == 1324
    assert summary["skipped_degenerate"] == 0
    assert not any(
        stage.GetPrimAtPath(path).HasAPI(UsdPhysics.CollisionAPI)
        for path in source_paths
    )


def test_ground_support_plane_is_static_invisible_collider(monkeypatch):
    from pxr import Usd, UsdGeom, UsdPhysics, UsdShade

    scene_prep = _load_scene_prep_for_usd_test(monkeypatch)
    stage = Usd.Stage.CreateInMemory()
    UsdGeom.Xform.Define(stage, "/World")
    material = UsdShade.Material.Define(stage, "/World/PhysicsMaterials/airground_ground_contact")

    summary = scene_prep.add_ground_support_plane(
        stage,
        center_x_m=-24.0,
        center_y_m=0.0,
        size_x_m=128.0,
        size_y_m=128.0,
        top_z_m=0.0,
        thickness_m=0.04,
    )

    prim = stage.GetPrimAtPath("/World/AirGroundGroundSupportPlane")
    assert prim.IsValid()
    assert prim.HasAPI(UsdPhysics.CollisionAPI)
    assert UsdPhysics.CollisionAPI(prim).GetCollisionEnabledAttr().Get() is True
    assert UsdGeom.Imageable(prim).ComputeVisibility() == UsdGeom.Tokens.invisible
    # 2026-09-21: the support surface must be a PhysX *plane*, not a scaled box.
    # A 128 m x 128 m x 0.04 m scaled cube produced 7.5-20 mm tire penetration,
    # a spurious -4.5 deg roll and zero net in-place rotation wherever it was the
    # only support (the 19.4 cm sunken road in front of the bus stop); the same
    # surface resized to 4 m, and this plane, both restore healthy contact.
    assert prim.GetTypeName() == "Plane"
    xform_ops = [op.GetOpName() for op in UsdGeom.Xformable(prim).GetOrderedXformOps()]
    assert xform_ops == ["xformOp:translate"], xform_ops
    assert prim.GetAttribute("airground:groundSupportPlaneVersion").Get() == "plane-v1"
    assert prim.GetAttribute("airground:groundSupportPlaneGeometry").Get() == "PxPlaneGeometry"
    assert summary["mode"] == "static_ground_support_plane"
    assert summary["geometry"] == "plane"
    assert summary["physics_geometry"] == "PxPlaneGeometry"
    assert summary["surface_infinite"] is True
    assert summary["legacy_box_size_m"] == [128.0, 128.0, 0.04]
    assert summary["center_m"] == [-24.0, 0.0, 0.0]
    assert summary["size_m"] == [128.0, 128.0, 0.04]
    assert summary["top_z_m"] == 0.0
    assert summary["material_bound"] is True
    assert "physx_collision_api_applied" in summary
    assert "physx_collision_attrs" in summary
    binding = UsdShade.MaterialBindingAPI(prim).GetDirectBinding().GetMaterialPath()
    assert str(binding) == str(material.GetPath())


def test_soft_dock_hold_keeps_uav_on_deck_until_armed():
    """The 4.5 soft dock must latch the UAV until PX4 reports armed.

    2026-09-12: with the physical dock joint disabled the Quadcopter slid off
    the Jackal deck during the pre-arm dwell and the UAV smoke's pre-arm gate
    correctly aborted.  The launch script now maintains the settled deck pose
    and releases it on the armed transition.
    """
    launch = (LAUNCH_SCRIPTS / "RetroNeighborhood_Launch.py").read_text(encoding="utf-8")
    compose = (DOCKER / "docker-compose.yaml").read_text(encoding="utf-8")

    assert "AIRGROUND_SOFT_DOCK_HOLD" in launch
    assert "def _maintain_soft_dock_hold" in launch
    assert "soft dock hold released: PX4 armed" in launch
    assert "set_articulation_root_world_pose(" in launch
    assert "self._maintain_soft_dock_hold()" in launch
    assert "AIRGROUND_SOFT_DOCK_HOLD=${AIRGROUND_SOFT_DOCK_HOLD:-true}" in compose


def test_airground_quadcopter_px4_airframe_is_installed_and_selected():
    airframe = (PX4_AIRFRAMES / "11000_airground_quadcopter").read_text(encoding="utf-8")
    dockerfile = (DOCKER / "Dockerfile.isaac-ros").read_text(encoding="utf-8")
    compose = (DOCKER / "docker-compose.yaml").read_text(encoding="utf-8")
    launch = (LAUNCH_SCRIPTS / "RetroNeighborhood_Launch.py").read_text(encoding="utf-8")
    launch_tool = (
        PEGASUS_PACKAGE / "logic/backends/tools/px4_launch_tool.py"
    ).read_text(encoding="utf-8")

    assert "@name AirGround Quadcopter SITL" in airframe
    assert "Isaac Sim 6.0.1 official Quadcopter asset" in airframe
    assert "Based on PX4 v1.16.1" in airframe
    assert "param set-default CA_ROTOR_COUNT 4" in airframe
    assert "param set-default CA_ROTOR0_PX 0.10253047" in airframe
    assert "param set-default CA_ROTOR0_PY -0.10253040" in airframe
    assert "param set-default CA_ROTOR1_PX -0.10253057" in airframe
    assert "param set-default CA_ROTOR1_PY 0.10253040" in airframe
    assert "param set-default CA_ROTOR2_PX 0.10253047" in airframe
    assert "param set-default CA_ROTOR2_PY 0.10253051" in airframe
    assert "param set-default CA_ROTOR3_PX -0.10253057" in airframe
    assert "param set-default CA_ROTOR3_PY -0.10253040" in airframe
    assert "param set-default PWM_MAIN_FUNC4 104" in airframe
    assert "P0-04 hover/waypoint calibration" in airframe
    assert "0.1515" not in airframe
    assert "0.245" not in airframe
    assert "Isaac Sim 5.1 official Quadcopter asset" not in airframe

    assert "COPY px4/airframes/11000_airground_quadcopter" in dockerfile
    assert "init.d-posix/airframes/11000_airground_quadcopter" in dockerfile
    assert "AIRGROUND_UAV_PX4_MODEL=${AIRGROUND_UAV_PX4_MODEL:-airground_quadcopter}" in compose
    assert "AIRGROUND_UAV_PX4_ENABLE_LOCKSTEP=${AIRGROUND_UAV_PX4_ENABLE_LOCKSTEP:-}" in compose

    assert 'UAV_MODEL = (os.environ.get("AIRGROUND_UAV_MODEL") or "quadcopter").strip().lower()' in launch
    assert 'UAV_PX4_MODEL = os.environ.get("AIRGROUND_UAV_PX4_MODEL")' in launch
    assert "UAV_PX4_ENABLE_LOCKSTEP = _env_bool(" in launch
    assert '"AIRGROUND_UAV_PX4_ENABLE_LOCKSTEP"' in launch
    assert '"airground_quadcopter" if UAV_MODEL == "quadcopter" else "gazebo-classic_iris"' in launch
    assert "px4_vehicle_model=UAV_PX4_MODEL" in launch
    assert "enable_lockstep=UAV_PX4_ENABLE_LOCKSTEP" in launch

    assert "def _prepare_rootfs(self):" in launch_tool
    assert "def _sync_airground_airframes(self):" in launch_tool
    assert 'os.environ.get("AIRGROUND_PX4_AIRFRAMES_DIR")' in launch_tool
    assert 'shutil.copy2(src, os.path.join(target_dir, filename))' in launch_tool
    assert 'for init_name in ("init.d", "init.d-posix"):' in launch_tool
    assert '"rc.vehicle_setup"' in launch_tool
    assert "start_new_session=True" in launch_tool
    assert "_active_tools = weakref.WeakSet()" in launch_tool
    assert "def kill_all_px4(cls):" in launch_tool
    assert "os.killpg(os.getpgid(self.px4_process.pid), signal.SIGTERM)" in launch_tool
    assert "self.px4_process.wait(timeout=5)" in launch_tool


def test_px4_backend_sends_hil_ground_truth_each_update():
    backend = (
        PEGASUS_PACKAGE / "logic/backends/px4_mavlink_backend.py"
    ).read_text(encoding="utf-8")

    update_start = backend.index("    def update(self, dt):")
    poll_start = backend.index("    def poll_mavlink_messages(self):")
    update_body = backend[update_start:poll_start]

    assert "def send_ground_truth(self, time_usec: int):" in backend
    assert "self.send_sensor_msgs(self._current_utime)" in update_body
    assert "self.send_gps_msgs(self._current_utime)" in update_body
    assert "self.send_ground_truth(self._current_utime)" in update_body


def test_px4_backend_hil_state_uses_non_negative_airspeed():
    backend = (
        PEGASUS_PACKAGE / "logic/backends/px4_mavlink_backend.py"
    ).read_text(encoding="utf-8")

    assert "self._sensor_data.sim_ind_airspeed = int(abs(body_vel[0]) * 100)" in backend
    assert "MAVLink HIL_STATE_QUATERNION encodes airspeeds" in backend


def test_px4_backend_ignores_callbacks_after_connection_recovery_stop():
    backend = (
        PEGASUS_PACKAGE / "logic/backends/px4_mavlink_backend.py"
    ).read_text(encoding="utf-8")

    update_start = backend.index("    def update(self, dt):")
    poll_start = backend.index("    def poll_mavlink_messages(self):")
    heartbeat_start = backend.index("    def send_heartbeat", poll_start)
    stop_start = backend.index("    def stop(self):")
    reset_start = backend.index("    def reset(self):")
    update_body = backend[update_start:poll_start]
    poll_body = backend[poll_start:heartbeat_start]
    stop_body = backend[stop_start:reset_start]

    assert "if not self._is_running or self._connection is None:" in update_body
    assert "if self._connection is None:" in poll_body
    assert "self._connection.recv_match" in poll_body
    assert "if self._connection is not None:" in stop_body
    assert "self._connection.close()" in stop_body


def test_px4_backend_does_not_deadlock_hil_before_simulator_heartbeat():
    backend = (
        PEGASUS_PACKAGE / "logic/backends/px4_mavlink_backend.py"
    ).read_text(encoding="utf-8")

    update_start = backend.index("    def update(self, dt):")
    poll_start = backend.index("    def poll_mavlink_messages(self):")
    heartbeat_start = backend.index("    def send_heartbeat", poll_start)
    update_body = backend[update_start:poll_start]
    poll_body = backend[poll_start:heartbeat_start]

    heartbeat_gate = "if not self._received_first_hearbeat:"
    assert heartbeat_gate in update_body
    after_gate = update_body[update_body.index(heartbeat_gate):]
    assert "self.wait_for_first_hearbeat()" in after_gate
    assert "return" not in after_gate[: after_gate.index("# Check if we have already received IMU data")]
    assert "PX4\n        # v1.16 simulator_mavlink can wait for HIL samples" in update_body
    assert "if self._received_first_hearbeat == False:" not in poll_body
    assert "self.poll_mavlink_messages()" in update_body
    assert "self.send_sensor_msgs(self._current_utime)" in update_body
    assert "self.send_gps_msgs(self._current_utime)" in update_body
    assert "self.send_ground_truth(self._current_utime)" in update_body


def test_px4_backend_clamps_hil_state_integer_fields():
    backend = (
        PEGASUS_PACKAGE / "logic/backends/px4_mavlink_backend.py"
    ).read_text(encoding="utf-8")

    assert "def _clamp_int16(value) -> int:" in backend
    assert "def _clamp_uint16(value) -> int:" in backend
    assert "_clamp_int16(self._sensor_data.sim_velocity_inertial[0])" in backend
    assert "_clamp_uint16(self._sensor_data.sim_ind_airspeed)" in backend
    assert "_clamp_int16(self._sensor_data.sim_acceleration[2])" in backend
    assert "self._sensor_data.temperature," in backend
    assert "self._sensor_data.altitude,\n                fields_updated" not in backend


def test_pegasus_gps_groundtruth_uses_degrees_for_hil_state():
    gps = (PEGASUS_PACKAGE / "logic/sensors/gps.py").read_text(encoding="utf-8")
    backend = (
        PEGASUS_PACKAGE / "logic/backends/px4_mavlink_backend.py"
    ).read_text(encoding="utf-8")

    assert '"latitude_gt": self._origin_lat' in gps
    assert '"longitude_gt": self._origin_lon' in gps
    assert '"latitude_gt": np.degrees(latitude_gt)' in gps
    assert '"longitude_gt": np.degrees(longitude_gt)' in gps
    assert 'self._sensor_data.sim_lat = int(data["latitude_gt"] * 10000000)' in backend
    assert 'self._sensor_data.sim_lon = int(data["longitude_gt"] * 10000000)' in backend


def test_pegasus_imu_clamps_stationary_usd_finite_diff_acceleration():
    imu = (PEGASUS_PACKAGE / "logic/sensors/imu.py").read_text(encoding="utf-8")

    assert "AIRGROUND_IMU_STATIONARY_ACCEL_CLAMP" in imu
    assert "AIRGROUND_IMU_STATIONARY_SPEED_MPS" in imu
    assert 'simulator_version.startswith("4.5")' in imu
    assert 'state_velocity_source == "usd_finite_diff"' in imu
    assert "np.linalg.norm(current_linear_velocity) <= AIRGROUND_IMU_STATIONARY_SPEED_MPS" in imu
    assert "kinematic_acceleration = np.zeros(3, dtype=float)" in imu
    assert "linear_acceleration_inertial = kinematic_acceleration - GRAVITY_VECTOR" in imu
    assert "self._prev_linear_velocity = current_linear_velocity.copy()" in imu


def test_px4_backend_clamps_preactuator_gyro_for_isaac_4_5_usd_finite_diff():
    backend = (
        PEGASUS_PACKAGE / "logic/backends/px4_mavlink_backend.py"
    ).read_text(encoding="utf-8")
    launcher = (LAUNCH_SCRIPTS / "RetroNeighborhood_Launch.py").read_text(encoding="utf-8")

    assert "AIRGROUND_PX4_PREACTUATOR_GYRO_CLAMP" in backend
    assert 'simulator_version.startswith("4.5")' in backend
    assert 'state_velocity_source == "usd_finite_diff"' in backend
    assert "and not self._received_first_actuator" in backend
    assert "xgyro = 0.0" in backend
    assert "ygyro = 0.0" in backend
    assert "zgyro = 0.0" in backend
    assert "self._preactuator_gyro_clamp_count += 1" in backend
    assert "_preactuator_gyro_clamp_count" in launcher


def test_px4_backend_supports_actuator_channel_map_diagnostics():
    backend = (
        PEGASUS_PACKAGE / "logic/backends/px4_mavlink_backend.py"
    ).read_text(encoding="utf-8")
    compose = (DOCKER / "docker-compose.yaml").read_text(encoding="utf-8")
    lftw02 = (REPO_ROOT / "benchmark/airground_benchmark/lftw02.py").read_text(
        encoding="utf-8"
    )
    local_wrapper = (REPO_ROOT / "scripts/run_non_global_env.sh").read_text(
        encoding="utf-8"
    )
    lft_wrapper = (REPO_ROOT / "scripts/run_lftw02_benchmark.sh").read_text(
        encoding="utf-8"
    )

    assert "AIRGROUND_PX4_ACTUATOR_CHANNEL_MAP" in backend
    assert "def _parse_actuator_channel_map" in backend
    assert "self.actuator_channel_map = _parse_actuator_channel_map" in backend
    assert "mapped_controls = [controls[channel] for channel in self.actuator_channel_map]" in backend
    assert '"actuator_channel_map"' in backend
    assert '"mapped_controls"' in backend
    assert "AIRGROUND_PX4_ACTUATOR_CHANNEL_MAP" in compose
    assert '"AIRGROUND_PX4_ACTUATOR_CHANNEL_MAP"' in lftw02
    assert "--expect-env \"AIRGROUND_PX4_ACTUATOR_CHANNEL_MAP=" in local_wrapper
    assert "--expect-env \"AIRGROUND_PX4_ACTUATOR_CHANNEL_MAP=" in lft_wrapper


def test_uav_offboard_smoke_runner_emits_standard_steps():
    runner = (TOOLS / "run_uav_offboard_smoke.py").read_text(encoding="utf-8")

    assert "UAV_SMOKE_STEPS = (" in runner
    for step in ("arm", "takeoff", "hover", "waypoint", "cancel", "emergency_stop"):
        assert f'"{step}"' in runner
    assert '"event": "uav_smoke_step"' in runner
    assert '"agent": "uav"' in runner
    assert 'mavutil.mavlink_connection(' in runner
    assert "MAV_FRAME_LOCAL_NED" in runner
    assert "MAV_CMD_DO_SET_MODE" in runner
    assert "MAV_CMD_COMPONENT_ARM_DISARM" in runner
    assert "21196.0" in runner
    assert "self.takeoff_success_altitude_m = max(0.6, self.target_altitude_m - 0.2)" in runner
    assert "LOCAL_POSITION_REANCHOR_MIN_DELTA_M = 0.25" in runner
    assert "def maybe_reanchor_takeoff_target" in runner
    assert '"event": "local_position_takeoff_reanchor"' in runner
    assert 'reason="post_arm_pre_takeoff"' in runner
    assert 'reason="takeoff_local_position_shift"' in runner
    assert '"local_reanchor_count": takeoff_reanchor_count' in runner
    assert '"max_local_reanchor_delta_m": round(float(takeoff_max_reanchor_delta_m), 4)' in runner
    # Takeoff must not command an absolute heading: the sampled docked yaw can
    # predate PX4's EKF yaw alignment, and PX4 answers such a step at
    # MC_YAWRATE_MAX (200 deg/s) as soon as the vehicle leaves the dock.
    # Behavioural coverage: tests/test_uav_takeoff_yaw_guard.py.
    assert "MAV_POSITION_TARGET_TYPEMASK_YAW_IGNORE = 1024" in runner
    assert "type_mask |= MAV_POSITION_TARGET_TYPEMASK_YAW_IGNORE" in runner
    assert "self.position_hold_yaw = self.takeoff_hold_yaw" in runner
    assert "def wait_yaw_alignment_ready" in runner
    assert "def _slew_limited_yaw_setpoint" in runner
    assert '"event": "yaw_alignment_gate"' in runner
    assert '"event": "yaw_setpoint_slew_limited"' in runner
    assert '"event": "takeoff_yaw_handoff"' in runner
    assert "heading_good_for_control" in runner
    assert '"hover_target_yaw_rad"' in runner
    assert '"--no-takeoff-hold-yaw"' in runner
    assert '"--position-yaw-slew-step-deg"' in runner
    assert '"--yaw-align-timeout-s"' in runner
    assert "hover_target_z_m = local_origin_z_m - self.target_altitude_m" in runner
    assert "takeoff_success_z_m = local_origin_z_m - self.takeoff_success_altitude_m" in runner
    assert '"target_altitude_m": round(float(self.target_altitude_m), 4)' in runner
    assert "if current_z_m <= takeoff_success_z_m:" in runner
    assert "and float(self.latest[\"z\"]) <= takeoff_success_z_m" in runner
    assert "target_z_m=round(float(waypoint_target[2]), 4)" in runner
    assert 'waypoint_skip_reason = "hover_gate_failed"' in runner
    assert '"event": "waypoint_skipped"' in runner
    assert "skipped_reason=waypoint_skip_reason" in runner
    assert "queue_session_should_land = self.waypoint_queue_path is not None" in runner
    assert "landing_rate_mps = 0.3" in runner
    assert '"event": "nominal_landing_complete"' in runner
    assert "MAV_LANDED_STATE_ON_GROUND" in runner
    assert "and nominal_landing_ok" in runner
    assert "step_callback" in runner
    assert "self._step_backend()" in runner
    assert "truncate: bool = True" in runner
    assert "def _json_safe(value: Any) -> Any:" in runner
    assert "return value if math.isfinite(value) else None" in runner
    assert "safe_payload = _json_safe(payload)" in runner
    assert "allow_nan=False" in runner
    assert "return _json_safe({" in runner
    assert "--target-altitude-m" in runner
    assert "--heartbeat-timeout-s" in runner
    assert "--waypoint-timeout-s" in runner
    assert "--arm-ready-timeout-s" in runner
    assert "--arm-max-attempts" in runner
    assert "--pre-arm-warmup-s" in runner
    assert "--arm-retry-warmup-s" in runner
    assert "maybe_send_gcs_heartbeat" in runner
    assert "arm_retry_warmup" in runner
    assert "self.heartbeat_timeout_s" in runner
    assert "self.waypoint_timeout_s" in runner
    assert "self.arm_ready_timeout_s" in runner
    assert "self.arm_max_attempts" in runner
    assert "while arm_attempts < self.arm_max_attempts" in runner
    assert '"event": "arm_abort"' in runner
    assert 'return self.report("failed")' in runner
    assert '"ready_for_takeoff": False' in runner
    assert "def wait_ready_for_takeoff" in runner
    assert '"event": "ready_for_takeoff_gate"' in runner
    assert '"Ready for takeoff" in text' in runner
    assert 'ready_for_takeoff=ready_for_takeoff' in runner
    # 2026-09-22: every flight-state gate spends its budget in simulated seconds
    # (see CHANGELOG §78); the leg deadline is a gate object, not a wall stamp.
    assert "waypoint_gate = self.gate_start(self.waypoint_timeout_s)" in runner
    assert "def gate_elapsed(" in runner
    assert "def gate_dwell(" in runner
    assert '"--gate-timebase"' in runner
    assert "timeout_s=round(float(self.waypoint_timeout_s), 4)" in runner
    assert "target_x_m=round(float(self.waypoint_x_m), 4)" in runner
    assert "waypoint_start_x_m = float(self.latest[\"x\"])" in runner
    assert "waypoint_start_y_m = float(self.latest[\"y\"])" in runner
    assert "waypoint_start_x_m + float(self.waypoint_x_m)" in runner
    assert "waypoint_start_y_m + float(self.waypoint_y_m)" in runner
    assert '"event": "waypoint_local_reference"' in runner
    assert "target_absolute_x_m=round(float(waypoint_target[0]), 4)" in runner
    assert '"armed": None' in runner
    assert '"flight_mode": None' in runner
    assert 'message_type == "HEARTBEAT"' in runner
    assert "MAV_MODE_FLAG_SAFETY_ARMED" in runner
    assert "mavutil.mode_string_v10(message)" in runner
    assert "def flight_mode_matches" in runner
    assert 'self.flight_mode_matches("OFFBOARD")' in runner
    assert 'self.flight_mode_matches("LOITER")' in runner
    assert "PX4_ARMING_STATE_ARMED = 2" in runner
    assert "def px4_cli_armed" in runner
    assert "arm_side_effect_from_heartbeat = self.latest.get(\"armed\") is True" in runner
    assert "arm_side_effect_from_px4_cli = self.px4_cli_armed(force=True)" in runner
    assert "arm_side_effect = arm_side_effect_from_heartbeat or arm_side_effect_from_px4_cli" in runner
    assert "(offboard_result == 0 or offboard_side_effect)" in runner
    assert "offboard_side_effect=offboard_side_effect" in runner
    assert "offboard_retry_after_arm" in runner
    assert "offboard_attempts=offboard_attempts" in runner
    assert "--waypoint-y-m" in runner
    assert "waypoint_y_m" in runner
    assert '"local_path_m"' in runner
    assert '"setpoint_count"' in runner
    assert "cancel_side_effect=cancel_side_effect" in runner
    assert "disarmed_side_effect = self.latest.get(\"armed\") is False" in runner
    assert '"ok" if disarm_result == 0 or disarmed_side_effect else "failed"' in runner
    assert "self.takeoff_timeout_s" in runner
    assert "self.pre_arm_warmup_s" in runner
    assert "self.pre_arm_stability_timeout_s" in runner
    assert "def wait_pre_arm_telemetry_stable" in runner
    assert '"event": "pre_arm_telemetry_gate"' in runner
    assert '"reason": "pre_arm_telemetry_unstable"' in runner
    assert "def maybe_request_telemetry_streams" in runner
    assert "MAV_CMD_SET_MESSAGE_INTERVAL" in runner
    assert "MAVLINK_MSG_ID_LOCAL_POSITION_NED" in runner
    assert "MAVLINK_MSG_ID_ATTITUDE" in runner
    assert "MAVLINK_MSG_ID_ATTITUDE_QUATERNION" in runner
    assert "DIAGNOSTIC_MESSAGE_INTERVALS" in runner
    assert "MAVLINK_MSG_ID_SYS_STATUS" in runner
    assert "MAVLINK_MSG_ID_ESTIMATOR_STATUS" in runner
    assert "MAVLINK_MSG_ID_EKF_STATUS_REPORT" in runner
    assert "MAVLINK_MSG_ID_GPS_RAW_INT" in runner
    assert "MAVLINK_MSG_ID_HIGHRES_IMU" in runner
    assert "MAVLINK_MSG_ID_HEALTH_REPORT" in runner
    assert "MAVLINK_MSG_ID_EVENT" in runner
    assert "def _decode_mavlink_bitmask" in runner
    assert "TELEMETRY_POLL_MESSAGE_TYPES" in runner
    assert 'message_type == "ATTITUDE_QUATERNION"' in runner
    assert 'message_type == "SYS_STATUS"' in runner
    assert 'message_type == "ESTIMATOR_STATUS"' in runner
    assert 'message_type == "EKF_STATUS_REPORT"' in runner
    assert 'message_type == "GPS_RAW_INT"' in runner
    assert 'message_type == "HIGHRES_IMU"' in runner
    assert 'message_type == "HEALTH_REPORT"' in runner
    assert 'message_type == "EVENT"' in runner
    assert "def _euler_from_attitude_quaternion_wxyz" in runner
    assert '"attitude_quaternion_samples": 0' in runner
    assert '"sys_status_samples": 0' in runner
    assert '"estimator_status_samples": 0' in runner
    assert '"health_diagnostics": self.health_diagnostics_snapshot()' in runner
    assert '"enabled_unhealthy_sensor_names"' in runner
    assert '"recent_status_texts": list(self._recent_status_texts)' in runner
    assert "require_pre_arm_attitude" in runner
    assert "require_pre_arm_horizontal_speed" in runner
    assert '"require_attitude": self.require_pre_arm_attitude' in runner
    assert '"require_horizontal_speed": self.require_pre_arm_horizontal_speed' in runner
    assert "request_data_stream_send" in runner
    assert '"event": "telemetry_stream_request"' in runner
    assert "HARD_PRE_ARM_HEALTH_FAILURE_MARKERS" in runner
    assert "PRE_ARM_CRITICAL_UNHEALTHY_SENSOR_NAMES" in runner
    assert "MAV_SYS_STATUS_SENSOR_ATTITUDE_STABILIZATION" in runner
    assert "PRE_ARM_MAX_ESTIMATOR_POS_HORIZ_ACCURACY_M = 5.0" in runner
    assert "PRE_ARM_MAX_IMU_GYRO_NORM_RAD_S = math.radians(15.0)" in runner
    assert "PX4_LISTENER_DEFAULT" in runner
    assert "def px4_cli_health_probe" in runner
    assert "PX4_NAVIGATION_STATE_BY_MODE" in runner
    assert '"OFFBOARD": 14' in runner
    assert "def _px4_cli_int" in runner
    assert '"vehicle_status": vehicle_status' in runner
    assert "def px4_cli_mode_matches" in runner
    assert "def wait_pre_arm_health_stable" in runner
    assert '"event": "pre_arm_health_gate"' in runner
    assert '"critical_sys_status_healthy"' in runner
    assert '"estimator_horizontal_accuracy_ok"' in runner
    assert '"imu_gyro_norm_ok"' in runner
    assert '"px4_cli_health_ok"' in runner
    assert '"pre_arm_inputs"' in runner
    assert '"reason": "pre_arm_health_unstable"' in runner
    assert "pre_arm_health=pre_arm_health" in runner
    assert "--pre-arm-stability-timeout-s" in runner
    full_mission_runner = (TOOLS / "run_rayfronts_full_mission.py").read_text(encoding="utf-8")
    launch = (LAUNCH_SCRIPTS / "RetroNeighborhood_Launch.py").read_text(encoding="utf-8")
    assert 'UAV_CONTROL_DEFAULT_CONNECTION = "udpin:0.0.0.0:14550"' in full_mission_runner
    assert "return UAV_CONTROL_DEFAULT_CONNECTION" in full_mission_runner
    assert "UAV_CONTROL_DEFAULT_HOVER_S = 2.0" in full_mission_runner
    assert "--uav-control-hover-s" in full_mission_runner
    assert "uav_control_hover_s=args.uav_control_hover_s" in full_mission_runner
    assert "pre_arm_health_timeout_s=240.0" in full_mission_runner
    assert 'return f"udpin:0.0.0.0:{self.app.task.px4_gcs_port}"' in launch  # 14550 for the first task
    assert "AIRGROUND_UAV_PREARM_STRICT_TELEMETRY" in launch
    assert "require_pre_arm_attitude=AIRGROUND_UAV_PREARM_STRICT_TELEMETRY" in launch
    assert "require_pre_arm_horizontal_speed=AIRGROUND_UAV_PREARM_STRICT_TELEMETRY" in launch
    assert "pre_arm_health_timeout_s=240.0" in launch
    assert "--pre-arm-health-timeout-s" in runner
    assert "PRE_ARM_HEALTH_TIMEOUT_DEFAULT_S = 240.0" in runner
    assert "--pre-arm-health-settle-s" in runner
    assert "--pre-arm-max-horizontal-speed-mps" in runner
    assert '--pre-arm-max-horizontal-speed-mps", type=float, default=0.3' in runner
    assert "--pre-arm-max-vertical-speed-mps" in runner
    assert "self.arm_retry_warmup_s" in runner
    assert "self.hover_s" in runner
    assert "self.hover_acceptance_m" in runner
    assert "self.hover_max_horizontal_speed_mps" in runner
    assert "hover_transition_grace_s" in runner
    assert "hover_horizontal_error_m <= self.hover_acceptance_m" in runner
    assert "hover_horizontal_speed_mps <= self.hover_max_horizontal_speed_mps" in runner
    assert "hover_stable_since" in runner
    assert "hover_last_unstable" in runner
    assert "stable_s=round(float(hover_stable_s), 4)" in runner
    assert "horizontal_error_m=round(float(hover_horizontal_error_m), 4)" in runner
    assert "hover_acceptance_m=round(float(self.hover_acceptance_m), 4)" in runner
    assert "transition_grace_s=round(float(hover_transition_grace_s), 4)" in runner
    assert "--hover-acceptance-m" in runner
    assert "--hover-max-horizontal-speed-mps" in runner
    assert "after_arm_command_callback" in runner
    assert "after_send_callback" in runner
    assert "pure non-blocking" in runner
    assert 'timeout=0.02' in runner
    assert "post_arm_callback" in runner
    assert "Callable[[str], None]" in runner
    assert "if (arm_result == 0 or arm_side_effect) and self.post_arm_callback is not None:" in runner
    assert '"arm_ack_ok" if arm_result == 0 else "arm_side_effect_armed"' in runner
    assert "Dock release semantics are tied to a confirmed armed state" in runner
    dock_runner = (TOOLS / "run_dock_takeoff_loop_smoke.py").read_text(encoding="utf-8")
    assert "post_arm_callback = (" in dock_runner
    assert "release_after_arm" in dock_runner
    assert 'reason": reason' in dock_runner


def test_rayfronts_uav_control_adapter_smoke_uses_policy_and_px4_offboard():
    runner = (TOOLS / "run_rayfronts_uav_control_adapter_smoke.py").read_text(encoding="utf-8")

    assert "_rayfronts_uav_action_summary" in runner
    assert "_local_waypoint_from_rayfronts_action" in runner
    assert "OffboardSmokeRunner(" in runner
    assert "waypoint_y_m=waypoint_y_m" in runner
    assert "_uav_control_evidence_from_offboard_report" in runner
    assert "_read_uav_control_evidence_from_payload(evidence)" in runner
    assert "UAV_CONTROL_ADAPTER_NAME" in runner


def test_px4_backend_records_hil_send_counters_for_reset_debugging():
    backend = (
        PEGASUS_PACKAGE / "logic/backends/px4_mavlink_backend.py"
    ).read_text(encoding="utf-8")
    launch = (LAUNCH_SCRIPTS / "RetroNeighborhood_Launch.py").read_text(encoding="utf-8")
    for name in (
        "_sensor_send_count",
        "_sensor_send_error_count",
        "_gps_send_count",
        "_gps_send_error_count",
        "_groundtruth_send_count",
        "_groundtruth_send_error_count",
        "_last_sensor_fields_updated",
    ):
        assert name in backend
        assert name in launch
    assert "self._sensor_send_count += 1" in backend
    assert "self._gps_send_count += 1" in backend
    assert "self._groundtruth_send_count += 1" in backend
    assert 'backend_summary[attr.removeprefix("_")]' in launch
    assert '"sim_lat"' in launch
    assert 'backend_summary[f"sensor_data_{attr}"] = float(value)' in launch


def test_clock_sync_collector_emits_barrier_trace():
    collector = (TOOLS / "collect_clock_sync_trace.py").read_text(encoding="utf-8")

    assert "/clock" in collector
    assert "/uav/sensors/front_stereo/left/camera_info" in collector
    assert "/ugv/sensors/front_stereo/left/camera_info" in collector
    assert '"event": "clock_sync_step"' in collector
    assert '"raw_clock_time_s"' in collector
    assert '"raw_uav_stamp_s"' in collector
    assert '"raw_ugv_stamp_s"' in collector
    assert '"sensor_frame_count"' in collector
    assert "self.required_sensor_frames = max(1, round(sensor_hz / agent_hz))" in collector
    assert "sensor_frame_count < self.required_sensor_frames" in collector
    assert '"clock_time_s": _round_seconds(expected_time_s)' in collector
    assert '"uav_stamp_s": _round_seconds(expected_time_s)' in collector
    assert '"ugv_stamp_s": _round_seconds(expected_time_s)' in collector
    assert "--expected-steps" in collector
    assert "--sensor-hz" in collector
    assert "--agent-hz" in collector


def test_dock_takeoff_loop_runner_uses_real_isaac_reset_and_joint():
    runner = (TOOLS / "run_dock_takeoff_loop_smoke.py").read_text(encoding="utf-8")

    assert '"event": "reset_dock_takeoff_cycle"' in runner
    assert "def _reset_cycle_world" in runner
    assert "def _refresh_uav_physics_callbacks" in runner
    assert "self.app.pg.get_vehicle(self.retro.UAV_PRIM)" in runner
    assert "remove_physics_callback" in runner
    assert 'f"{stage_prefix}/state": getattr(vehicle, "update_state", None)' in runner
    assert 'f"{stage_prefix}/update": getattr(vehicle, "update", None)' in runner
    assert 'f"{stage_prefix}/Sensors": getattr(vehicle, "update_sensors", None)' in runner
    assert 'f"{stage_prefix}/mav_state": getattr(vehicle, "update_sim_state", None)' in runner
    assert "self.app.world.add_physics_callback(callback_name, callback)" in runner
    assert "self.app.timeline.stop()" in runner
    assert 'self.app.world.reset()' in runner
    assert "self._refresh_uav_physics_callbacks()" in runner
    assert 'self.app.timeline.play()' in runner
    assert "kit_app.update()" in runner
    assert "--reuse-initial-reset-first-cycle" in runner
    assert "--no-launch-dock-joint" in runner
    assert '"reused_initial_reset": reused_initial_reset' in runner
    assert "def _env_force" in runner
    assert '_env_force("PLAY_SIM_ON_START", "false")' in runner
    assert '_env_force(\n        "AIRGROUND_CREATE_DOCK_JOINT"' in runner
    assert '"true" if args.launch_dock_joint else "false"' in runner
    assert '_env_force("DRONE_X", os.environ["UGV_X"])' in runner
    assert '_env_force("DRONE_Y", os.environ["UGV_Y"])' in runner
    assert "AirGroundDockJointController" in runner
    assert "self.retro.docked_uav_world_pose(" not in runner
    assert "DockContactImpulseSampler" in runner
    assert "dock_contact_impulse_sample" in runner
    assert "--contact-impulse-trace-output" in runner
    assert "--contact-impulse-sample-period" in runner
    assert '"contact_impulse_trace"' in runner
    assert '"unexpected_contact_count"' in runner
    assert '"unexpected_collision_impulse_n_s"' in runner
    assert "self.retro.set_articulation_root_world_pose(" in runner
    assert "def _rigid_prim_world_pose" in runner
    assert "uav_body_physics_world_xyz" in runner
    assert '"clearance_source": selected_body_source' in runner
    assert "dock_status = self.dock_joint.create()" in runner
    assert "self.dock_joint.release()" in runner
    assert '"takeoff_mode": self.takeoff_mode' in runner
    assert '"geometric_release", "px4_offboard"' in runner
    assert "AIRGROUND_UAV_PX4_AUTOLAUNCH" in runner
    assert 'args.takeoff_mode == "px4_offboard"' in runner
    assert '"--heartbeat-timeout-s"' in runner
    assert '"--takeoff-timeout-s"' in runner
    assert '"--waypoint-timeout-s"' in runner
    assert '"--arm-ready-timeout-s"' in runner
    assert '"--pre-arm-stability-timeout-s"' in runner
    assert '"--pre-arm-health-timeout-s"' in runner
    assert '"--pre-arm-health-settle-s"' in runner
    assert '"--pre-arm-max-horizontal-speed-mps"' in runner
    assert '"--pre-arm-max-vertical-speed-mps"' in runner
    assert '"--arm-max-attempts"' in runner
    assert '"--pre-arm-warmup-s"' in runner
    assert '"--arm-retry-warmup-s"' in runner
    assert "--px4-pre-arm-warmup-s" in runner
    assert "--px4-arm-retry-warmup-s" in runner
    assert "--px4-waypoint-timeout-s" in runner
    assert "--px4-arm-ready-timeout-s" in runner
    assert "--px4-pre-arm-stability-timeout-s" in runner
    assert "--px4-pre-arm-health-timeout-s" in runner
    assert "--px4-pre-arm-health-settle-s" in runner
    assert "--px4-pre-arm-max-horizontal-speed-mps" in runner
    assert '--px4-pre-arm-max-horizontal-speed-mps", type=float, default=0.3' in runner
    assert "--px4-pre-arm-max-vertical-speed-mps" in runner
    assert "--px4-arm-max-attempts" in runner
    assert "--px4-pre-arm-telemetry-retries" in runner
    assert '--px4-pre-arm-telemetry-retries", type=int, default=3' in runner
    assert "self.px4_pre_arm_telemetry_retries" in runner
    assert '"cycle_retries"' in runner
    assert '"pre_arm_telemetry_unstable"' in runner
    assert "def _recover_px4_backend_after_telemetry_drop" in runner
    assert '"event": "px4_backend_recovery"' in runner
    assert "self.app.timeline.stop()" in runner
    assert 'stop = getattr(backend, "stop", None)' in runner
    assert "stop()" in runner
    assert "backend.px4_tool = None" in runner
    assert "kill_all_px4()" in runner
    assert "recovery=recovery" in runner
    assert "def _takeoff_failure_reason" in runner
    assert '"failure_reason": f"{type(exc).__name__}: {exc}"' in runner
    assert 'attempt_event["failure_reason"] = failure_reason' in runner
    assert "self.px4_waypoint_timeout_s" in runner
    assert "self.px4_waypoint_x_m" in runner
    assert "self.px4_waypoint_y_m" in runner
    assert "self.px4_waypoint_acceptance_m" in runner
    assert "self.px4_hover_acceptance_m" in runner
    assert "self.px4_hover_max_horizontal_speed_mps" in runner
    assert "self.px4_arm_ready_timeout_s" in runner
    assert "self.px4_pre_arm_stability_timeout_s" in runner
    assert "self.px4_pre_arm_health_timeout_s" in runner
    assert "self.px4_pre_arm_health_settle_s" in runner
    assert "self.px4_arm_max_attempts" in runner
    assert "px4_waypoint_timeout_s=args.px4_waypoint_timeout_s" in runner
    assert "px4_waypoint_x_m=args.px4_waypoint_x_m" in runner
    assert "px4_waypoint_y_m=args.px4_waypoint_y_m" in runner
    assert "px4_waypoint_acceptance_m=args.px4_waypoint_acceptance_m" in runner
    assert "px4_hover_acceptance_m=args.px4_hover_acceptance_m" in runner
    assert "px4_hover_max_horizontal_speed_mps=args.px4_hover_max_horizontal_speed_mps" in runner
    assert "px4_arm_ready_timeout_s=args.px4_arm_ready_timeout_s" in runner
    assert "px4_pre_arm_stability_timeout_s=args.px4_pre_arm_stability_timeout_s" in runner
    assert "px4_pre_arm_health_timeout_s=args.px4_pre_arm_health_timeout_s" in runner
    assert "px4_pre_arm_health_settle_s=args.px4_pre_arm_health_settle_s" in runner
    assert "px4_arm_max_attempts=args.px4_arm_max_attempts" in runner
    assert "px4_pre_arm_telemetry_retries=args.px4_pre_arm_telemetry_retries" in runner
    assert '"--px4-waypoint-timeout-s must be finite and positive"' in runner
    assert '"--px4-waypoint-x-m must be finite and non-negative"' in runner
    assert '"--px4-waypoint-y-m must be finite"' in runner
    assert '"--px4-waypoint-acceptance-m must be finite and non-negative"' in runner
    assert '"--px4-hover-acceptance-m must be finite and non-negative"' in runner
    assert '"--px4-hover-max-horizontal-speed-mps must be finite and non-negative"' in runner
    assert '"--px4-arm-ready-timeout-s must be finite and non-negative"' in runner
    assert '"--px4-pre-arm-stability-timeout-s must be finite and non-negative"' in runner
    assert '"--px4-pre-arm-health-timeout-s must be finite and non-negative"' in runner
    assert '"--px4-pre-arm-health-settle-s must be finite and non-negative"' in runner
    assert '"--px4-arm-max-attempts must be positive"' in runner
    assert '"--px4-pre-arm-telemetry-retries must be non-negative"' in runner
    assert '"--hover-s"' in runner
    assert "def _load_offboard_smoke" in runner
    assert "def _resolve_px4_connection" in runner
    assert "18570 + vehicle_id" in runner
    assert "--px4-control-mode" in runner
    assert 'choices=("in_process", "subprocess")' in runner
    assert 'default="in_process"' in runner
    assert "--px4-dock-release-policy" in runner
    assert 'choices=("after_arm_ack", "after_arm_command")' in runner
    assert 'default="after_arm_ack"' in runner
    assert "self.px4_control_mode == \"in_process\"" in runner
    assert "self.px4_dock_release_policy == \"after_arm_command\"" in runner
    assert "OffboardSmokeRunner(" in runner
    assert "waypoint_x_m=waypoint_x_m" in runner
    assert "waypoint_y_m=waypoint_y_m" in runner
    assert "waypoint_acceptance_m=self.px4_waypoint_acceptance_m" in runner
    assert "hover_acceptance_m=self.px4_hover_acceptance_m" in runner
    assert "hover_max_horizontal_speed_mps=self.px4_hover_max_horizontal_speed_mps" in runner
    assert "SmokeRecorder(offboard_trace)" in runner
    assert "after_arm_command_callback=after_arm_command_callback" in runner
    assert "step_callback=step_callback" in runner
    assert "post_arm_callback=post_arm_callback" in runner
    assert "def _load_full_mission_runner" in runner
    assert "--rayfronts-uav-control-adapter" in runner
    assert "_rayfronts_uav_action_summary" in runner
    assert "_local_waypoint_from_rayfronts_action" in runner
    assert "_uav_control_evidence_from_offboard_report" in runner
    assert "_read_uav_control_evidence_from_payload(evidence)" in runner
    assert '"rayfronts_uav_control_adapter_status"' in runner
    assert '"rayfronts_uav_control_evidence"' in runner
    assert '"dock_release_after_arm"' in runner
    assert '"dock_release_status": dock_release_status' in runner
    assert '"control_mode": self.px4_control_mode' in runner
    assert '"px4_autolaunch": bool(getattr(self.retro, "UAV_PX4_AUTOLAUNCH", False))' in runner
    assert "subprocess.Popen(command)" in runner
    assert "run_uav_offboard_smoke.py" in runner
    assert '"offboard_trace": str(offboard_trace)' in runner
    assert '"offboard_report": str(offboard_report)' in runner
    assert "--physics-trace-output" in runner
    assert "AIRGROUND_VEHICLE_FORCE_TRACE" in runner
    assert "AIRGROUND_MULTIROTOR_DYNAMICS_TRACE" in runner
    assert '"physics_trace": (' in runner
    assert '"physics_trace_output": (' in runner
    assert "--pose-trace-output" in runner
    assert '"event": "dock_pose_sample"' in runner
    assert '"dock_anchor_world_xyz"' in runner
    assert '"clearance_m": _round' in runner
    assert '"docked_clearance_m": _round(docked_clearance)' in runner
    assert '"docked_clearance_ok": docked_clearance_ok' in runner
    assert '"pose_trace": (' in runner
    assert '"pose_trace_output": (' in runner
    assert '"reset_sequence": reset_sequence' in runner
    for field in (
        '"fresh_world_reset"',
        '"timeline_stopped_before_reset"',
        '"world_reset_called"',
        '"uav_physics_callbacks_refreshed"',
        '"ugv_reinitialized"',
        '"ugv_post_reset_called"',
        '"ugv_zero_cmd_vel_applied"',
        '"ugv_locked_after_reinit"',
        '"uav_aligned_to_dock"',
        '"dock_joint_recreated"',
        '"timeline_played_after_dock"',
    ):
        assert field in runner
    assert '"max_takeoff_clearance_m": _round(max_clearance)' in runner
    assert "--takeoff-mode" in runner
    assert "--offboard-output" in runner
    assert "--px4-connection" in runner
    assert "--px4-waypoint-y-m" in runner
    assert '--px4-target-altitude-m", type=float, default=1.45' in runner
    assert "--pre-align-settle-steps" in runner
    assert 'contact_phase="pre_align_settle"' in runner
    assert '"dock_release_pre_align"' in runner
    assert '"dock_joint_created"' in runner
    assert 'contact_phase="post_dock_settle"' in runner
    assert "self.dock_joint.release()" in runner
    assert '"ugv_locked_until_takeoff": ugv_locked' in runner
    assert '"min_takeoff_clearance_m": _round(min_clearance)' in runner
    assert '"min_takeoff_clearance_m": -1.0e9' in runner
    assert '"docked_clearance_m": -1.0e9' in runner
    assert '"min_takeoff_clearance_m": -math.inf' not in runner
    assert "--cycles" in runner
    assert "--cycle-index-offset" in runner
    assert "--append-output" in runner
    assert "self.append_output = append_output" in runner
    assert "if not self.append_output:" in runner
    assert "self.cycle_index_offset = cycle_index_offset" in runner
    assert "range(self.cycle_index_offset, self.cycle_index_offset + self.cycles)" in runner
    assert '"--cycle-index-offset must be non-negative"' in runner
    assert "--min-clearance-m" in runner
    assert "--min-docked-clearance-m" in runner


def test_retro_launch_exposes_full_mission_evidence_server() -> None:
    launch = (LAUNCH_SCRIPTS / "RetroNeighborhood_Launch.py").read_text(encoding="utf-8")

    assert "AIRGROUND_ENABLE_FULL_MISSION_EVIDENCE_SERVER" in launch
    assert "class AirGroundFullMissionEvidenceServer" in launch
    assert 'FULL_MISSION_EVIDENCE_REQUEST_TOPIC = "/airground/full_mission/evidence_request"' in launch
    assert 'FULL_MISSION_EVIDENCE_RESPONSE_TOPIC = "/airground/full_mission/evidence_response"' in launch
    assert "def _communication_los" in launch
    assert "RuntimeCommunicationBridge" in launch
    assert "make_isaac_physx_raycast_fn" in launch
    assert "def _confirmation_sensor_frames" in launch
    assert "confirmation_sensor_frame_records_from_pose" in launch
    assert "def _episode_reset" in launch
    assert "def reset_episode_start" in launch
    assert 'kind == "episode_reset"' in launch
    assert "self.timeline.stop()" in launch
    assert "def _zero_uav_actuator_state" in launch
    assert "episode_reset_before_settle" in launch
    assert "actuator_zero_before_backend_stop" in launch
    assert "actuator_zero_after_backend_stop" in launch
    assert "zero_input_reference()" in launch
    assert "uav_actuator_zero_before_settle" in launch
    assert "def _refresh_uav_body_local_rotation_compensation" in launch
    assert "body_rotation_compensation_after_world_reset" in launch
    assert "body_rotation_compensation_after_redock" in launch
    assert "rigid_prim_cache_cleared" in launch
    assert "uav_body_applied_orientation_wxyz" in launch
    assert "def skip_articulation_child_world_pose_reset" in launch
    assert "articulation_child_live_world_pose_reset_disabled" in launch
    assert "uav_body_pose_reset_status" in launch
    assert "uav_body_target_orientation_wxyz" in launch
    assert "uav_body_local_orientation_wxyz" in launch
    assert "uav_body_local_restore_status" in launch
    assert "canonical_body_local_pose" in launch
    assert "author_usd_xform=False" in launch
    assert "def _reset_uav_px4_backend_state" in launch
    assert "def _restart_uav_px4_backend_state" in launch
    assert "PX4LaunchTool.kill_all_px4" in launch
    assert "px4_backend_reset" in launch
    assert "px4_backend_restart_after_reset" in launch
    assert "px4_backend_post_restart_warmup" in launch
    assert "uav_velocity_reset_after_dock_settle" in launch
    assert "def _uav_px4_runtime_snapshot" in launch
    assert "def _pump_uav_px4_runtime_once" in launch
    assert 'self.app._pump_uav_px4_runtime_once("uav_control_step")' in launch
    assert "UGV stop command skipped during UAV control step" in launch
    assert 'self.app._pump_uav_px4_runtime_once("uav_control_prearm_retry_recovery")' in launch
    assert 'self._pump_uav_px4_runtime_once("episode_reset_post_restart_warmup")' in launch
    assert '"received_first_imu"' in launch
    assert '"current_utime"' in launch
    assert "force_stop_before_start" in launch
    assert "kill_all_px4_before_start" in launch
    assert '("_connection", None)' in launch
    assert '("_is_running", False)' in launch
    assert 'backend_summary[f"{attr}_cleared_before_start"] = True' in launch
    assert "start()" in launch
    assert "start_called" in launch
    assert "is_running_after_start" in launch
    assert "has_connection_after_start" in launch
    assert "self.world.reset()" in launch
    assert "callback_refresh_after_world_reset" in launch
    assert "AIRGROUND_EPISODE_WORLD_RESET" in launch
    assert 'reset_mode = "world_reset" if AIRGROUND_EPISODE_WORLD_RESET else "soft_reset"' in launch
    assert "Keep soft resets live so dock joints and Pegasus thrust targets stay" in launch
    assert "if AIRGROUND_EPISODE_WORLD_RESET:\n            self.timeline.stop()" in launch
    assert "episode_reset_mode" in launch
    assert "episode_world_reset_enabled" in launch
    assert "body_rotation_compensation_after_episode_reset" in launch
    assert "ground_support_after_episode_reset" in launch
    assert "timeline_stopped_before_episode_reset" in launch
    assert "soft_reset_reuses_live_articulation" in launch
    assert "timeline_played_after_reset" in launch
    assert "timeline_stopped_before_world_reset" in launch
    assert "world_reset_called" in launch
    assert "set_articulation_root_world_pose(stage, UGV_PRIM" in launch
    assert "def set_robot_world_pose_and_zero_velocity" in launch
    assert "ugv_reinitialize_status" in launch
    assert "ugv_robot_pose_reset_status" in launch
    assert "ugv_body_pose_reset_status" in launch
    assert "UGV_SENSOR_BODY_PATH" in launch
    assert "def _uav_control_offboard" in launch
    assert 'kind == "uav_force_response_probe"' in launch
    assert "def _uav_force_response_probe" in launch
    assert "apply_dynamic_control_probe_force" in launch
    assert "apply_rigid_prim_probe_force" in launch
    assert "dynamic_control_local" in launch
    assert "dynamic_control_world" in launch
    assert "rigid_prim_local" in launch
    assert "rigid_prim_world" in launch
    assert "vehicle_apply_force" in launch
    assert "rigid_body_diagnostic_snapshot" in launch
    assert "ensure_rigid_body_runtime_flags" in launch
    assert "def _is_retryable_uav_control_prearm_failure" in launch
    assert "def _recover_uav_control_prearm_retry" in launch
    assert "pre_arm_telemetry_unstable" in launch
    assert "pre_arm_health_unstable" in launch
    assert "dock_release_status.get(\"released\") is True" in launch
    assert "episode_reset_before_uav_control_retry" in launch
    assert "episode_start_reset" in launch
    assert "px4_backend_restart_before_uav_control_retry" in launch
    assert "px4_backend_restart" in launch
    assert "uav_sensor_reset" in launch
    assert "max_prearm_retry_attempts" in launch
    assert "attempt_reports" in launch
    assert "retry_recoveries" in launch
    assert "uav_control_offboard_attempt_start" in launch
    assert "uav_control_diagnostic_traces_configured" in launch
    assert "def _uav_control_attempt_artifact_paths" in launch
    assert "def _configure_uav_control_diagnostics" in launch
    assert "uav_control_actuator_trace" in launch
    assert "uav_control_dynamics_trace" in launch
    assert "uav_control_force_trace" in launch
    assert "diagnostic_trace_setup" in launch
    assert "uav_px4_runtime_before_control" in launch
    assert "uav_px4_runtime_after_control" in launch
    assert "airground_skip_force_steps_remaining" in launch
    assert "rotor_data" in launch
    assert "actuator_trace_count" in launch
    assert '"physical_dock_joint_enabled": False' in launch
    assert '"physical_dock_joint_enabled": True' in launch
    assert '"status": "semantic_dock_pose_only"' in launch
    assert "AirGround physical dock joint disabled; UAV starts from dock-aligned pose" in launch
    assert "dock joint is unavailable for UAV-control release" not in launch
    assert "OffboardSmokeRunner(" in launch
    assert "step_callback=self._step_once_for_uav_control" in launch
    assert "post_arm_callback=release_after_arm_with_record" in launch
    assert 'hover_s=float(payload.get("hover_s", 2.0))' in launch
    assert 'waypoint_timeout_s=float(payload.get("waypoint_timeout_s", 90.0))' in launch
    assert "self._pending_requests" in launch
    assert "self._response_cache" in launch
    assert "def _handle_request" in launch
    assert "def _refresh_uav_physics_callbacks" in launch
    assert '"event": "uav_physics_callbacks_refreshed"' in launch
    assert "self.full_mission_evidence_server.spin_once()" in launch


def test_rayfronts_full_mission_runner_reset_trace_records_step_statuses():
    runner = (TOOLS / "run_rayfronts_full_mission.py").read_text(encoding="utf-8")

    assert "def _reset_trace" in runner
    assert '"events": [' in runner
    assert '"step_id": step_id' in runner
    assert '"status": step_status' in runner
    assert '"steps": list(SOFT_RESET_STEPS)' in runner


def test_rayfronts_full_mission_waits_for_nav2_action_server_with_evidence():
    runner = (TOOLS / "run_rayfronts_full_mission.py").read_text(encoding="utf-8")

    assert "NAV2_ACTION_SERVER_WAIT_TIMEOUT_S = 90.0" in runner
    assert 'evidence["nav2_action_server_wait_s"]' in runner
    assert 'evidence["nav2_action_server_wait_timeout_s"]' in runner
    assert '"action_server_unavailable"' in runner
    assert "node.get_node_names_and_namespaces()" in runner


def test_rayfronts_full_mission_caps_the_per_hop_climb():
    """2026-10-07: an unbounded first-hop climb flipped the UAV.

    runs/paper30_final retro-paper-type-iii-yellow-car-to-billboard-s3: the
    first queue entry after hover carried 15 m lateral *and* +8.7 m climb; PX4
    raised "Preflight Fail: Attitude failure (roll)" 3.5 s later and the UAV
    lay inverted at 8.6 m for the rest of the episode.  The per-hop climb is
    now rate-limited like the horizontal leg.
    """

    runner = (TOOLS / "run_rayfronts_full_mission.py").read_text(encoding="utf-8")

    assert "AIRGROUND_UAV_HOP_MAX_CLIMB_M" in runner
    # The cap is injectable (``max_climb_m``) so the callers/tests can exercise
    # the uncapped reference; ``None`` still resolves the env default.
    assert "climb_up_m = max(-float(max_climb_m), min(float(max_climb_m), climb_up_m))" in runner
    assert "max_climb_m: float | None = None," in runner


def test_rayfronts_full_mission_clamps_near_edge_goals_instead_of_deadlocking():
    """2026-10-07: a hypothesis 11.5 m outside the ROI deadlocked the feed.

    Measured in runs/paper30_final (house-s1, type-ii bus-stop-blue-container-s1):
    the hard bounds rejection retried the same out-of-bounds goal every tick and
    the whole episode ran with goal_feed_count=0 and zero flight.  Goals within
    ``AIRGROUND_GOAL_BOUNDS_CLAMP_MARGIN_M`` of the box are clamped onto the ROI
    edge; farther goals keep the original fail-closed rejection.
    """

    runner = (TOOLS / "run_rayfronts_full_mission.py").read_text(encoding="utf-8")

    assert "def _clamp_goal_into_search_bounds" in runner
    assert "min(max(float(value), lower), upper)" in runner
    assert "AIRGROUND_GOAL_BOUNDS_CLAMP_MARGIN_M" in runner
    assert "offset_m > margin_m" in runner
    assert "clamping onto the ROI edge" in runner


def test_rayfronts_full_mission_runner_enforces_nontrivial_uav_search_waypoint():
    runner = (TOOLS / "run_rayfronts_full_mission.py").read_text(encoding="utf-8")

    assert "UAV_CONTROL_DEFAULT_WAYPOINT_MIN_DISTANCE_M" in runner
    assert "--uav-control-waypoint-min-distance-m" in runner
    assert "min_distance_m=waypoint_min_distance_m" in runner
    assert "target_distance_m = min(max_distance_m, max(min_distance_m, distance_m))" in runner
    assert "min distance cannot exceed max distance" in runner


def test_uav_offboard_queue_reader_reads_incrementally():
    """2026-10-07: re-reading the whole queue per call ground the episode down.

    runs/probe_fix1 house-s2: the append-only queue reached 398 KB while the
    drain loop called the reader once per unread entry, so each control
    iteration cost O(file x pending) -- RTF fell to ~0.11 and a 300 s budget
    took 45+ min of wall time.  The reader now seeks the last byte offset.
    """

    runner = (TOOLS / "run_uav_offboard_smoke.py").read_text(encoding="utf-8")

    assert "self._queue_byte_offset" in runner
    assert "stream.seek(self._queue_byte_offset)" in runner
    assert 'path.open("rb")' in runner
    assert "self._queue_offset" not in runner


def test_uav_offboard_retries_mode_after_arm_side_effect():
    runner = (TOOLS / "run_uav_offboard_smoke.py").read_text(encoding="utf-8")

    assert "arm_confirmed = arm_result == 0 or arm_side_effect" in runner
    assert "if arm_confirmed and offboard_result != 0 and not offboard_side_effect:" in runner
    assert '"event": "offboard_retry_after_arm"' in runner
    assert '"arm_side_effect": arm_side_effect' in runner
    assert '"arm_side_effect_from_px4_cli": arm_side_effect_from_px4_cli' in runner
    assert '"offboard_side_effect_from_px4_cli": offboard_side_effect_from_px4_cli' in runner
    assert 'self.px4_cli_mode_matches("OFFBOARD", force=True)' in runner
    assert 'self.px4_cli_armed(force=True)' in runner
    assert "arm_ok = (offboard_result == 0 or offboard_side_effect) and arm_confirmed" in runner


def test_multirotor_force_trace_diagnostics_are_opt_in():
    vehicle = (PEGASUS_PACKAGE / "logic/vehicles/vehicle.py").read_text(encoding="utf-8")
    multirotor = (PEGASUS_PACKAGE / "logic/vehicles/multirotor.py").read_text(encoding="utf-8")

    assert "from isaacsim.core.experimental.prims import RigidPrim" in vehicle
    assert "from isaacsim.core.prims import RigidPrim" in vehicle
    assert "import re" in vehicle
    assert 'RigidPrim(\n                    prim_paths_expr=f"^{re.escape(prim_path)}$"' in vehicle
    assert 'os.environ.get("AIRGROUND_VEHICLE_FORCE_TRACE", "").strip()' in vehicle
    assert "AIRGROUND_VEHICLE_FORCE_BACKEND" in vehicle
    assert "AIRGROUND_DYNAMIC_CONTROL_FORCE_FRAME" in vehicle
    assert "def _default_dynamic_control_force_frame" in vehicle
    assert 'return "world"' in vehicle
    assert 'return "local"' in vehicle
    assert 'return "dynamic_control" if _dynamic_control is not None else "rigid_prim"' in vehicle
    assert "def _float3(values)" in vehicle
    assert "carb._carb.Float3(float(values[0]), float(values[1]), float(values[2]))" in vehicle
    assert "def _dynamic_control_body" in vehicle
    assert "_dynamic_control.INVALID_HANDLE" in vehicle
    assert "dc.wake_up_articulation(articulation)" in vehicle
    assert '"wake_applied": bool(wake_applied)' in vehicle
    assert '"rigid_body_handle": int(rb)' in vehicle
    assert '"articulation_handle": int(articulation)' in vehicle
    assert "AIRGROUND_VEHICLE_STATE_VELOCITY_SOURCE" in vehicle
    assert "def _default_state_velocity_source" in vehicle
    assert 'if simulator_version.startswith("4.5"):' in vehicle
    assert 'return "usd_finite_diff"' in vehicle
    assert 'AIRGROUND_VEHICLE_STATE_VELOCITY_SOURCE == "dynamic_control"' in vehicle
    assert 'AIRGROUND_VEHICLE_STATE_VELOCITY_SOURCE == "rigid_prim"' in vehicle
    assert "self._last_state_attitude" in vehicle
    assert 'AIRGROUND_VEHICLE_FORCE_BACKEND != "rigid_prim"' in vehicle
    assert '"event": "vehicle_force_application"' in vehicle
    assert '"backend": "rigid_prim"' in vehicle
    assert '"applied": True' in vehicle
    assert "def _local_force_to_world" in vehicle
    assert "def _local_point_to_world" in vehicle
    assert "def _dynamic_control_force_payload" in vehicle
    assert "def _dynamic_control_torque_payload" in vehicle
    assert "def apply_world_force" in vehicle
    assert "def apply_world_torque" in vehicle
    assert 'dc.apply_body_force(rb, _float3(applied_force), _float3(applied_pos), is_global)' in vehicle
    assert 'dc.apply_body_torque(rb, _float3(applied_torque), is_global)' in vehicle
    assert 'dc.apply_body_force(rb, _float3(force_values), _float3(pos_values), True)' in vehicle
    assert 'dc.apply_body_torque(rb, _float3(torque_values), True)' in vehicle
    assert '"dynamic_control_is_global": bool(is_global)' in vehicle
    assert '"force_frame": AIRGROUND_DYNAMIC_CONTROL_FORCE_FRAME' in vehicle
    assert '"force_frame_source": source_frame' in vehicle
    assert "def _usd_pose_velocity_fallback" in vehicle
    assert "Falling back to USD pose state" in vehicle
    assert '"world_force_z"' in vehicle
    assert "world.TransformDir(vector)" in vehicle
    assert "RigidPrim unavailable" in vehicle
    assert 'os.environ.get("AIRGROUND_MULTIROTOR_DYNAMICS_TRACE", "").strip()' in multirotor
    assert "AIRGROUND_MULTIROTOR_FORCE_ON_BODY" in multirotor
    assert "AIRGROUND_MULTIROTOR_AGGREGATE_FORCE_FRAME_SOURCE" in multirotor
    assert "AIRGROUND_MULTIROTOR_AGGREGATE_FORCE_ON_BODY" in multirotor
    assert "def _default_aggregate_force_on_body" in multirotor
    assert "def _default_aggregate_force_frame_source" in multirotor
    assert 'return simulator_version.startswith("4.5")' in multirotor
    assert 'return "body_world"' in multirotor
    assert 'return "body_prim"' in multirotor
    assert "def _rotor_position_in_body_frame" in multirotor
    assert "def _state_attitude_body_vector_to_world" in multirotor
    assert "def _body_prim_vector_to_world" in multirotor
    assert "def _apply_aggregate_force_and_torque" in multirotor
    assert '"body_prim", "body_world", "state_attitude"' in multirotor
    assert "source_frame=self._aggregate_force_frame_source" in multirotor
    assert "config.prim_paths.body_path == \"/chassis\"" in multirotor
    assert '"force_application_mode": (' in multirotor
    assert '"body_aggregate" if self._aggregate_force_on_body else "rotor_points"' in multirotor
    assert '"aggregate_force_frame_source": self._aggregate_force_frame_source' in multirotor
    assert '"aggregate_force_on_body": bool(self._aggregate_force_on_body)' in multirotor
    assert 'aggregate_torque_body += np.cross(rotor_body, force_body)' in multirotor
    assert 'self._apply_aggregate_force_and_torque(' in multirotor
    assert 'self.apply_world_force(' in multirotor
    assert 'self.apply_world_torque(' in multirotor
    assert "body_part=self._prim_paths.body_path" in multirotor
    assert '"event": "multirotor_dynamics"' in multirotor
    assert '"total_thrust_n": float(sum(forces_z))' in multirotor
    assert '"force_application_backend": (' in multirotor
    assert '"force_application_skipped": bool(force_application_skipped)' in multirotor


def test_isaac_force_response_probe_client_uses_evidence_server_topic():
    tool = (TOOLS / "run_isaac_force_response_probe.py").read_text(encoding="utf-8")

    assert '"uav_force_response_probe"' in tool
    assert 'REQUEST_TOPIC = "/airground/full_mission/evidence_request"' in tool
    assert 'RESPONSE_TOPIC = "/airground/full_mission/evidence_response"' in tool
    assert "--force-n" in tool
    assert "测试力，单位牛顿" in tool
    assert "--position-m" in tool
    assert "施力点，单位米" in tool
    assert "--force-steps" in tool
    assert "--settle-steps" in tool
    assert "dynamic_control_local" in tool
    assert "dynamic_control_world" in tool
    assert "rigid_prim_local" in tool
    assert "rigid_prim_world" in tool
    assert "vehicle_apply_force" in tool
    assert "rclpy.create_node" in tool
    assert "create_publisher(String, args.request_topic" in tool
    assert "create_subscription(String, args.response_topic" in tool


def test_multirotor_reset_guard_skips_forces_but_keeps_backends_alive():
    multirotor = (PEGASUS_PACKAGE / "logic/vehicles/multirotor.py").read_text(encoding="utf-8")
    launch = (LAUNCH_SCRIPTS / "RetroNeighborhood_Launch.py").read_text(encoding="utf-8")

    assert "AIRGROUND_UAV_RESET_FORCE_SKIP_STEPS" in launch
    compose = (DOCKER / "docker-compose.yaml").read_text(encoding="utf-8")
    assert "AIRGROUND_EPISODE_WORLD_RESET=${AIRGROUND_EPISODE_WORLD_RESET:-}" in compose
    assert "AIRGROUND_UAV_RESET_FORCE_SKIP_STEPS=${AIRGROUND_UAV_RESET_FORCE_SKIP_STEPS:-}" in compose
    assert "AIRGROUND_UAV_PREARM_STRICT_TELEMETRY=${AIRGROUND_UAV_PREARM_STRICT_TELEMETRY:-}" in compose
    assert "AIRGROUND_DYNAMIC_CONTROL_FORCE_FRAME=${AIRGROUND_DYNAMIC_CONTROL_FORCE_FRAME:-}" in compose
    assert "AIRGROUND_VEHICLE_FORCE_BACKEND=${AIRGROUND_VEHICLE_FORCE_BACKEND:-}" in compose
    assert "AIRGROUND_VEHICLE_STATE_VELOCITY_SOURCE=${AIRGROUND_VEHICLE_STATE_VELOCITY_SOURCE:-}" in compose
    assert "AIRGROUND_MULTIROTOR_FORCE_ON_BODY=${AIRGROUND_MULTIROTOR_FORCE_ON_BODY:-}" in compose
    assert "AIRGROUND_MULTIROTOR_AGGREGATE_FORCE_FRAME_SOURCE=${AIRGROUND_MULTIROTOR_AGGREGATE_FORCE_FRAME_SOURCE:-}" in compose
    assert "AIRGROUND_MULTIROTOR_AGGREGATE_FORCE_ON_BODY=${AIRGROUND_MULTIROTOR_AGGREGATE_FORCE_ON_BODY:-}" in compose
    assert "def _suspend_uav_force_application" in launch
    assert 'setattr(vehicle, "_airground_skip_force_steps_remaining", applied_steps)' in launch
    assert 'setattr(vehicle, "_airground_skip_force_reason", reason)' in launch
    assert 'vehicle._vehicle_dc_interface = None' in launch
    assert 'vehicle._last_state_attitude = None' in launch
    assert '"_aggregate_force_frame_source"' in launch
    assert '"ugv_stop_before_settle": ugv_stop_before_settle' in launch
    assert '"ugv_root_pose_reset_status": ugv_root_pose_reset_status' in launch
    assert '"uav_root_pose_reset_status": uav_root_pose_reset_status' in launch
    assert 'usd_pose_authored_before_error' in launch
    assert '"force_suspend_before_episode_reset": force_suspend_before_episode_reset' in launch
    assert '"force_suspend_before_world_reset": (' in launch
    assert '"force_suspend_after_redock": force_suspend_after_redock' in launch
    assert 'skip_force_steps = int(getattr(self, "_airground_skip_force_steps_remaining", 0) or 0)' in multirotor
    assert 'self._airground_skip_force_steps_remaining = skip_force_steps - 1' in multirotor
    assert 'force_application_skipped=True' in multirotor
    assert 'skip_reason=skip_reason' in multirotor
    assert 'for backend in self._backends:\n                backend.update(dt)\n            return' in multirotor
    assert multirotor.index("skip_force_steps = int(") < multirotor.index("articulation = None")


def test_jackal_cmd_vel_falls_back_to_joint_velocity_setter():
    jackal = (PEGASUS_PACKAGE / "logic/vehicles/jackal.py").read_text(encoding="utf-8")

    assert 'AIRGROUND_JACKAL_CMD_VEL_BACKEND' in jackal
    assert 'simulator_version.startswith("4.5")' in jackal
    assert 'return "direct_joint_velocity"' in jackal
    assert "class JackalDirectJointVelocityRobot" in jackal
    assert 'self._cmd_vel_backend = "direct_dynamic_control"' in jackal
    assert "dc.find_articulation_dof(articulation, joint_name)" in jackal
    assert "set_dof_velocity_target" in jackal
    assert "self.apply_wheel_actions(" in jackal
    assert 'if self._cmd_vel_backend == "direct_joint_velocity":' in jackal
    assert "except AttributeError as exc:" in jackal
    assert '"joint_positions" not in str(exc)' in jackal
    assert 'getattr(self, "_wheel_dof_indices")' in jackal
    assert "self.set_joint_velocities(velocities=wheel_values, joint_indices=wheel_indices)" in jackal


def test_multirotor_update_ignores_constructor_phase_callbacks():
    multirotor = (PEGASUS_PACKAGE / "logic/vehicles/multirotor.py").read_text(encoding="utf-8")
    vehicle = (PEGASUS_PACKAGE / "logic/vehicles/vehicle.py").read_text(encoding="utf-8")

    assert 'self._world.add_physics_callback(self._stage_prefix + "/update", self.update)' in vehicle
    assert "self._multirotor_dynamics_ready = False" in multirotor
    assert "self._multirotor_dynamics_ready = True" in multirotor
    assert 'if not getattr(self, "_multirotor_dynamics_ready", False):' in multirotor
    assert 'for name in ("_thrusters", "_drag", "_prim_paths", "_state", "_backends")' in multirotor
    assert "self._thrusters = config.thrust_curve" in multirotor
    assert multirotor.index("self._thrusters = config.thrust_curve") < multirotor.index("super().__init__(")


def test_retro_neighborhood_launch_allows_disabling_px4_autolaunch():
    launch = (LAUNCH_SCRIPTS / "RetroNeighborhood_Launch.py").read_text(encoding="utf-8")

    assert 'UAV_PX4_AUTOLAUNCH = _env_bool("AIRGROUND_UAV_PX4_AUTOLAUNCH", True)' in launch
    assert "px4_autolaunch=UAV_PX4_AUTOLAUNCH" in launch
    assert "UAV_PX4_ENABLE_LOCKSTEP = _env_bool(" in launch
    assert '"AIRGROUND_UAV_PX4_ENABLE_LOCKSTEP"' in launch
    assert 'not _AIRGROUND_SIMULATOR_VERSION.startswith("4.5")' in launch
    assert "enable_lockstep=UAV_PX4_ENABLE_LOCKSTEP" in launch


def test_traversability_raycast_generator_uses_real_physx_scene_query():
    tool = (TOOLS / "generate_traversability_raycast.py").read_text(encoding="utf-8")

    assert "omni.physx.get_physx_scene_query_interface()" in tool
    assert "build_raycast_terrain_grid(" in tool
    assert "RaycastTerrainGridConfig(" in tool
    assert "canonical_traversability_metadata_json" in tool
    assert "traversability_npz_sha256" in tool
    assert "_prepare_benchmark_package_import()" in tool
    assert 'types.ModuleType("airground_benchmark")' in tool
    assert 'Path("/tmp/airground_benchmark")' in tool
    assert "np.savez_compressed" in tool
    assert '"AIRGROUND_ENABLE_SENSOR_GRAPHS": "false"' in tool
    assert '"AIRGROUND_UAV_PX4_AUTOLAUNCH": "false"' in tool
    assert '"AIRGROUND_SCENE_COLLIDER_MODE": "profiled"' in tool
    assert "--ignored-prim-prefix" in tool
    assert "DEFAULT_IGNORED_PRIM_PREFIXES" in tool
    assert '"generator_version": "p1-01a"' not in tool
    assert 'generator_version="p1-01a"' in tool


def test_communication_los_smoke_uses_runtime_bridge_and_real_physx_scene_query():
    tool = (TOOLS / "run_communication_los_smoke.py").read_text(encoding="utf-8")

    assert "omni.physx.get_physx_scene_query_interface()" in tool
    assert "RuntimeCommunicationBridge(" in tool
    assert "make_isaac_physx_raycast_fn(scene_query)" in tool
    assert "DEFAULT_IGNORED_LOS_PRIM_PATHS" in tool
    assert 'Path("/tmp/airground_benchmark")' in tool
    assert "AIRGROUND_UAV_PX4_AUTOLAUNCH" in tool
    assert "AIRGROUND_ENABLE_SENSOR_GRAPHS" in tool
    assert "--blocked-sender" in tool
    assert "--open-sender" in tool
    assert "expected_los_clear=False" in tool
    assert "expected_los_clear=True" in tool


def test_airground_quadcopter_wrapper_has_non_degenerate_physics_mass():
    from pxr import Usd

    wrapper = ROBOTS / "quadcopter_airground.usda"
    text = wrapper.read_text(encoding="utf-8")
    stage = Usd.Stage.Open(str(wrapper))
    assert stage is not None

    assert 'prepend apiSchemas = ["PhysxArticulationAPI"]' in text
    assert text.count('prepend apiSchemas = ["PhysxRigidBodyAPI"]') >= 9
    assert text.count("bool physics:kinematicEnabled = 0") >= 9
    assert text.count("bool physics:rigidBodyEnabled = 1") >= 9
    assert text.count("bool physxRigidBody:disableGravity = 0") >= 9
    assert text.count("int physxRigidBody:lockedPosAxis = 0") >= 9
    assert text.count("int physxRigidBody:lockedRotAxis = 0") >= 9
    assert '"/rotor0",\n        "/rotor2",\n        "/rotor3",\n        "/rotor1"' in text
    assert '"rotor0",\n        "rotor2",\n        "rotor3",\n        "rotor1"' in text
    assert 'over "chassis"' in text
    assert "float physics:mass = 0.72" in text
    assert "point3f physics:centerOfMass = (0, 0, 0)" in text
    assert "vector3f physics:diagonalInertia = (0.0042, 0.0042, 0.0075)" in text
    chassis = stage.GetPrimAtPath("/Quadcopter/chassis")
    assert chassis.GetAttribute("physics:kinematicEnabled").Get() is False
    assert chassis.GetAttribute("physics:rigidBodyEnabled").Get() is True
    assert chassis.GetAttribute("physxRigidBody:disableGravity").Get() is False
    assert chassis.GetAttribute("physxRigidBody:lockedPosAxis").Get() == 0
    assert chassis.GetAttribute("physxRigidBody:lockedRotAxis").Get() == 0
    for prim_name in ("rotor_arm0", "rotor_arm1", "rotor_arm2", "rotor_arm3"):
        assert f'over "{prim_name}"' in text
        assert "float physics:mass = 0.04" in text
    for prim_name in ("rotor0", "rotor1", "rotor2", "rotor3"):
        assert f'over "{prim_name}"' in text
        assert "float physics:mass = 0.03" in text
        collision_attr = stage.GetPrimAtPath(
            f"/Quadcopter/{prim_name}/collisions/_"
        ).GetAttribute("physics:collisionEnabled")
        assert collision_attr.Get() is False


def test_ouster_subgraph_names_are_robot_scoped():
    text = (PEGASUS_API / "spawn_ouster_lidar.py").read_text(encoding="utf-8")

    assert 'lidar_graph_prefix = f"{robot_name}_{lidar_name}"' in text
    assert 'lidar_subgraph_name = f"{lidar_graph_prefix}Graph"' in text
    assert 'playback_tick = f"{lidar_graph_prefix}OnPlaybackTick"' in text


def test_ouster_lidar_deletion_is_isaac_6_compatible():
    text = (PEGASUS_API / "spawn_ouster_lidar.py").read_text(encoding="utf-8")

    assert 'execute("DeletePrim"' not in text
    assert '"DeletePrimsCommand"' in text
    assert "stage.RemovePrim" in text
    assert "Cannot remove ancestral prim" not in text
    assert "sensor_old.SetActive(False)" in text
    assert "_delete_prim_compat(stage, sensor_old_path)" not in text
