> 用户暂停（2026-10-19 16:46）：持续目标已paused；两个后台队列均Ready，相关诊断进程为0。新Construction地图保存52/70块、3302912格；后续四项GPU诊断未启动。保留STOP断点，等待用户明确恢复。

# RAVEN-AirGround 实施计划（活文档）

> 版本规范（2026-09-30）：当前运行环境为 Isaac Sim **4.5.0 / ROS 2 Humble/Jammy**；运行位置遵循根 AGENTS.md（LFT-W02）。本文中所有 **6.0.1 / Jazzy** 的命令、版本下限、报告和证据均为**历史归档**，不作为当前运行指令；历史版本号与 checksum 保留原值。
>
> 本文件只维护当前状态、阶段总结、开放任务和发布决策。详细证据按主线放在 `docs/development/simmt/`、`docs/development/ugv-ogn/`、`docs/development/evidence/<主题>/`，6.0.1 时代证据在 `docs/development/archive/isaac6/`，逐日流水在 `docs/development/CHANGELOG.md`；总索引 `docs/development/README.md`。
>
> 写作规则（2026-10-05 起，2026-10-12 重申）：不向本文追加"记账式"长段落。新证据先写入对应主线目录的 evidence 文档，本文每个任务只保留勾选状态、一到三行结论（含剩余风险）和证据链接。2026-10-12 整理时迁出的条目原文在各主线目录的 `plan-log.md`。

## 1. 当前结论

### 交付进度

- 项目主线是 UAV+UGV 协同语义搜索 + UGV 地面确认 benchmark；实际基础为 Isaac Sim 4.5.0、ROS 2 Humble/Jammy、PX4 SITL、官方 Quadcopter、Clearpath Jackal、RetroNeighborhood、RayFronts/VLFM；6.0.1/Jazzy 路线只作历史归档。
- Batch B1-B4 已完成（真实物理、真实 GT、任务/数据划分、系统运行闭环）；Batch B5（评测与发布闭环）未完成，卡在 RayFronts/VLFM 正式 public/hidden 重跑，见 §3。
- **UGV 侧里程碑（2026-10-05）**：31 目标巡游在真实 Isaac/ROS 上完成闭环——31/31 全部到达、129/129 航点成功、零脱困，`exit 0`、metrics ok，`tour_navigation_audit.json` 与运动轨迹两份审计同报 **K=31/31**。任务 catalog 重算为 **10/10 ok**（31 个论文实例全部 ground-reachable）。
- **GT-AABB ROI 搬运审核（Phase B/C）已取消（2026-10-05）**：全部 31 个实例联通可达，无需搬运目标或重导场景；Phase A 全图分析、单卡 raycast 与 0.05 m 候选导航包保留为现行地图依据，见 §6。
- **单进程多任务并行（P0-Sim-MultiTask）已完成（2026-10-13）**：3 进程 × 10 任务验收通过，每任务 RTF 0.46–0.50；论文协议对标主线 `P0-UGV-OGN-Benchmark` 恢复为 P0，此后的评测默认在多任务运行时上进行（见 §6）。
- 当前主力阻塞：**算法侧语义检测质量**（UAV 自主搜索 → detection → UGV 这条正式 lane 尚未合格，`UGV-OGN-CalibrationGate` 未勾选）。其余未完成项：Type III/多目标循环验收、三类任务 smoke 视频、redacted aggregate、性能与发布门。

### 运行与验收红线

- 运行位置：LFT-W02 的 `~/jun` 工作区（4.5.0 / Humble）；本地只做编辑、commit/push、同步和审阅已拉回 artifact。本地 `.venv` 只允许离线 CLI/schema/审计，不替代服务器运行结果。
- 资源门：`airground run --mode isaac` 强制 host/容器双层 resource guard（CPU/memory/memory+swap/PID/private IPC/shm 硬上限 + 运行期 monitor），guard 不得关闭；LFT-W02 使用 `lft-w02-rootless-no-cgroup` profile。2026-09-17 用户授权 default profile 的 swap 上限 0.90（RAM 下限 20 GiB、主机 RAM ≤62%、容器 ≤55% 等不变）。
- 文档口径优先于实现乐观假设：未经真实 Isaac/ROS/Nav2/PX4 复验的 WIP 代码或 host-only 测试不能修改 checkbox，也不能写成成绩。
- **no-score policy**：`collect_runtime_metrics_smoke.py`、contract run、离线 evidence bundle、host-only 测试和毫秒级/近零路径 artifact 都不是 benchmark 成绩；RayFronts/VLFM 正式 full-mission 成绩仍为"未测得"。
- **物理可信下限**是硬门槛：TTC ≥ 5.0 s、D2C ≥ 1.0 s、UAV 3D path ≥ 1.0 m、UGV planar path ≥ 1.0 m，且必须齐备 PX4/AirStack UAV-control、Isaac PhysX LOS communication、UGV Nav2 reached、confirmation-region membership、sensor/continuous visibility 与 occlusion-clear evidence。
- 在 full-mission public/hidden 重跑通过前，不移动或重建 `benchmark-v1.0-retro` tag。
- 运行方式（用户 2026-10-12）：默认单卡 1 个 Isaac 进程跑一个出生点的完整 10 个任务；只有最终验收才用 3 进程 × 10 任务（同一场景三个出生点）。启动前卡需空闲 > 60 s 且没有其他用户的评测 lane；runs/ 保持在 50 GB 以下。

### 当前可引用口径

| 内容 | 口径 |
| --- | --- |
| 环境与任务框架 | 可引用：Isaac Sim 4.5.0、ROS 2 Humble/Jammy、Quadcopter、Jackal、dock、RetroNeighborhood、traversability GT、confirmation region、paired starts、public/hidden split 和指标工具均已具备真实证据。 |
| UGV 中心指标与任务集 | 可引用：`Progress/PPL/SR/SPL`（含视锥朝向门与表面式 reach 集合）、10 任务 catalog（10/10 ok）、31 目标全图可达性与导航验收（K=31/31，双来源审计）。 |
| RayFronts/VLFM 依赖与接口面 | 可引用为 smoke/preflight/interface evidence：dependency、semantic encoder、mapper hypothesis、selected behavior、render+file-backed intrinsics、communication bridge、TaskGate/UAV-control adapter/evidence gate、sensor-trace confirmation builder、Isaac-resident evidence surface 均已接入；reviewed-public 单集 full-mission proof 已过 physical mission gate。 |
| P2-11s/P2-11t public/hidden60 | 不可引用为成绩：这些产物是 metrics surface smoke（毫秒级确认、近零路径）。 |
| RayFronts/VLFM full-mission benchmark | 正式结果仍"未测得"：需用 `--require-rayfronts-physical-mission` 重跑 reviewed public 60 与 hidden 60 同一 gate 后才能报告。 |
| 物理可信性判断 | 必须同时满足时间/路径下限与完整证据链；耗时越短不代表越好。 |

## 2. 近期状态

按主题记录仍影响当前判断的状态；更早的逐轮历史在 `docs/development/CHANGELOG.md` 与 `docs/development/archive/`。

### 单进程多任务并行（2026-10-10 → 10-13，已完成）

- 从每卡 1 个任务（Kit 主线程单核 89–100%、GPU 约 10%）做到每卡 1 个进程 10 个任务、三卡 30 任务同时运行，每任务 RTF ≥ 0.46。逐轮证据 `docs/development/simmt/evidence-01…08`，详见 §6 已完成节。

### UGV 目标巡游（2026-10-01 → 10-05，已闭环）

- **验收**：31 个论文目标全部到达。最终一轮 `runs/p0_ugv_ogn/20261005_tour31_final`（预算 3600 s，实际驱动到 sim ≈2100 即由 `ugv_lane_goal_reached` 收尾）：129/129 hop 成功、逐腿路线 1.4–204.8 m 全部在严格阈值 240 下求得、最大自身格代价 238、零失败零脱困；`exit 0`、metrics ok；`tour_navigation_audit.json` 与 `.motion_trace.json` 双来源 K=31/31。
- **关键机制**：注入车道改为"实时 costmap 上求最短可通行路线、终点落在实例 [1.5, 8.0] m 到达带"（`_shortest_passable_route` + 逐实例 id），弃用净空/走廊/via 启发式；到达朝向由用户口径固定为"朝发来的原始点"。
- **调试史一句话版**：卡死根因链依次证伪缘线台沿、指令流抖动等假设，收敛到驱动标定 + 路由模型失真；口径在 10-03/10-04 三次修正（视锥朝向门、到达朝向、K 与算法解耦）；10-05 查出并修复最优路由的三个真实缺陷（OBB 形状丢失、粗格非保守采样、hop 失败无重规划）。
- 详细证据：`docs/development/ugv-ogn/nav2-60s-cold-warm-20260930.md`。

### 地图与 GT（2026-09-30 → 10-05）

- GT-AABB 全图（0.10 m 决策图 + 0.05 m 候选导航包 `p1_03_single_gpu_0p05_full_20260930_r2_native`）完成并通过 validate；31/31 几何目标归属、30 个可靠绑定；单卡 CUDA/Warp raycast 实测查询/回传 0.475 s。
- 红车绑定恢复完成（撤销旧排除，重新生成到达集）。
- 31 个实例全部联通可达（catalog 10/10 ok，2026-10-05 重算）；因此搬运审核 Phase B/C 取消。
- 巡游使用的 Nav2 地图即上述 0.05 m 候选包（`retro_gt_aabb_0p05_candidate.nav2.yaml`），"真实 Nav2 行驶门"由此关闭。

### 检测链（最新记录 2026-09-22）

- detection lane（UAV 全自主：搜索 → 语义检测 → UGV）最好记录为 `smoke_20260922_064731_type-i` 的 **K=1/M=2**（budget 120）；离线复现显示语义分数不可分（真/假正例都 0.96–0.99，"bus stop" 稳态 0.2000 = 1/5 标签），且搜索覆盖不足（bus_stop.0001 整轮未入镜）。
- 一个 300 s 预算的复跑（`smoke_20260922_074555_type-i`）已启动，结果未在本计划回填；`UGV-OGN-CalibrationGate` 仍未勾选。
- 相关修复（mapper 空缓冲、voxel 2D 拜访判据、起飞甩头、门时钟改仿真秒等）均已合入并有真实复跑证据，见 CHANGELOG。

### UGV 中心口径迁移与 FIFO（2026-09-13 → 09-21）

- `task_catalog.py` 与 `ugv_progress.py` 落地（10 任务、`Progress/PPL/SR/SPL`、Held-Karp `d_K`、2D traversability 最短路、视锥朝向门）；AGENTS.md、benchmark/README.md、benchmark_zh.md 全部改为 UGV 中心主口径，legacy 全链降级为诊断 lane。
- UGV FIFO 多目标并发导航落地：UAV 搜索跑满预算、detection 去重入队、UGV 独立线程并发导航、单目标失败只跳过、预算耗尽取消在飞目标。
- 注入诊断通道（`--ugv-inject-goal-position-m`）在 09-20/09-21 首次达成 K==2（bus stop 两实例），此后作为 UGV 侧验收主通道。

### full-mission runner 收敛史（2026-09-10 → 09-14）

2026-09-10 起运行位置迁回 LFT-W02；期间收敛了环境迁移（Isaac 版本降级 4.5.0、driver 550.144.03 固定）、渲染/同步加载缺陷、UAV 控制门、mapper 空缓冲与语义深度标定、PX4 估计器健康门与仿真标定偏置等一批真实缺陷，并交付一键 smoke/热启动入口（热启动 34.6 s）。逐项记录见 CHANGELOG 与 `docs/development/archive/`。

