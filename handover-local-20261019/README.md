# 本地双机复现代码交接（2026-10-19）

本目录对应 `P0-UGV-OGN-Benchmark / Scene-GT-Handover`，是新增的源码交接包。
它保留 10 月 17–19 日产生的代码、测试、诊断脚本及证据说明；不是已通过 S0–S10 的正式发布。

## 上传方法：只增加本目录

1. 在 GitHub 的 `YidanZhong/Yidan-Zhong` 页面从 `main` 创建一个新分支，例如 `handover/local-scenes-20261019`。
2. 确认当前选择的是新分支，再用 Add file → Upload files 上传整个 `handover-local-20261019` 文件夹；文件较多时可以分目录上传。
3. 确认提交列表中的路径全部以 `handover-local-20261019/` 开头且均为新增文件，再提交到新分支。
4. 不上传本机整个仓库，不把 `source/root` 的内容拖到仓库根目录，不覆盖原 README、IMPLEMENTATION_PLAN 或 AirStack；不合并到 main。

本交接包以独立新增目录提交到 `YidanZhong/Yidan-Zhong` 的 `handover/local-scenes-20261019` 分支，起点为该仓库 main 的 `2e52b90c41c46d8b236fa54289b6ad6f43267c66`。不改动该仓库原 README 或 main，也不改动 BCU-Robot/RAVEN-AirGround 或任何子仓库指针。
以下实测及补丁基线均指原项目 `BCU-Robot/RAVEN-AirGround`，不是交接存储仓库。原项目远程 main 的检查基线为 `43cca28f5167ff31047bde8ce8d74941b450bc2f`；原工作目录保留未提交改动。此目录是源码交接包，不是包含原项目资产和全部依赖的独立可运行工程。

## 目录说明

- `source/root/`：主仓库改动与新增文件的完整源码快照，含 benchmark、scripts、tests 和文档。
- `source/AirStack/`：AirStack 七个本地提交涉及的完整源码快照；不依赖尚未推送的子仓库提交。
- `patches/`：可恢复上述改动的 Git 补丁，主仓库与 AirStack 分开。
- `diagnostics/helpers/`：本次工作生成的本地准备、诊断、分析、归档脚本。包含历史失败方案和安装/清理脚本，禁止批量执行。
- `diagnostics/frozen/`：各次独立诊断冻结的代码版本及纯作业参数；包含已失败和已失效的旧方案，必须先读交接状态。
- `SOURCE_MANIFEST.json`：每个源文件的原始位置、用途、大小和 SHA-256。
- `PATCH_COMPATIBILITY.json`：补丁对原测试基线及当前远程基线的实际检查结果。
- `LOCAL_INPUTS_NOT_UPLOADED.json`：未上传的本地运行输入；它们并不代表代码缺失。
- `VERIFY_PACKAGE.py`：只读校验所有交接文件的哈希，不启动仿真、不修改系统。

## 基线与集成边界

本次实测主仓库基线是 `0ddd5d9441e7d502df23450e4b1d2eacd4a8d084`。
AirStack 实测改动为 `b6cd51d46dcec1b1cca99d1b55bfa61f206d05ad` → `c01d33b17641dd502e1f714319f1ea318156b60e`。
远程 main 已前进，其 AirStack 指针为 `5f745b6e10ba7190ad2c33f0d0a69ff12d27dbcf`。
因此不得用旧源码快照直接覆盖最新 main；补丁在原基线经过 `git apply --cached --check`，最新基线是否有冲突见检查报告。

需要复核原实测代码时，在另一个临时 checkout/worktree 中检出上述原基线，分别应用两份补丁；先 `git apply --check`，再决定是否应用。AirStack 已有提交在本机 `airground` 分支。
本包不自动应用补丁、不执行 cherry-pick、不覆盖远程新功能，也不宣称完成最新 main 的集成回归。
`source/root/IMPLEMENTATION_PLAN.md` 是暂停时唯一任务清单的历史快照；它包含按时间追加的旧状态，须以本页暂停说明及清单中后续更正为准。

## 已完成的真实结果

- 第二台 RTX 4060 Laptop（8 GiB 显存、32 GiB 内存）运行 Windows Isaac Sim 4.5；WSL Humble/Nav2 与仿真通信、Jackal前进/转向/停车及局部导航已实测。
- RetroNeighborhood：0.05 m全图527块、32,235,504格完成并通过拼接/窗口对照；全图三目标路线有成功记录；31个论文目标62张真实审核图片保存在本地。
- 原预算三轮导航：9/9 action返回成功，但严格位置和朝向仅7/9、整轮2/3，稳定性不通过。新的严格控制配置尚未实测。
- ConstructionSite：发现并修正诊断配置中地形凸体失真及5075实例漏碰撞；修正后51,200格真实PhysX窗口一致性通过。
- FireAcademy：静态三角碰撞/双面射线扩大验证49,152格通过；尚无完整全图及正式GT。
- AbandonedFactory：真实基线证实合并地面凸体高度失真；候选修正未运行。
- 通用场景参数化、输入错配拒绝、引用路径映射、显式碰撞manifest接口等已有CPU检查。接口检查不等于完整双机器人运行通过。
- 其余五个可读取根USD的CPU碰撞覆盖检查已执行，结果留在本地 `runs/partial_scene_collisions_20261019/`，尚未纳入正式物理结论。

