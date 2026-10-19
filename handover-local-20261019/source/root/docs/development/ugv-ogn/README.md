- [静态实例运行接口 CPU 校验与新地图首批归档](static-instance-runtime-interface-20261019.json)：c01d33b1，20项检查通过，原生/引用挂载结果一致；新接口真实PhysX验证待执行。

# UGV-OGN：UGV 中心 benchmark（P0-UGV-OGN-Benchmark）

- 2026-10-19：[本机全图 Nav2 验证](full-map-nav2-20261019.json)：a02 三目标通过，a01 末端超时保留；全图逐格匹配，转向稳定性和视觉/物理地面高差待处理。

勾选状态只在 `IMPLEMENTATION_PLAN.md` → `P0-UGV-OGN-Benchmark` 维护（2026-10-10 → 10-13 曾降为 P1，名为 `P1-UGV-OGN-Benchmark`）；本目录是该主线的评测文档与 Isaac 4.5.0 时代证据。

运行方式（2026-10-13 起）：评测默认在单 Isaac 进程多任务运行时上进行，单卡跑一个出生点的完整 10 个任务；配置与服务器入口见 `../simmt/README.md`。

## 评测与视频

| 文件 | 内容 |
| --- | --- |
| `ugv-ogn-paper-protocol-eval.md` | 论文协议 10 任务 × 3 起点 = 30 集的正式评测：输入、官方命令、评分与结果（含 2026-10-05 首轮与 10-07 Paper30Eval） |
| `ugv-ogn-smoke-video-sets.md` | Type I/II/III 三类任务 smoke 视频集 |
| `smoke-video-rtx-four-view.md` | 4.5.0 RTX 回放 + 机载相机录像的四视角视频 |
| `smoke-video-offline-render.md` | 从 full-mission 轨迹离线渲染（绕开 Isaac 回放渲染器段错误） |
| `plan-log.md` | 2026-10-12 整理前计划条目原文（按条目 ID 检索根因、修复、验证与 artifact） |

## 地图、GT 与导航

| 文件 | 内容 |
| --- | --- |
| `scene-gt-adaptation-20261017.json` | 本机九场景 handover 的 CPU 适配、下载校验、候选绑定与真实运行阻塞证据 |
| `construction-ground-fix-20261019.json` | ConstructionSite 两块地形的真实 PhysX A/B、原始基线隔离备份及修正地图重采；未审核 GT |
| `merged-mesh-collision-preflight-20261019.json` | FireAcademy/AbandonedFactory 大型合并网格离线碰撞风险、源三角形交点及待运行射线诊断；不构成真实碰撞错误结论 |
| `partial-scene-geometry-20261019.json` | 六个不完整资产包的CPU全网格读取审计和五场景未应用绑定建议；DowntownWest 28空mesh、SnowyVillage 197缺失资产 |
| `construction-review-failure-20261019.json` | ConstructionSite第二轮首帧时限失败，0/56 RGB；完整失败日志已保存 |
| `visibility-scene-selection-20261019.json` | S8工具场景选择与资产哈希保护，5项CPU检查；不代表真实可见性已通过 |
| `factory-adaptation-20261019.json` | AbandonedFactory 199 资产隔离传输校验、缺失辅助材质定位及未审核面级候选 |
| `unreviewed-arrival-candidates-20261019.json` | Retro 31 个论文目标完整逐实例几何候选，保留重叠；非正式 arrival_regions |
| `nav2-dwb-stability-20261019.json` | 原预算三轮 DWB 重复：9/9 action 成功但严格回报位姿 7/9，稳定性未通过 |
| `local-scene1-preparation-20261017.json` | 本机场景一环境与资产准备；未取得真实仿真成绩 |
| `second-pc-preparation-20261018.json` | 第二台 RTX 4060 电脑连接、隔离环境与原生兼容性检查 |
| `second-pc-runtime-20261018.json` | 原生 Isaac 4.5 安装、ROS 消息测试、受控渲染尝试与资源证据；不代表场景复现 |
| `rtx-first-frame-20261018.json` | RTX 相机首帧诊断、用户授权分页文件调整、真实 Retro 双视角 RGB 和运行截图；未完成导航实验 |
| `ros-bridge-20261018.json` | Windows Isaac ↔ WSL Humble 实际时钟、相机像素哈希和反向速度消息验证；未驱动机器人或验收导航 |
| `jackal-motion-20261018.json` | 真实 Jackal 四轮驱动、前进/转向/停止/断流停车及 357 组里程计/TF 交叉验证；附截图，未验收 Nav2 |
| `nav2-local-goal-20261018.json` | 真实局部地图/CPU 点云、单目标 Nav2 到达、116 帧点云及 438 组里程计交叉验证、三张原始截图；不代表复杂避障或论文场景完整复现 |
| `nav2-route-20261018.json` | 连续三目标、转弯、静态树木绕行并返回起点；1,051 帧点云与 3,986 组里程计交叉核对、七张原始截图及首次失败记录；仅验收该路线，正式论文 episode 仍为 0 |
| `target-integration-20261018.json` | 单个未审公交站接入、真实驶近、五帧目标 RGB/PhysX 可见性、11 张原图和 31 实例审核草稿；未执行语义检测，正式 episode=0 |
| `paper31-review-20261018.json` | 全部 31 论文目标的 62 张真实双视角 RGB、24 个歧义、标注/候选框与待审表；全图 ROI 和本机 64 GiB 入口限制；未批准 GT |
| `tiled-map-validation-20261018.json` | 两个真实 PhysX 小区域的整块/分块等价对比、halo 块缝与连通性验证；红车绑定独立副本修正；未生成正式全图 |
| `resumable-map-20261018.json` | 两次独立真实进程的断点续跑验证、6 项持久化检查及全图后台采样启动快照；非完成结论 |
| `ugv-ogn-single-gpu-raycast.md` | GT-AABB ROI 单卡 CUDA raycast（现行地图依据） |
| `ugv-ogn-gt-aabb-roi-human-review.md` | GT-AABB 连通分量人审（Phase B/C 已取消，仅作记录） |
| `red-car-binding-recovery.md` | 红车目标绑定恢复与 RGB 确认 |
| `ugv-obstacle-layer-3d-and-0p05-traversability.md` | 3D 点云 VoxelLayer 与 0.05 m traversability |
| `ugv-proximity-scan-obstacle-awareness.md` | UGV 栏杆卡停诊断与近距扫描 |
| `nav2-60s-cold-warm-20260930.md` | 一分钟冷/热启动、31 目标巡游（K=31/31）与性能数据 |
| `nav2-benchmark-lane-rtf-baseline-20261005.md` | benchmark 车道 RTF 基线（native 性能环境约 0.73） |