## 3. 批次交付门

| 批次 | 状态 | 当前结论 | 未闭合边界 |
| --- | --- | --- | --- |
| B1 真实双机器人物理闭环 | 已完成 | Quadcopter/PX4 60s hover / 10m waypoint、Jackal 60s static / 10m straight precision、Jackal/Nav2、dock/takeoff、contact impulse、RetroNeighborhood 地面物理和双机器人 headless smoke 均有真实证据。 | 无当前非发布阻塞。 |
| B2 真实场景真值闭环 | 已完成 | Isaac raycast、Jackal footprint sweep、traversability NPZ/Nav2 map、GT-AABB 全图与 0.05 m 候选包、target USD/OBB 人审、confirmation region 可见性均已完成。 | 无当前发布阻塞。 |
| B3 任务与数据划分闭环 | 已完成 | reviewed public 60、hidden 60、difficulty 三轴、paired starts、oracle 完成性和 hidden redaction 均已完成。 | hidden 细节继续保持私有。 |
| B4 系统运行闭环 | 已完成 | 真实 adapter、5 Hz barrier、通信 LOS、reset/run/record/termination、RayFronts/VLFM mapper/smoke surface、full-mission runner、UAV-control adapter、anti-smoke gate 和 host resource guard 已完成。 | 无当前非发布阻塞。 |
| B5 评测与发布闭环 | 未完成 | UGV 中心指标、artifact surface、public/hidden split、release tooling、RayFronts physical-mission gate 已完成；UGV 侧 31/31 导航验收闭环。 | 需用正式 gate 重跑 reviewed public 60 与 hidden 60；release tag 未授权移动。 |

## 4. 用户目标验收矩阵

| 层级 | 状态 | 总结 |
| --- | --- | --- |
| 模型/物理仿真层 | 完成 | Quadcopter 60s hover / 10m waypoint；Jackal 60s static / 10m straight precision；dock 平台、UGV 场景、地面物理、双机同步。 |
| 场景层 | 完成 | Traversability GT、目标 USD/OBB/instance id、人审排除、ground reachability、confirmation region、真实 PhysX raycast、GT-AABB 全图与 0.05 m 候选包、连续 sensor-frame visibility。 |
| 任务层 | 完成 | 成对起点、UAV 从 UGV 平台起飞、单目标/多目标/顺序目标 episode、visibility/detour/occlusion 难度划分、10 任务 catalog（10/10 ok）。 |
| 系统层 | 完成 | 双机器人同步仿真、统一 observation/action API、通信模拟器、自动 reset/run/record/termination、full-mission entrypoint、UGV 目标 FIFO 与最优路由注入通道。 |
| 评测层 | 部分完成 | UGV 中心指标链路（`Progress/PPL/SR/SPL` + 视锥门 + 双源审计）与 31/31 导航验收已完成；RayFronts/VLFM 正式 public/hidden full-mission 成绩仍"未测得"（依赖检测质量门与正式重跑）。 |

## 5. Phase 总览

| Phase | 状态 | 总结 |
| --- | --- | --- |
| 0-12 基础与环境 | 完成 | 仓库/子模块/规范、Isaac 4.5 资产与版本固定、UAV/UGV 迁移、dock 与双机同步、RetroNeighborhood 物理、traversability GT、目标实例与确认区域、episode 与难度、PettingZoo/ROS 2 API、通信模拟器、reset/run/termination。 |
| 13 RayFronts 协同 baseline | 部分完成 | surface、mapper-derived hypothesis、VLFM encoder、file-backed intrinsics、selected behavior gate、full-mission runner、UAV 控制适配均完成；检测质量门（CalibrationGate）未过。 |
| 14 指标与记录 | 部分完成 | 全链指标与 artifact consistency 完成；UGV 中心指标（含视锥朝向门）完成并通过 31 目标验收；RayFronts/VLFM 正式成绩未测得。 |
| 15 测试、性能与发布 | 未完成 | checksum/fresh clone/fault injection/strict preflight 工具完成；单进程多任务并行（P0-Sim-MultiTask）已完成，30 任务并行每任务 RTF ≥ 0.46；发布门见 §6/§7。 |

## 6. 当前开放任务

### P0-UGV-OGN-Benchmark（主线；2026-10-10 曾降为 P1，2026-10-13 P0-Sim-MultiTask 完成后恢复为 P0）

