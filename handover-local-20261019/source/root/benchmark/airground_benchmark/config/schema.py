"""Strict configuration schema for the first benchmark release."""

from __future__ import annotations

from airground_benchmark.scenes import SceneCatalogId, validate_scene_catalog, SceneId

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

SCHEMA_VERSION = "1.0.0"


class StrictModel(BaseModel):
    """Base class that rejects undeclared configuration fields."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class TimingConfig(StrictModel):
    physics_hz: int = Field(gt=0)
    ugv_control_hz: int = Field(gt=0)
    sensor_hz: int = Field(gt=0)
    agent_hz: int = Field(gt=0)

    @model_validator(mode="after")
    def validate_rates(self) -> "TimingConfig":
        for name, rate in (
            ("ugv_control_hz", self.ugv_control_hz),
            ("sensor_hz", self.sensor_hz),
            ("agent_hz", self.agent_hz),
        ):
            if self.physics_hz % rate:
                raise ValueError(f"physics_hz must be divisible by {name}")
        if self.sensor_hz % self.agent_hz:
            raise ValueError("sensor_hz must be divisible by agent_hz")
        return self


class RosConfig(StrictModel):
    domain_id: int = Field(ge=0, le=232)
    simulator_distro: Literal["jazzy"]
    robot_distro: Literal["humble"]
    clock_topic: Literal["/clock"]
    use_sim_time: Literal[True]


class RuntimeConfig(StrictModel):
    seed: int = Field(ge=0)
    timing: TimingConfig
    ros: RosConfig


class SceneConfig(StrictModel):
    scene_id: SceneId
    asset_id: str = Field(min_length=1)
    map_frame: Literal["map"]
    meters_per_unit: Literal[1.0]


class CameraConfig(StrictModel):
    width: Literal[480]
    height: Literal[300]
    rgb_dtype: Literal["uint8"]
    depth_dtype: Literal["float32"]


class LidarConfig(StrictModel):
    max_points: Literal[16384]
    point_fields: Literal[4]
    dtype: Literal["float32"]


class SensorsConfig(StrictModel):
    front_rgbd: CameraConfig
    lidar: LidarConfig


class RobotConfig(StrictModel):
    role: Literal["uav", "ugv"]
    asset_id: str = Field(min_length=1)
    namespace: str = Field(pattern=r"^/(uav|ugv)$")
    base_frame: str = Field(pattern=r"^(uav|ugv)/base_link$")
    motion_adapter: Literal["px4_airstack", "nav2_diff_drive"]
    sensors: SensorsConfig


class RobotsConfig(StrictModel):
    uav: RobotConfig
    ugv: RobotConfig

    @model_validator(mode="after")
    def validate_identity(self) -> "RobotsConfig":
        expected = {
            "uav": (self.uav.role, self.uav.namespace, self.uav.base_frame),
            "ugv": (self.ugv.role, self.ugv.namespace, self.ugv.base_frame),
        }
        for name, identity in expected.items():
            if identity != (name, f"/{name}", f"{name}/base_link"):
                raise ValueError(f"{name} identity does not match the stable API contract")
        return self


class ApiConfig(StrictModel):
    possible_agents: tuple[Literal["uav"], Literal["ugv"]]
    path_max_poses: Literal[64]
    inbox_max_messages: Literal[8]
    payload_max_bytes: Literal[65536]
    lidar_max_points: Literal[16384]


class ChannelConfig(StrictModel):
    model: Literal["distance_los_seeded_v1"]
    max_range_m: Literal[150.0]
    mtu_bytes: Literal[1200]
    base_bandwidth_bps: Literal[2000000]
    base_latency_ms: Literal[30.0]
    nlos_bandwidth_multiplier: Literal[0.25]
    nlos_latency_penalty_ms: Literal[150.0]


class EpisodeCatalogConfig(StrictModel):
    catalog_id: SceneCatalogId
    scene_id: SceneId
    public: Literal[True]
    zero_shot: Literal[True]
    total: Literal[60]
    single_target: Literal[30]
    unordered_multi_target: Literal[15]
    sequential_target: Literal[15]

    @model_validator(mode="after")
    def validate_counts(self) -> "EpisodeCatalogConfig":
        validate_scene_catalog(self.scene_id, self.catalog_id)
        subtotal = (
            self.single_target
            + self.unordered_multi_target
            + self.sequential_target
        )
        if subtotal != self.total:
            raise ValueError("episode task counts must sum to total")
        return self


class BenchmarkConfig(StrictModel):
    schema_version: Literal[SCHEMA_VERSION]
    runtime: RuntimeConfig
    scene: SceneConfig
    robots: RobotsConfig
    api: ApiConfig
    channel: ChannelConfig
    episodes: EpisodeCatalogConfig

