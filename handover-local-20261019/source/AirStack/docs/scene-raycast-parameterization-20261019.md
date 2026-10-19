# 显式场景 raycast 输入

`generate_traversability_raycast.py` 新增 `--scene-id` 和 `--scene-usd`。
非 Retro 场景必须显式指定资产；在加载共享 AirGround launch 之前设置
`AIRGROUND_ENV_URL`，输出 metadata 使用同一个 scene_id。默认仍使用
Retro 双机器人模板，未切换到各场景的 legacy PX4 launch。

该提交只完成入口参数化，不表示各场景的双机器人、坐标、支持平面或导航已验收。
用户授权的 Windows 原生诊断另由顶层仓库 `scripts/probe_tiled_terrain.py`
执行；正式容器入口的资源保护没有修改。

验证：顶层仓库 2026-10-19 的场景、ROI、地图比较及 collision geometry
测试 58 项通过，另执行本文件对应脚本的 py_compile。使用主机隔离环境
`/home/raven/.venvs/raven-scene1/bin/python`，Isaac 仿真未在此 CPU 测试中启动。
证据：顶层 `runs/construction_adaptation_20261019/cpu-tests-scene1-env.log`；
唯一任务状态仍在顶层 `IMPLEMENTATION_PLAN.md`，S0/runtime 尚未全部完成。

## ConstructionSite 两块地形的碰撞分类

2026-10-19 的真实 PhysX 射线发现，`ConstructionSite/Land/Landscape2/Landscape2`
在两处视觉表面 z=-0.3 m 的位置产生了 z=1.210654 m 的碰撞顶部，且从
z=0.05 m 发出的障碍带射线在起点即命中。原名称规则没有识别 Landscape，
将其当作静态障碍做 convexDecomposition，填平了开放地形的凹处。

`scene_audit.py` 现在将以下两个精确、相对场景的 mesh 路径识别为 ground：

- `/ConstructionSite/Land/Landscape/Landscape_0`
- `/ConstructionSite/Land/Landscape2/Landscape2`

ground 沿用既有 meshSimplification 与地面接触材质。动态刚体判断仍优先；
不使用宽泛的 land/landscape 字符串匹配，不修改其他场景、原始 USD 或坐标。
这是碰撞配置变化，旧地图不可混用。z=0 无限支持平面仍保留；视觉表面与
支持平面的高度差仍存在，未通过移动机器人或资产掩盖。

真实有界验证：Isaac Sim 4.5 Windows 原生（非容器）、RTX 4060 Laptop
8 GiB / driver 577.02，无 ROS，静态确定性射线无随机 seed。命令及全部参数见
顶层 `runs/construction_adaptation_20261019/ground-v2-evidence/logs/`
`construction-ground-a01/execution.json`。运行退出0，142.69 s，峰值提交
6.129 GiB，仍保留14 GiB/840 s等资源保护。682个碰撞体全部保留，只有两块
地形的碰撞近似改变；两个8×8 m、0.05 m窗口的整块/分块对照通过。
厕所窗口footprint从0变为16,219格，另一空地窗口14字段全部不变。
同位置射线恢复为z=-0.3 m，障碍带错误命中消失。

CPU验证命令：`python -m pytest -q simulation/isaac-sim/tests/test_scene_audit.py`，
3项通过，包括精确匹配边界、动态优先与原Retro完整资产审计。
真实归档SHA-256：`cff78d7ef5123a1a3147a6c8daf93efd7c7b55a4f6c746a0567fd0000a3bf0c0`。
结果只验收上述碰撞修正及窗口对照；新全图、人工GT、S8可见性和巡游仍待验收。
# Confirmation visibility scene selection

`simulation/isaac-sim/tools/validate_confirmation_visibility_raycast.py` now
loads annotations before importing the simulation launcher. Non-Retro annotations
require `--scene-usd`; an inherited `AIRGROUND_ENV_URL` alone cannot silently
select an asset for a new scene. Explicit paths take precedence over that
environment variable. A known scene export filename that contradicts the
annotation scene, a missing file, or a supplied `--scene-sha256` mismatch is
rejected before Isaac starts. Custom filenames remain allowed; their recorded
hash provides provenance, not proof of semantic asset identity.

Example after reviewed regions have actually been prepared:

```bash
./python.sh tools/validate_confirmation_visibility_raycast.py \
  --annotations "$REVIEWED_TARGETS" --scene-usd "$CONSTRUCTION_USD" \
  --scene-sha256 "$EXPECTED_SCENE_SHA256" --output "$RUN_DIR/visibility.json"
```

All camera, distance, visibility, consecutive-frame and ray sampling defaults
are unchanged. The existing validator still produces the same report schema;
`visibility.scene-runtime.json` additionally records scene, annotation, launcher
and report hashes. This sidecar does not approve human GT. The launcher already
accepts `AIRGROUND_ENV_URL`; its support geometry is an infinite PhysX plane at
z=0, so legacy 128 m size fields do not limit map coverage.

CPU validation: four scene-selection checks passed in the local reproduction
WSL environment, including rejection using the real unreviewed ConstructionSite
manifest before the launcher can start. These tests exercise selection/hashing,
not USD loading or actual visibility. New-scene S8 remains pending reviewed
inputs and a guarded real PhysX run. No running diagnostic source snapshot was
changed by this edit.

The runner also checks every declared target prim path in the actual loaded
stage before querying visibility. A CPU reproduction of Pegasus `AddReference`
showed that the downloaded exports have default prim `/World`: referencing them
at `/World/stage` adds an extra `stage` namespace. The current unreviewed bound
paths therefore do not exist unchanged in that referenced composition (Retro
165, ConstructionSite 25, AbandonedFactory 1). The native direct-stage diagnostic
loads preserve those paths and are unaffected. No GT paths were rewritten and
no namespace remapping is claimed approved. A real USD composition regression
now rejects the mismatched reference and accepts the same path in the direct
stage. Merely selecting the right file is insufficient for S8.

For the shared reference loader, `--target-reference-root /World/stage` now
explicitly projects source-default-prim paths into that mount **in memory only**.
It first compares the source and runtime world matrices and world bounds of
every declared target. Missing geometry or a changed world pose is rejected;
the sidecar records each path pair and measured errors. All annotation fields
except the temporary path are preserved, including OBB, regions and verified
state; source files are never rewritten. Native direct-stage loading should
omit this flag.

Seven CPU checks pass, including an actual target transform perturbation that
must be rejected. A separate read-only composition check covers Retro 165,
ConstructionSite 25 and Factory 1 declared paths with unchanged input hashes.
These are USD composition tests, not a real shared-launcher or PhysX run.