- [ ] **Scene-GT-Handover（2026-10-17）**：按用户交接 PDF 适配后续九场景；本机授权沿用。
  - [x] S0/CPU：统一十场景 `SceneId`，九个新场景各 4+3+3 论文任务；参数化候选池、论文任务过滤、到达集类别选择、smoke 起点选择、30 集构建与任务 ID 评分解析。保留 Retro 编号和 31 目标验收门；Type III 过滤保留顺序；跨场景输入拒绝混用。验证：130 项核心/场景测试 + 25 项相关 CLI 测试通过，实际 FireAcademy CLI 转换/catalog exit 0。AirStack `airground` 提交 `d3f829bb` 已本地登记并暂存顶层 gitlink。证据及命令见 `docs/development/ugv-ogn/scene-gt-adaptation-20261017.json`。
  - [ ] S0/runtime：`run_roi_analysis.py` 的场景路径、0.10 m 文件名和 CUDA 31 目标门，`generate_traversability_raycast.py` 的场景 metadata，以及双机器人 launch/支持平面范围仍需参数化并在兼容 GPU 上验证。不得把其他场景的 legacy PX4 launch 当作双机器人模板。 下一有界阶段：ConstructionSite 在独立副本完成传输哈希/依赖/坐标预检，再以现有 14 GiB 原生诊断入口生成未审核两视角材料；缺失绑定保持未绑定，优先暴露真实资产问题。
  - S0/runtime 本轮代码（2026-10-19）：原生分块/后处理及地图比较已参数化 scene_id/目标哈希/论文类别；正式 ROI 默认 0.05 m、动态文件名/路径和精确目标身份校验，共享 AirGround raycast 接收显式资产。Retro 31 目标与所有资源门保留。58 项 CPU 回归通过；原生 ConstructionSite 两窗口 PhysX 对照通过；完整双机器人实测尚未完成，不勾选 S0/runtime。证据 `docs/development/ugv-ogn/construction-adaptation-20261019.json`。
  - [ ] S0/S8 可见性入口场景契约：现有 `validate_confirmation_visibility_raycast.py` 仍可对新场景标注默认加载Retro。补充显式场景资产/可选预期SHA、启动前场景一致性拒绝及独立资产来源记录；沿用所有可见性参数和人工审核规则。纯CPU检查只验收入口保护，正式S8仍须审核输入和真实PhysX。 实现已本地提交AirStack e427fbf3，4项选择保护及1项既有adapter绑定检查通过；未运行新场景正式S8。共享双机器人启动器已有AIRGROUND_ENV_URL；z=0支持为无限PhysX Plane，128m旧尺寸仅为审计兼容字段，不能误判为地图边界限制。
  - S0/S8路径核查：CPU重现Pegasus引用语义，四个导出资产defaultPrim均为/World；引用到/World/stage后，Retro165/ConstructionSite25/Factory1个原绑定路径均需额外stage层。已加缺失路径拒绝，提交10d18eba，6项CPU检查通过。显式reference-root映射已实现，仅在内存投影路径；世界矩阵/包围盒及原GT非路径字段检查通过，共191条路径，7项CPU检查通过，提交250474bc；真实共享启动器尚待验证。不得修改原GT、坐标或verified。原生直接open_stage的地图/导航诊断不受此路径问题影响。
  - [x] 资产准备：官方 ZIP 4,541,378,641 bytes、SHA-256 `cc20fb05345f93577d20321de25c9435d1e0ccf63d8fa3e0c876f4a9b7120280`；解压三个新场景 908 文件并逐项 CRC 校验，保留 Retro 修复。官方包不含其余六场景。
  - [x] S1：九场景 164 个实例完成转换，显式零 spawn offset 保留上游世界坐标；运行时坐标对齐仍待核对。输出 `runs/scene_gt_adaptation_20261017/<scene>/targets.converted.json`，全部 `verified=false` / `ground_reachable=unknown`。
  - [ ] S2–S3：ConstructionSite 649 候选、25/28 暂绑（25 歧义、3 tarp 未绑）；AbandonedFactory 135 候选、1/11 暂绑（1 歧义）；FireAcademy 主体为单个合并网格，名称候选为 0。已有绑定报告、几何近邻诊断和台账模板；需真实 RGB 核对层级、网格分组及 OBB，禁止仅放宽距离阈值强行绑定。
  - S2–S3 面级候选诊断（2026-10-19）：`audit_annotation_mesh_faces.py` 在 `/World/stage` 范围审计 FireAcademy 3,966,071面主体及96面圆柱；13个原标注均得到几何候选，保存OBB局部AABB粗筛/顶点均值包含/全顶点包含面ID与材质子集、USD/源码哈希。旋转/跨边界2项测试通过，实际只读诊断exit0。初版包含默认环境辅助mesh，保留后以显式场景根复跑a02；输出 `runs/fireacademy_adaptation_20261019/face-candidates-a02/`。不证明语义归属，不写入绑定或verified，仍需真实图像和人工审核。
  - [x] Resource-Download（2026-10-18）：从官方历史 Google Drive 文件夹补下 AbandonedCity、DowntownWest、MilitaryBase、ModernCityDowntown、Shipyard 五个根 USD（1,353,809,419 bytes）；从公开 Nucleus 补下 SnowyVillage 根层（17,862,348 bytes）。六份根层/asset 字段可读取，五场景各 3 个网格样本读取通过，记录长度和 SHA-256；隔离保存在仓库外缓存，未覆盖现有场景。公开依赖另外缓存 30 文件。完整依赖仍受上游 Nucleus 权限阻塞，证据：`docs/development/ugv-ogn/scene-resource-recovery-20261018.json`。
  - [ ] 缺失输入：六个场景的根 USD 已于 2026-10-18 取得到隔离缓存，仍需补齐完整贴图、材质、模型引用和版本；AbandonedFactory 缺 `SubUSDs/materials/Ground.mdl`。FireAcademy 需有实例结构的资产或经审阅的面级目标归属方案，不能把整个场景 mesh 直接当作每个目标。
  - 其他场景独立预检（2026-10-19）：AbandonedFactory 1,643 prim，1候选坐标一致/10未绑定；确认为真实 MDL 缺失的仅 `Ground.mdl`，另348项为 Unreal 来源元数据。FireAcademy 198 prim/13未绑定，离线未解析的 `OmniPBR.mdl` 已确认存在于 Isaac 4.5 内置 MDL 目录，尚未做真实材质渲染。已准备13目标/26视角上下文清单并完成377个 FireAcademy 原始资产到隔离副本的传输/CRC/SHA逐文件校验（不等于渲染通过）。两份只读 pxr 预检 exit 2 如实保留，不冒充通过；证据 `docs/development/ugv-ogn/additional-scene-preflight-20261019.json`。
  - AbandonedFactory 材质依赖细查（2026-10-19）：Ground.mdl唯一实际绑定为 `/World/Environment/ground`，USD可见性invisible、无CollisionAPI；不是工厂可见模型地面。缺失依赖仍记录，但不阻塞几何预检/隔离资产传输与有界诊断渲染尝试；不猜测替换材质。证据 `runs/additional_scene_preflight_20261019/AbandonedFactory-ground-material-usage.json`。199个实际资产已隔离传输/逐文件SHA校验，11目标22视角清单及10个未绑定实例的面级几何候选完成，未绑定/审核状态未改；证据 `factory-adaptation-20261019.json`。
  - [ ] S0/S5 合并网格碰撞预检：FireAcademy 主体396万面、AbandonedFactory 16个大型复杂网格当前采用convexDecomposition；离线尺寸/面数只构成风险提示，不证明真实碰撞错误。先生成少量固定XY的源三角形垂直交点基线，再在隔离诊断入口以真实PhysX逐点比较。无绑定的场景使用明确的纯几何坐标锚点，不制造目标绑定、不更改GT；保持z=0平面、0.05m和资源门，确认后才考虑完整地图采样。
  - [ ] S0/S5其他五场景碰撞覆盖预检：对已可读取根USD的AbandonedCity、DowntownWest、MilitaryBase、ModernCityDowntown、Shipyard，在CPU隔离进程内检查实例代理/碰撞覆盖、现有profile应用前后差异及大型凸体风险；每场景180s/8GiB上限，仅session层修改，不保存原USD，不运行GPU、不把分类结果当作真实PhysX。SnowyVillage仍因197缺失资产没有有效几何，跳过依赖。
  - [ ] S0/S2 六个不完整资产包的独立几何审计：已下载根USD只做过三网格抽查；在每场景180s/8GiB CPU虚拟内存限额内遍历可读取网格，记录顶点/索引有效性、世界范围、原始根变换及标注的粗包围盒候选。缺失材质/贴图仍阻塞真实RGB审核和完整依赖验收；几何诊断不改原USD、不写正式绑定，也不将可读取根文件等同完整场景。
  - S0/S2 CPU审计结果（2026-10-19）：六个根USD审计完成并归档45文件SHA/CRC；AbandonedCity 19,295、MilitaryBase 4,303、ModernCityDowntown 9,657、Shipyard 5,032个mesh可读取，四项exit0；DowntownWest可读6,026个，另28个声明无顶点/索引（不是仅材质缺失），exit2；SnowyVillage有745条组合引用错误/197个缺失资产，0有效mesh，exit2。另五个场景生成原始路径名称候选及未应用绑定建议，分别7/22、11/42、14/14、7/7、6/17；有歧义，不能当作正式绑定，所有原标注哈希未变。证据 `partial-scene-geometry-20261019.json`、`runs/partial_scene_geometry_20261019/查看几何预检.html`。仅主机pxr0.26.8 CPU结果，尚未确认Isaac4.5/4060整场景可运行。
  - [ ] S4：兼容环境下渲染 RGB 与 hybrid review packet，逐实例核对类别/OBB/prim，完成真实 verify/exclude ledger 后 apply-review 和 audit。AbandonedCity 缺 car/yellow motorhome 标注；SnowyVillage tower/water tower 和 Shipyard `ship silo` 原文解释待确认。2026-10-19 ConstructionSite 首轮真实渲染在材质编译时达到 840 s 保护截止，0/56 张 RGB；峰值提交 8.058 GiB，失败包已归档，未冒充 S4 通过。第二轮construction-review-a02在601.33s因Camera stable-frame deadline失败，0/56 RGB，峰值11.656GiB；21文件失败包已回传核验，任务结果1，guard未记录子进程exit_code，不臆造该值。两窗口真实 PhysX 对照随后通过；全图 4,395,972 格/70 块首批已正常结束，保存19块/1,224,192格（27.85%），全图未完成。当前先将原生 review 入口参数化到 ConstructionSite，允许未绑定实例仅按原始 OBB 拍摄上下文，并明确记录 unbound；不编造 candidate，不自动批准。原生分块采样/后处理的 scene_id 和目标数量随后从经校验输入推导，保留 Retro 回归及跨场景拒绝检查。
  - [ ] S5：从全部目标 OBB 的 AABB 加 2 m 取 ROI；真实 Isaac/PhysX 或经校验 Warp raycast，分辨率 0.05 m、z=8→-2、normal≥0.35、障碍高度 0.05–1 m；与运行时相同的 z=0 支持平面。各场景 `raycast.request.json` 仅是参数草稿，不是 GT。
  - S5 诊断进展（2026-10-19）：ConstructionSite `construction-tiles-a01` 两个 160×160 窗口/51,200 格/314,976 射线，14 字段整块与分块逐值完全一致（含块缝）；0.05 m 台阶、z=0 支持平面核对通过。exit 0、483.12 s、峰值提交 6.640 GiB；原始日志保留薄网格凸分解和 Plywood CPU 碰撞回退警告。归档 `runs/construction_adaptation_20261019/construction-tiles-a01-evidence.zip`（29 文件哈希/CRC 已校验）。`construction-map-a01` 已正常退出0，19/70块（27.85%）、990.27 s、峰值6.185 GiB；保持最多20新块/900 s采样、14 GiB/1200 s总保护，原始断点保存于第二台 `logs/construction-full-map-20261019`；不批准未审核 GT，S5 正式项保持未勾选。
  - S5 自动续采准备（2026-10-19）：在当前 DWB 有界复测结束并清理ROS后，使用有限队列串行运行 ConstructionSite a02–a05（最多4批，每批仍14GiB/1200s、20新块/900s采样）。每批验证正常退出与进度增长，完成70块才运行原参数后处理；失败停止队列并保存日志，不并行GPU、不自动重启、不循环重试。
  - S5 碰撞分类诊断（2026-10-19）：真实 `construction-audit-a01` 退出0/122.59s，厕所附近两点的 Landscape2 碰撞顶部z=1.210654m，绝对障碍带起点即命中；只读源三角形检查同位置视觉表面z=-0.3m。现有名称规则未识别两块 Land/Landscape 地形，将其作为 static_obstacle 做 convexDecomposition，存在人为封闭凹地形的证据。保留正在续采的原碰撞基线数据；准备仅针对两块已测地形的明确 ground 分类候选，独立 source/contract 下做真实射线及窗口A/B，成功后必须重新采样受影响地图，不混用旧块，不修改原始USD/目标坐标或人工审核位。AsphaltRoller/RoadBlock/RoadClosure 等名称误匹配也记录待审计，不通过广泛字符串替换改变所有场景。
  - S5 地形修正有界实测已通过（2026-10-19）：`construction-ground-a01` 退出0/142.69s/峰值6.129GiB。碰撞表核对仅两块Land地形由convexDecomposition变为meshSimplification，682个碰撞体均保留；原USD/目标哈希、z=0支持平面及采样参数不变。两点实际地形命中恢复至-0.3m，绝对障碍带虚假命中消失；厕所8×8m窗口障碍24,160→1,982格、footprint 0→16,219格，另一空地窗口14字段全部保持一致，新配置两窗口整块/分块均通过。3项CPU回归含原Retro完整USD审计通过。旧基线以STOP在块边界正常收尾，36/70块、2,296,320格/52.24%，原始块+110文件已备份，SHA见 `construction-ground-fix-20261019.json` 及 `runs/construction_adaptation_20261019/baseline36-evidence/`。不再续旧碰撞配置；新数据集 `construction-ground-map-20261019` 从零重采，首批groundmap-a01已退出0/752.49s/峰值6.102GiB，20/70块、1,268,736格/28.86%；76文件完整原始断点包回传核验通过，SHA003d511f3d79ea4ed5ccbb83d6e27cecb3368c5b1dfa1c27d47ec065bb80a582。该首批为历史断点，现70/70完成，见下方S5–S7记录。图文证据 `runs/construction_adaptation_20261019/teacher-report/查看进展.html`。
  - S5 局部障碍诊断准备：在独立冻结脚本副本中记录 ConstructionSite 厕所区域与压路机空地的原始向下射线和0.05–1m障碍带向上射线命中（点、法线、prim），不改变碰撞配置、支持平面或已采样数据；用于定位局部不可通行来源。
  - [ ] S6–S7：真实 raycast 输入验证后，以 0.508×0.430 m footprint、16 yaw、15° 坡度、0.05 m 台阶、0.5 m 顶部余量生成地图；reach clearance=0.1075 m、8 连通，按论文目标覆盖数再按面积选连通分量；重建 OBB 表面 1.5–8 m 稠密到达集，导出 Nav2 地图和审计。
  - S7 独立准备：增加只读未审核几何候选导出，锁定后处理报告/地图/目标哈希，沿用已验证 surface_window 距离公式，按实例分别保存所有到达格索引以保留重叠；不写 reviewed targets、不更新 reachable/verified、不填 visible_fraction=1、不进入正式 catalog。先在已有 Retro 全图验证，再用于 ConstructionSite 新图；同时报告重叠格数，避免单标签可视化掩盖多个实例共享到达格。
  - [ ] S8：真实 PhysX 可见性记录；相机 1.2 m、HFOV 90°、1.5–8 m、5 表面采样点、可见比例≥0.2 连续 5 帧。占位 `visible_fraction=1` 不算验证。 原代码可见性距离按中心算，handover可达性明确按OBB表面算：35个大尺寸未审核论文目标在两种窗口下无交集的必要条件已记录，见visibility-distance-compatibility.json。等待协议确认，不改阈值、不排除目标；ConstructionSite无该尺寸必要条件冲突。
  - S5–S7历史诊断（后发现实例漏碰撞，产物已INVALIDATED，不可验收）：当时修正碰撞配置全图70/70块、4,395,972格，0.05m footprint/reach/Nav2导出通过；接缝与两独立窗口对照通过，241文件归档核验。18论文目标完整几何候选保留重叠，2个未绑定蓝篷布仅作为未审核几何；S4缺审核，因此正式S5–S7仍未勾选。证据 `docs/development/ugv-ogn/construction-full-map-20261019.json`。
  - S8未审核诊断准备：ConstructionSite新图完成后，从完整逐实例几何候选中最多取8方向位姿，保持中心/表面原距离门；未绑定目标跳过。按原1.2m/90°/5点/0.2阈值，在5个真实PhysX时间（25步间隔）记录全部原始射线；不使用旧函数返回的“连续5帧”占位，而以实际时间样本计数。目标实际命中、零距离命中及失败位姿全部保留。仅私有观察位姿，不生成正式GT、不冒充RGB或UGV巡游；原资源限额与冻结碰撞配置保持。
  - [ ] S5合并网格碰撞修正诊断：FireAcademy三点实际射线均在Ds_001凸体内部零距离命中，与源三角形高度不符；先保存原基线，再在独立内存场景中仅将该静态合并网格改为三角网格碰撞做同点A/B。保留其他碰撞体、材质、z=0支持面、资源预算和原资产；三个向下命中已与源面一致（误差<1e-4m），仅一个碰撞体变化；140.56s退出0、峰值8.122GiB，38文件归档核验。双面查询a02已检出0.8720466m源表面；采样报告通过但关闭卡住，终止时匹配到guard导致作业回收且无execution.json，39文件包及更正记录已保存，不计正常退出。三128×128窗口/49,152格扩大验证已退出0/152.70s/峰值6.824GiB；14字段整块/分块/接缝差异均0，38文件回传核验。局部诊断通过，不等于全图或正式GT；暂不扩散到其他场景。
  - [x] S6导出完整性：Windows实文件回归已重现CRLF导致YAML声明SHA不符；改为确定UTF-8 LF字节写入，Windows/Linux各2项检查通过。现有3份图的实际SHA均与归档manifest一致，原包保留；详见 `nav2-yaml-integrity-20261019.json`。不代表地图正式审核完成。
  - S4有界续拍准备：ConstructionSite warm-cache a03保存12/56张真实RGB（前6个候选双视角），第13视角480s稳定帧门失败；707.78s/峰值11.731GiB，guard无正常子进程退出码，33文件核验。view-2/10/11明显遮挡，质量合格不等于目标可见；部分审核包已生成，人工批准仍0。准备最多8目标/批，保持原60连续有效帧、960×600、14GiB/840s保护；单视角60s后记录原始失败缓冲并跳过，partial_review保留非零退出，不计完整通过。
  - S6小窗口派生字段更正：历史window reach_component从support/obstacle种子生成，未接车体footprint；现根scripts/probe_tiled_terrain.py已改为footprint后0.1075m/8连通，增加子集检查。五个真实窗口原始采样的CPU重算通过，整块/分块一致；原归档不改。全图后处理本来使用footprint并重算窗口参考，当前冻结采样不受影响；详见window-reach-correction-20261019.json。
  - S0/S4/S8独立诊断有限队列（2026-10-19）：当前地图队列完全结束且无活动GPU进程后，仅依次运行construction-portable-a01、construction-clock-a01、factory-triangle-a01、construction-review-a04，各保持14GiB/840s，无自动重试；正常退出的科学检查失败保留后可继续独立项，资源/启动保护失败则停止。源码50文件校验、重复任务拒绝、源码漂移拒绝、放宽内存拒绝、真实占用检测均已通过。最多等待60分钟；队列运行不代表四项已经实测或通过。 16:38:08已核实等待进程PID42424和任务Running；当前地图44/70、2799616格，队列steps为空。首20块8通道shape/dtype/有限值及SHA全部通过。
  - [ ] S0/S5运行时碰撞接口：将已实测的静态实例展开/精确几何原型碰撞继承做成显式manifest接口；资产SHA、目标/原型几何、动态祖先、引用路径映射和展开前后世界几何均需校验。先CPU实际USD及失败保护检查，再接入运行入口；不能将接口通过写成完整运行时/巡游验收，当前GPU冻结源不变。
  - S0/S5接口阶段结果（2026-10-19）：AirStack airground提交c01d33b1加入显式manifest与可选运行入口，20项CPU检查通过；真实Construction USD原生/引用两种挂载均补全5075网格、5757场景碰撞列表与此前真实PhysX完全一致，源资产未改，CPU峰值322.184MiB。这仍不是新接口的真实PhysX或UGV巡游验收；独立construction-portable-a01已冻结准备，等待单GPU队列空闲。新图a01/a02均正常退出0，40/70块、2537472格；a03继续。首20块120文件已回传逐文件核验，归档SHA9536c52a…。详见static-instance-runtime-interface-20261019.json。
  - [ ] S5碰撞覆盖修正：已确认ConstructionSite 5,075个可见实例代理网格缺运行时碰撞（总网格5,759）；旧70块全图/S7候选已加INVALIDATED侧文件，不能用于导航/验收，须新契约重采。内存展开5,075实例后全部网格几何/变换/可见性字节一致，原USD未变、CPU峰值269MiB；真实PhysX a02预检已退出0/380.03s/峰值8.207GiB：5757场景网格及支持平面共5758碰撞体、缺失0，厕所2/压路机2实际命中恢复，38文件核验；51,200格/314,986射线扩大验证已退出0/265.62s/峰值8.211GiB，14字段及块缝差异0、38文件核验；两个窗口footprint分别减少2090/4328格，确认旧图低估障碍。新契约dc30bf4a…/独立数据集已启动重采；首批20块/900s采样、14GiB/1200s保护，已启动等待首批通过后至多4批的有限串行续采，失败停止，70块齐全后才后处理。见 `construction-instance-colliders-20261019.json`。
  - [ ] S9：重新构建可运行 catalog；每场景选择 3 个满足到达集距离≥1.5 m 且初始不可见的起点，生成 10×3=30 集并审计。当前九份 `task_catalog.blocked.json` 均为 10/10 blocked，未生成冒充真实验收的 episode。
  - [ ] S10：真实 UGV Nav2 巡游取得 K=M，保存轨迹、仿真时间、ROS/TF、可见性诊断及失败日志后，才验收对应场景。主机RTX5060环境曾因Isaac4.5兼容/资源受限；第二台RTX4060现已有真实Isaac4.5/Humble/局部Nav2诊断链路，但九个新场景仍未完成正式巡游。

