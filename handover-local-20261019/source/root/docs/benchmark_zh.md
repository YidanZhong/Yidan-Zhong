> 用户暂停（2026-10-19 16:46）：持续目标已paused；两个后台队列均Ready，相关诊断进程为0。新Construction地图保存52/70块、3302912格；后续四项GPU诊断未启动。保留STOP断点，等待用户明确恢复。

> 本机 handover 当前状态（2026-10-19）：后续场景正式验收仍为0。ConstructionSite旧70块图/S7候选因5075实例漏碰撞已标记INVALIDATED；精确几何原型补全的真实PhysX预检已通过（380.03s、峰值8.207GiB），51,200格扩大验证也已通过（265.62s、14字段差异0），新契约a01/a02正常退出0，16:38核查已44/70块，有限队列继续；首20块120文件已回传核验。显式运行时碰撞manifest接口c01d33b1通过20项CPU检查及实际USD双挂载对照，新接口真实PhysX尚待独立测试；四项有限诊断队列已实际启动等待当前地图释放GPU，尚未执行新诊断。ConstructionSite另有12张真实RGB部分审核材料，第13视角失败且部分图有遮挡，人工批准仍0。FireAcademy三角碰撞/双面查询已通过49,152格扩大验证（14字段差异0，152.70s退出0）；Factory单个合并地面修正待实测。Retro三轮导航严格位姿7/9，尚未通过稳定性。原资产、人工审核位及验收阈值均保留。小窗口reach派生已纠正并用五个真实窗口重算，原全图后处理正确；旧归档保留。当前状态只维护于IMPLEMENTATION_PLAN.md，详细结果见docs/development/ugv-ogn内construction-instance-colliders、fireacademy-collision、factory-collision、nav2-dwb-stability证据文件；历史完整图记录不代表当前可验收。

# RAVEN-AirGround Benchmark 中文指南

> 自主交接推进（2026-10-19）：正在执行 Scene1-Nav2-ArrivalStability 的轮控接口 A/B 物理诊断，区分直接关节速度状态写入与驱动目标；尚未认定转向根因或替换正式默认配置。人工 GT 审核与外部资产问题记录后继续独立工作，正式验收门保持。

> 全图 Nav2 局部路线验证（2026-10-19）：完整 32,235,504 格/0.05 m 地图跨端逐格匹配；a02 连续三个 action 成功，路径 21.717 m、最终误差 0.249 m、最小保守水平障碍净空 0.713 m，1,081 帧点云哈希和 4,100 组里程计匹配，七张原始截图已检查。退出 0、362.42 s、Isaac 作业峰值提交 10.804 GiB，临时运行资源已清理。a01 第二目标 120 s 超时，仅 2/3；a02 预算为 180 s，但该段实际 93 s，不能认定延长时限解决了问题。末端收敛波动、支持平面与视觉路面高差及偶发规划频率不足仍待处理。只证明全图接入与一条局部路线，不代表 31 目标实跑、人工 GT 或正式论文 episode。见[本轮证据](development/ugv-ogn/full-map-nav2-20261019.json)。

> 本机全图后处理完成（2026-10-19）：527 块/32,235,504 格/0.05 m 已拼接，全图导数、块缝及两个真实 PhysX 小窗口内部对照通过。显式 5 cm 台阶、16 朝向车体检查后，生成 0.1075 m 净空和 63 个 reach 连通区域；选定 C0 覆盖 31/31 论文目标的几何候选到达区，所有目标仍未审核且不可正式计分。未审核 Nav2 图导出并逐格核验方向，退出 0、133.05 s、峰值提交内存 2.960 GiB，运行任务已清理。下一步为全图 Nav2 真实验证；人工 GT、到达集及正式 episode 仍未验收。见[全图后处理证据](development/ugv-ogn/full-map-postprocess-20261019.json)。

> 本机分块验证（2026-10-18）：两个 8×8 m 区域 / 0.05 m 分辨率 / 51,200 个参考网格，真实 PhysX 射线 314,976 次；整块与带一圈 halo 的分块地形、全窗口 seed/footprint/reach 连通结果超差值 0，块缝超差值 0。红车整车根绑定已写入独立未审核副本，原标注框不变；所有目标仍未获人工批准。真实运行退出 0，峰值提交内存 8.840 GiB，资源保护与 64 GiB 正式入口门禁未放宽。小范围结果不能替代全图、老师地图对比或正式 episode；下一步仍需全图诊断生成和审核。见[分块地图验证证据](development/ugv-ogn/tiled-map-validation-20261018.json)。

> 全部论文目标审核材料（2026-10-18）：已用原生 Isaac 4.5 渲染 31 实例 / 8 类 / 62 张双视角原始 RGB，生成标注框、实际候选包围盒、XY 位置和空白审核台账；31 组候选包围盒与静态导出一致，图像完整性与哈希核对通过。24 个绑定有歧义，红车 Object_9 零件误绑和黄车范围差异已重点标注，修正方案尚未应用；人工审核仍为 0/31。运行退出 0，峰值提交内存 10.401 GiB / 显存约 3.37 GiB，临时资源已清理。正式 0.05 m 全图 ROI 为 32,235,504 格；既有入口的 64 GiB 可用内存门与本机 32 GB 不兼容，门禁未放宽，分块生成仍待实测。正式地图、到达集与论文 episode 尚未生成。见[目标审核包证据](development/ugv-ogn/paper31-review-20261018.json)。

> 公交站目标接入进展（2026-10-18）：单个未审公交站实例已由真实 Nav2 驶近并停车，路径 8.859 m、最终误差 0.198 m；停车后的目标朝向诊断相机（1.2 m / HFOV 90°）取得五个不同渲染帧，每帧五条 PhysX 射线均无遮挡，OBB 表面距离 3.683 m。11 张原始 RGB 已检查，560 帧点云及 2,123 组里程计跨端核对通过，退出 0，临时资源已清理。尚未执行语义检测或验证机载相机控制，目标保持 verified=false / ground_reachable=unknown，正式 catalog 10/10 blocked、论文 episode=0；已保存 31 个论文实例审核队列与台账草稿。0.1 m 局部图最小保守外接圆净空 0.077 m，仍需正式 0.05 m 地图复核；转向效率和支持平面与视觉路面高度差也尚未解决。该结果只对应目标接入及审核辅助，不能关闭全场景 handover 验收。见[公交站目标接入证据](development/ugv-ogn/target-integration-20261018.json)。

> 连续三目标与静态绕障进展（2026-10-18）：同一段真实仿真中完成三个 Nav2 目标，均 SUCCEEDED（4），包含转弯、绕开树木碰撞投影和返回起点，目标间无重置/传送。路径 22.062 m，最终误差 0.242 m，停车速度 0.00230 m/s；实际轨迹扣除车体外接圆后的最小静态净空 0.384 m，中心未进入已测障碍或未知区。1,051 帧接收点云哈希和 3,986 组里程计全部匹配源记录，保存 187 条规划及七张已检查的原始截图。恢复仓库默认角加速度解决首次停驻转向死锁，失败证据保留；其他速度、轮扭矩和资源保护未放宽。成功运行退出 0，峰值提交内存 10.934 GiB / 显存约 3.35 GiB，临时资源已清理。此项仅验收一条静态路线，第二段路径效率仍待优化；使用 PhysX 里程计、CPU 点云、未审局部地图和支持平面，定位、RTX 雷达、动态障碍、语义任务和正式论文 episode 尚未验收。见[三目标绕障证据](development/ugv-ogn/nav2-route-20261018.json)。以下为此前阶段记录。

> 单目标 Nav2 进展（2026-10-18）：真实 Retro 场景中 NavigateToPose 返回 SUCCEEDED（4）；到达阶段 13.825 s 仿真，实际位移 2.257 m，最终误差 0.244 m，停车速度 0.00125 m/s。使用实际 PhysX 生成的 20×20 m 局部地图和 CPU 障碍点云，WSL 收到的 116 帧点云哈希、438 组里程计全部与源记录一致；两级代价地图及 14 条规划路径有证据，三张原始截图已检查。正常退出 0，峰值提交内存 11.020 GiB / 显存约 3.56 GiB，临时运行资源已清理。该结果仅验收一次短距离导航；定位、RTX 雷达、复杂绕障、多目标、语义搜索和正式论文 episode 仍未验收，不能等同于场景一完整复现。见[单目标导航证据](development/ugv-ogn/nav2-local-goal-20261018.json)。

> Jackal 运动进展（2026-10-18）：真实 Retro 场景中的四轮关节驱动通过：前进 0.976 m、转向 49.3°、停止和断流停车成功；WSL 收到 357 组里程计/TF，逐条与 PhysX 位姿一致，单时钟无倒退。保存四张 960×600 原始图像，程序退出 0，峰值提交内存 10.715 GiB、显存约 3.40 GiB。120 Hz 诊断使用仓库支持平面；里程计是仿真状态、map→odom 为诊断恒等变换，未验收定位、障碍点云、Nav2 或正式 episode。见[真实运动证据](development/ugv-ogn/jackal-motion-20261018.json)。

> ROS 通信进展（2026-10-18）：Windows Isaac 4.5 ↔ WSL Humble 在独立 domain 42 实测通过：488 条仿真时钟无倒退、160 张 480×300 RGB 与发送端像素哈希全部一致、162 条 CameraInfo、166 条反向速度消息及运行标识回执；退出 0，内存与显存保护保留。仅验证消息链路，未驱动车轮、未验收 TF/里程计、Nav2 或 episode。临时进程、任务和两条测试防火墙规则均已清理。见[ROS 双向通信证据](development/ugv-ogn/ros-bridge-20261018.json)。

> 第二台电脑进展（2026-10-18）：Windows 原生 Isaac 4.5、Humble 和 Nav2 已安装，Linux ROS 实际收发通过。真实 Retro 场景加载、PhysX 抽样及 **RTX 相机双视角出图已通过**：27,986 个 prim，两张 960×600 原始 RGB，经图像检查、稳定等待及人工查看；最新运行退出码 0，耗时 51.31 s，峰值进程提交内存约 10.424 GiB。经用户同意新增 D 盘 16–24 GiB 分页文件（16 GiB 已即时启用），独立诊断上限 14 GiB，保留主机与显存保护；正式 benchmark 资源门未改。当前采用普通相机诊断配置并关闭 Motion BVH，不能替代完整机器人/RTX 雷达验收。原始道路抽样未添加正式 runtime 的 z=0 支持平面，不能当作 GT；跨系统 ROS 已由后续专项验证，导航与正式 episode 尚未验收。见[最新 RTX 证据](development/ugv-ogn/rtx-first-frame-20261018.json)；早期失败过程见[运行记录](development/ugv-ogn/second-pc-runtime-20261018.json)。

> 本机复现准备（2026-10-17）：本次用户已明确授权本机运行，任务记录在 `IMPLEMENTATION_PLAN.md` 的 `Local-Scene1-Reproduction`。该授权仅改变本次运行位置；4.5.0/Humble 版本、资源保护和真实闭环验收口径不变。离线工具或资产检查通过不代表仿真复现成功。

10 月 17 日准备结果：场景修复后的 SHA 与已记录版本一致、26 个 manifest 资产及 66 项离线测试通过；当时主机硬件兼容与内存限制、已审核实验输入缺失阻塞真实仿真。10 月 18 日第二台电脑已通过物理子检查，当前状态以上方最新记录为准。详见[本机准备证据](development/ugv-ogn/local-scene1-preparation-20261017.json)。

> 资源补充（2026-10-18）：五个独立场景 USD 和 SnowyVillage 根层已下载到 `../.raven-setup-cache/scene-resources-20261018/`，记录字节数与 SHA-256；另缓存公开材质/天空依赖。原有场景目录未覆盖。Nucleus 私有依赖读取返回 `ERROR_ACCESS_DENIED`，尚未形成可运行完整包。详见[资源补充证据](development/ugv-ogn/scene-resource-recovery-20261018.json)。

## 九场景 handover 本机进展（2026-10-17）

`Scene-GT-Handover` 当前只完成 CPU 准备。九场景共 164 条标注已转换，每场景 10 条论文任务及待审台账已生成；所有实例仍未核验、可达性未知，九份 catalog 均为 10/10 blocked。原场景一的任务编号、可达口径和 31 目标门保留。

官方 ZIP 已完整下载；新解压 FireAcademy、ConstructionSite、AbandonedFactory 共 908 文件。ConstructionSite 暂绑 25/28（25 歧义），AbandonedFactory 暂绑 1/11（1 歧义），FireAcademy 因主体合并网格无名称候选。截至 2026-10-17 其余六场景未取得 USD；2026-10-18 已通过官方历史目录和公开 Nucleus 取得六份根层，完整外部依赖仍未补齐；AbandonedFactory 另缺 `SubUSDs/materials/Ground.mdl`。CPU 支持不表示真实仿真已完成。

在含 `usd-core` 的隔离环境中，从仓库根目录运行：

```bash
python scripts/prepare_scene_gt.py --output-dir runs/scene_gt_adaptation_20261017
# 可附加 --scene ConstructionSite 单独重跑；输出是未审阅准备产物。
```

产物包括 `targets.converted.json`、`targets.unreviewed.json`、`prim_candidates.json`（有可读 USD 时）、`binding.report.json`（有候选时）、`review.queue.json`、`review.ledger.template.json`、`task_catalog.blocked.json` 和 `raycast.request.json`。最后一项只是未来真实 raycast 参数；不是地图。ledger 模板不能直接作为人审完成证据。

任务勾选与后续 S0–S10 步骤只维护在 [实施计划](../IMPLEMENTATION_PLAN.md)。本机 RTX 5060/Isaac 4.5 渲染不兼容，WSL 内存也不满足现行保护门；未启动仿真、未生成真实地图/30 集/巡游成绩。相关回归 155 项通过（130 项核心/场景测试 + 25 项 CLI），FireAcademy 实际 CLI 转换和 catalog 构建通过；完整 release CLI 套件未作为验收执行完。资产 SHA 和逐场景状态见 [本次证据](development/ugv-ogn/scene-gt-adaptation-20261017.json)。

**历史场景一状态（2026-10-05；并非本机本次复现成绩）**

- **UGV 侧已闭环**：31 个论文目标全部到达（真实 Isaac/ROS，双来源审计 K=31/31、`exit 0`、metrics ok）；10 任务 catalog 重算 10/10 `ok`。索引：[实施计划](../IMPLEMENTATION_PLAN.md)、[Nav2 与巡游证据](development/ugv-ogn/nav2-60s-cold-warm-20260930.md)。
- **GT-AABB ROI 搬运审核（Phase B/C）已取消**：31 个实例全部联通可达，无需搬运目标或重导场景；现行导航/评分地图是 0.05 m 全图候选包（见下节）。
- **当前主力阻塞是算法侧语义检测**：detection lane（UAV 自主搜索 → 检测 → UGV）的语义分数真/假不可分、搜索覆盖不足（最好 K=1/M=2）；`UGV-OGN-CalibrationGate` 未过，RayFronts/VLFM 正式 public/hidden 成绩仍为"未测得"。
- **性能现状（2026-10-05 更新）**：性能基线（Fabric 状态 + native 桥/机体数学 + GPU 点云 + 相机对齐渲染门）已接入 benchmark 车道，
  **检测车道（相机 + mapper + Nav2 全栈）任务窗 RTF 实测 0.63–0.78**（此前 ~0.1）。逐项证据见
  [benchmark 车道 RTF 实测](development/ugv-ogn/nav2-benchmark-lane-rtf-baseline-20261005.md) 与
  [一分钟性能与巡游证据](development/ugv-ogn/nav2-60s-cold-warm-20260930.md)。
- **当前评测协议（2026-10-05）**：单场景评测与上游论文（RAVEN, arXiv 2509.23563）一致——**10 个 Table A.3
  任务 × 3 个起始位姿 = 30 集**（`runs/p1_09_episode/paper_protocol_20261005/paper30_episodes.draft.json`，
  GT 为 2026-09-30 重标定包）。仓库原有的 **60 集（30/15/15）** 契约是发布用（release pair / release audit）的
  历史设计，**不是当前评测输入**；下文中所有 `public60`/`hidden60` 均属该发布/历史语境。

> 版本规范（2026-09-30）：当前运行环境为 Isaac Sim **4.5.0 / ROS 2 Humble/Jammy**；运行位置遵循根 AGENTS.md（LFT-W02）。本文中所有 **6.0.1 / Jazzy** 的命令、版本下限、报告和证据均为**历史归档**，不作为当前运行指令；历史版本号与 checksum 保留原值。

本文档面向 benchmark 使用者和开发者，固定首版 UAV+UGV 协同语义搜索与地面确认任务的复现实验口径。当前仓库同时维护顶层 Python contract/schema 工具和真实 Isaac Sim 4.5.0 + ROS 2 Humble smoke 入口；真实双机器人闭环仍按 `IMPLEMENTATION_PLAN.md` 分阶段补齐证据。