## 检测链

| 文件 | 内容 |
| --- | --- |
| `ugv-ogn-calibration-gate-type-i.md` | Type I 检测质量门的历次运行（`UGV-OGN-CalibrationGate`） |

reach 重标定（`ugv-ogn-reach-region-1p5w-recalibration.md`）与早期 confirmation 区域工具属于版本无关的契约，放在
`../evidence/ugv-ogn/`；6.0.1 时代的 UGV-OGN 证据在 `../archive/isaac6/ugv-ogn/`。

全图采样中断及续跑（2026-10-19）：[监控修复和真实恢复证据](full-map-recovery-20261019.json)，记录采样恢复阶段；后续全图后处理结果见下文，论文复现仍待验收。

全图诊断后处理（2026-10-19）：[拼接、块缝、可通行性与目标候选证据](full-map-postprocess-20261019.json)。原始采样及后处理已完成；31/31 仅为未审核几何候选覆盖，下一步进行真实 Nav2 验证。

[ConstructionSite 参数化、真实 PhysX 对照与失败渲染证据](construction-adaptation-20261019.json)。

[轮控 A/B 与支持平面高度审计](drive-ground-audit-20261019.json)。

[其他场景离线依赖与坐标预检](additional-scene-preflight-20261019.json)。

[DWB 原预算有界导航复测与真实截图](nav2-dwb-stability-20261019.json)。

- [ConstructionSite完整修正诊断图](construction-full-map-20261019.json)：70块全图与18目标未审核S7候选，正式验收未完成。

- [FireAcademy碰撞A/B](fireacademy-collision-20261019.json)：三点真实对照及双面射线剩余问题。
- [Windows Nav2 YAML完整性](nav2-yaml-integrity-20261019.json)：实文件回归与跨系统修复。
- [ConstructionSite可见性时序诊断](construction-visibility-timing-20261019.json)：保留失败证据与定位过程。

- [ConstructionSite实例碰撞覆盖与旧图失效](construction-instance-colliders-20261019.json)：5,075代理网格缺碰撞，需补全重采。

- [Factory合并地面碰撞基线](factory-collision-20261019.json)：三点源面/真实凸体差异，修正候选待实测。

- ConstructionSite真实RGB部分审核包：`runs/construction_adaptation_20261019/teacher-review-a03/查看进展.html`（12/56图，整批失败，遮挡已记录，人工批准0）。

- [小窗口reach派生更正](window-reach-correction-20261019.json)：从保存的真实地形重算，原归档不改，当前全图流程不受影响。