- [ ] **Local-Scene1-Reproduction（2026-10-17 → 10-18）**：当前用户明确授权本机运行；隔离工具环境、26 个 manifest 资产、场景贴图修复（SHA 与记录一致）、59 个车辆贴图引用及 66 项离线测试均通过。10 月 17 日主机准备阶段受 RTX 5060 / Isaac 4.5 兼容性、WSL 24 GiB 资源限制影响，未启动仿真；10 月 18 日第二台 RTX 4060 电脑已通过真实 Retro 加载、PhysX 抽样和 RTX 相机双视角出图检查，见下方子项。跨系统 ROS、有界 Jackal 运动/里程计/TF、局部地图与点云接入后的单目标导航、连续三目标转弯与一次静态障碍绕行已验收；正式全图、动态障碍、语义任务和论文 episode 尚未验收，精确复现仍缺审核输入，正式 benchmark guard 未修改。前期证据：[本机准备记录](docs/development/ugv-ogn/local-scene1-preparation-20261017.json)，日志：`runs/local_scene1_preparation_20261017/`。
  - [x] Second-PC-Preparation（2026-10-18）：SSH 指纹核对和密钥登录通过；RTX 4060 Laptop 8 GiB / 32 GiB 第二台电脑 D 盘已建立独立 RAVEN WSL，保留既有 ROS 工作区。代码/场景一资产哈希一致，隔离依赖、core doctor、26 个 manifest 文件和 USD 静态检查通过。官方 Windows Isaac 4.5 兼容性检查器 D3D12/RTX 4060 启动成功、PASSED、exit 0；WSL Vulkan 初始化失败。证据：[第二台电脑准备](docs/development/ugv-ogn/second-pc-preparation-20261018.json)。
  - [ ] Second-PC-Runtime：验证 Windows 原生 Isaac 4.5 的真实 Retro 场景加载与显存占用，再适配 Linux ROS/Windows Isaac 启动、通信及受控资源配置；已通过实际渲染、ROS、轮式运动、局部单目标 Nav2 和连续三目标静态绕障；完整多机仿真、审核全图与论文 episode 尚未验收，现有内存保护门未放宽，精确复现仍缺老师的审核 GT/地图/episode 输入。
    - [x] Scene1-ResumableMap-Launch（2026-10-18）：`resumable_terrain_store.py` / `probe_resumable_terrain.py` 实现原子 NPZ+完成记录、哈希/形状/有限性/参数与源码校验、OS 写锁、磁盘 8 GiB 预留、批次数/时长预算及恢复进度；由 `probe_tiled_terrain.py` 复用已验收真实 PhysX 配置。`resume-test-a01` 保存 2 块退出 0，独立 `resume-test-a02` 校验跳过 2 块并新采 7 块退出 0，首次 2 块记录/哈希不变；25,600 格 × 8 原始字段与此前实际整块参考完全一致。`python -m unittest discover -s tests -p test_resumable_terrain_store.py -v` 6 项通过（持久化失败检查，不冒充真实 PhysX）。命令/退出结果与数据 `runs/resumable_map_20261018/`，证据 `docs/development/ugv-ogn/resumable-map-20261018.json`。已启动第二台 `full-map-a01` 全图后台诊断，2026-10-18T22:28:35.5606858+08:00 快照 5/527 块、327,680/32,235,504 格；不是完成结论。守护进程保持 14 GiB 内存/60% CPU/物理内存 4 GiB/提交 2 GiB/GPU 80% 门限，总时限 8 h、采样预算 7.5 h，逐块保存，临时防自动休眠后恢复；正式服务器 64 GiB 门未改。恢复测试计划任务已移除；全图任务在本条启动快照时运行，后续 a01 中断及自清理失败已在 TelemetryRecovery 项记录。当前仅验收恢复和启动，未完成全图后处理、人工 GT 审核或正式 episode。
    - [x] Scene1-FullMap-Completion（2026-10-19）：527 块 / 32,235,504 格 / 0.05 m 原始采样完成，`full-post-a01` 完成磁盘拼接及 8 字段回读一致、无遗漏重叠；全图坡度/台阶重算及块缝超差值 0，两个先前真实 PhysX 窗口的原始字段及 5 cm 台阶配置下 footprint/reach 内部区域对照超差值 0（剔除局部窗口边界影响）。显式 0.508×0.430 m /16 yaw /15°/0.05 m 台阶/0.5 m 顶部余量，footprint 29,275,763 格；其上 0.1075 m 净空及 8 连通 reach 28,880,101 格/63 区域。按论文目标覆盖数、面积选 C0，27,551,898 格/68,879.745 m²，31/31 目标仅几何候选相交，均保持未审核且不可正式计分。生成 footprint/reach/selected 未审核 Nav2 YAML/PGM/NPZ，全部导出格点与上下方向校验通过。命令和退出 0 见 `runs/full_map_postprocess_20261019/full-post-a01/execution.json`；耗时 133.05 s，峰值提交 2.960 GiB，14 GiB 等守护门不变。拼接 2 项检查两台通过，随后新增拒绝已有输出目录以保护旧报告的 CLI 检查，本地 3 项通过，数值算法未变，实际运行源码与加固版本分开保留。证据 `docs/development/ugv-ogn/full-map-postprocess-20261019.json`；图文包 `runs/full_map_postprocess_20261019/teacher-report.zip`。临时采样/后处理任务与进程已清理，数据保留。此项只验收全图诊断后处理，不代表老师地图等价、人工 GT、真实导航或正式 episode 验收。
    - [x] Scene1-FullMap-Nav2Validation（2026-10-19，仅单次全图接入与局部路线验收）：`full-nav-a02` 在原生 Isaac 4.5 / Humble / RTX 4060 上，以哈希锁定 7792×4137 / 0.05 m 未审核全图；32,235,504 格 ROS map 与源 PGM 逐格匹配，全尺寸 global costmap 及实时 local costmap 留存二进制快照，启用现有 lean subscriptions。沿用原三目标位置、朝向和 8 m 位移边界，三个 action 均 SUCCEEDED（4），实际路径 21.717 m，最终误差 0.249 m、停车 0.00186 m/s；采样轨迹未进入不可通行格，扣除车体外接圆后的最小原始障碍净空 0.713 m。1,081 帧接收点云哈希、4,100 组里程计全部匹配 PhysX，单时钟无倒退，154 条规划，七张原始 RGB 与轨迹图已查看。a01 第二目标近距转向漂移，120 s 超时，严格成功 2/3，失败证据保留；a02 每目标诊断预算为 180 s，但该段实际仅 93 s，不能把通过归因于延长时限或宣称稳定性已修复。480/540 s 整轮截止、速度/容差/停车及 14 GiB 等资源保护不变，正式 episode 预算未改。离线地图方向/净空/哈希拒绝/目标预检 3 项两台通过；命令、退出 0、362.42 s 和峰值 Isaac 提交内存 10.804 GiB 见 `runs/full_map_nav2_20261019/full-nav-a02/execution.json`。临时任务、ROS 防火墙和专用 WSL 已清理。证据 `docs/development/ugv-ogn/full-map-nav2-20261019.json`，展示包 `runs/full_map_nav2_20261019/teacher-report.zip`。限制：全局静态图、局部 CPU 点云、PhysX 里程计、未审 GT；支持平面与视觉路面存在高差，规划器偶尔低于 5 Hz，末端收敛波动未解决。只验收本条局部路线，不是 31 目标实跑、正式 episode 或论文复现完成。
    - [ ] Scene1-Nav2-ArrivalStability：基于 a01/a02 的原始 pose/cmd/action 证据，定位近距转向漂移与路径更新对到达判定的影响；在原位置、目标朝向和 120 s 诊断预算下进行有界重复验证，不以放宽容差、取消朝向或只进入到达圈替代成功。 首先在同一场景/轮扭矩/摩擦/120 Hz 配置下，对 direct joint-state 写入与驱动 action 进行独立进程 A/B；记录车体位姿、实际轮速、转向漂移及停车。SDK 本地源码表明前者同时写入速度状态和目标，不能仅凭 USD maxForce 声称状态写入受驱动力矩约束。通过实际短测后才选择候选接口做原 120 s 三目标回归。 2026-10-19 已完成 direct/actions 两个真实 56 s 有界对照，左右转向最大平移分别约 0.387/0.389 m 与 0.362/0.347 m；动作接口未解决漂移，未切换默认或声称稳定性通过。归档及图见 `runs/drive_audit_20261019/`，证据 `docs/development/ugv-ogn/drive-ground-audit-20261019.json`。
      - DWB 原预算三轮对照已完成（2026-10-19）：复用已有 profile，保留原三目标/朝向、0.25 m/0.30 rad 容差、120 s 单目标预算及资源保护。a01/a02/a03 全部退出0，9/9 action成功；但 a03 前两目标在状态消息到达时最新 PhysX 位姿误差0.251970/0.264959m，严格位姿仅7/9、整轮2/3，不勾选稳定性。三轮点云/里程计/32,235,504格源地图交叉一致，原始RGB、轨迹、源码/日志哈希已归档至 `runs/nav2_dwb_stability_20261019/`，证据 `docs/development/ugv-ogn/nav2-dwb-stability-20261019.json`。a03前两目标回报前1秒均无采样同时满足位置和朝向，排查发现 stateful SimpleGoalChecker 与 DWB RotateToGoal 的状态锁存机制；尚无控制器内部判定时刻证据，不能把回报时位姿等同内部判定位姿。默认RPP/轮控方式未改，也不把 authored maxForce 当作状态写入的实际力矩保护。已停止无差别重试，下一步设计同时校验位置/朝向及退出锁存后的重定位方案，再做有界真实验证。临时ROS规则、任务和专用WSL已清理。
    - [ ] Scene1-GroundHeightAlignment：审计 z=0 物理支持平面、视觉路面和轮胎接触高度；先验证高度/碰撞契约，再复核地图及导航，不为修图直接移动机器人或篡改截图。 2026-10-19 已记录五处真实射线：支持平面约 z=0、原道路 z=-0.19126 m，轮心约 z=0.098 m；轮胎 schema/关节轴一致，缓存 extent 异常不作为实际碰撞错误结论。未改变任何坐标或原始资产，视觉高差仍未消除。
    - 到达判定下一候选准备（不改变默认配置）：独立 Nav2 runner 副本令 SimpleGoalChecker 每次同时检查位置/朝向（stateful=false，仍0.25m/0.30rad），DWB内部切换纯转向的窗口从0.25m收紧为0.10m，为已观测平移留余量；原目标/朝向/120s及资源和速度保护不变。该窗口是控制切换参数，不是放宽验收容差。先1次有界真实测试；若失败保存原因，不无限重试。原轮控/物理高差及DWB转向锁存仍是限制，不能靠只切换stateful宣称修复。
      - [x] Scene1-FullMap-TelemetryRecovery（2026-10-19）：a01 在 133/527 块后因单次 GPU 查询超时退出；`run_windows_probe.py` 现为每次查询 8 s、最多容忍连续两次失败，第三次停止，预检仍严格，未知读数记 null，内存/总时限检查与全部资源门保持。5 项故障注入测试在主机和第二台均通过（非真实物理证据）。133 块的哈希/形状/类型/有限值全部通过预检；真实 Isaac a02 跳过 133 块，新提交块已验证，原 133 块记录及 NPZ 哈希未变。2026-10-19T00:16:54.7642264+08:00 快照 135/527 块（26.99%），后台运行中。源码、命令和失败证据见 `runs/resumable_map_20261018/recovery-20261019/`；证据 `docs/development/ugv-ogn/full-map-recovery-20261019.json`。a01 自清理因 Limited 用户权限失败，现同名无触发器任务运行 a02，结束后可能保留 Ready；不会自动重复执行。仅验收修复及续跑启动，全图完成项保持未勾选。
    - [x] Scene1-TiledMap-Validation（2026-10-18）：两个 8×8 m 区域 / 0.05 m 分辨率 / 51,200 个参考网格，真实 PhysX 射线 314,976 次；整块与带一圈 halo 的分块地形、全窗口 seed/footprint/reach 连通结果超差值 0，块缝超差值 0。原生 Windows Isaac 4.5 使用现有 profiled collider、z=0 无限支持平面和 terrain 算法，源码哈希锁定；红车在独立未审核副本中改绑整车根，实际 USD 包围盒核对通过，165 条标注仅该 prim 路径变化，原 OBB 不变。源码 `scripts/probe_tiled_terrain.py` 和 `scripts/probe_windows_scene_render.py`；py_compile、真实数组比较、离线有限性/哈希/目标 schema/副本差异/ZIP CRC/报告链接检查通过。命令和退出 0 见 `runs/tiled_map_validation_20261018/tile-map-a01/execution.json`；耗时 464.00 s，峰值提交内存 8.840 GiB / 显存约 2.428 GiB，14 GiB 进程保护保持，临时任务已清理。证据 `docs/development/ugv-ogn/tiled-map-validation-20261018.json`、图文包 `runs/tiled_map_validation_20261018/teacher-report.zip`。只证明两个窗口的分块一致性；未实测全图峰值内存、未与老师地图比对，正式 64 GiB 入口保护未修改；人工 GT 审核仍 0/31、正式地图/到达集/episode 未完成。下一阶段为可断点续跑的全图诊断生成与全局后处理验证。
    - [x] Scene1-Paper31-ReviewPacket（2026-10-18）：`paper31-review-a01` 在受控原生 Isaac 4.5 中完成 31 个论文实例 / 8 类 / 62 张双视角原始 RGB，实际 USD 候选包围盒 31/31 与导出候选一致；每图连续 60 个有效缓冲帧。已生成可切换红色标注 OBB / 青色候选世界 AABB 的 HTML、XY 位置图、候选层级列表、空白审核 CSV 与待批准台账模板。24 个目标有绑定歧义；重点标出红车误绑 Object_9 零件（体积比 0.204，建议整车根，未应用）和黄车范围差异（3.293）。源码 `scripts/probe_windows_scene_render.py`；py_compile、62 图像完整性/哈希及 31 组包围盒核对通过，原生命令 `runs/paper31_review_20261018/paper31-review-a01/execution.json`，退出 0；峰值提交内存 10.401 GiB / 显存约 3.37 GiB，限额保持，临时任务已清理，未启动 ROS/WSL 或新增网络规则。证据 `docs/development/ugv-ogn/paper31-review-20261018.json`，展示包 `runs/paper31_review_20261018/teacher-report.zip`，视觉抽查范围和遮挡限制见证据。全部 165 OBB + 2 m 的 0.05 m ROI 为 4137×7792 = 32,235,504 格；现有 `run_roi_analysis.py:host_sample` 要求 available RAM≥64 GiB，本机总内存 32 GB 不满足，正式入口与保护条件未修改；分块原生生成方案尚待实测。本项仅完成审核材料：人工审核仍 0/31、正式地图/到达集/episode 均未完成，不关闭 S4–S10。
    - [x] Scene1-Target-Integration（2026-10-18）：`jackal-target-a01` 将 `retro-type-i-bus-stop` 的 `RetroNeighborhood.bus_stop.0002` 接入诊断；从 (-30,-24) 经真实 Nav2 驶近 (-30,-18)，SUCCEEDED（4），实际路径 8.859 m、位移 5.817 m、最终误差 0.198 m、停车速度 0.00174 m/s。停车后在实际 XY、z=1.2 m、HFOV 90° 的目标朝向诊断相机取得五个不同渲染帧，每帧五条真实 PhysX 射线均无遮挡；OBB 表面距离 3.683 m，原始射线命中路径已保存。运行时模型包围盒与导出候选一致，11 张原始 RGB 已检查。源 `scripts/probe_target_confirmation.py` 和 `scripts/probe_windows_scene_render.py`；Isaac Python 导入/目标窗口预检及 py_compile 通过，接收端 560 帧点云哈希、2,123 组里程计与源逐条一致。两端退出 0，峰值提交内存 10.820 GiB / 显存约 3.23 GiB，资源保护未改，临时运行资源已清理。原生命令 `runs/target_integration_20261018/jackal-target-a01/execution.json`，WSL 命令同目录 `jackal-target-a01-wsl/command.json`；证据 `docs/development/ugv-ogn/target-integration-20261018.json`，图文包 `runs/target_integration_20261018/teacher-report.zip`。全库 165 实例自动绑定、154 歧义，另产出论文 31 实例审核队列与不可直接 apply 的台账模板；本实例仍 verified=false / ground_reachable=unknown，正式 catalog 10/10 blocked、episode=0。本项只验收单实例接入诊断：未运行语义检测，相机朝向取自已知目标，不代表机载相机控制；五帧沿用 Isaac 时间但未验收可见性 ROS 话题。0.1 m 局部图上最小保守外接圆净空 0.077 m，需正式 0.05 m 图复核，不认定通过 handover 净空门；转向效率、z=0 支持平面与视觉路面的高度差仍有局限。全场景 S4/S8/S10 及论文复现保持未完成。
    - [x] Jackal-Nav2-LocalGoal（2026-10-18）：`jackal-nav2-a04` 真实 NavigateToPose 返回 SUCCEEDED（4），2.5 m 外的目标经 13.825 s 仿真到达；全诊断实际位移 2.257 m、轨迹 2.293 m、最终误差 0.244 m、停车速度 0.00125 m/s。20×20 m / 0.1 m 局部 PhysX 投影含 2,762 个障碍栅格；135 帧 CPU 射线点云，WSL 接收的 116 帧哈希全部与源一致，438 组里程计与 PhysX 逐条吻合，单时钟无倒退。14 条规划路径，局部/全局地图均启动并订阅障碍点云；已保存三张 960×600 原始 RGB。源码 `scripts/probe_jackal_nav2.py`、`scripts/probe_nav2_wsl_peer.py`；原生参数见 `runs/nav2_local_goal_20261018/jackal-nav2-a04/execution.json`，WSL 命令见同目录 `jackal-nav2-a04-wsl/command.json`，两端退出 0，源码 py_compile 与数据交叉验证通过，证据 `docs/development/ugv-ogn/nav2-local-goal-20261018.json`，展示包 `teacher-report.zip`。曾修复相机预热短暂失效（改为原超时内连续 60 帧有效）和 RaycastHit 对象适配；一次显卡查询超时按原保护中止。峰值提交内存 11.020 GiB / 显存约 3.56 GiB，临时进程、任务、防火墙均已清理。直接 map→base_link 仿真状态 TF、CPU 点云、未审局部投影与 z=0 支持平面仅用于诊断；未验收定位、RTX 雷达、强制绕障、多目标、语义搜索或论文 episode。
    - [x] Jackal-Nav2-RouteCoverage（2026-10-18）：复用实际 20×20 m 局部地图，扩展为连续三个目标（含转弯、穿树木碰撞投影直线的绕行、返回起点），`jackal-route-a02` 全部 SUCCEEDED（4），目标间无重置/传送。实际轨迹 22.062 m，最终误差 0.242 m，停车速度 0.00230 m/s；首段相对穿障直线偏离最大 1.621 m，扣除车体外接圆后的静态保守净空最小 0.384 m，轨迹中心无障碍/未知栅格命中。WSL 收到的 1,051 帧点云哈希和 3,986 组里程计逐条匹配源数据，单时钟无倒退；保存 187 条规划、代价地图证据及七张已检查的 960×600 原始 RGB。首次 a01 因诊断角加速度覆盖值 0.4 导致停驻转向死锁而超时，保留失败证据；移除覆盖、恢复仓库默认 20 后通过，角速度/轮扭矩/失联停车及资源上限未放宽。源码 `scripts/probe_jackal_nav2.py`、`scripts/probe_nav2_wsl_peer.py`、`scripts/probe_windows_scene_render.py`，验证 `python -m py_compile` 和两端数据交叉审计；原生命令 `runs/nav2_route_20261018/jackal-route-a02/execution.json`、WSL 命令 `jackal-route-a02-wsl/command.json`，两端退出 0。证据 `docs/development/ugv-ogn/nav2-route-20261018.json`，展示包 `runs/nav2_route_20261018/teacher-report.zip`；峰值提交内存 10.934 GiB / 显存约 3.35 GiB，临时进程、任务和网络规则已清理，专用 WSL 已停止。本项只验收这条静态路线，第二段路径效率尚未优化；继续使用 PhysX 里程计、CPU 点云、未审局部投影及 z=0 支持平面，未验收定位、RTX 雷达、动态障碍、语义搜索或论文 episode。下一阶段按 handover 接入正式目标绑定和任务输入。
    - [x] Jackal-ROS-Motion（2026-10-18）：`jackal-motion-a03` 在真实 Retro 场景加载官方 Jackal 包装资产，采用仓库差速参数、支持平面与车轮接触配置，WSL `/ugv/cmd_vel` 驱动四轮关节；前进 0.976 m、转向 0.861 rad（49.3°），停止段最大平移速度 0.00273 m/s、偏航角速度 0.00300 rad/s，断流停车通过。19 s 仿真诊断正常退出 0；Linux 收到 357 组里程计/TF，时间戳和位姿 357/357 与 PhysX 记录一致，单时钟无倒退；四张 960×600 真实截图已人工检查。源码 `scripts/probe_jackal_motion.py`、`scripts/probe_jackal_wsl_peer.py`，参数、两端日志和轨迹 CSV：`runs/jackal_motion_20261018/`；证据 `docs/development/ugv-ogn/jackal-motion-20261018.json`。首轮末端采样 18.97 s 导致时长门失败，修正终点采样后重跑；一次显卡查询超时由保护门中止，原保护不变。峰值提交内存 10.715 GiB、显存约 3.40 GiB；临时进程、任务、防火墙规则已清理。使用 120 Hz CPU 物理和显式出生点，运动中未改 pose；里程计来自仿真状态、map→odom 为诊断恒等变换，不验收定位、车载障碍点云、Nav2 或正式 benchmark。
    - [x] Windows-Install / ROS-Base（2026-10-18）：官方 Windows 4.5.0 完整包 7,013,544,567 bytes 下载并记录 SHA-256，96,318 个归档条目解压/续传 CRC 全通过；Humble 和 Nav2 已安装，隔离 domain 42 的真实 talker/listener 通信通过。包安装与 ROS 本机通信不代表机器人导航通过。证据：`docs/development/ugv-ogn/second-pc-runtime-20261018.json`。
    - [x] Retro-Physics-Load（2026-10-18）：Windows Isaac 4.5.0 实际加载 27,986 个 prim，PhysX 推进约 1.533 s，两条射线命中真实道路网格，报告保存距离、位置和法线；正常退出 0，峰值进程提交内存 5.846 GiB。原始道路命中 z≈-0.19126 m，本诊断未添加 benchmark 的 z=0 支持平面，不能用于替代正式 GT。证据：`runs/second_pc_runtime_20261018/retro-physics-result-a01/report.json` 和 `retro-physics-a01/execution.json`。不替代 RTX RGB、0.05 m GT、机器人导航或 episode 验收。
    - [x] Empty-PhysX（2026-10-18）：真实方块从 z=1.5 m 落至 z=0.24999979 m，物理子检查通过；同次相机首帧等待失败，整体渲染诊断不通过。证据：`runs/second_pc_runtime_20261018/cube-frames-a07/report.json`，其中 `physics_passed=true`、整体 `status=failed`。
    - [x] Windows-Render-Diagnostic（2026-10-18）：最小物理方块和真实 Retro 相机出图通过，均正常退出 0。Vulkan 采用有限权限桌面会话和 NVIDIA ICD 过滤，延后建场景、16 个 CPU 线程、1 个 shader 编译并发、异步加载，普通相机诊断关闭 Motion BVH；未验证 RTX 雷达/激光雷达及完整机器人 runtime。初期失败证据保留在 `second-pc-runtime-20261018.json`，最新证据见 [RTX 首帧记录](docs/development/ugv-ogn/rtx-first-frame-20261018.json)。
      - [x] RTX-First-Frame / Screenshots：`cube-a12` 捕获 `LLVM ERROR: out of memory`，提交余量最低 0.600 GiB，仍有约 12.66 GiB 物理内存。经用户明确同意，C 盘保持系统管理，D 盘新增 16–24 GiB 分页文件，SSH 设为开机启动；D 盘 16 GiB 立即生效，提交容量约 33.61→49.61 GiB，无需本轮重启。诊断上限改为 14 GiB 后方块 `cube-a13` 出图，峰值约 10.989 GiB；不能把单项配置视为独立归因实验。
      - [x] Retro-RTX-Images：首次 `retro-render-a01` 的地面图近黑，旧方差门误判为通过，人工复核拒绝该图；加入非黑像素比例门和 60 帧稳定等待。`retro-render-a02` 保存两张 960×600 原始 RGB 及 Isaac 内实际 RGB 预览面板截图，图像逐一检查；正常退出 0，耗时 51.31 s，峰值进程提交内存 10.424 GiB。日志：`runs/rtx_first_frame_20261018/`；展示包：`runs/rtx_first_frame_20261018/teacher-screenshots.zip`。
      - 资源保护：独立诊断默认 8 GiB、最高 14 GiB；14 GiB 对照启动前至少 18 GiB 可用物理内存和 16 GiB 提交余量，运行中保留 4 GiB 物理/2 GiB 提交余量，显存不超过 80%，CPU 60%，最多 32 进程并设墙钟超时。正式 benchmark guard 不变。本轮进程已退出、临时任务已删除；导航、GT 与论文实验未验收，正式 episode 仍为 0。
    - [x] Windows-WSL-ROS-Bridge（2026-10-18）：`ros-bridge-a01` 在 domain 42、WSL NAT UDP 定向发现下通过 Windows Isaac 4.5 ↔ WSL Humble 真实消息验证；原生桥扩展启用，以内置 rclpy 发布真实传感器缓冲区和 World 仿真时间。Linux 收到 488 条 `/clock`（单发布者、无倒退，6.883→15.000 s）、160 张 480×300 RGB（160/160 像素 SHA-256 与发送端匹配）、162 条 CameraInfo；Windows 收到 166 条 `/ugv/cmd_vel`，前进/转向/停止及运行标识回执通过。35 s 有界通信阶段、全进程退出 0，峰值提交内存 10.099 GiB、显存约 3.08 GiB；启动前/运行中保护保留。源码 `scripts/probe_isaac_ros_bridge.py`、`scripts/probe_ros_wsl_peer.py`；验证参数及两端日志 `runs/ros_bridge_20261018/`，证据 `docs/development/ugv-ogn/ros-bridge-20261018.json`。没有驱动车轮，不验收 Jackal 运动、TF/里程计、Nav2、全量传感器吞吐或论文 episode。