## GT-AABB 全图与 0.05 m 候选地图（2026-09-30；Phase B/C 已取消）

**现状与结论**：这一流程最初用于"生成逐目标搬运候选并人审、再派生新场景"，目的是让不可达目标进入评分面。2026-10-05 用户决定**取消 Phase B/C**：全部 31 个论文实例联通可达（catalog 10/10 ok、31 目标导航验收 K=31/31），无需搬运。现行导航与评分地图即下面的 0.05 m 全图候选包；搬运候选规则、箭头图与 before/after 流程、`apply_scene_patch` 仅作历史工具保留，不进入评分流程。

**已完成**

- Phase A 全图分析：全部标注 OBB 的世界 AABB + 2 m 自动生成 0.10 m 决策图 → 真实 Isaac/PhysX band raycast → footprint sweep（Jackal 0.508×0.430 m、16 yaw、step 0.05 m）→ package/validate，报告 JSON/CSV/PNG 落 `component_report/`。联通判据为原始几何 **0.645 m 走廊**（1.5 × UGV 宽 0.430 m）+ 额外净空 0.1075 m / 8 连通；0.05 m 对应轴向 3 格（0.15 m）、0.10 m 对应 2 格（0.20 m），实现保留现有欧氏距离阈值。目标归属 `A(T) ∩ C ≠ ∅`（表面式到达集 ∩ 联通块），取目标数最多的块（面积与块号仅作平局判据）。**粗图偏保守，不能用作评分 GT。**
- 几何归属语义：`in_selected_component` 表示到达集交集，`eligible_in_selected_component` 另要求可靠 prim 绑定。未绑定对象仍参与几何分析并进入人审清单，但不得把绑定问题写成地形不可达；当前 31/31 几何归属、30 个可靠绑定。
- 单卡 CUDA/Warp raycast（默认入口 `--backend warp --gpu 0`，生成阶段 CPU scene query=0；几何导出与后处理仍在 CPU，PhysX `raycast_all` 保留作参考）：cooked triangle/shape 从 live PhysX RepX 导出；0.05 m 全图 32,235,504 格查询/回传 0.475 s、端到端 319.5 s（exit 0）。与同一 live PhysX 场景的 footprint 对照通过：0.10 m 全图无误放开导航格、44 块/31 目标归属一致；0.05 m 公交站 32 万格完全一致，房屋区域 48.84 万格仅 17 个边界采样差异且经物理 footprint 复核可接受。
- 0.05 m 候选导航包：`runs/p1_03_traversability/p1_03_single_gpu_0p05_full_20260930_r2_native/package/retro_gt_aabb_0p05_candidate.nav2.yaml`（附 PGM、全幅标注图与 31 行目标报告），validate ok；64 个 reach 块、C0 面积 68,866.6 m²。
- 2026-09-30 服务器实测（0.10 m 包）：validate ok、网格 `(2069,3897)`、C0 面积 69,722.22 m²、31/31 几何归属、30 个可靠绑定（当时仅 `red_car.0000` 缺可靠 prim，后由 `recover-red-car` 恢复）；已绑定块外目标 0 个。`_r2` 曾误关运行期 z=0 支撑平面，已恢复并重导 `_r3_plane_on`（旧主块 98.94% 格子仍在 C0，公交站抽样点与三个旧起点均恢复 C0）；分析入口要求真实日志证明支撑平面 collider 已建立。
- 红车绑定恢复（`recover-red-car`）：保留 `red car` 类别与实例 ID，依据唯一车辆（`Vehicles/Nissan_Fairlady_Z_S30240Z_1978`，中心误差 0.495 m）与红色材质恢复绑定，撤销旧排除并重生成到达集。来源与图证见 [红车绑定证据](development/ugv-ogn/red-car-binding-recovery.md)。
- 行驶门关闭：31 目标巡游直接运行在该 0.05 m 候选地图上并 31/31 到达（2026-10-05，[巡游证据](development/ugv-ogn/nav2-60s-cold-warm-20260930.md)）。

**工具入口**

- `scripts/run_non_global_env.sh --mode roi-analysis -- --phase prepare|raycast|analyze|propose|render-target --targets <reanchored.json> --output-dir runs/p1_03_traversability/<dated-dir>`（`propose` 另需 `--starts`；`raycast` 需授权 Docker 写入与显式 GPU；`render-target` 只在内存 session layer 加检查相机与补光，保存目标两侧真实 RGB PNG 与 `render_execution.json`，不改场景）。
- `--mode roi-tools -- tour prepare|run|audit`：31 实例诊断巡游（prepare 校验同一起点与各 OBB 表面 1.5–8 m 到达集有同块交集；run 只注入检测点，由 UGV 侧路由与到达判定执行；audit 用 `compute_ugv_progress` 复核实际轨迹，重叠区域独立保存）。`tour prepare --budget-s 60` 生成一分钟诊断；`tour clock-rate --wall-seconds` 只订阅公开 /clock 采样 RTF，不改仿真状态。
- 诊断开关：`AIRGROUND_STACK_WATCHDOG_S`（冷启动无 /clock 时输出 Python 阻塞栈）、`AIRGROUND_CPU_THREAD_LIMIT`（Kit 创建前限制 tasking/TBB 线程池，参与容器复用签名）、`AIRGROUND_UGV_CLOUD_BACKEND=cpu|gpu`（UGV 3D 点云；4.5 仍拒绝 RTX 点云 writer）。
- `--mode roi-tools -- report|moves|patch|cli`：服务器 CPU 工具入口；`scene-inspect`（不按名称筛选、检查附近全部几何/材质）与 `patch`（`--source/--prim/--evidence` 捕获实际世界矩阵；应用阶段需 source SHA-256 + 逐对象批准）保留。
- 新旧地图对照：`roi-tools -- report --compare-reach-metadata/--compare-reach-npz` 输出同世界坐标对照 PNG 与旧块→新块重叠统计；块号只在各自地图内有效。

**过程记录**：2026-09-30 的候选生成与人审材料（`component_report/`、`movement_review/`、箭头图与逐候选 before/after 图）保留为 Phase B/C 取消前的历史记录；`apply_scene_patch`（源 SHA-256 + 逐对象批准 + 真实 prim world matrix，保留原资产与父变换，派生 USD 落 `runs/scene/`）不再计划使用。原候选规则（footprint ≥0.5 m 净空、与其它目标到达集 ≥1.5 m、避开 UGV/paired 起点、10 m PCA 道路朝向；旧位恢复只作二维代理）与原 Phase C 流程（派生 USD → 0.10 m 全图复算归属/阻断 → 联合 AABB + 5 m、0.05 m snap → 权威 raycast/sweep/package → 重算稠密 arrival、catalog、paired starts、visibility → `episodes audit-gt` = 0 → 同步 checksum 与 smoke 包引用）保留为历史记录，不再执行。更多细节见 [单卡执行与对照](development/ugv-ogn/ugv-ogn-single-gpu-raycast.md)、[人审材料](development/ugv-ogn/ugv-ogn-gt-aabb-roi-human-review.md)。


## 历史成绩口径（2026-08-06，已被头部现状取代）

> 本节记录当时 legacy RayFronts/VLFM 车道的状态与失败切片，保留作历史；当前状态与评测协议见文首。

| 项目 | 当前状态 | 公开/论文/leaderboard 是否可引用 |
| --- | --- | --- |
| Quadcopter、Jackal、dock、RetroNeighborhood、traversability GT、confirmation region、public/hidden split、指标工具 | 已有真实 Isaac/ROS 或真实 artifact 验收 | 可作为 benchmark 环境与评测框架基础 |
| RayFronts/VLFM dependency、semantic encoder、mapper-derived hypothesis、selected behavior、communication linkage | 已完成 smoke / preflight / artifact gate | 只能引用为依赖链和接口面证据 |
| P2-11s/P2-11t public/hidden60 RayFronts/VLFM 结果 | 已重分类为 metrics surface smoke；确认耗时毫秒级、UGV 路径近零 | 不可作为 Mission Success、TTC、D2C、路径、能耗、安全或通信成本成绩 |
| RayFronts/VLFM full-mission benchmark | reviewed-public 单集 integration proof 已通过；latest public2 reset/odom 复验证明第 2 集 UGV 起点 odom 已正确刷新且 UGV 路径非平凡。历史 long-route Nav2 timeout 已定位为 wall-clock 评分错误，runner 已改为 `/clock` deadline 但尚无真实复验；PX4 telemetry/EKF evidence 也仍缺失，hidden60 尚未重跑 | 当前正式成绩仍是“未测得” |

**结论**：现在还没有一个可以对外报告的 RayFronts/VLFM 搜索算法 benchmark 分数。当前 `--rayfronts-full-mission-runner` 是防伪确认和真实 runner 接入入口；communication path 已强制使用 Isaac PhysX LOS evidence，confirmation 和 UAV control 也已有 evidence gate。这些 gate 只能说明不合格 artifact 会被拒绝，不能替代 public/hidden full-mission 重跑。真实 UGV sensor-frame publisher 已完成 live Isaac/ROS topic smoke：`/ugv/confirmation_visibility_sensor_frames` published/received/decoded 1660/1660/1660 records，sensor-trace validation `status=ok`。RayFronts UAV action 也已接入真实 PX4 OFFBOARD adapter，真实 evidence run `runs/p0_rayfronts_full_mission/p0_uav_control_adapter_20260805_184533/` 记录 `path_m=9.674077180701294`、`command_count=1497` 且 strict UAV-control evidence gate 通过。reviewed public 单集 full-mission proof `runs/p0_rayfronts_full_mission/p0_public_single_full_mission_min_uav_waypoint_live_20260806_091649/` 已能完成 VLFM mapper hypothesis、真实 PX4 OFFBOARD UAV 搜索、Isaac PhysX communication LOS、UGV Nav2 到 confirmation region、sensor-derived ground confirmation，并通过 physical mission gate。随后 reviewed-public60 首轮重跑 `runs/p0_rayfronts_full_mission/p0_public60_full_mission_20260806_093106/` 在第 1 集失败：UGV Nav2 已到达 reviewed confirmation region，UGV path `16.211822539604825m`，confirmation sensor frames 5/5，physical sanity failures 为空；失败点是 strict UAV-control evidence 未满足 `search_motion_ok=true`，PX4 OFFBOARD waypoint 30.003s 后 endpoint error `1.7803m` 超过 `0.75m` acceptance。后续修复加入 90s waypoint timeout、episode-level Isaac world reset、Pegasus PX4 backend/PX4LaunchTool reset、UAV actuator 清零、body-local attitude compensation refresh、direct UAV chassis pose reset 和 UGV reset/odom stale-start gate。latest public2 reset/odom run `runs/p0_rayfronts_full_mission/p0_public2_full_mission_reset_odom_v2_20260806_121109/` 第 1 集通过（TTC `43.888002739s`、D2C `11.904002739s`、UAV path `2.357986182597032m`、UGV path `15.798058160870157m`、collision count 0）；第 2 集 UGV reset odom 已正确刷新（distance `0.0035479399682303704m` from requested start），Nav2 从当前 episode 起点发车并产生 UGV path `24.81662679848338m`、5990 条 Nav2 cmd_vel，但仍失败：PX4 报 `Preflight Fail: ekf2 missing data` 导致 strict UAV-control evidence 缺失，porch confirmation goal `[-40.625,-31.625]` 长路线 `NavigateToPose result timed out`。只有 public60/hidden60 用 `--require-rayfronts-physical-mission` 重跑通过后，才允许报告正式结果；host-only unit test、离线 JSONL、预生成 confirmation evidence、单集 proof、失败 public60 artifact 或失败 public2 artifact 都不等于 benchmark aggregate。异常短耗时的原因和正式 artifact 条件见 `docs/development/archive/isaac6/rayfronts/rayfronts-full-mission-gap-analysis.md`。

**时钟口径——**Nav2 mission deadline 只按仿真 `/clock` 累计，不能将慢速但持续推进的 Isaac 误判为 timeout。每个已接受 goal 的 `nav2_evidence` 都会记录 `elapsed_sim_s`、`elapsed_wall_s` 和 `timeout_source`；`/clock` 完全停滞会作为基础设施诊断并 best-effort cancel goal，不会写成 mission timeout。该行为当前只有 host-side regression，仍须受保护真实 Isaac/Nav2 长路线复验。

**场景容量诊断（可选）**：`AIRGROUND_SCENE_COLLIDER_MODE=proxy` 保留完整 RetroNeighborhood 可见几何、RGB-D 和 ground collider，从 live stage overlay 移除逐 mesh static-obstacle `CollisionAPI`，并按确定性资产组生成保守 AABB PhysX proxy。默认仍是 `profiled`；最近一次 `profiled` 受保护单集 retry 使用默认的 12 GiB available-RAM、80% host-RAM/VRAM 和 48 GiB cgroup，已经越过正值 `/clock` 并启动 mapper/Nav2，资源 guard 未触发，最终阻断是 PX4 reset 后 `ekf2 missing data`，尚未产出 benchmark evidence。proxy 仍未通过真实受保护路线、PhysX LOS 和 confirmation 等价性复验，不能作为 public/hidden benchmark 成绩或替代正式物理配置。

**PX4 估计器健康门（仿真标定）**：`run_rayfronts_full_mission.py` 与 `run_uav_offboard_smoke.py` 默认注入 `EKF2_GYR_B_LIM=0.5`、`EKF2_ABL_LIM=1.5`、`EKF2_ABL_ACCLIM=20`、`EKF2_ABL_GYRLIM=2`（显式 `--uav-control-px4-param`／`--px4-param` 仍可覆盖）。原因是本 simulator 的速率/加速度通道带有求解器级内容（飞行中 15.2 Hz 俯仰极限环 std≈1.3 rad/s、加速度计偏置 0.5–0.8 m/s²），PX4 stock 上限（0.15 rad/s / 0.4 m/s²）会让 estimator health check 在飞行中误报 `High Gyro Bias`／`High Accelerometer Bias` 并触发 failsafe。该配置只调整仿真标定值：门仍有限（0.375 rad/s / 1.125 m/s²），2026-09-14 两轮真实 run 全程无健康失败；UAV-control evidence 仍必须由真实 PX4 OFFBOARD 飞行产生，不能用该配置替代任何 benchmark gate。

**物理可信下限**：耗时过短不是好结果，而是物理可信性失败信号。默认 full-mission gate 要求 TTC `>= 5.0s`、D2C `>= 1.0s`、UAV 3D path `>= 1.0m`、UGV planar path `>= 1.0m`；低于该下限的 episode 即使写出了 detection / communication / confirmation 字段，也只能归类为 smoke 或诊断产物。时间/路径达标后仍必须同时具备 PX4/AirStack UAV-control evidence、Isaac PhysX LOS communication evidence、UGV Nav2 goal-reached evidence、confirmation-region membership、sensor visibility、continuous visibility 和 occlusion-clear confirmation evidence，才能写入 Mission Success。

**结果解释硬规则**

- `collect_runtime_metrics_smoke.py` 生成的 60/60 linked confirmation 只能算 metrics smoke；若 confirmation 在毫秒级、UAV/UGV path 近零，即使旧 gate 通过，也必须视为无效 benchmark 成绩。
- `airground run --rayfronts-full-mission-runner` 是当前唯一允许推进 RayFronts/VLFM full-mission 成绩的 runner；它必须同时经过真实 Isaac/ROS/PX4/Nav2/RayFronts 执行面和 `--require-rayfronts-physical-mission` 复算。
- Mission Success 必须由 UGV ground confirmation 关闭；UAV detection、RayFronts hypothesis、手工 confirmation JSON、离线 sensor trace 或 host-only unit test 都不能单独产生任务成功。
- public/hidden 正式结果必须包含非平凡 UAV 搜索路径、非平凡 UGV Nav2 路径、sensor-derived confirmation、通信成本、能耗和安全指标；缺任一项时只能写“未测得”或“未通过 gate”。

## 1. 快速开始

推荐使用仓库根目录下的本地虚拟环境，避免用户级 ROS/Python 包污染测试结果。

```bash
cd /home/jun/RAVEN-AirGround
./scripts/deploy_non_global_env.sh
./scripts/run_non_global_env.sh --mode doctor
./scripts/run_non_global_env.sh --mode offline-tests
```

隔离脚本只使用仓库内 conda prefix，并在执行 `airground` / pytest 时清空 `PYTHONPATH`、设置 `PYTHONNOUSERSITE=1`。ROS、PX4、Nav2、Isaac、RayFronts/LVLM runtime 依赖必须留在 Docker 镜像内；`.[test]` 已固定 ROS Jazzy `launch_testing` 需要的 `lark`，但正式 contract 回归仍使用隔离路径，避免宿主 `/opt/ros`、用户级 site-packages 或系统插件影响结果。