## 暂停断点：2026-10-19 16:46（北京时间）

用户明确要求 stop，持续目标已暂停；最后确认两个后台队列均 Ready，相关诊断进程为0。
ConstructionSite新地图保存52/70块、3,302,912/4,395,972格（按格数75.13%），状态 `operator_stop_file`；a03正常退出0。
数据集：第二台 `D:/RAVEN-4060/logs/construction-instance-map-20261019`。
契约SHA：`dc30bf4ac8d061ceb549233a18a7a8206b29380bac5d97acebcc205c909e0366`。
首20块120文件已回传并校验；全部52块未重新打包回主机，不可误称已完整备份。

旧ConstructionSite完整70块地图、旧S7候选因漏碰撞已添加INVALIDATED标记，绝不可用于导航或正式验收。
旧契约：`659129eb5189aeeaab7e7525956ce76c409a5215aae2f3359be5785069a749cd`。
ConstructionSite只取得12/56张有效原始RGB，部分图遮挡目标；第13视角稳定帧失败，不能记整批通过。

下列四项排队任务在暂停前均未启动：construction-portable-a01、construction-clock-a01、factory-triangle-a01、construction-review-a04。
STOP文件仍保留在地图数据集、construction-instance-batches-20261019及independent-diagnostics-20261019三个目录；不能未经明确恢复就删除。
有限队列的旧输出目录已有内容，原启动脚本会拒绝覆盖。恢复时先审查断点和源码哈希，再使用新的运行标识/配置。

## 接手者接下来需要处理的依赖

任务状态继续以 IMPLEMENTATION_PLAN.md 为准；以下是交接顺序说明，不另建完成清单。
先核验52块断点、停止状态及资源余量，随后完成新图剩余18块、全局后处理、独立窗口对照和归档。
新图通过后重新生成未审核S7候选，再验证实际PhysX时钟采样及可见性；不能沿用失效旧图的观察位姿。
GPU空闲后逐项验证通用碰撞接口、Factory修正及小批次审核拍图；FireAcademy全图准备完毕但未启动。
场景一末端收敛修正还须按原位置、朝向、0.25m/0.30rad容差及120s预算有界复测。
全部新场景正式验收0/9，正式episode0/270；reviewed GT、正式arrival_regions、10/10任务、30集审计、S8和实际UGV K=M均不能提前勾选。

## 人工/外部输入

- 所有目标逐实例verify/exclude仍待人工；ConstructionSite绑定歧义、篷布与塔吊层级、FireAcademy/Factory面级归属不能自动批准。
- 六个部分资产包仍缺完整依赖；SnowyVillage197个缺失引用资产，DowntownWest28个空mesh声明，需同版本完整包或作者说明。
- 35个大尺寸论文目标存在“到OBB表面1.5–8m”与当前可见性“到中心1.5–8m”的兼容问题，需老师确认协议/校验器版本，不能自行放宽阈值或排除目标。
- 视觉地面低于z=0支持平面的现象已测得；如需整体对齐，必须确认坐标策略并重验GT/地图。
- AbandonedCity缺car/yellow motorhome标注，SnowyVillage类别别名及Shipyard的ship silo任务解释待确认。

## 运行限制与未上传内容

仍使用Isaac Sim4.5/Humble；一次只运行一个GPU仿真，14GiB是进程提交内存上限，不是显存。
保持原内存/显存/超时/失联停车保护，不改VPN、不自动重启、不覆盖原始USD，不把CPU检查当真实PhysX。
诊断脚本记录了本机历史路径、用户名、局域网地址及固定诊断位置；这是实验源码快照，不是通用部署入口。迁移须显式检查路径、资产SHA和作业配置。
不含SSH私钥、密码、令牌、虚拟环境、第三方安装包、USD/贴图、原始NPZ/PGM地图、完整运行日志、视频或截图，也不含未经审核的运行GT/hidden输入。
原始证据保存在主机 `D:/xprogram/RAVEN-AirGround-github/runs/`、准备目录 `D:/xprogram/.raven-setup-cache/`，以及第二台 `D:/RAVEN-4060/logs/`、`setup/`、`assets/`。不要删除这些本地文件。
文档JSON中的日志路径/图片路径是本地证据索引，在GitHub上不会自动变成可访问的运行文件。

主机图片入口：`runs/paper31_review_20261018/teacher-report/查看进展.html`、`runs/nav2_dwb_stability_20261019/teacher-report/查看进展.html`、`runs/construction_adaptation_20261019/teacher-review-a03/查看进展.html`。