> 2026-10-10 → 10-13 文档中的 `P1-UGV-OGN-Benchmark` 与更早的 `P0-UGV-OGN-Benchmark` 均指本项。证据与评测文档在 `docs/development/ugv-ogn/`（索引见其 `README.md`）；2026-10-12 整理前各条目的详细原文（根因、修复、验证、artifact）在 `docs/development/ugv-ogn/plan-log.md`，按条目 ID 检索。

- [ ] P0-UGV-OGN-Benchmark：把评测主体从 UAV 迁移为 UGV，落地上游 4+3+3 任务、`Progress/PPL/SR/SPL` 指标，并产出三类任务 smoke 视频。
  - 口径：UGV 是唯一评测主体；UAV detection/通信/confirmation 只写诊断字段；`M` 只统计 `ground_reachable == "reachable"` 实例；reach window 主口径 `[1.5, 8.0] m`（见 AGENTS.md）。
  - 运行方式（用户 2026-10-12，2026-10-13 起生效）：评测与调试默认用 SimMT 多任务运行时，单卡 1 个 Isaac 进程跑一个场景、一个出生点的完整 10 个任务（`~/jun/launch1.sh REP ENV SPAWN [CARD]`）；只有最终验收这类工作才用 3 进程 × 10 任务（同一场景三个出生点，`~/jun/acc_launch.sh`）。配置基线为 SimMT-7 验收配置 `~/jun/s7z3_env.sh`，见 `docs/development/simmt/README.md`。
  - 最近一次正式评测：Paper30Eval（2026-10-07）28/30 集有分，ALL K=8/136、Progress 6.41%、PPL 3.18%、SR/SPL 0；主损失是语义检测与 UAV 搜索覆盖。
  - **检测链（当前主阻塞：`UGV-OGN-CalibrationGate`）**
    - [ ] UGV-OGN-DetectionCoverage（2026-10-07）：离线测得 bus stop 最高分仅 0.7115 且 GT 几乎不可见，主因搜索覆盖不足；分数门限不是可用修法，方向为覆盖偏好。
    - [ ] UGV-OGN-RangeGateA/B 结果（2026-10-07）：yellow-car-s1 两次 A/B 均 0 visits，最高分仅 0.1306；远距类级编码器响应处于噪声级，不是搜索/访问机制可修。
    - [ ] UGV-OGN-RangeGate（2026-10-07）：检测弱的上游是从未靠近目标（最近 15–27 m）；待 investigation pass 的近距重打分活体 A/B 验证。
    - [ ] UGV-OGN-CalibrationNext（2026-10-07）：标定实验清单未完成：phrasing×cue 离线 A/B 首轮 6 变体已启动，活体 investigation 与 v1/v2 对照待做。
    - [ ] UGV-OGN-DetectionCensus（2026-10-07）：修正普查：28 集中 10 集有 FIFO 检测入队、6 次实际到达，18 集零检测，触发具逐集航路相关性。
    - [ ] UGV-OGN-SyncSlop（2026-10-08）：根因为 RGBD 同步 slop 过紧致 mapper 饥饿，已改默认 0.35 待长窗口复验；远起点零检测另因 clip_bbox 裁掉 ROI 外体素。
    - [ ] UGV-OGN-InvestigationAB 结果（2026-10-07）：低阈值 0.25 下 0 次 investigation visit、0 次 handoff；高分体素落在高架杂物上，通道保持默认关。
    - [ ] UGV-OGN-InvestigationPass（2026-10-07）：已实现（默认关）的低于门限靠近重打分通道，容器内 3/3 测试通过；活体 A/B 待执行。
    - [ ] UGV-OGN-DetectionProbe（2026-10-07）：离线重放：bus stop 分数 0.9494 未过 0.95 门限；过门的 bus stop sign 命中的是高楼而非 GT，属编码器/词汇问题。
    - [ ] UGV-OGN-PipelineShift（2026-10-07）：5/7 集 GT 目标曾入画，但 ΣK/ΣM 仅 1/15：瓶颈转为检测到 UGV 的管线（误检或晚检出），待 campaign 后分析。
    - [ ] UGV-OGN-DetectionTiming（2026-10-07）：检测确会触发（分数 0.962–0.988）但 K 仍为 0，瓶颈转为检出时机与可达性或误检，待加入每集分析。
    - [ ] UGV-OGN-CalibrationGate：原主线阻塞（次于 UavSearchContinuity）：真假检测语义分数不可分，迭代候选（query、阈值、帧累积等）待逐条离线验证。
  - **UAV 飞行与搜索**
    - [ ] UGV-OGN-UavSearchContinuity（2026-10-06）：UAV 主阻塞：goal 取自停驻的 tracking point，93% 时间静止、仅 1–2 次 hand-off；无目标时重发陈旧 target 为待验证根因。
    - [ ] UGV-OGN-BelowGroundFrontiers（2026-10-06）：根因：+Inf 深度沿射线把地面下刻为 free；已在 RayFronts b245a93 源头截断并收窄 clip_bbox，待真实 run 验证。
    - [ ] UGV-OGN-MagStale（2026-10-06）：实测失稳链：磁力计 STALE 触发罗盘故障、failsafe 与翻滚；待有界测量定位 STALE 来源，验收为连续 3 集无 STALE。
    - [ ] UGV-OGN-Px4MagAndParams（2026-10-06）：SYS_HAS_MAG 已移出参数表（PX4 对其不回 ACK）并加 5 s 墙钟上限；磁力计保持开启，关闭则无法起飞。
    - [ ] UGV-OGN-UavStallDiagnosis（2026-10-07）：走廊护栏已消除翻滚（最大横滚 3.14→0.89 rad）但仍 88% 悬停；磁力计 STALE 为停泊期现象；待用 frontier trace 诊断。
    - [ ] UGV-OGN-AllLaneCorridorGuard（2026-10-07）：待实现（须等 30 集 campaign 结束）：走廊护栏仅覆盖 frontier 车道，检测/假设车道同样需加。
    - [ ] UGV-OGN-TakeoffPositionShift（2026-10-13，SimMT-7 期间发现）：3×10 运行中约每 30 任务 1 次起飞失败（`takeoff_local_position_shift` 之后 PX4 failsafe，s7acc4 p2 t6、s7acc5 p0 t3），s7acc7 未出现；根因未查。证据 `simmt/evidence-08-*` s7acc4/5 节。
    - [ ] UGV-OGN-DroanBlindRewind（2026-10-13，SimMT-7 期间发现）：所有候选轨迹都判为碰撞时 droan 按上游写法不发布、控制器沿旧段继续飞，卡住阈值后倒飞并撞障（s7w1 t7）。需在线记录视差帧率与 droan 日志，判断是否有运行侧（掉帧、UDP 丢包约 3.7%）放大。证据 `simmt/evidence-08-*` s7w1 节。
    - [ ] UGV-OGN-UavLocalAvoidance（2026-10-08）：droan 单集 live 验证通过（6 个链进程存活、目标流正常）；与 offboard_direct 的单集 A/B 及稳定性决定尚待完成。
    - [ ] UGV-OGN-UavDutyCycle（2026-10-08）：根因为 UAV 以约 0.05 m/s 爬行（直连车道用裸位置设定点），已对两车道启用 velocity 模式，待单集 A/B。
    - [ ] UGV-OGN-UavReachMech（2026-10-07）：待实现 v3：访问路点外 1.0 m 与 3.0 m 门控使 UAV 约 4 m 即判已访问；拟加 env 开关做 A/B。
    - [ ] UGV-OGN-SearchMechFixes（2026-10-07）：四项搜索运动学修复已落地；单集 150 s 探针 path 19→27 m、候选 1→7.9、无翻滚，尚未勾选验收。
    - [ ] UGV-OGN-TakeoffStallRootCause（2026-10-07）：根因假设降级：起飞停驻与 s2 出生点旁障碍及水平漂移相关，非 dock joint；待加出生点离障约束或起飞离障。
    - [ ] UGV-OGN-CoveragePolicy（2026-10-07）：待实现，下一步最大杠杆：现状就近 greedy 使 300 s 覆盖率约 4–10%，拟偏好未访问区域，验收以 GT 可见帧统计。
    - [x] UGV-OGN-GroundOcclusionClamp（2026-10-06）：已修并现场验证：地面下选中 frontier 为 0 个；含 ground clamp、VLFM 补传 occ 算法、ray_sampling 近平面保护。
    - [x] UGV-OGN-SpanningClusterViewpoint（2026-10-07）：已修并现场验证：跨界大 cluster 改取最近前沿 cell 作视点，移动时间 78→202 s，triage 0 defect。
    - [x] UGV-OGN-FrontierSubsampleFallback（2026-10-07）：已修：抽稀后不足 3 点时回退到原始 cell 聚类；此前 91 条记录中 80 条直接放弃选择。
    - [x] UGV-OGN-VisitedPenaltyInversion（2026-10-07）：已修：已访问惩罚由减法改为加法（修正取最小语义）；单集 A/B 未见可见性改善，待 30 集统计判定。
    - [x] UGV-OGN-CorridorDensify（2026-10-07）：已修并现场验证：走廊采样间距 0.25 m，blue-container-s1 path 19→83 m 且不再翻滚，两个目标均可见。
  - **评测与口径**
    - [ ] UGV-OGN-Paper30Final（2026-10-07）：进行中：前 4 集 ΣK/ΣM=2/9=0.222（修复前同 4 集为 1/24），剩余主要损失仍是语义检测未检出。
    - [ ] UGV-OGN-SpawnCoincidentReach（2026-10-07）：house-s3 的 K=1 为 t=0 起点重合命中（p_m=0），评分口径允许；最终报告需加脚注，可选给剔除变体。
    - [ ] UGV-OGN-PaperComparisonFraming（2026-10-07）：对标口径待定：legacy 门按构造全部失败属诊断 lane；最终表需标注 RayFronts 无 LVLM 配置，并列 RAVEN、VLFM-3D 参照。
    - [ ] UGV-OGN-CampaignFailModes（2026-10-07）：前 11 集 3 次 gate 失败，根因为起飞停驻×2 与探索死锁×1；UAV lane 失败时 UGV lane 早退，修复待 campaign 后实施。
    - [ ] UGV-OGN-V3Checklist（2026-10-07）：v3 变更清单已拟定，待 campaign 完成后按序执行（如 UGV 速度 1.6 m/s、会话结束续跑、守卫收窄），尚未执行。
    - [ ] UGV-OGN-UgvSpeed（2026-10-07）：UGV 单目标余量约 83 s、多目标结构性不足；拟将 desired_linear_vel 调至 1.6 m/s，单集 A/B 因无检测无结论。
    - [ ] UGV-OGN-RunnerMultiGoal：有限多目标循环与 FIFO 机制已在，真实 Type III run 尚未验收。
    - [ ] UGV-OGN-Aggregate：待对最新真实 run 离线回算 UGV 中心指标并发布 redacted aggregate，尚未完成。
    - [x] UGV-OGN-InjectedGoalDiagnostic：注入诊断通道已实现（可带逐实例 id 与 via 链），明确定义为非 benchmark 证据。
    - [x] UGV-OGN-FixVal4Campaign（2026-10-06）：4 集逐集独立跑完且全部出分，ΣK/ΣM=1/24=0.042；剩余差距归因于检测质量与 UAV 稳定性两问题。
    - [x] UGV-OGN-Paper30Eval 结果（2026-10-07）：28/30 集有分：ALL K=8/136、Prog 6.41%、PPL 3.18%、SR/SPL=0，与 Frontier-3D 同档；2 集无数据。
    - [x] Paper-Protocol-Eval（2026-10-05）：首轮 0 分因 UAV 全程未离地而不构成算法结论；已定位 dock joint、mapper 吞吐等真实缺陷并记录修复。
  - **运行环境**
    - [x] UGV-OGN-MultiTaskEquivalence（2026-10-13，SimMT 遗留）：s1 出生点 10 个 episode，多任务（s7acc6/7 p0）与 N=1 各 20 个任务。UAV 侧一致（正确/错误信号 19/9 对 24/10，UAV Progress @1m 16.6% 对 20.6%）。UGV 侧差异（8/20 对 0/20）来自与多任务无关的时钟 bug：t0（N=1 时唯一的任务）的 `/clock` 有 OmniGraph 和 Python 两个发布者，消息乱序导致 Nav2 等待判超时。修复 `AIRGROUND_SINGLE_CLOCK_PUBLISHER`（AirStack b6cd51d4），N=1 复测 3 个 episode 中 UGV 到达 2 个、时钟倒退消失。剩余风险：修复后只复测 3 个 episode；此前平铺后端运行中 t0 的 UGV 结果无效。证据 `docs/development/simmt/evidence-09-multitask-equivalence.md`。
    - [ ] Nav2-60s-ColdWarm：历史冷启动 482.7 s、片段 RTF 0.17–0.19 未通过；热启动准备已优化至约 44–50 s，仍待复核。
    - [ ] Nav2-RuntimePerformance：GPU 点云、native 状态桥等已交付；当前 warm RTF 约 0.71–0.78，未达 1:1。
    - [ ] UGV-OGN-Par1Wrapup（2026-10-10）：4 卡并行 600 s 轮已跑完未收尾：g0/g3 到达，g1 预算耗尽，g2 被启动守卫 docker kill；守卫策略待用户决定。
    - [ ] UGV-OGN-RunInfra（2026-10-06）：已记录多项运行问题：/tmp 跨容器残留需每轮清理，GPU 上限 0.85，宿主 GPU2/3 出现 Xid 31；多集改每集独立进程。
    - [ ] UGV-OGN-GuardScopeFix（2026-10-07）：待修（campaign 后）：external-CUDA 扫描未按 GPU 收窄，误判会 docker kill 并整集重跑；修法为按容器进程 GPU uuid 收窄。
    - [ ] UGV-OGN-MissionWatchdog（2026-10-08）：立项未实现：长跑与挂死无法区分，拟以产物 mtime 超 5 分钟无更新判死并自动留存现场。
    - [ ] UGV-OGN-RetryClobber（2026-10-07）：外部 CUDA 误判触发重跑且重跑工件覆盖评分工件；后处理须按 mtime 筛选，收紧重试待 GuardScopeFix 一并完成。
    - [ ] UGV-OGN-CampaignV2Stability（2026-10-07）：s3 两次 exit 137 归因为宽模式 pkill 误杀；已加 flock 防双启并改按 PID kill，s3 第 3 次尝试续跑。
    - [x] UGV-OGN-WarmRunMemory（2026-10-06）：已结案：非泄漏，是 RLIMIT_AS 8 GiB 上限卡在地址空间地板上；replay 改流式写，多集运行加上限告警。
  - **基础、地图与导航（已基本闭环）**
    - [ ] UGV-OGN-ObstacleLayer3D / UGV-OGN-Traversability0p05：代码与离线 artifact 已完成；待检测门通过后以正式 run 回填。
    - [x] UGV-OGN-Catalog 与 UGV-OGN-Metric：10/10 任务 ok；已修 K 假 0（单标签 npz 环带重叠被覆盖），改为按 manifest OBB 与 traversability 逐实例精确重建。
    - [x] UGV-OGN-Docs：AGENTS.md、benchmark/README.md、benchmark_zh.md 已改为 UGV 中心主口径。
    - [x] UGV-OGN-ReachRegion1p5w（2026-09-24）：原始几何 0.645 m 走廊重判可达性；全图重导后 31 实例均有到达集，catalog 10/10 ok。
    - [x] GT-AABB 全图与 0.05 m 候选包（2026-09-30）：全图 band raycast 与单卡 CUDA 候选包完成，31/31 目标归属、30 个可靠绑定；_r2 支撑平面误关经 _r3 重导修正。
    - [x] RedCar-BindingRecovery（2026-09-30）：红车类别与实例 ID 保留，恢复真实车辆绑定并重生成到达集。
    - [x] Resolver-Nav2StandardOnly（2026-10-01）：2026-10-01 退役净空/走廊门，2026-10-05 被实时 costmap 最短带内路线取代。
    - [x] Nav2-31ObjectTour（2026-10-05）：2026-10-05 完成：20261005_tour31_final 129/129 航点、零脱困，双来源审计 K=31/31。
    - [x] UGV-OGN-GTAabbROI（2026-10-05）：Phase B/C 于 2026-10-05 取消（31 实例全部联通、无需搬运）；保留 Phase A 全图分析与单卡后端。
    - [x] UGV-OGN-VehicleTextures（2026-10-07）：本地已修车辆白模（去除路径残渣 ]，生成 51 个平面色贴图，59/59 校验 ok）；服务器场景已于 10-07 同步；场景 SHA-256 改为 `2a7141ce…`（用户 2026-10-12 决定按新值固定，场景审计测试同步更新）。
    - [x] UGV-OGN-SmokeVideoTypeI/II/III（2026-10-05）：真实链路重做完成：Type I 1/2、II 2/6、III 1/3，五视频齐备；Type I/III 未达 K=2，UGV 第一视角未发布。