UGV reach 判定口径（2026-09-17 明确，仅补文档、不改任何指标数值）：只看 UGV **平面位置**与 reviewed confirmation pose 的 2D 距离 ≤0.5 m，**不计 yaw**；reach window 主口径 `[1.5, 8.0] m` 指 reviewed pose 到目标实例的距离带；`M` 与 reach 共用同一 reviewed pose 集合。UGV 目标解析在 runner 侧只用公开数据（mapper detection payload + live costmap，优先 `/ugv/global_costmap/costmap_raw`，只有发布态 0-100 时按 `100=lethal` 归一）：anchor = 检测点 3 m 内 lethal 栅格质心，派发点 = 从 UGV 当前 cell 出发在可通行栅格上 8 连通 BFS 后离 anchor 最近且距 UGV ≥0.5 m 的合法 cell，朝向指向 anchor；超过 `--ugv-goal-adjust-max-m`（默认 3.0 m）则记 `no_reachable_goal_within_cap` 且不派发。reviewed 位姿只在 evaluator 侧用于判 `K`，runner 不读。任意 run 的离线复算：

UGV reach 判定口径（2026-09-24 重标定，取代上一条的"位姿点"口径）：`M` 与 `K` 共用**表面式稠密抵达集合** `A(T)` = 到实例 OBB **表面**距离 ∈ `[1.5, 8.0] m` 的全部可通行格（取消 32 角/128 点采样上限；旧口径下 17/22 个区域被截断到 ≤3.53 m，并会让起点在 t=0 假计 K），`K` = UGV 平面位置到 `A(T)` 的栅格距离 ≤ `--reach-tolerance-m`（默认 0.5 m），`yaw` 仍不参与。目标可达 = `A(T)` 与可达区域交集非空，**不要求目标自身或 OBB 在可达块内**；可达区域 = 当前障碍图上距非通行格 ≥ 0.1075 m（=1.5×UGV 宽 0.430 m 走廊）的 8 连通块中含最多论文搜索目标的那一块。命令入口：`airground gt traversability reach-region`、`scripts/calibrate_reach_region.py`、`airground metrics ugv-progress --arrival-regions/--arrival-region-index`；证据见 `docs/development/evidence/ugv-ogn/ugv-ogn-reach-region-1p5w-recalibration.md`。

UGV reach 判定补充与修正（2026-10-04/05）：**2026-10-04（用户规则）**进入 `A(T)` 容差内之外，UGV 在该采样点的 **heading 视锥**（水平 FOV 90°，`ugv_progress.DEFAULT_VIEW_HORIZONTAL_FOV_RAD`，与 confirmation 相机默认一致）必须与目标 OBB 相交，该目标才计入 `K`；**2026-10-05** 修复 `K` 假 0：`arrival_regions.npz` 是单标签栅格，两实例环带重叠时后画实例覆盖先画实例的格，先画实例的 `A(T)` 被静默削减（实测 type-ii smoke run：`bus_stop.0001` 声明的 68,506 格剩 6,555 格，UGV 停在带内却 `K=0`）。评测侧现在由 manifest OBB + traversability 栅格逐实例**精确重建** `A(T)`（`ugv_progress.build_exact_region_membership`，与 GT builder 同规则；场景可通行区是单一连通块，`component >= 0` 与发布工件的连通块限制等价），报告里逐目标记录 `reach_domain`（`exact_region` 为计分路径，`region_raster`/`pose_samples` 仅兼容回退）；npz 栅格本身不变，降级为诊断缓存。`yaw` 对 `d_K`/`p` 仍不参与。

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/audit_ugv_goal_selection.py \
  --run-dir runs/p0_ugv_ogn/20260913_migration/smoke_20260917_045258_type-i
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/audit_ugv_motion.py \
  --run-dir runs/p0_ugv_ogn/20260913_migration/smoke_20260917_045258_type-i
```

`scripts/airground_smoke.sh` 默认打开 `AIRGROUND_ENABLE_UGV_CONTACT_PUBLISHER=true` 与 `AIRGROUND_UGV_MOTION_TRACE=1`：前者让 `/ugv/contact_state` 真有数据，后者写 `ugv_motion_trace.jsonl`（轮速/车速/接触/命令）供 `audit_ugv_motion.py` 给出 `ok | chassis_stall | wheel_slip | wheels_not_turning | no_data` 判定。两者都是诊断，不改变控制律、指标或验收门。

LFT-W02 上的真实 RayFronts/VLFM benchmark 必须使用 `scripts/run_lftw02_benchmark.sh`，不能在远程手写 `airground run`。该脚本固定 `lft-w02-rootless-no-cgroup` profile：允许 rootless Docker no-cgroup，但仍保留 64 GiB 可用内存、90% 主机内存、85% 目标 GPU 显存、8 GiB host address-space 和 1s 采样 guard。每次运行前必须显式传 `--isaac-gpu` 和 `--rayfronts-device`；若已有 `isaac-sim` 容器运行且镜像/环境/GPU/cache/health 与本次签名匹配，脚本会复用 warm container，并写出 `isaac_container_reuse.json`。只有环境不匹配、容器曾 OOMKilled 或显式传 `--force-recreate-isaac` 时才重建。系统显示服务 `Xorg`/`Xwayland` 不算任务，但目标 GPU 总显存仍必须低于空闲阈值。LFT-W02 的 Isaac/Omniverse cache 必须通过 `AIRGROUND_DOCKER_HOME=/home/LFT-W02/jun/docker` 挂载，并写入 startup signature；smoke 和正式 public60/hidden60 不得混用不同 cache root。reset-support readiness 必须同时看到 RayFronts health 和 Nav2 startup smoke 的 `action_server_ready`，不能只凭 Nav2 topic 存在继续。若目标 GPU 有其他非目标进程或显存未空闲，脚本会拒绝运行且不 kill 任何非目标任务。

LFT-W02 的 smoke 和正式 public60/hidden60 使用同一 full-mission 启动签名，只有 episode 子集和输出目录不同。smoke 结束后必须把 artifact 拉回本地，用 `scripts/replay_trajectory_video.sh` 或 `airground replay trajectory-video` 从 UAV/UGV 轨迹生成第三人称 follow 视频和所有已声明采样相机的一人称视频；人工审核通过后生成 `smoke_review_manifest.json`，正式 public60/hidden60 必须通过 `--smoke-review-approved` gate 才能启动。任何 commit、submodule、Docker image、episode/target/map 文件、GPU、resource guard 或 timeout 变化，都必须重新 smoke 和重新审核。该流程只控制正式运行前置门，不把 smoke 或视频审核计为正式 benchmark 成绩。

除四路单视角外，还必须产出 **2560×1440 综合视频** `four_view_composite.mp4`（`scripts/render_smoke_video_from_trajectory.py --composite`，或入口 `scripts/render_replay_third_person.sh`，默认开）：四路按仿真时间**交集**对齐（每帧取最近仿真时间的那一帧，丢弃比例超过 `--max-drift-fraction`（默认 5%）直接报错退出），右下角叠实时小地图（`debug_artifacts/rgbd_search_cloud/topdown_plain.png`，世界→像素映射取自 `provenance.json` 的 `topdown_projection`）。该文件也写进 `expected_video_paths`/`videos`，缺失即 `missing_video_paths` 非空，上述 review gate 不放行。注入诊断车道没有 UAV 观测云底图，小地图改用 `scripts/export_nav2_topdown_basemap.py` 从 run 实际导航的 Nav2 地图生成同格式底图（`--minimap-image` 指到 `minimap_nav2/topdown_plain.png`，provenance 记录静态地图来源）。三类任务视频集（2026-10-05，K=2/2、2/4、2/4）见 [ugv-ogn-smoke-video-sets.md](development/ugv-ogn/ugv-ogn-smoke-video-sets.md)。

第三人称 follow 视频默认用**完整位姿（xyz + rpy）**重放导出，且第三人称相机的朝向口径与一人称相机一致（同一航向来源，机位在车体航向正后方）：`trajectory.parquet` 自 2026-09-20 起写入 `qw/qx/qy/qz/roll_rad/pitch_rad/yaw_rad`（可空，旧轨迹仍合法），`trajectory_replay.json` 据此写 `orientation_source=odometry_pose` 并逐帧使用记录姿态；只有旧轨迹缺这些列时才回退到位移推断航向（≥5 cm 真实位移才更新、最多向前看 2 s、静止保持上一航向）。渲染产物 `trajectory_video_render_report.json` 用 `orientation.<agent>.full_pose` 与 per-view `camera_heading_source` 记录本次实际来源，禁止把推断航向的旧 run 当成"真实姿态重放"审核。

LFT-W02 诊断路径默认启用 `AIRGROUND_ENABLE_GROUND_SUPPORT_PLANE=true`，只用于验证/规避该主机上 profiled scene mesh ground support 或 collision cooking 失效导致 UGV 跌穿地面的情况。它不改变 Nav2 map、traversability GT、LOS/obstacle collider、confirmation region 或 Mission Success 判定；若真实 smoke 仍发生 UGV 跌穿、近零路径或 PhysX/PX4 backend traceback，应进入 Isaac Sim 降级验证，而不是放宽 benchmark gate。

验证配置、资产入口和公开 draft manifest：

```bash
.venv/bin/airground config validate \
  --config benchmark/airground_benchmark/config/scenes/retro_neighborhood.yaml \
  --config benchmark/airground_benchmark/config/robots/quadcopter.yaml \
  --config benchmark/airground_benchmark/config/robots/jackal.yaml
.venv/bin/airground assets root
.venv/bin/airground assets manifest
.venv/bin/airground episodes validate
```

执行 Isaac headless 前置检查，并用 `VERSION` 文件拒绝误用非 4.5.0 容器：

```bash
.venv/bin/airground smoke isaac-preflight \
  --asset-root assets/cache/4.5.0 \
  --isaac-version-file /isaac-sim/VERSION \
  --simulator-version 4.5.0 \
  --output runs/p0_02_headless/isaac_preflight.json
```

该命令只检查 Isaac executable、资产目录、GPU/driver 和可选 VERSION 文件；不会启动 Isaac，也不能替代 P0-02 的真实 headless smoke。

生成 Isaac Sim 4.5.0 RetroNeighborhood headless smoke 的 Docker/compose 启动计划：

```bash
.venv/bin/airground smoke isaac-launch-plan \
  --repo-root . \
  --asset-root assets/cache/4.5.0 \
  --output runs/p0_02_headless/isaac_launch_plan.json
```

该命令只固定 build、launch、container preflight、log capture 和 teardown 命令面；真实 P0-02 仍需执行计划中的命令并归档 headless log、GPU/driver/container 版本和 scene/ROS smoke 证据。

执行真实 headless run 后，用 JSONL 证据校验器固定环境、scene/ROS milestone、launch log artifact 和退出码：

```bash
.venv/bin/airground smoke check-isaac-headless \
  --trace runs/p0_02_headless/headless_smoke.jsonl \
  --output runs/p0_02_headless/headless_smoke_check.json
```

该命令只校验已归档证据，不启动 Isaac/ROS；`P0-02` 仍需真实 run log 与 scene/ROS smoke 通过后才能勾选。

将 headless runtime、UAV+dock、Jackal UGV、确认区域和 reset recovery 五个真实 evidence surface 聚合为一个可复跑集成门：

```bash
.venv/bin/airground smoke check-headless-integration \
  --headless-artifact-dir runs/p2_15_stability/p2_15a_headless_render_uptime_20260803_151546 \
  --headless-run-dir runs/p2_15_stability/p2_15a_headless_render_uptime_20260803_151546/run \
  --require-headless-render \
  --require-energy-evidence \
  --dock-trace AirStack/runs/p0_09_dock_takeoff/p0_09am_chunked_100cycle_20260727_063228.jsonl \
  --jackal-trace runs/p1_04_traversability/p1_04_200route_rollout_20260727_121036/jackal_routes_200.jsonl \
  --confirmation-annotations runs/p1_05_targets/p1_05k_human_review_apply_20260803_approved/targets.reviewed.with_regions.json \
  --confirmation-trace runs/p1_07_targets/p1_07f_reviewed_sensor_trace_20260803/confirmation_visibility_sensor_frames.jsonl \
  --reset-recovery-run-dir runs/p2_04_reset/p2_04az_reset_recovery_soft_live_fixed_20260804_043034 \
  --output runs/p2_15_stability/headless_integration_check.json
```

P0/Gate B 当前已由归档真实 artifact 复验同步关闭：P0-04 UAV OFFBOARD smoke 通过 `arm/takeoff/hover/waypoint/cancel/emergency_stop`，P0-09am strict ACK dock/takeoff 100/100 cycles 通过，P0-11 Jackal contact-route smoke 10/10 routes 通过且无 unsafe contact。长时/长距离精度专项（60 秒 hover、10 米 waypoint、10 米 UGV straight-line）仍按 `IMPLEMENTATION_PLAN.md` 保持独立未勾选。

该命令只复算真实 artifact，不重新启动 Isaac/ROS；它用于 Phase 15 headless integration gate，不替代 P2-15g GUI/headless 长稳证据或生产级 in-process reset。

生成并校验 RayFronts UAV+UGV baseline contract smoke，覆盖全部任务类型和 difficulty 等级：

```bash
.venv/bin/airground smoke rayfronts-baseline-contract \
  --manifest runs/p1_11_release_pair/p1_11_profiled_roi_release_pair_20260727_141500/public_episodes.json \
  --rayfronts-root RayFronts \
  --trace-output runs/rayfronts_baseline_smoke/rayfronts_baseline.jsonl \
  --output runs/rayfronts_baseline_smoke/rayfronts_baseline_check.json
```

也可以只校验已有 trace：

```bash
.venv/bin/airground smoke check-rayfronts-baseline \
  --trace runs/rayfronts_baseline_smoke/rayfronts_baseline.jsonl \
  --output runs/rayfronts_baseline_smoke/rayfronts_baseline_check.json
```

`rayfronts-baseline-contract` 会实际加载 RayFronts UAV/UGV policy skeleton，并只通过 public observation、public hypothesis、handoff payload 和 evaluator report-id feedback 生成 contract smoke evidence；它不启动 Isaac、ROS、Nav2 或真实 evaluator。真实 runtime 指标和 oracle 发布门仍在 P2-08/P2-09/P2-10。

真实 RayFronts baseline smoke artifact 可以用 `isaac` mode 显式启用 RayFronts baseline surface，再用单独 gate 校验；该路径当前用于验证真实 Isaac/ROS/RayFronts 依赖、mapper-derived hypothesis、通信和确认事件表面，不能直接作为完整搜索 + 地面确认 benchmark 成绩：

```bash
.venv/bin/airground run \
  --mode isaac \
  --episodes runs/path/to/public_episodes.json \
  --agent real://rayfronts-baseline \
  --rayfronts-baseline \
  --output-dir runs/path/to/rayfronts_baseline_real_run \
  --repo-root .
```

完整 mapper 启动路径使用 `--rayfronts-baseline-mode mapper`。该模式会先运行 mapper runtime preflight，再在 managed reset support 内同时启动 RayFronts health node、RayFronts mapper server 和 Nav2 hold，并要求每集 evidence 来自 mapper-derived hypothesis：

```bash
.venv/bin/airground run \
  --mode isaac \
  --episodes runs/path/to/public_episodes.json \
  --agent real://rayfronts-baseline \
  --rayfronts-baseline \
  --rayfronts-baseline-mode mapper \
  --output-dir runs/path/to/rayfronts_mapper_baseline_real_run \
  --repo-root .
```

Semantic VLFM mapper 单集 pilot 使用 `--rayfronts-baseline-mode vlfm`。该模式会在 mapper runtime preflight 后额外运行 NARadio/RADIO/SigLIP semantic encoder offline preflight，并启动 `rayfronts.mapping_server_vlfm`：

```bash
.venv/bin/airground run \
  --mode isaac \
  --episodes runs/path/to/public_episodes.json \
  --agent real://rayfronts-vlfm-baseline \
  --rayfronts-baseline \
  --rayfronts-baseline-mode vlfm \
  --output-dir runs/path/to/rayfronts_vlfm_baseline_real_run \
  --repo-root .
```

**共享编码器（SimMT-6a，opt-in，2026-10-10）**：设置 `AIRGROUND_RAYFRONTS_ENCODER=naradio_remote` 时，`mapper`/`vlfm` 两条 mapper 启动路径改用 `encoder=naradio_remote`，连接 Isaac 容器内同一 GPU（按 `CUDA_VISIBLE_DEVICES` 区分）的共享 NARadio 编码器服务 `/tmp/airground_encoder_<gpu>.sock`；同卡第一个 mapper 在 `flock` 下以 pid 文件判活并启动 `python3 -m rayfronts.image_encoders.shared_service`（分辨率取 `AIRGROUND_RAYFRONTS_RGB_RESOLUTION`，`AIRGROUND_ENCODER_SERVICE_MAX_BATCH` 默认 1，即与本地编码器逐位一致的内联模式），后续 mapper 只连接。默认 `naradio` 行为不变。该开关偏离上游运行时，N=1 full-mission A/B 与多任务显存/串扰检查经用户评审前不得用于正式成绩。

**产物重分类（2026-08-05）**：P2-11l/P2-11m/P2-11s/P2-11t 现重分类为 RayFronts mapper/VLFM metrics surface smoke evidence：它们证明历史归档的 live Isaac Sim 6.0.1 / ROS 2 Jazzy 容器中 RayFronts mapper 或 `vlfm` mode 能启动，semantic encoder/preflight 可通过，episode artifact 中能写出 mapper-derived hypothesis、selected behavior、通信、UGV confirmation linkage 和 truth-leak 检查结果。它们不证明 UAV 已完成真实语义搜索，也不证明 UGV 已通过 Nav2/动作 API 到达 confirmation region 后完成地面确认。2026-08-05 审计发现 P2-11s public60 的 per-episode TTC 只有 `0.047999999999944976s` 到 `0.12800000600003614s`，样例 UGV path 仅约 `0.000018m` 到 `0.000095m`；生成脚本 `collect_runtime_metrics_smoke.py` 文件头也明确说明这是 metrics surface smoke，不是 full benchmark episode/oracle implementation。因此，RayFronts/VLFM full-mission benchmark 成绩当前标记为未测得。

**搜索侧接口面（已实现）**：当前可称为“已实现”的内容包括 RayFronts/VLFM dependency、semantic encoder、mapper-derived hypothesis、render+file-backed intrinsics、selected behavior surface、communication linkage、TaskGate/sensor confirmation path、RayFronts action→PX4 OFFBOARD UAV-control adapter、Isaac-resident evidence surface、full-mission runner 和 artifact gate；reviewed-public 单集已通过 strict physical-mission proof。还不能称为正式 benchmark 成绩，因为 reviewed public60 / hidden60 full-mission benchmark 尚未重跑。完整口径、失败原因和剩余切片见 `docs/development/archive/isaac6/rayfronts/rayfronts-full-mission-gap-analysis.md`。

**full-mission runner entrypoint（2026-08-06）**：`airground run --rayfronts-full-mission-runner` 会把 per-episode runner 从 `collect_runtime_metrics_smoke.py` 切到 AirStack 的 `run_rayfronts_full_mission.py`，并把 `benchmark/airground_benchmark` 复制到容器供 runner 导入 `RuntimeCommunicationBridge`。该 runner 会订阅 live ROS `/clock`、UAV/UGV odom、RayFronts public hypothesis，并向 UGV Nav2 `NavigateToPose` action server 发送目标；通信事件来自外部 `--communication-evidence-json` 或 runner 内部用 `RuntimeCommunicationBridge` + UAV/UGV odom radio pose + Isaac PhysX scene-query raycast 生成的 evidence；没有 Nav2 result、PhysX LOS communication delivered evidence 和 evaluator-owned confirmation evidence 时会失败，不允许从 hypothesis 直接伪造 communication delivered 或 UGV confirmation。runner 内部也内置最小 TTC/D2C/UAV path/UGV path sanity gate，低时长或近零路径不能写 mission success。根 `airground run` 支持 per-episode evidence bundle 目录：`--rayfronts-confirmation-evidence-dir`、`--rayfronts-communication-evidence-dir`、`--rayfronts-uav-control-evidence-dir`；也支持 runner-side sensor trace adapter：`--rayfronts-target-annotations` + `--rayfronts-confirmation-sensor-trace-dir`，由 AirStack runner 在 Nav2 到达后生成 `sensor_confirmation_evaluator` evidence。若只提供 `--rayfronts-target-annotations` 而不提供 `--rayfronts-confirmation-sensor-trace-dir`，AirStack runner 会使用 live `/ugv/confirmation_visibility_sensor_frames` topic records 生成 confirmation evidence；真实 sensor-frame publisher topic smoke 已完成。若启用 `--rayfronts-uav-control-adapter`，runner 会把 RayFronts UAV motion action 映射到 PX4 OFFBOARD waypoint 并生成 strict UAV-control evidence；真实 adapter smoke 已通过。每个 per-episode 目录可使用 `<episode_id>.<stem>.json`、`<episode_id>/<stem>.json` 或 `<stem>.json`；sensor trace 使用 `.jsonl` 后缀且 stem 为 `confirmation_sensor_trace`。该 entrypoint 仍不是完整 benchmark 成绩：public/hidden full-mission 重跑仍在 P0-RayFronts-FullMission 后续子项中。

**依赖证据（P2-11o/P2-11p）**：冻结镜像已完成 NARadio/RADIO/SigLIP 真实语义编码器权重解析、CUDA 前向预检和 frozen image 复验。P2-11q/P2-11r 仍作为 `vlfm` mapper pilot/selected-behavior surface 证据有效：reviewed public `retro-public-000` 可输出 `selected_behavior_modes=["VLFM-based"]`、`mapper_derived_hypothesis_count=1`、`hypothesis_evidence_types=["rayfronts_vlfm_mapper"]`、`vlfm_condition.ok=true`。但正式 benchmark 需要新的 full-mission runner：UAV 根据公开 observation 搜索并检测，communication simulator 投递 report，UGV 导航到有效 confirmation region，并在区域、视锥、遮挡和连续可见门控通过后才允许确认。既有 release tag 不移动。

**P2-11s behavior gate（2026-08-04 复验）**：只保留为 smoke 审计证据——报告要求真实 `isaac_ros` backend、UAV detection report、已投递通信、UGV confirmation、UGV confirmation `report_id` 引用 UAV detection、policy/communication isolation、0 truth leak，并输出 60/60 linked UGV confirmation。但该 gate 未要求 UAV 搜索轨迹、UGV 导航到 confirmation region、最小时长/路径或 sensor-derived confirmation，因此不得用于关闭 full-mission benchmark 成绩。

```bash
.venv/bin/airground smoke check-rayfronts-baseline-run \
  --run-dir runs/path/to/rayfronts_baseline_real_run \
  --expected-episodes 60 \
  --output runs/path/to/rayfronts_baseline_real_run/check.json
```

`run --mode isaac --rayfronts-baseline` 当前仍通过 AirStack metrics collector 生成 per-episode artifact。它会要求 live ROS 图中存在 RayFronts public hypothesis topic，并将 `rayfronts_baseline_evidence.json` 写入 run artifact；缺失 public hypothesis 时不会回退到普通 metrics smoke。Isaac run 在启动 managed reset support 前会预检查容器内 Nav2 ROS package（`nav2_map_server`、`nav2_lifecycle_manager`、`nav2_controller`、`nav2_planner`、`nav2_bt_navigator`、`nav2_behaviors`、`nav2_smoother`、`nav2_velocity_smoother`），并写出 `reset_support/reset_support_dependency_report.json`；缺包时会 fail-fast，而不是等长稳运行中途掉线。`--rayfronts-baseline-mode surface` 是 public map-probe surface 路径；`--rayfronts-baseline-mode mapper` 会额外启动 frontier mapper server；`--rayfronts-baseline-mode vlfm` 会额外运行 semantic encoder preflight 并启动 semantic VLFM mapper server。`mapper` 和 `vlfm` 都会让 episode collector 使用 `--require-rayfronts-mapper-derived-hypothesis`，并在启动前的 Isaac runtime preflight 中要求 `/uav/sensors/front_stereo/left/image_rect` 与 `/uav/sensors/front_stereo/left/depth_ground_truth` 有非空 Image payload；只有 topic endpoint、无图像帧的容器会 fail-closed。`check-rayfronts-baseline-run` 要求 `run_manifest.json` 来自真实 `isaac_ros` backend，`agent_entrypoint` 明确标识 RayFronts baseline，并逐集检查 UAV detection report、已投递通信、UGV confirmation、UGV confirmation 的 `report_id` 是否引用 UAV detection report、metrics validation 和 UAV/UGV 能耗证据。默认还要求 `reset_support` dependency evidence 可解析到 `reset_support/reset_support_dependency_report.json` 且 `status=ok`、`missing_packages=[]`；`--no-require-reset-support-dependencies` 仅用于旧产物诊断，不能作为发布级 RayFronts baseline 证据。同时会要求 run 或 episode 记录包含 RayFronts policy isolation、communication isolation 和 truth-leak evidence；`--no-require-policy-evidence` 同样仅用于旧产物诊断。完整 RayFronts mapper/encoder/policy baseline smoke 还必须使用 `--rayfronts-baseline-mode mapper` 或 `--rayfronts-baseline-mode vlfm` 生成 run，并使用 `--require-mapper-derived-hypothesis` 复算，要求 hypothesis evidence type 为 `rayfronts_mapper_frontier` 或 `rayfronts_vlfm_mapper`；当前 lightweight public map-probe surface 会显式标记为 `rayfronts_public_map_probe`，在该严格模式下会失败。`check-rayfronts-baseline-run` 只复算已有真实 run artifact，不启动 RayFronts/Isaac/ROS；普通 `real://runtime-metrics-smoke` run 不能通过该门。正式 full-mission gate 已通过 `--require-physical-mission` / `--require-rayfronts-physical-mission` 提供；它只负责拒绝不合格 artifact，不能把 metrics collector 升级成真实 runner。

```bash
.venv/bin/airground smoke check-rayfronts-baseline-run \
  --run-dir runs/path/to/rayfronts_baseline_real_run \
  --expected-episodes 60 \
  --require-mapper-derived-hypothesis \
  --output runs/path/to/rayfronts_baseline_real_run/check.full_mapper.json
```

VLFM behavior smoke 证据可加 selected-behavior gate；正式 release 不得只依赖该 gate：

```bash
.venv/bin/airground smoke check-rayfronts-baseline-run \
  --run-dir runs/path/to/rayfronts_vlfm_baseline_real_run \
  --expected-episodes 60 \
  --require-mapper-derived-hypothesis \
  --require-selected-behavior-mode VLFM-based \
  --output runs/path/to/rayfronts_vlfm_baseline_real_run/check.vlfm_behavior.json
```

正式 full-mission RayFronts/VLFM benchmark gate 必须额外开启 physical mission 检查。该 gate 会拒绝毫秒级确认、近零路径、缺少 Nav2 到达和缺少 confirmation-region/sensor visibility/occlusion 证据的 artifact：

运行阶段可直接加 run-level 防线，让 `airground run` 在产物写出后立即复算 full-mission gate；若仍然生成 metrics smoke 产物，命令会返回失败并在 run 根目录写出 `rayfronts_full_mission_gate.json`：

```bash
.venv/bin/airground run \
  --mode isaac \
  --episodes runs/path/to/public_episodes.json \
  --agent real://rayfronts-vlfm-baseline \
  --rayfronts-baseline \
  --rayfronts-baseline-mode vlfm \
  --rayfronts-full-mission-runner \
  --rayfronts-target-annotations runs/path/to/retro_neighborhood.targets.with_regions.json \
  --rayfronts-confirmation-sensor-trace-dir runs/path/to/full_mission_evidence/confirmation_sensor_trace \
  --rayfronts-communication-evidence-dir runs/path/to/full_mission_evidence/communication \
  --rayfronts-uav-control-evidence-dir runs/path/to/full_mission_evidence/uav_control \
  --require-rayfronts-physical-mission \
  --output-dir runs/path/to/rayfronts_vlfm_full_mission_run \
  --repo-root .
```

若 confirmation evidence 已由外部 evaluator 预生成，可改用 `--rayfronts-confirmation-evidence-dir`；该目录不能与 `--rayfronts-target-annotations` / `--rayfronts-confirmation-sensor-trace-dir` 同时使用。

若要走 live confirmation sensor-frame collector 路径，则保留 `--rayfronts-target-annotations`，移除 `--rayfronts-confirmation-sensor-trace-dir`；runner 会订阅 `/ugv/confirmation_visibility_sensor_frames`。该路径依赖真实 UGV camera/raycast publisher 在 episode 内产出 distance/FOV/visible-fraction/raycast evidence records；publisher/topic smoke 已通过，完整 public/hidden 仍需随 UAV control adapter 端到端重跑。

也可以对已有 artifact 单独复算：

```bash
.venv/bin/airground smoke check-rayfronts-baseline-run \
  --run-dir runs/path/to/rayfronts_vlfm_full_mission_run \
  --expected-episodes 60 \
  --require-mapper-derived-hypothesis \
  --require-selected-behavior-mode VLFM-based \
  --require-physical-mission \
  --min-time-to-confirmation-s 5.0 \
  --min-detection-to-confirmation-s 1.0 \
  --min-uav-path-m 1.0 \
  --min-ugv-path-m 1.0 \
  --output runs/path/to/rayfronts_vlfm_full_mission_run/check.full_mission.json
```

`--require-physical-mission` 要求每集 summary 至少包含 `time_to_confirmation_s`、`detection_to_confirmation_s`、`path_m.uav_3d` 和 `path_m.ugv_planar`；要求 `rayfronts_full_mission_trace.json` 包含 PX4/AirStack-owned UAV control evidence，证明 OFFBOARD/armed/takeoff/waypoint/search motion；并要求 linked UGV confirmation event 含 `confirmation_source`、`evaluator_valid=true`、匹配同一 `report_id` / `target_id`、`visible_frame_count`、`required_visible_frames`、`confirmation_region_id`、`inside_confirmation_region=true`、`sensor_visibility_ok=true`、`continuous_visibility_ok=true`、`occlusion_clear=true` 和 `nav2_goal_reached=true`。2026-08-05 复算 P2-11s public60 smoke artifact 时，该 gate 输出 `status=failed`、`physical_mission_episode_count=0`、最小 TTC `0.047999999999944976s`、最小 UGV path `1.4188688047338622e-05m`，符合预期。

RayFronts mapper-derived + semantic preflight 的当前 frozen Isaac/ROS 镜像为 `raven-airground:6.0.1-p2-11p-3cd19de`（image id `sha256:4a5b13265a3c7042ca7d929e7dd524562cfb879daa737d6609c9cef606c85e48`，size `33381564938` bytes），fresh-container verification 已确认 8/8 Nav2 package、GeographicLib datasets、PX4 SITL binary、Pegasus extension、Torch/torchvision/torch-scatter/pyopenvdb/transformers/filelock imports、RayFronts mapper runtime preflight 和离线 RayFronts semantic encoder preflight 全部通过；证据见 `docs/development/archive/isaac6/rayfronts/rayfronts-semantic-image-freeze.md`。历史 mapper-only 镜像 `raven-airground:6.0.1-p2-11n-6b66753` 早于 P2-11o/P2-11p semantic encoder 修复与新冻结验证，历史 reset-support-only 镜像 `raven-airground:6.0.1-p2-11h-7566161` 早于 P2-11j/P2-11k/P2-11l/P2-11m mapper dependency/runtime 修复，均不再作为当前 RayFronts release 镜像。

RayFronts semantic encoder 预检真实加载 `NARadioEncoder(model_version="radio_v2.5-b", lang_model="siglip")` 所需的 RADIO checkpoint、SigLIP/OpenCLIP safetensors 与 tokenizer，并执行 text/spatial/global/aligned tensor finite 检查。P2-11o report SHA-256 为 `6694ba56bbd844ef03f1c325caa769f894d77b1d0bba8fbfae65328fd4d1be2c`，RADIO checkpoint SHA-256 为 `6bff4bd732d815136652d454598e8fe6c6f4e658716d5e6a697f0e6b60bd8a98`，OpenCLIP safetensors SHA-256 为 `97faeafa0576c1ba4c92bae739ca06ef5f5d0c2db92f86a6086653d82a262043`；P2-11p 在新冻结镜像中用 `HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1` 复验 semantic preflight，offline report SHA-256 为 `9c25824d6ac4ed95e0043b16eacb33bf04e454656f29b2cadefb7ba69e24a23e`；P2-11q live `vlfm` pilot semantic preflight SHA-256 为 `b60a9e6d21b4311f976b4eeaa6123241c128712f1d14b3a6eaee8dc6e91bbb7b`；P2-11r selected-behavior gate report SHA-256 为 `f1449592aac6a5eb47bf01bce27cb5b9de2437894f54402796d8e8ed348fe292`，evidence SHA-256 为 `78a46394b38d0fe460b0d863a48d3ef64d7564b4e1cbb11d1dc255445e784b51`；P2-11s public60 behavior gate SHA-256 为 `565e580f8fda80cb09764e201fa0a4b0bda547e581ceda112f0b2abbf877ba5f`；P2-11t hidden60 redacted summary SHA-256 为 `01019f8e9c7538fb0066031cb7ac3ebabde62168036c63ccabd6d3dc8a036959`。证据见 `docs/development/archive/isaac6/rayfronts/rayfronts-semantic-encoder-preflight.md`、`docs/development/archive/isaac6/rayfronts/rayfronts-semantic-image-freeze.md`、`docs/development/archive/isaac6/rayfronts/rayfronts-vlfm-single-pilot.md`、`docs/development/archive/isaac6/rayfronts/rayfronts-vlfm-behavior-pilot.md`、`docs/development/archive/isaac6/rayfronts/rayfronts-vlfm-public60-behavior-run.md` 和 `docs/development/archive/isaac6/rayfronts/rayfronts-vlfm-hidden60-redacted.md`。