### P0-RayFronts-FullMission（legacy 诊断 lane，继续维护）

- [ ] P0-RayFronts-FullMission：把 RayFronts/VLFM 从 metrics surface smoke 升级为完整 full-mission benchmark runner（UAV 语义搜索 → 通信 → UGV Nav2 确认；正式成绩必须过 `--require-rayfronts-physical-mission`）。
  - 已完成（按证据类别）：
    - Runner 主体与防伪门：entrypoint、physical sanity gate（TTC/D2C/path 下限）、TaskGate evidence 链（evaluator 来源、连续可见帧、区域/视锥/遮挡）、anti-smoke artifact gate。
    - 真实接入面：UAV-control adapter（PX4 OFFBOARD，`p0_uav_control_adapter_20260805_184533`）、communication bridge + Isaac PhysX LOS、sensor-frame publisher（1660/1660 records）、file-backed intrinsics、Isaac-resident evidence surface。
    - 单集 proof：`p0_public_single_full_mission_min_uav_waypoint_live_20260806_091649` 通过 physical mission gate（TTC 43.7 s、UGV path 16.4 m、confirmation 5/5）。
    - 复位与时钟：episode reset（PX4 backend、UAV chassis pose、UGV odom stale-start gate）与 `/clock` deadline 计分（`elapsed_sim_s`/`timeout_source`）。
  - 未闭合（当前阻塞）：
    - [ ] P0-RayFronts-FullMission-Public / -Hidden：用同一 runner + gate 重跑 reviewed public 60 与 hidden 60，发布 redacted aggregate 与 salted checksum。
    - [ ] Runner-UAVControlBatchStability：批量 run 中 strict UAV-control evidence 偶发失败（单集可过；public60 首集 endpoint error 1.78 m 超 0.75 m 门）。
    - [ ] Runner-IsaacRuntimePreflight / SoftDockAndStartGate / WarmReuseGpuFootprint / Px4Stability / TraversabilityThinObstacles：运行稳定性与物理收敛项，见 CHANGELOG。
  - 说明：2026-09 及更早的逐项子任务（Runner-Entrypoint、TaskGate-*、UAV-Control*、Communication-*、RenderIntrinsics、Nav2ConfirmationDistance、IsaacResidentEvidence 等）均已勾选完成，本文压缩为上面的类别摘要；逐条证据路径见 `docs/development/CHANGELOG.md`、`docs/development/evidence/` 与 `docs/development/archive/isaac6/`。
  - 详细口径：`docs/development/archive/isaac6/rayfronts/rayfronts-full-mission-gap-analysis.md`。