完整 RayFronts mapper/encoder/policy baseline 仍需要使用包含 P2-11j mapper 依赖层和 P2-11o semantic encoder 修复的镜像或在 live container 中运行 mapper runtime preflight 与 semantic encoder preflight；mapper preflight 会构建 `rayfronts_cpp`、导入 ROS/VLFM mapper server，并执行 OpenVDB occupancy update/query/frontier 函数检查：

```bash
docker exec isaac-sim /bin/bash -lc 'set -e; source /opt/ros/jazzy/setup.bash; python3 /isaac-sim/AirStack/simulation/isaac-sim/tools/preflight_rayfronts_mapper_runtime.py --rayfronts-root /isaac-sim/RayFronts --build --output /isaac-sim/runs/p2_11_rayfronts/p2_11j_mapper_runtime_preflight.json'
```

验证 traversability GT 并派生 Nav2 map_server 地图：

```bash
.venv/bin/airground gt traversability validate \
  --metadata path/to/traversability.yaml \
  --npz path/to/traversability.npz
.venv/bin/airground gt traversability package \
  --metadata path/to/traversability.yaml \
  --npz path/to/traversability.npz \
  --output-dir path/to/traversability_artifact \
  --stem retro_traversability
.venv/bin/airground gt traversability sweep-footprint \
  --metadata path/to/raycast_metadata.yaml \
  --npz path/to/raycast_seed.npz \
  --output-dir path/to/footprint_sweep \
  --stem retro_footprint_sweep \
  --footprint-report AirStack/simulation/isaac-sim/assets/reports_verified/jackal_6_0_1.json \
  --yaw-samples 16
.venv/bin/airground gt traversability export-nav2 \
  --metadata path/to/traversability.yaml \
  --npz path/to/traversability.npz \
  --output-dir path/to/nav2_map \
  --stem retro_traversability
.venv/bin/airground gt traversability rollout-report \
  --samples path/to/jackal_rollout_samples.jsonl \
  --min-samples 200 \
  --min-consistency 0.98
.venv/bin/airground gt traversability mismatch-review \
  --samples path/to/jackal_rollout_samples.jsonl \
  --output path/to/mismatch_review.json
.venv/bin/airground gt traversability calibrate-thresholds \
  --trace path/to/jackal_ground_testbed_outcomes.jsonl \
  --output-report path/to/jackal_ground_threshold_report.json \
  --output-config path/to/jackal_thresholds.yaml
```

`package` 会写出 deterministic NPZ、带 `npz_sha256` 的 metadata、Nav2 YAML+PGM 和 checksum manifest，固定后续真实 GT 冻结时的 artifact 表面。真实 RetroNeighborhood raycast 入口位于 `AirStack/simulation/isaac-sim/tools/generate_traversability_raycast.py`，需要在 Isaac Sim 6.0.1 容器内运行，并通过 `AIRGROUND_BENCHMARK_PACKAGE=/tmp/airground_benchmark` 指向当前 benchmark 包副本。该 Isaac-side 工具已完成 P1-01 smoke：使用真实 `omni.physx.get_physx_scene_query_interface()` 生成 height、normal、support mask、obstacle mask、ceiling height、slope、step 和 overhead clearance seed arrays。`sweep-footprint` 会读取这些 raycast auxiliary arrays，按 Jackal footprint 生成 traversable mask、inflation mask、component 和 cost grid，并写出 swept artifact 与 sweep auxiliary NPZ；提供 `--footprint-report` 时会从 verified Jackal asset report 自动派生 footprint 长宽，并在 summary 中保存 report SHA、collision path 和 wheel joint path。`rollout-report` 会读取真实 Jackal 动力学 rollout JSONL 样本，汇总 traversability label 与物理结果的一致率和失败样例；`mismatch-review` 会对 rollout mismatch 强制要求截图路径和最终处理结论，零 mismatch 时输出空审阅报告；`calibrate-thresholds` 会从标准地面测试场 outcome JSONL 自动派生 Jackal 最大测试稳定坡度和台阶高度，并写出独立版本化 YAML 配置。当前 checked-in 配置位于 `benchmark/airground_benchmark/config/traversability/jackal_thresholds.yaml`，真实 Isaac 6.0.1 标准测试场结果为 `max_stable_slope_deg=15.0`、`max_step_height_m=0.2`。普通 route smoke trace 缺少 `test_kind=slope/step` 证据时，该命令会失败而不是生成阈值。`export-nav2` 输出 Nav2 可读的 YAML+PGM。可通行 cell 写为 free，非可通行 cell 写为 occupied；当前 traversability schema 尚未区分 unknown mask，因此该派生图不生成 unknown cell。

正式 RetroNeighborhood GT（2026-09-17 起）：`runs/p1_03_traversability/p1_03_profiled_roi_0p05_20260917_1900/`，分辨率 **0.05 m**、origin `(-64,-32)`、1600×1280，raycast 由运行期 PhysX `profiled` 场景生成（`ray-start-z 8.0`、`ray-end-z -2.0`、`min-ground-normal-z 0.35`、`overhead-ray-distance 3.0`），footprint sweep 用 `--max-step-height 0.05`（footprint 0.508×0.430 m、`yaw-samples 16`、`max-slope 15°`、`min-overhead-clearance 0.50`）——即 **地面之上 ≥5 cm 高差在 GT 里就是不可通行**，与运行期 3D 点云的 `min_obstacle_height 0.05` 同一口径。`package/` 下的 `retro_p1_03_profiled_roi_0p05.npz` / `.metadata.yaml` / `.nav2.{yaml,pgm}` 是正式引用，派生 confirmation region/reach set 为 `runs/p1_05_targets/p1_05m_regen_0p05_20260917/targets.reviewed.with_regions.json`（`ground_reachable` 22/22 未变、10 任务仍 4 ok / 2 degraded / 4 blocked）；历史 0.25 m 包（`p1_03_profiled_roi_20260727_120158`）只作已冻结历史 artifact，不再被 smoke/episode/文档引用为正式包。新旧图逐格差异审计用 `scripts/compare_nav2_maps.py` 复算。

同轮起，UGV 运行期障碍源是 **Ouster OS1 3D 点云**（`/ugv/sensors/ouster/point_cloud`）：Nav2 local/global costmap 都用 `nav2_costmap_2d::VoxelLayer` 消费它（`min_obstacle_height 0.05`、`max 1.00`、`z_resolution 0.05`、`z_voxels 16`、`mark_threshold 0`、`footprint_clearing_enabled false`、`resolution 0.05`），Isaac 侧同时发布 `ugv/base_link -> ugv_os1_lidar` 静态 TF（Nav2 需要 tf2 才能把点云变换到 `map`）。旧 2D 平面扫描 `/<ns>/scan`（`AIRGROUND_ENABLE_UGV_PROXIMITY_SCAN`）默认停用，仅作为回退对比开关保留。点云来源由 `AIRGROUND_UGV_LIDAR_SOURCE` 选择：`rtx`（默认，Isaac RTX LiDAR writer）或 `physx_raycast`（CPU 多仰角 PhysX 射线，同 topic/frame，5 Hz）——本机 Isaac 4.5 的 RTX writer 实测**只发空云**（`width=0`），故 4.5 lane 与 smoke 用 `physx_raycast`。真实 Type I run `smoke_20260917_200702_type-i`（本机 default profile 的 swap 上限经用户 2026-09-17 明确授权调至 0.90，`resource_guard_session.json` `failures=0`）已验证：Nav2 `lifecycle_active`/两套 costmap/`action_server_ready` 一次通过、`/ugv/global_costmap/costmap` 1600×1280 @0.05、cloud 2163 点经 TF 到 `map` 后 min/median z≈0、障碍带 91 点中 95.6% 落在静态 GT lethal 格、local costmap 仅 680 lethal（车体悬空时会整片误标）、事故点窗口 65 lethal；UGV 停稳 z=0.063–0.064。**未回填**：该 run 结束于 `detection_gate_failed`（`queued_count=0`、`attempted_count=0`、`K=0/M=2`），UGV 未收到目标，因此“UGV 不再上台面 / K 重算 / 无 planner 失败 / costmap 更新耗时”仍需检测门修好后的 run；正式成绩与勾选状态不受本轮离线+运行期证据影响。

Python API `build_raycast_terrain_grid(metadata, raycast_fn, config)` 固定真实 adapter 的 raycast-to-grid 调用面：注入 Isaac/PhysX scene raycast provider 后，可生成上述 terrain seed arrays。`estimate_jackal_footprint_from_asset_report()` 可从 Jackal collision report 派生矩形 footprint；`sweep_ugv_footprint_over_terrain(terrain, config)` 可在 raycast terrain grid 上执行 deterministic rectangular UGV footprint sweep，生成 traversable mask、inflation mask、component 和 finite cost seed arrays。`compute_local_traversability_features(grid, ...)` 可对已验证 traversability 网格派生坡度、相邻台阶高度、车体横向净空、头顶净空、障碍膨胀 mask 和 safe mask。这些 API 都不替代 live Isaac articulation mesh-level collision sweep、动力学 rollout 或正式 RetroNeighborhood GT 冻结。

通信 LOS 可通过 `airground_benchmark.isaac_los.make_isaac_physx_raycast_fn()` 接入 Isaac PhysX scene-query。该模块为可选适配器，普通 benchmark 包导入不要求 Isaac；真实 adapter 可在 Isaac 内懒加载 `omni.physx.get_physx_scene_query_interface()`，或显式注入 scene query。默认忽略 `/World/UAV`、`/World/uav`、`/World/UGV`、`/World/ugv` 子树，避免 UAV/UGV 自身 collider 被当作通信遮挡。`RuntimeCommunicationBridge` 已固定天线 pose + LOS provider 到 seeded 通信信道的 adapter-facing 调用面；真实 backend 仍需完成 step-barrier 同步、事件记录和长稳验证。

生成 USD prim 候选绑定、目标标注审计和审阅图，用于检查 source path、USD prim path、人工复核字段、OBB、标签和可选 USD prim path：

```bash
python AirStack/simulation/isaac-sim/tools/export_target_prim_candidates.py \
  --stage AirStack/scenes/RetroNeighborhood/RetroNeighborhood_Export.usd \
  --output path/to/retro_usd_prim_candidates.json \
  --min-volume 0.1
.venv/bin/airground gt targets bind-usd-prims \
  --annotations benchmark/airground_benchmark/gt/targets/retro_neighborhood.targets.json \
  --prim-candidates path/to/retro_usd_prim_candidates.json \
  --output-annotations path/to/retro_neighborhood.targets.with_prims.json \
  --output-report path/to/target_prim_binding_report.json
.venv/bin/airground gt targets review-ledger-template \
  --annotations path/to/retro_neighborhood.targets.with_prims.json \
  --review-queue path/to/target_review_queue.json \
  --review-version manual-review-v1 \
  --source-review-media path/to/p1_05_target_hybrid_review_packet.mp4 \
  --output path/to/target_review_ledger_template.json
.venv/bin/airground gt targets apply-review \
  --annotations path/to/retro_neighborhood.targets.with_prims.json \
  --ledger path/to/target_review_ledger.json \
  --output-annotations path/to/retro_neighborhood.targets.reviewed.json \
  --output-report path/to/target_review_apply_report.json
.venv/bin/airground gt targets audit \
  --annotations path/to/retro_neighborhood.targets.reviewed.json \
  --require-source-path \
  --require-usd-prim \
  --require-verified \
  --require-review-version
.venv/bin/airground gt targets review \
  --annotations path/to/retro_neighborhood.targets.with_regions.json \
  --output-dir path/to/target_review
.venv/bin/airground gt targets validate-confirmation-visibility \
  --annotations path/to/retro_neighborhood.targets.with_regions.json \
  --metadata path/to/traversability.yaml \
  --npz path/to/traversability.npz \
  --output path/to/confirmation_visibility_proxy.json
python AirStack/simulation/isaac-sim/tools/validate_confirmation_visibility_raycast.py \
  --annotations path/to/retro_neighborhood.targets.with_regions.json \
  --output path/to/confirmation_visibility_raycast_report.json \
  --target-sample-count 5 \
  --min-visible-fraction 0.2 \
  --required-consecutive-frames 5
.venv/bin/airground gt targets validate-confirmation-sensor-trace \
  --annotations path/to/retro_neighborhood.targets.with_regions.json \
  --trace path/to/confirmation_visibility_sensor_frames.jsonl \
  --output path/to/confirmation_visibility_sensor_report.json
.venv/bin/airground gt targets build-confirmation-evidence \
  --annotations path/to/retro_neighborhood.targets.with_regions.json \
  --trace path/to/confirmation_visibility_sensor_frames.jsonl \
  --target-id RetroNeighborhood.target.0000 \
  --report-id rayfronts-full-mission-report \
  --nav2-goal-reached \
  --output path/to/full_mission_evidence/confirmation/retro-public-000.confirmation_evidence.json
```

`export_target_prim_candidates.py` 使用 PXR 读取真实 RetroNeighborhood USD crate，输出 prim path、semantic hints 和 world-space bbox；`bind-usd-prims` 会按语义 hints/path token、中心距离和尺寸差自动写入候选 `usd_prim_path`，并输出 binding report。该步骤不会设置 `verified=true` 或 `review_version`，不能替代人工复核。`review-ledger-template` 会从 review queue 生成安全草稿模板，记录 source checksum、视频路径、帧索引和每行待填字段；该模板 generator 为 `airground-target-human-review-ledger-template-v1`，不能直接传给 `apply-review`。`apply-review` 用人工填写的 `airground-target-human-review-ledger-v1` ledger 写回 `verified=true`、`review_version`、修正后的 `usd_prim_path`/OBB/category 或 `excluded_reason`，并默认校验 `source_annotations_sha256`，防止把旧人审结果套到漂移后的 target artifact。`audit` 会检查发布完整性门槛：非排除目标必须有 source path、USD prim path、`verified=true` 和 `review_version`；人工复核后排除的目标可以没有 `usd_prim_path`，但必须保留 `excluded_reason`、`verified=true` 和 `review_version`，不能伪造 prim path。P1-05k 已根据 hybrid 人审批准生成 reviewed target artifact：165 个目标中 161 个 `verify`、4 个 `exclude`，reviewed 与 reviewed-with-regions audit 均 `issue_count=0`。P1-07f 已在同一 reviewed artifact 上用真实 Isaac Sim 6.0.1 / RetroNeighborhood / PhysX scene-query 复跑 confirmation visibility raycast 和连续 sensor-frame trace，报告 `status=ok`、`issue_count=0`。`build-confirmation-evidence` 在该 trace 已通过时，为单个 UAV report/target 生成 full-mission runner 可读取的 `sensor_confirmation_evaluator` JSON，并要求调用方显式提供 Nav2 到达结果；它不把 GT 暴露给 policy，也不替代 live runner 内 sensor-frame collector/publisher。正式 release 应以 P1-05k/P1-07f/P1-11b reviewed artifact 作为当前基线，旧 P1-05c/P1-09/P1-11 产物只作为历史证据。

生成 paired start candidates artifact：

```bash
airground episodes paired-starts \
  --targets path/to/targets.with_regions.json \
  --metadata path/to/traversability.yaml \
  --npz path/to/traversability.npz \
  --ceiling-npz path/to/ceiling_height.npz \
  --output path/to/paired_starts.json
```

Python API `build_paired_start_candidates(grid, confirmation_regions, ...)` 可从已验证 traversability grid 和 reachable confirmation regions 生成 UAV/UGV 成对起点：UGV 起点位于同一可通行 component，UAV 以 `ugv/platform` 相对位姿停在平台上，并可用 ceiling height 过滤起飞净空不足 cell。P1-08b 已基于 P1-05k/P1-07f reviewed target artifact 和真实 `profiled` ROI traversability package 生成 72 个 RetroNeighborhood paired starts，UAV parent frame 固定为 `ugv/platform`，证据见 `docs/development/evidence/release/episode-release-pair-reviewed.md`；旧 77-start artifact 被 reviewed split 取代。

从 paired starts、目标标注、visibility/occlusion report 和 traversability grid 组装候选池：

```bash
airground episodes build-candidates \
  --paired-starts path/to/paired_starts.json \
  --targets path/to/targets.with_regions.json \
  --visibility-occlusion path/to/visibility_occlusion.json \
  --metadata path/to/traversability.yaml \
  --npz path/to/traversability.npz \
  --gt-traversability gt/traversability/retro.npz \
  --gt-targets gt/targets/retro.targets.json \
  --gt-confirmation-regions gt/targets/retro.targets.json \
  --gt-checksum <64-hex-checksum> \
  --output path/to/episode_candidates.json
```

该命令会生成单目标、多目标和顺序目标候选，raw difficulty 采用保守组合规则：visibility 取目标组合内最小值，occlusion 和 detour 取最大值；easy/medium/hard 标签由候选池内三分位派生。P1-09f reviewed candidate pool 为 720 个候选，未引用 P1-05k 排除目标。它不替代真实 Isaac/ROS oracle run。

候选池进入正式 manifest 生成前，应先检查 difficulty 标签和 oracle/path evidence：

```bash
airground episodes grid-oracle-estimate \
  --candidates path/to/episode_candidates.json \
  --targets path/to/targets.with_regions.json \
  --output path/to/candidate_oracle_evidence.grid_estimate.json
airground episodes attach-oracle \
  --candidates path/to/episode_candidates.json \
  --oracle-evidence path/to/candidate_oracle_evidence.grid_estimate.json \
  --require-all \
  --output path/to/episode_candidates.with_oracle.json
airground episodes difficulty-metadata \
  --candidates path/to/episode_candidates.with_oracle.json \
  --validate-labels \
  --output path/to/difficulty-retro-v1.json
airground episodes audit-difficulty \
  --candidates path/to/episode_candidates.with_oracle.json \
  --metadata path/to/difficulty-retro-v1.json \
  --output path/to/difficulty_audit.json
airground episodes audit-candidates \
  --candidates path/to/episode_candidates.with_oracle.json \
  --require-oracle \
  --output path/to/candidate_pool_audit.json
```

`grid-oracle-estimate` 会从 candidate pool 和 reviewed target GT 生成确定性的 grid/path 级候选时间估计，用于候选筛选、difficulty metadata 和初始 timeout；它不是 Isaac/ROS 真正运行证据。`attach-oracle --require-all` 会将候选级 path/time evidence 按 `candidate_id` 回填到候选池；`audit-candidates --require-oracle` 要求每个候选包含估计完成时间、D2C、UAV/UGV 路径长度、waypoint 数和可选 checksum。这三个命令只管理候选池证据，不替代 reviewed split 的真实 Isaac/ROS oracle run；当前 reviewed public/hidden 60 episode 真实 oracle 均已通过，reviewed public 60 episode 资源稳定性证据见 `docs/development/archive/isaac6/runtime/performance-reviewed-public60-resource-stability.md`，reviewed fresh-clone 复验证据见 `docs/development/archive/isaac6/release/fresh-clone-reviewed-release-evidence.md`，reviewed strict-release preflight 证据见 `docs/development/archive/isaac6/release/release-reviewed-strict-preflight.md`，release tag freeze 证据见 `docs/development/evidence/release/release-tag-freeze.md`。

`audit-difficulty` 会从候选池重算 visibility、occlusion、detour 三轴边界，并与已保存 metadata 的 canonical checksum 对比，用于发布前防止 metadata 漂移或被手工篡改。

正式从候选池生成 manifest 时，推荐开启 candidate-level oracle timeout：

```bash
airground episodes generate-from-candidates \
  --candidates path/to/episode_candidates.with_oracle.json \
  --split public \
  --use-oracle-timeouts \
  --output path/to/public_episodes.json
```

`--use-oracle-timeouts` 使用候选 `oracle.estimated_completion_time_s`，按 `clip(ceil(4 * oracle_time_s), 300, 1200)` 写入 `timeout_s`；候选缺失 oracle evidence 时会失败。

运行 contract/oracle dry-run。注意：包内默认 manifest 仍是空 `draft`；仓库发布契约的 60 集 pair 已于 2026-08-03 生成（见 [episode-release-pair-reviewed](development/evidence/release/episode-release-pair-reviewed.md)），当前论文协议评测使用 30 集 manifest（见文首），两者都需要显式传入非空 manifest 才能运行。

```bash
.venv/bin/airground run \
  --episodes path/to/non-empty-episodes.yaml \
  --agent contract://oracle \
  --output-dir runs/contract-smoke
.venv/bin/airground evaluate --run runs/contract-smoke
```

真实 Isaac/ROS metrics smoke 可以通过同一个 `run` 入口生成标准 run artifact；该模式会调用 Docker 容器内的 AirStack collector，不会回退到 contract：

```bash
.venv/bin/airground run \
  --mode isaac \
  --episodes path/to/non-empty-episodes.yaml \
  --output-dir runs/real-isaac-smoke \
  --repo-root . \
  --isaac-container isaac-sim
```

Isaac 容器 CPU 硬上限可通过 `AIRGROUND_ISAAC_CPU_LIMIT`（compose）或 wrapper `--isaac-cpu-limit` 显式调整，并进入 warm-reuse 启动签名；默认保持 12.0。2026-09-11 的对照实验显示，把它提高到 20 不能解决 render=true 启动卡死：容器 CPU 随配额顶到 2015%、`carb.tasking*` 线程各 ~87% 忙等、`/clock` 仍停在 0.068--0.092s，因此该参数只作为诊断/授权调节入口，不是 render 修复手段。

Isaac Sim 4.5 headless 渲染必须保持 `SimulationApp` 的 `sync_loads=True`（launch 已固定，会转发到 `/rtx/materialDb/syncLoads`、`/rtx/hydra/materialSyncLoads`、`/omni.kit.plugin/syncUsdLoads`）；设为 `False` 时首个 `world.step(render=True)` 会停在 RTX material DB 等一个永不完成的 `carb.tasking` 任务，表现为 `/clock` 冻结 + 容器 CPU 忙等。render=true 还必须使用 `RayTracedLighting` 或 `PathTracing`，其他 renderer 名会被原样写入 `/rtx/rendermode` 并导致永不产帧。

安全边界：Isaac compose 默认设置 12 CPU、32GiB `mem_limit`、等额 `memswap_limit`（容器不能占用 host swap）、`pids_limit=1024` 和 4GiB 私有 `shm_size`，禁止共享 host IPC。cgroup 上限还必须满足 host reserve 规则（≤ 主机 RAM 的 55% 且给主机留 ≥ 24GiB），否则 `airground run` 在 episode 前 fail-closed。`airground run --mode isaac` 启动前会校验 Docker `HostConfig` 与容器 cgroup 的 `memory.max`、`memory.swap.max`、`pids.max`、`cpu.max`，并写入 `container_resource_limits.json`；官方 CLI 自身及其 host 子进程同时受 8GiB `RLIMIT_AS` 硬限制。`resource_guard_session.json` 从 reset-support 启动起持续覆盖 detached RayFronts/Nav2 与 episode 生命周期；默认本机 profile 为 20GiB 可用内存、80% 主机 RAM（2026-09-21 用户授权，从 62% 提高：Type I lane 自身峰值约本机 RAM 的 63%）、90% host swap（2026-09-17 授权）、80% GPU VRAM、单失败样本和 1 秒轮询，超限或 telemetry 失败时立即停止整个 Isaac container。32GiB memory/memory+swap、12 CPU、1024 PID、4GiB 私有 shm 和 8GiB host 地址空间限制保持不变。Isaac 模式不可使用 `--no-resource-guard`，也不能越过 20GiB/80% RAM/90% swap/80% VRAM 边界、增加失败样本/轮询间隔或提高 host 地址空间上限。该机制不能从阻止 watchdog 调度的内核、驱动、电源或整机冻结中恢复。运行默认 `AIRGROUND_CGROUP_MODE=unified`：wrapper、`airground` CLI、guard 与容器全部线程必须落在同一个 `airground.slice`（内核同步 `memory.max`，容器用 `cgroup_parent` 加入），需要一次性 `sudo scripts/setup_airground_cgroup_slice.sh` 授权；未授权时 fail-closed，不会退化成只守护容器的轮询模式（`AIRGROUND_CGROUP_MODE=split` 仅供诊断）。以上限制不改变 benchmark 评分或 physical-mission gate。
在复制 episode runner 或启动 reset-support 前，官方路径还会写出 `isaac_runtime_preflight.json`，要求 Isaac 容器为 `running` 且 Docker health 为 `healthy`，能看到 NVIDIA GPU，并提供有效的镜像 `MIN_DRIVER_VERSION`，且 host driver 不低于该值。NVIDIA 固定 Isaac Sim 6.0.1 页面列出的 tested driver `595.58.03` 与镜像启动下限分开记录；`580.95.05` 是独立 6.0.0 页的 tested 值。当实际 driver 不同仅写 warning，不单独拒绝。物理 benchmark 启动还必须显式设置 `PLAY_SIM_ON_START=true`；仓库默认 paused，即使 topic 存在而 `/clock=0` 也不能启动 mapper/Nav2 或计为真实物理运行。preflight 会在 whole-stack guard 保护下最多等待 600 秒取得正值 `/clock`，并把实际 timeout 写入报告；health、GPU、镜像下限、版本格式或推进的 `/clock` 任一项失败都必须 fail-closed，不会启动 detached RayFronts/Nav2 worker；该报告只是运行安全证据，不是 benchmark 成绩。LFT-W02 若被固定在低于镜像 `MIN_DRIVER_VERSION` 的 driver 上，只能通过显式 `--allow-unsupported-driver-diagnostic` 做受保护的诊断运行；该开关会写入启动签名和 artifact，不会跳过 health、`/clock`、GPU 空闲、resource guard、轨迹和人工审核 gate。上一次受保护的 profiled 场景在旧 420 秒默认等待内仍处于 PhysX collider cooking，容器健康且资源保护未触发，因此该 artifact 仅是启动时序诊断，不是资源失败或 benchmark 成绩。当前本机 `580.173.02` 满足镜像 `570.169` 下限，详见 `docs/development/archive/isaac6/runtime/host-resource-guard-hard-limits.md`。

当前 `--mode isaac` 支持单 episode smoke 和 `--limit` 多 episode 顺序 real-backend oracle run，用于生成真实 backend artifact、metrics evidence gate、fresh-clone real episode smoke 以及 public/hidden oracle 证据；RayFronts/VLFM public/hidden full-mission 长稳仍按 `IMPLEMENTATION_PLAN.md` 继续推进。

`--mode isaac` 默认要求容器 collector 在每个 episode artifact 中写出 `reset_trace.json`、`reset_health.json`，并在 reset trace 中包含 UAV/UGV RGB、depth、LiDAR payload byte_count/SHA-256 digest 以及 AirStack trajectory buffer before dirty / after zero evidence；这些文件可直接由 `airground reset check-run --require-sensor-payloads --require-airstack-trajectory-clear` 校验。只有诊断旧容器或隔离 ROS topic 问题时才使用 `--no-reset-sensor-payloads` 或 `--no-reset-airstack-trajectory-clear`，这些开关不能作为发布级 reset 证据。

校验一批 public/hidden oracle run 的完成性与 per-episode evaluator artifact 一致性：

```bash
.venv/bin/airground smoke check-oracle-run \
  --run-dir runs/contract-smoke \
  --expected-episodes 60 \
  --split public \
  --output runs/contract-smoke/oracle_run_check.json
```

隐藏集只输出公开安全摘要时，必须启用 redaction 并提供私有 salt：

```bash
.venv/bin/airground smoke check-oracle-run \
  --run-dir runs/hidden-oracle-private \
  --expected-episodes 60 \
  --split hidden_test \
  --redact-private \
  --salt-file path/to/private_salt.txt \
  --output runs/hidden-oracle-private/hidden_oracle_summary.public.json
```

默认不记录全量传感器。需要固定 MCAP artifact 表面时显式开启：

```bash
.venv/bin/airground run \
  --episodes path/to/non-empty-episodes.yaml \
  --agent contract://oracle \
  --output-dir runs/contract-smoke-sensors \
  --record-sensors
```

`check-oracle-run` 会读取 `run_manifest.json`、root `run_summary.json` 和每个 episode 的 `events.jsonl`、`summary.json`、`trajectory.parquet`，要求 episode 数、split、Mission Success、per-episode evaluator artifact 一致性和 timeout 建议值可审计。`--redact-private` 只保留 hidden run 的聚合统计、timeout 范围和 salted checksum，不输出 run id、unsalted manifest checksum、artifact path、episode id 或 oracle trace。它不替代真实 Isaac/ROS oracle，也不替代 `--require-metrics-evidence` 的真实能耗/通信发布门。contract mode 会写出 reset trace/health 契约文件，但不代表真实 Isaac/ROS reset；contract mode 的 `sensors.mcap` 只包含 metadata-only 记录状态，不包含真实图像或点云；真实 Isaac/ROS backend 接入后应在同一 artifact 表面记录 RGB-D 和 LiDAR topic。

## 2. 系统架构

首版目标是 Isaac Sim 6.0.1 + RetroNeighborhood + Quadcopter UAV + Clearpath Jackal UGV 的协同 benchmark；Isaac Sim 5.1 仅作为历史基线保留。系统分层如下：

- 顶层 `benchmark/` Python 包：配置、统一 API、episode manifest、GT schema、通信、run orchestrator、metrics、CLI 和测试。
- `AirStack/` 子仓库：Isaac Sim 场景、Quadcopter/PX4/AirStack、Jackal/Nav2、dock 平台、物理和 ROS adapter。
- `RayFronts/` 子仓库：语义地图、UAV/UGV 协同 baseline、reset、namespace 和 topic 适配。
- 评测器：独占目标真值、traversability、confirmation region 和隐藏测试集；算法只能通过 observation/action API 与通信 inbox 交互。

核心任务流程：

1. UGV 携带 UAV 到成对起点，UAV 从 UGV 平台起飞。
2. UAV 和 UGV 在同步仿真时间下独立观测、行动和通信。
3. 任一机器人可上报 detection；有效 detection 生成不可猜测 `report_id`。
4. 任务最终成功必须由 UGV 在地面 confirmation region 内引用有效 `report_id` 完成确认。
5. 顺序任务只暴露当前 active query；确认当前目标后才发布下一个目标。

## 3. API 契约

外部环境采用 PettingZoo `ParallelEnv` 形态：

```python
observations, infos = env.reset(seed=episode_seed)
observations, rewards, terminations, truncations, infos = env.step({
    "uav": uav_action,
    "ugv": ugv_action,
})
env.close()
```

固定 agent：

- `possible_agents == ("uav", "ugv")`
- 正式运行期间不得动态增删 agent
- timestep 为 5 Hz agent step；正式指标使用仿真 `/clock`

Observation 使用 UAV/UGV 同构 `Dict` space，包含：

- `ego`：位姿、速度、agent 状态等自车信息
- `rgb` / `depth`：前视 RGB-D；正式协议默认 RGB 为 `uint8[300, 480, 3]`，depth 为米制 `float32[300, 480]`。Isaac 容量诊断可同时设置 `AIRGROUND_UAV_CAMERA_WIDTH` / `AIRGROUND_UAV_CAMERA_HEIGHT`，runner 会按实际 render-product 尺寸生成 file-backed intrinsics；该诊断配置仍必须保留 RGB-D 帧，不能作为 public/hidden benchmark 成绩或改变正式固定 observation 协议。
- `lidar`：固定上限 padded 点云和有效 mask
- `mission`：公开任务字段、active query、目标序号和剩余时间
- `timing`：`ego/rgbd/lidar/inbox` 的 source timestamp、age 和 valid mask；有效 source timestamp 不得晚于当前 agent step
- `inbox`：通信模拟器送达的 bytes payload，固定上限加 mask/length
- `safety`：公开安全状态
- `last_action_status`：上一动作是否被 adapter 接受及拒绝原因

Contract env 中 `communication` action 已接入通信模拟器：发送方提交 bytes payload 后，接收方下一步 observation 的 `inbox.payloads/lengths/mask/sender` 会收到 padded/masked 消息。真实 Isaac/ROS backend 可通过 `RuntimeApiBridge` 校验 action/observation batch 和 public info 泄漏边界，通过 `RuntimeCommunicationBridge` 复用同一通信模型，输入当前天线 pose、仿真时间和 PhysX LOS provider；`airground smoke check-runtime-api --require-full-surface --require-task-feedback --require-sensor-payloads` 会在发布级 adapter 证据中强制检查 mission、inbox、per-agent `last_action_status`、public TaskGate feedback，以及 UAV/UGV RGB、depth、LiDAR payload byte_count/SHA-256 digest，并继续拒绝 public info 泄漏 evaluator-only truth。`StepBarrierClock` 固定 250 Hz physics、10 Hz sensor frame 与 5 Hz agent step 的对齐窗口，并验证 observation source timestamp 不使用未来或过期帧。真实 runtime barrier smoke 可用 `airground smoke check-runtime-barrier --trace <runtime_barrier.jsonl> --require-sensor-payloads` 校验 action、communication、physics、observation、public-info validation 阶段顺序，以及每步 UAV/UGV RGB、depth、LiDAR payload byte_count/SHA-256 digest；`airground smoke check-runtime-interface-bundle` 会把 strict runtime API sample 与 barrier trace 作为一个 bundle 重新复算，用于关闭真实 adapter 统一 API 与同步 step barrier 主项。`airground smoke check-system-run-bundle` 会把 production reset orchestrator、真实 60 episode run、performance/resource report、runtime fault suite 和 run manifest recording surface 作为一个系统运行证据包重新复算，用于验收自动 reset/run/record/fault/abnormal termination 60 episode 无残留。标准 episode run artifact 与 production reset gate 已由 P2-04/P2-08/P2-09/P2-10/P2-04ba/P2-06h 关闭，RayFronts action→PX4 OFFBOARD adapter 已有真实 evidence；完整 public/hidden policy 长稳另行推进。