### 已完成：P0-Sim-MultiTask（2026-10-10 → 10-13）

设计 `docs/development/simmt/design.md`；证据索引、开关与服务器入口 `docs/development/simmt/README.md`；压缩前的完整子项原文（SimMT-0～7）在 `docs/development/simmt/plan-log.md` 末节。

- [x] P0-Sim-MultiTask：一个 Isaac Sim 进程并行跑 N 个任务（N 组 UAV+UGV，同一场景），Kit 主线程只做批量状态读写、物理步、渲染与 raycast，PX4/建图/Nav2/droan/runner 每任务各自成进程，任务间互不可见。
  - 验收（SimMT-7，s7acc7，2026-10-13 17:44–17:57 UTC）：3 个 Isaac 进程 × 10 任务 = RetroNeighborhood 三个出生点的全部 30 个任务，CPU 150 核预算内（稳态 82–88 核），三个 Kit 主线程独占 Socket 1 的 76/78/56；搜索前 30/30、无卡死、无守护击杀；每任务 RTF 0.464 / 0.496 / 0.481（目标 ≥ 0.4）；显存峰值 14.9–16.1 GB。代码根仓库 b2726c9、AirStack fdf8a155、RayFronts a5cea2c；证据 `simmt/evidence-08-three-process-30-tasks.md` 末节。
  - 关键修复：PX4 hub、原生 fleet 步与机队状态发布等批量运行时；建图宿主（每卡一进程）与每实例 ROS 读取子进程；Fast DDS 2.6.8 死锁补丁（#5432 移植）；标注清单 JSON 快路径；建图宿主显存分块与原地运算；主线程集中到低负载 Socket；任务执行器代价地图原地读取（去掉约 10 核与内存带宽争用）。
  - 剩余风险：只验收一轮，s7acc3–s7acc6 间 RTF 有明显环境波动，最终验收建议重复；UDP 接收丢包约 3.7%；起飞失败与 droan 盲倒飞已转入 P0-UGV-OGN（`UGV-OGN-TakeoffPositionShift`、`UGV-OGN-DroanBlindRewind`），多任务与 N=1 的结果等价核对转入 `UGV-OGN-MultiTaskEquivalence`。
  - 后续项（不阻塞，按需再开）：SimMT-1～6 中未勾选的早期路线验证（平铺 RGB-D N=1 A/B、N=16/32 吞吐、共享编码器服务审阅、每任务独立 reset 验证等）；SimMT-7f 剩余削减（任务执行器重复 `/ugv/odom` 订阅、droan 每帧阻塞计时查询、多节点重复 `TransformListener`）；需 A/B 的功能偏差候选（全局代价地图缩小、BT 重规划频率、fp16/TF32、关抗锯齿）；Fast DDS 共享内存传输已证实会死锁，不再使用。