Action 使用同构 `Dict` space，包含：

- `motion`：hold、goal/path、cancel 等高层运动动作；UAV path 保留三维 pose，UGV path 必须投影并验证地面可通行性
- `report_detection`：query id、估计世界坐标、confidence
- `confirm`：仅 UGV 可完成最终确认，必须引用当前目标有效 `report_id`
- `communication`：bytes payload，不解释语义，所有跨机器人信息必须经过通信模拟器

正式模式下禁止通过 `state()`、`info`、debug topic 或共享 Python 对象泄露目标真值、通信前消息、hidden manifest 或 oracle trace。

## 4. Reset 与健康握手契约

真实 Isaac/ROS backend 接入前，顶层工具已固定 reset 顺序和健康恢复策略：

```bash
.venv/bin/airground reset plan --mode soft
.venv/bin/airground reset plan --mode hard
.venv/bin/airground reset check-trace \
  --mode soft \
  --trace path/to/reset_trace.yaml \
  --health path/to/component_health.yaml \
  --require-sensor-payloads \
  --require-airstack-trajectory-clear \
  --require-nav2-cancel \
  --require-uav-px4-cancel \
  --require-control-hold \
  --require-healthy-components
.venv/bin/airground reset check-run \
  --run-dir path/to/real-60-episode-run \
  --expected-episodes 60 \
  --require-sensor-payloads \
  --require-airstack-trajectory-clear
.venv/bin/airground reset decide-recovery --health path/to/component_health.yaml
.venv/bin/airground reset run-recovery \
  --artifact-dir runs/p2_04_reset/manual_recovery/run \
  --health path/to/component_health.yaml \
  --container isaac-sim \
  --airground-cli .venv/bin/airground
.venv/bin/airground reset check-recovery-run \
  --run-dir runs/p2_04_reset/manual_recovery/run \
  --output runs/p2_04_reset/manual_recovery/check.json
.venv/bin/airground reset run-soft-full-action \
  --artifact-dir runs/p2_04_reset/manual_soft_full_action/run \
  --container isaac-sim \
  --airground-cli .venv/bin/airground
.venv/bin/airground reset check-soft-full-action-run \
  --run-dir runs/p2_04_reset/manual_soft_full_action/run \
  --output runs/p2_04_reset/manual_soft_full_action/check.json
.venv/bin/airground reset check-production-orchestrator \
  --soft-full-action-run-dir path/to/soft_full_action/run \
  --recovery-run-dir path/to/reset_recovery/run \
  --hard-restart-run-dir path/to/hard_restart/run \
  --reset-state-run-dir path/to/real_60_episode_reset/run \
  --dock-reset-pose-report path/to/dock_takeoff_reset_pose_check.json \
  --dock-reset-sequence-report path/to/dock_takeoff_reset_sequence_check.json \
  --expected-episodes 60 \
  --require-clock-epoch-reset \
  --output path/to/production_reset_orchestrator_check.json
```

soft reset 契约要求先暂停 physics，再取消 AirStack/Nav2 goal，清空控制命令、轨迹、RayFronts、ROS 队列、通信队列和指标累积器，随后重置 Jackal、UAV/PX4、传感器和 simulator timeline，传送 Jackal 到起点，重建 dock joint，将 UAV 放到平台相对位姿，等待 simulator、PX4、AirStack、Nav2、RayFronts、sensors 和 agent adapter 健康握手，最后恢复 physics。真实 adapter 可用 `ResetTraceRecorder` 记录每个 step 的仿真时间、组件和状态，并把 deterministic trace JSON 写入 run artifact；`reset check-trace` 可直接校验该结构化 trace，开启 `--require-sensor-payloads` 时还会要求 reset trace 含 UAV/UGV RGB、depth、LiDAR payload byte_count/SHA-256 digest，开启 `--require-airstack-trajectory-clear` 时会要求 adapter-facing AirStack trajectory buffer 具备 before dirty / after zero evidence，开启 `--require-nav2-cancel`、`--require-uav-px4-cancel` 和 `--require-control-hold` 时会分别要求真实 UGV Nav2 active goal cancel、UAV PX4 safe cancel 和 UGV dirty-to-zero hold evidence，开启 `--require-healthy-components` 时还会要求 simulator、PX4、AirStack、Nav2、RayFronts、sensors 和 agent adapter 全部健康。`reset run-soft-full-action` 可在健康 live container 上自动编排 RayFronts/Nav2 support、full reset trace collector、host gates 和 postflight 扫描，成功后嵌入 `check-soft-full-action-run` artifact gate，用于复跑这些 action-surface 证据。`reset run-recovery` 会从 pre-recovery health 复算 `decide-recovery`：首次 infra failure 只启动当前 soft runner 支持的失败组件（目前为 Nav2/RayFronts）并重新采集 full-action reset gate，重复 failure 则委托 hard restart full-health runner；`check-recovery-run` 会重算决策并复验 soft/hard artifact，防止 recovery summary 与实际执行漂移。`check-production-orchestrator` 会把 soft full-action、selective recovery、hard restart clock epoch、60 episode reset-state audit、dock pose 和 dock sequence 六类真实 artifact 聚合复算，作为 P2-04 生产级 reset orchestrator 发布门。

`reset check-run` 面向多 episode run artifact：它会读取 root `run_manifest.json`，逐集查找 `reset_trace.json` 与 `reset_health.json`，并按同一 reset plan、健康组件和可选传感器 payload checksum 规则校验。当前命令只是发布证据门，不会执行 reset；缺少 per-episode reset trace/health 时会失败，用于防止 60 episode 长稳运行没有残留状态证据仍被误判通过。

如果健康握手失败，第一次 infrastructure failure 只重启失败组件并重试 episode；重复失败升级为 hard reset 整个 simulation stack。顶层 run orchestrator 已固定 retry 语义：retryable `infra_error` 使用相同 episode seed 自动重试一次，重复失败在最终 `termination_report.json` 中仍标记为 `infra_error`，不会归为算法失败。生产级 reset orchestrator 由 `check-production-orchestrator` 聚合真实 P2-04 artifact 复算；后续 public/hidden full-mission 重跑仍必须按同一契约写出可复验 artifact。

contract 级故障注入入口：

```bash
.venv/bin/airground faults catalog
.venv/bin/airground faults run-contract --scenario px4_disconnect
.venv/bin/airground faults run-contract --all
```

当前 fault catalog 覆盖无 RGB-D、无 LiDAR、消息全丢、通信队列/收件箱溢出、Nav2 stuck、PX4 disconnect 和 simulator exception。`run-contract` 只验证 contract environment 的终止 reason code；真实 Isaac/ROS backend 仍需要单独完成传感器断流、通信黑洞、通信溢出、Nav2 stuck、PX4 disconnect 和 simulator exception 的集成故障注入。

真实 Isaac/ROS runtime fault suite artifact 校验入口：

```bash
.venv/bin/airground smoke check-runtime-fault-suite \
  --suite-dir runs/p2_15_faults/p2_15d_runtime_fault_suite_20260804_051533 \
  --require-sensor-payloads \
  --output runs/p2_15_faults/p2_15d_runtime_fault_suite_20260804_051533/runtime_fault_suite_check.json
```

`check-runtime-fault-suite` 会逐项复算 `no_rgbd`、`no_lidar`、`messages_all_dropped`、`nav2_stuck`、`px4_disconnect` 和 `simulator_exception` 的 reason code/category、affected agents、retryable、scenario id、Isaac/ROS backend 和 sensor payload checksum。`--forbid-manual-trigger` 用于后续自动故障注入发布门；当前 P2-15d suite 是 adapter-reported/manual fault artifact suite，不替代自动断流、断连或 stuck 注入。

一键真实采集并校验六个 runtime fault artifact：

```bash
.venv/bin/python tools/run_runtime_fault_suite_smoke.py \
  --output-dir runs/p2_15_faults/p2_15e_runtime_fault_suite_runner_20260804_052734 \
  --require-sensor-payloads \
  --episode-prefix p2-15e
```

该 runner 连接 live `isaac-sim` 容器，逐场景执行 `collect_runtime_fault_smoke.py`，复制 artifact 回 host，运行 suite gate，并额外运行 `--forbid-manual-trigger` negative check。它固定可复跑采集流程，但仍不替代自动故障注入器。

运行 Phase 15 自动 fault injector suite：

```bash
.venv/bin/python tools/run_runtime_fault_suite_smoke.py \
  --output-dir runs/p2_15_faults/p2_15f_phase15_fault_injector_suite_20260804_054109 \
  --require-sensor-payloads \
  --collector-trigger-mode phase15_fault_injector \
  --phase15-injection-timeout-s 0.25 \
  --require-fault-injection-evidence \
  --forbid-manual-trigger \
  --episode-prefix p2-15f
```

该模式在真实 Isaac/ROS graph 采集 readiness 和 sensor payload 后，从 adapter 接收侧注入六类 Phase 15 fault，并要求每个场景都有 `phase15_fault_injected` event、`fault_injection_evidence`、非 manual provenance 和稳定 reason code。

## 5. Episode Schema

episode manifest 是固定 split 和评分口径的唯一公开入口。核心字段包括：

- `schema_version`：当前为 `1.0.0`
- `catalog_id`：例如 `benchmark-v1.0-retro`
- `status`：`draft` 或 `released`
- `split`：`public` 或 `hidden_test`
- `release_channel`：公开集为 `public`，隐藏集私有 manifest 为 `private`
- `difficulty_version`：例如 `retro-v1`
- `episodes[]`：episode 列表

每个 episode 至少包含：

- `episode_id` 与 `seed`
- `scene_id`
- `task_type`：`single_target`、`unordered_multi_target` 或 `sequential_target`
- `starts`：UGV 起点和 UAV-on-platform 相对/世界起点
- `targets[]`：目标实例、query、顺序索引和 GT 引用
- `timeout_s`
- `difficulty`：visibility、occlusion、detour 三轴标签与数值
- `ground_truth.checksum_sha256`

公开发布规则：

- 公开 release 只包含 `split=public` manifest。
- 隐藏测试集只发布 episode 数量、任务类型分布、difficulty 分布、GT checksum 集合、evaluator checksum 和 salted manifest checksum。
- 隐藏起点、目标、seed、oracle trace 和私有 manifest 不得进入公开仓库或普通日志。
- `public` 与 `hidden_test` 必须使用相同 schema、资产版本、GT 生成器、difficulty 边界、timeout 规则和 evaluator。

## 6. 指标与记录

### 6.1 UGV 中心 OGN 指标（2026-09-13 起主口径）

评测主体是 UGV；UAV 只作辅助，detection/通信/confirmation 全部只写诊断字段，不进入指标分子分母，也不作为计分前置条件。算法可以完全不使用 UAV。

任务与目标集合：

- 任务词表逐字取自上游 RAVEN 论文附录 Table A.3（RetroNeighborhood 场景 4 个 Type I + 3 个 Type II + 3 个 Type III）。
- 目标集合 `G` = 查询类中 `ground_reachable == "reachable"` 的标注实例；`M = |G|`。
- `M = 0` 的任务标记 `blocked`（不评分）；某查询类贡献 0 个可达实例但并集 `M > 0` 的任务标记 `degraded`；Type III 任一时序阶段没有可达目标时同样标记 `blocked`。
- 当前 reviewed GT（2026-10-05 重算）：10 个任务全部 `ok`——31 个论文实例（4 Type I + 3 Type II + 3 Type III 的目标并集）全部 `ground_reachable`，`M` 合计 31；无 `degraded`/`blocked`。

指标定义（`reach window` 主口径 `[1.5, 8.0] m`）：

- reach：UGV 平面位姿首次进入实例 `g` 的 reach set（表面式稠密抵达集合 `A(T)`，见上文 2026-09-24/2026-10-04/2026-10-05 三条口径；允许 `reach_tolerance_m` 默认 0.5 m 的离散化容差，并要求该采样点视锥与目标 OBB 相交）的仿真时刻 `t_g`；`M` 与 reach 必须使用同一 reach set。
- `K` = `budget_s` 内 `t_g` 存在的目标数；`Progress = K / M`。
- runner 侧语义（**2026-09-22 起**）：`budget_s`（`--budget-s`，默认 **240**）是**总模拟耗时预算**，同时也是 K 窗口：`K` 窗 = `[window_start_s, window_start_s + budget_s]`，`window_start_s` 默认为 0 秒，即"模拟时钟开始走表"的 episode 起点（`ugv_progress.json` 会记录 `window_start_s`/`window_end_s`）。runner 用 `--rayfronts-uav-control-mission-budget-s`（= 同一个 `budget_s`）在 `/clock` 上执行该截止：**搜索本身不设预算**（`--rayfronts-uav-control-search-budget-s 0`），UAV 连续搜索直到截止；截止到达时 runner 取消 UAV goal（正常 cancel/land）与 UGV 在飞 goal，未尝试目标记 `cancelled_budget_exhausted`，随后正常结算并写出产物，`termination_report.reason` = `mission_budget_exhausted`（`category=timeout`、`timeout=true`、`fatal=false`，不再记为 agent failure）。每个通过检测门的 detection 仍按平面 10 m 去重后进入 UGV FIFO，UGV 自第一个目标起并发导航，单目标失败/超时（默认 60 仿真秒）后继续下一个。UGV 是否 reach 仍只由 evaluator 离线按本节的 `K`/`PPL` 口径判定，runner 不自报 K。
- 搜索前启动预算（**2026-10-12 起**）：UAV 搜索会话启动后，若 `AIRGROUND_PRE_SEARCH_BUDGET_S`（默认 **40** 仿真秒，0 关闭）内仍未发出第一个搜索目标（解锁、起飞、悬停、规划器启动均计入），runner 立即终止该任务、不重试，`termination_report.reason` = `pre_search_budget_exceeded`（`category=agent`、`fatal=true`），报错信息记录卡住的阶段。修复后该阶段约 20 仿真秒（N=1 21.7 s，N=9 37.6–39.4 s 含 25 s 悬停）。public 与 hidden 共用同一规则。
- 检测门（2026-09-22）：语义体素簇 = softmax(query labels) ≥ **0.95** 且 3D CCL 连通簇 ≥ **5** 体素（score 保持 0.95，因为本场景最佳 bus stop 体素只有 0.9793，上游 0.98 永不触发；τ_min 从上游硬编码的 30 依次降到 10、再降到 5，因为实测 `bus_stop.0002` 只有 11–22 体素、`bus_stop.0001` 只有 **5** 体素——30 与 10 都漏掉 0001，而 0001 可见窗口内不存在同尺寸的竞争簇）。另外**簇中心安全飞行高度门**：簇中心低于 `AIRGROUND_VOXEL_MIN_CLUSTER_CENTER_Z_M`（默认 **0.5 m**，map 帧）的簇一律丢弃（镜像上游 frontier 的 1.5 m 规则；实测唯一持续的非目标 8–12 体素簇位于 map z=−0.46 m 的地面以下，是深度伪影）。
- per-detection 可视化：run 产物 `ugv_detection_pose_trace.jsonl` 记录每次 detection 的 `uav_position_m`、`detection_position_m` 与派发的 `ugv_goal_position_m`；`scripts/export_rgbd_search_cloud.py --detection-pose-trace` 把它们渲染为点云 `kind=5`（UAV↔UGV 目标连线）与 `kind=6/7`（UAV 检测位置 / UGV 目标点）散点，`provenance.json` 登记 `detection_count`/`detection_segment_count`。
- `p` = 到第 K 个目标首次 reach 时刻的 UGV 平面累积路径长。
- `d_K` = 2D traversability 栅格上"起点 → 最优 K 子集 → 最优顺序"的最短路径总和；`M <= 12` 用 Held-Karp 精确解，超过时用贪心+2-opt 并记录 `optimality=heuristic_v1`。
- `PPL = (d_K / p) · (K / M)`，`d_K/p` 截断到 1.0，`K = 0` 时 `PPL = 0`。
- `SR = 1[K = M]`，`SPL = (d_M / p) · 1[K = M]`。

工具入口：

```bash
.venv/bin/airground tasks build-catalog --targets <reviewed-targets.json> --output <catalog.json>
.venv/bin/airground metrics ugv-progress --trajectory <trajectory.parquet> --targets <reviewed-targets.json> --catalog <catalog.json> --task-id <task-id> --budget-s <s> --traversability-npz <npz> --traversability-metadata <json> --output <report.json>
.venv/bin/airground metrics aggregate-progress --report <episode-report.json> [--report ...] --output <aggregate.json>
```

### 6.2 legacy 全链诊断指标（降级）

以下指标自 2026-09-13 起只作诊断与消融，不再决定成功：

- legacy Mission Success：超时前完成全部目标；最终确认全部来自 UGV；无 fatal event。
- UGV 计分 lane 的完成标记事件为 `ugv_lane_success`（`type`、`time_s`、`target_id`、可选 `report_id`、`nav2_goal_reached=true`）；2026-09-19 起该事件同 `pose`/`energy` 一样可携带可选 `agent` 标签（`uav`/`ugv`）。full-mission runner 一直写出该标签，但 evaluator 的严格模型此前拒绝它——这会让**第一次真正成功的 UGV lane**把整条 artifact 流水线打断（`smoke_20260919_171142_type-i`），因此模型改为接受可选 `agent`（旧 trace 不带该字段仍然合法）。
- Time to Confirmation：从查询发布到最后一个目标被 UGV 确认的仿真时间。
- Detection-to-Confirmation Time：每个目标第一条有效 detection 到 UGV confirmation 的时间。
- UAV/UGV 路径：UAV 三维路径长度，UGV 平面路径长度。
- 能耗：UAV rotor 与 UGV wheel 原始 effort 保留，并用版本化固定负载/效率模型积分。
- 碰撞与安全：碰撞次数、累计/最大冲量、最小净空、off-traversability、UGV 姿态、UAV 地面冲击、near miss。
- 通信成本：提交/送达 bytes、packets、drop、平均/P95 latency、airtime 和 blackout。

默认 run artifact：

- `run_manifest.json`
- `run_summary.json` / `run_summary.csv`
- per-episode `events.jsonl`
- per-episode `trajectory.parquet`
- per-episode `summary.json` / `summary.csv`
- per-episode `termination_report.json`

单 episode run 会在 run 根目录同步 `events.jsonl`、`trajectory.parquet`、`summary.json/csv` 和 `termination_report.json`，便于 `airground evaluate --run` 快速复核。开启 `--record-sensors` 后额外写 `sensors.mcap`。

真实 run artifact 完成后，应额外执行指标证据检查：

```bash
.venv/bin/airground evaluate \
  --run path/to/run-dir \
  --check-artifacts \
  --require-success \
  --output-dir path/to/run-dir/evaluation
```

`--check-artifacts` 会从 `events.jsonl` 重算 summary、比对 `summary.json`、检查 `trajectory.parquet` 与 pose event 行数，并要求 trace 中包含 detection/confirmation、UAV/UGV pose、能耗和通信证据。AirStack 的 `collect_runtime_metrics_smoke.py` 可从 live `/clock`、`/uav/odom`、`/ugv/odom` 生成一个 real-backend metrics smoke artifact，用于验证 metrics evidence gate。该命令和 smoke 只验证指标记录表面和 run artifact 一致性，不替代真实 Isaac/ROS episode、oracle 或发布级 60 episode 运行；发布级 `--require-metrics-evidence` 还会要求 `run_manifest.json` 声明真实 Isaac/ROS `runtime_backend`，contract/toy trace 不可作为发布级指标证据。

发布前可生成机器可读发布 manifest，将资产、episode、隐藏 checksum、evaluator checksum、GT artifact、container reference 和 repo/submodule commit 汇总到同一 JSON；container reference 必须是显式非 `latest` tag 或 `@sha256:` digest：

```bash
.venv/bin/airground release manifest \
  --release-dir path/to/release_pair \
  --release-id benchmark-v1.0-retro \
  --simulator-version 6.0.1 \
  --container-tag raven-airground:<tag-or-digest> \
  --gt-artifact targets=path/to/targets.with_regions.json \
  --gt-artifact traversability=path/to/traversability.yaml \
  --run-dir path/to/run_dir \
  --output path/to/release_pair/release_manifest.json
.venv/bin/airground release checklist \
  --release-dir path/to/release_pair \
  --run-dir path/to/run_dir \
  --fresh-clone-plan path/to/fresh_clone_plan.json \
  --fresh-clone-report path/to/fresh_clone_report.json \
  --fault-report path/to/fault_report.json \
  --performance-report path/to/performance_report.json \
  --reset-state-report path/to/reset_state_audit.json \
  --reset-state-run-dir path/to/reset_state_run_dir \
  --soft-reset-full-action-report path/to/soft_reset_full_action_report.json \
  --gt-artifact targets=path/to/targets.with_regions.json \
  --gt-artifact traversability=path/to/traversability.yaml \
  --require-fresh-clone \
  --require-metrics-evidence \
  --require-gt-artifacts \
  --require-fault-report \
  --require-performance-report \
  --require-reset-state-report \
  --require-soft-reset-full-action-report \
  --require-release-id benchmark-v1.0-retro \
  --require-simulator-version 6.0.1 \
  --strict-release \
  --strict-clean \
  --fail-on-warn
.venv/bin/airground faults run-contract --all --output path/to/fault_report.json
.venv/bin/airground release repro-plan \
  --repo-url git@github.com:<owner>/RAVEN-AirGround.git \
  --output path/to/fresh_clone_plan.json
.venv/bin/airground release repro-report \
  --plan path/to/fresh_clone_plan.json \
  --results path/to/fresh_clone_results.json \
  --artifact-root path/to/fresh_clone_checkout \
  --repo-root path/to/fresh_clone_checkout \
  --output path/to/fresh_clone_report.json
```

`release audit-pair` 会交叉检查 public/hidden manifest、release report 与 hidden summary 的任务计数和 visibility/occlusion/detour 三轴难度分布，并要求发布分布满足 30/15/15 任务计数和 20/20/20 easy/medium/hard 边际分布；同时会递归扫描 hidden summary，拒绝私有字段名以及从 hidden manifest 泄漏出的 episode id、seed、query、target/region id 等私有值。`release manifest --release-id benchmark-v1.0-retro` 会把版本号写入发布 manifest；`release checklist --require-release-id benchmark-v1.0-retro` 会拒绝 release id 漂移。`release manifest --simulator-version 6.0.1` 会选择 packaged Isaac Sim 6.0.1 asset manifest 并把对应 packaged path 写入 release manifest；显式 `--asset-manifest` 仍优先使用用户提供的 YAML。`release manifest --run-dir` 会把 run artifact 目录下每个文件的相对路径、大小和 SHA-256 写入发布 manifest，便于 release review 追踪运行产物。`release checklist --strict-release` 会一次性启用 strict-clean、fail-on-warn、metrics evidence、fresh-clone evidence、fault report、performance/long-stability report、reset state long-run audit、soft reset full-action report、GT artifact、target human-review gate、`benchmark-v1.0-retro` release id 和 Isaac 6.0.1 asset manifest 发布门。`release checklist` 默认要求 `<release-dir>/release_manifest.json` 存在，并重算 asset manifest checksum、release-pair episode/difficulty checksums、hidden summary redaction、evaluator checksum 和当前 repo/submodule provenance，以确认资产清单、public/hidden/difficulty manifest、隐藏集公开 metadata、当前源码 surface、commit、dirty 状态与 submodule 状态均和 release manifest 一致，同时检查 container reference、GT checksum、repo/submodule commit、run artifact index 和 release-pair 一致性；hidden summary redaction 会同时检查私有字段名和 hidden manifest 私有值泄漏。`--require-simulator-version 6.0.1` 会要求 release manifest 的 asset manifest `simulator_version` 与真实闭环目标一致。缺失 container reference、未带 tag 的镜像和 `:latest` tag 会失败，显式非 `latest` tag 或 `@sha256:` digest 才可通过。`--require-gt-artifacts` 会把缺少 GT artifact checksum evidence 从 warning 升级为 failure；提供 `--gt-artifact name=path` 时，checklist 会从文件重算 GT artifact SHA-256 并与 release manifest 中的同名 checksum 精确比对；`--require-target-review` 会要求名称包含 `target` 的 GT artifact 通过 target audit：非排除目标必须具备 source path、USD prim path、`verified=true` 和 `review_version`，人工复核排除目标可没有 USD prim path 但必须具备 `excluded_reason`、`verified=true` 和 `review_version`，防止 P1-05 自动候选绑定结果绕过人工复核进入正式 release，也防止为了通过 gate 伪造 prim path。`--require-fresh-clone` 会要求 fresh-clone plan 和 report 均已提供。`--reset-state-report` 会读取 `airground reset audit-state-run` 的 stored report 并默认对同一 `--run-dir` 重新执行 strict reset state validation；如果 reset/no-residual 长稳证据来自另一个真实 run，可用 `--reset-state-run-dir` 指定复算目录。`--require-reset-state-report` 会把缺失 reset state long-run audit 报告升级为 failure，`--strict-release` 会自动启用该要求。`--soft-reset-full-action-report` 会读取 `airground reset check-soft-full-action-run` 的 stored report，根据 report 内 `run_dir` 重新执行 strict artifact validation，并比对 stored/recomputed status、Nav2 smoke、reset full-action、health、trace validation、surface 和 postflight；`--require-soft-reset-full-action-report` 会把缺失该报告升级为 failure，`--strict-release` 会自动启用该要求。`--strict-clean` 会把 dirty repo/submodule provenance 从 warning 升级为失败，`--fail-on-warn` 会把任意 warning 作为失败发布门。提供 `--run-dir` 时，还会要求 release manifest 的 `run_artifact_dir` 等于当前 `--run-dir`，并重算 run artifact index 与 release manifest 比对，同时校验 run manifest、单 episode root artifact 或 multi-episode `episodes/<episode_id>/` 下的 events/summary/termination/trajectory/metrics validation artifact，以及可选 MCAP，并重算 evaluator/oracle artifact 来确认 summary 和 trajectory 没有漂移。`--require-metrics-evidence` 会进一步要求 detection/confirmation、UAV/UGV pose、能耗和通信证据完整，并要求 `run_manifest.json` 声明真实 Isaac/ROS `runtime_backend`（`simulator=isaac_sim`、`ros=ros2`、`simulator_version`、`ros_distro`）；`mode=contract` 的 run artifact 即使包含手工能耗事件也会失败。该命令只固定发布证据表面；reviewed P1-11b public/hidden 真实 oracle、reviewed public 60 episode 资源稳定性、reviewed fresh-clone 真实 episode 复验、reviewed strict-release preflight、GUI/headless 长稳、production reset orchestrator 和 release tag freeze 已完成，RayFronts/VLFM public/hidden full-mission 长稳仍以 `IMPLEMENTATION_PLAN.md` 的后续完成定义为准。

生成性能/长稳发布报告：

```bash
.venv/bin/airground release performance-report \
  --run-dir path/to/real-run-dir \
  --resource-trace path/to/resource_trace.jsonl \
  --min-episodes 60 \
  --max-system-memory-growth-mb 1024 \
  --max-gpu-memory-growth-mb 512 \
  --max-gpu-memory-fraction 0.95 \
  --output path/to/performance_report.json
```

`resource_trace.jsonl` 每行至少包含 `timestamp_s` 或 `time_s`，并可包含 `cpu_percent`、`system_memory_used_mb`、`gpu_memory_used_mb`、`gpu_memory_total_mb` 和 `oom_killed`。报告会从 `run_dir` 重算 oracle/metrics 一致性，默认要求真实 Isaac/ROS backend、全部任务成功、真实能耗证据、无 OOM、资源样本数达标，并记录系统内存/GPU 显存峰值、last-minus-first 增长和 peak delta；`--max-system-memory-growth-mb` 与 `--max-gpu-memory-growth-mb` 可把持续增长升级为失败发布门。`release checklist --performance-report` 会重新计算该报告，防止手工篡改。该报告是发布证据门，不替代产生 run artifact 的真实 60 episode 运行。

`faults run-contract --all --output` 可生成 fault report，`release checklist --fault-report` 会校验报告覆盖全部 fault scenarios 且每项终止 reason 与 fault catalog 一致；`--require-fault-report` 可将缺失故障注入报告升级为失败发布门。该报告表面不替代真实 Isaac/ROS 故障注入。`release repro-plan`/`release repro-report` 固定 fresh-clone 复现计划和结果报告 schema；默认计划包含 clone、submodule、Python install、doctor、assets manifest、contract tests 和真实 Isaac/ROS episode smoke。`repro-report` 会把缺少 expected artifact paths 的 required step 判为失败，并可在 step result 中记录产物 SHA-256；提供 `--artifact-root` 时会从 fresh-clone checkout 自动读取 `artifact_paths` 并计算 SHA-256。`release checklist --fresh-clone-report --fresh-clone-plan` 会校验报告 schema、status、真实 episode smoke 标志、plan checksum、fresh-clone checkout commit、expected artifact paths，以及 expected artifacts 是否带 checksum 证据。`repro-report --repo-root` 或 `--repo-commit` 应记录 fresh-clone 实际复现的 commit；缺失 commit 会产生 warning，commit 与当前 release repo 不一致会失败。该命令只固定发布证据表面；reviewed fresh-clone 真实 episode 复验已由 `docs/development/archive/isaac6/release/fresh-clone-reviewed-release-evidence.md` 记录，reviewed strict-release preflight 已由 `docs/development/archive/isaac6/release/release-reviewed-strict-preflight.md` 记录，最终 release tag/materials 仍以 `IMPLEMENTATION_PLAN.md` 的发布级完成定义为准。

## 7. 0-shot 与隐藏测试规则

RAVEN-AirGround 首版按 0-shot benchmark 设计，不设训练集。算法开发只能使用：

- 公开文档
- 公开配置和 schema
- 公开 `public` episode manifest
- 公开 observation/action API
- 自身 observation、动作反馈和通信 inbox
- 文档化的公开调参配置

禁止行为：

- 读取 hidden manifest、hidden GT、hidden seed、oracle trace 或私有评分文件。
- 通过 ROS topic、Python 对象、文件路径、debug info 或 simulator internals 绕过通信模拟器共享真值。
- 在公开集上手工写死 episode id、目标坐标、确认区域或 oracle 路径。
- 使用公开 episode ID、seed 或排序规则反推出隐藏起点与目标。
- 将隐藏测试运行日志、传感器记录或私有 checksum salt 提交到公开仓库。

允许行为：

- 在公开集上调试算法和记录公开指标。
- 使用 `contract://oracle` 或 toy traces 验证本地 evaluator、artifact 和提交格式。
- 在不访问 hidden 数据的前提下使用公开模型、公开语义先验或自有算法。

正式报告必须同时披露公开集配置、代码版本、模型权重 checksum、推理耗时、硬件环境、是否使用传感器 MCAP，以及所有非默认参数。
UAV 建图与 GT 可见性诊断：真实 VLFM smoke 可设置 `AIRGROUND_VOXEL_DIAGNOSTIC=1`，在 `reset_support/voxel_diagnostic/` 导出 mapper 实际输入的 RGB、深度、位姿、仿真时间戳和原始体素快照。运行 `scripts/inspect_uav_gt_voxels.py --diagnostic-dir <dir> --gt <reviewed-targets.json> --target-class "bus stop" --output-dir <review-dir>`，可用 reviewed GT OBB 离线高亮 UAV 地图体素并筛选候选原始帧。目标标签只来自 GT，不来自检测/语义分数；当前 reviewed GT 只有 OBB，没有精确逐体素标签，故高亮交集不能单独证明目标表面被看到。OBB 与深度只提供代理筛选；是否真正无遮挡、目标是否清晰，仍须检查原始帧并在必要时做 Isaac mesh raycast。该产物不进入算法输入或 UGV 评分。

若需要场景 mesh 级 GT 表面体素，可在 Isaac/PXR 环境运行 `scripts/export_gt_target_mesh_voxels.py --stage <scene.usd> --gt <reviewed-targets.json> --candidates <prim_candidates.json> --instance-id <id> --uav-map <map_*.npz> --output-dir <dir>`；再向上述筛帧工具添加 `--instance-id <id> --gt-mesh <gt_mesh_surface_voxels.npz>`。USD prim 仅通过 reviewed OBB 与候选清单匹配并记录误差，属于离线推断，**不**回填正式 GT。mesh 表面体素与 UAV 地图重叠、深度粗筛候选以及原图无遮挡判定是三种不同证据。


# Type I 恢复验证（历史摘要）

Type I（单类目标）的恢复验证目标是让"UAV 自主检测 → UGV 到达"这条 lane 至少一次闭环。2026-09-13 起先后修掉：航点上限与上游 frame 语义不一致、Ray/Frontier 双航点路径覆盖、ZED mount 静态位姿、mapper 参数与上游对齐（max_rays_per_frame / vox·ray accum period / 分辨率）、语义深度标定与 occupancy 算法等；`smoke_20260915_090354_type-i` 之后检测门可稳定通过。

当前状态（2026-10-05）：Type I 的 **K≥1** 已于 2026-09-22 达成（`K=1/M=2`：真检测被派发并到达，假正例被目标解析 fail-closed 拒绝）；K=2 仍取决于检测质量（见 `UGV-OGN-CalibrationGate`）。`UAV-AwayFacingRecovery`（固定相对 yaw 的冷启动鲁棒性）仍未验收。逐轮记录见 `docs/development/CHANGELOG.md`（2026-09-13 → 09-16）。本页原有的性能/RTF 逐轮记录已并入 [一分钟性能与巡游证据](development/ugv-ogn/nav2-60s-cold-warm-20260930.md)。