### 已完成的基础验收

- [x] P0-UAV-Precision：真实 Isaac/PX4 60 s hover（drift 0.2076 m）与 10 m waypoint（error 0.4816 m）。
- [x] P0-UGV-Precision：Jackal 60 s 静止（drift 0.0071 m）与 10 m 直线（error 0.0588 m），无翻覆/unsafe contact。
- [x] P0-Dock-Impulse：100-cycle reset/dock/takeoff（100/100 ok）与 contact impulse 安全证据（真实 Isaac 6.0.1 历史运行）。
- [x] P0-Observation-Time-Diff：双机 observation 时间差 ≤ 10 Hz 周期（max delta 0.016 s）。

### 发布任务

- [ ] B5-Release-Tag：经用户明确授权后，决定是否移动 / 重建 `benchmark-v1.0-retro` tag。
- [ ] B5-Release-Notes：若移动 tag，重建 release manifest、strict checklist、README 版本说明和 checksum 索引。
- [ ] B5-Final-Audit：最终发布前复查本文、archive、CHANGELOG、README、hidden redaction 和 fresh clone 证据一致性。

## 7. 发布状态

| 项目 | 状态 | 说明 |
| --- | --- | --- |
| public 60 / hidden 60 episode | 部分完成 | split 与 oracle evidence 已完成；UGV 侧已有 31/31 目标验收；RayFronts/VLFM 正式 full-mission 需重跑。 |
| GT / episode / evaluator checksum | 完成 | release manifest 与 strict checklist 已覆盖。 |
| container tag / image | 完成 | 当前 live tag 指向 P2-11p frozen image `sha256:4a5b13265a3c7042ca7d929e7dd524562cfb879daa737d6609c9cef606c85e48`。 |
| fresh clone | 部分完成 | current-HEAD fresh clone 真实 episode 通过；full-mission gate 修正后需复跑。 |
| strict release preflight | 未完成 | 需在正式 public/hidden 重跑后重建（旧 41/41 建立在已重分类的 smoke 结果上）。 |
| UGV 31 目标巡游 | 完成 | 2026-10-05 双来源 K=31/31，`exit 0`、metrics ok。 |
| release tag | 未完成 | 不移动 `benchmark-v1.0-retro`，除非用户明确授权。 |

## 8. 证据索引

- 文档总索引：`docs/development/README.md`
- P0-UGV-OGN（主线）：`docs/development/ugv-ogn/README.md`（协议评测、视频集、地图/巡游/性能证据）
- P0-Sim-MultiTask（已完成）：`docs/development/simmt/README.md`（设计、证据、开关、服务器入口）
- 完整旧计划归档：`docs/development/archive/implementation-plan-full-archive-2026-08-04.md`
- 近期变更记录：`docs/development/CHANGELOG.md`
- Nav2/巡游/性能证据：`docs/development/ugv-ogn/nav2-60s-cold-warm-20260930.md`
- 单卡 raycast 与 GT-AABB 全图：`docs/development/ugv-ogn/ugv-ogn-single-gpu-raycast.md`、`docs/development/ugv-ogn/ugv-ogn-gt-aabb-roi-human-review.md`
- 红车绑定：`docs/development/ugv-ogn/red-car-binding-recovery.md`
- RayFronts full-mission gap analysis：`docs/development/archive/isaac6/rayfronts/rayfronts-full-mission-gap-analysis.md`
- 中文使用文档：`docs/benchmark_zh.md`；benchmark README：`benchmark/README.md`；开发规范：`AGENTS.md`

## 9. 维护规则

- 修改 checkbox 前，必须确认代码/配置、真实或离线验证、证据文档三者同步。
- 真实 Isaac/ROS/PX4/Nav2/RayFronts 项不得用 mock/contract 结果替代。
- 大段命令输出、checksum、逐项日志写入 `docs/development/CHANGELOG.md` 或对应主线目录（`simmt/`、`ugv-ogn/`、`evidence/<主题>/`）的证据文档；本文只保留可读摘要与结论。
- 隐藏集路径、seed、episode id、oracle trace 和 private run dir 不写入公开文档。
- AirStack/RayFronts 修改必须先在子模块 `airground` 分支提交推送，再更新顶层 submodule pointer。
