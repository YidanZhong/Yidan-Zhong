from pathlib import Path
root=Path(r'D:\xprogram\RAVEN-AirGround-github')
p=root/'IMPLEMENTATION_PLAN.md';s=p.read_text(encoding='utf-8')
old=next(l for l in s.splitlines() if '- [ ] Scene1-Target-Integration' in l)
new='    - [x] Scene1-Target-Integration（2026-10-18）：`jackal-target-a01` 将 `retro-type-i-bus-stop` 的 `RetroNeighborhood.bus_stop.0002` 接入诊断；从 (-30,-24) 经真实 Nav2 驶近 (-30,-18)，SUCCEEDED（4），实际路径 8.859 m、位移 5.817 m、最终误差 0.198 m、停车速度 0.00174 m/s。停车后在实际 XY、z=1.2 m、HFOV 90° 的目标朝向诊断相机取得五个不同渲染帧，每帧五条真实 PhysX 射线均无遮挡；OBB 表面距离 3.683 m，原始射线命中路径已保存。运行时模型包围盒与导出候选一致，11 张原始 RGB 已检查。源 `scripts/probe_target_confirmation.py` 和 `scripts/probe_windows_scene_render.py`；Isaac Python 导入/目标窗口预检及 py_compile 通过，接收端 560 帧点云哈希、2,123 组里程计与源逐条一致。两端退出 0，峰值提交内存 10.820 GiB / 显存约 3.23 GiB，资源保护未改，临时运行资源已清理。原生命令 `runs/target_integration_20261018/jackal-target-a01/execution.json`，WSL 命令同目录 `jackal-target-a01-wsl/command.json`；证据 `docs/development/ugv-ogn/target-integration-20261018.json`，图文包 `runs/target_integration_20261018/teacher-report.zip`。全库 165 实例自动绑定、154 歧义，另产出论文 31 实例审核队列与不可直接 apply 的台账模板；本实例仍 verified=false / ground_reachable=unknown，正式 catalog 10/10 blocked、episode=0。本项只验收单实例接入诊断：未运行语义检测，相机朝向取自已知目标，不代表机载相机控制；五帧沿用 Isaac 时间但未验收可见性 ROS 话题。0.1 m 局部图上最小保守外接圆净空 0.077 m，需正式 0.05 m 图复核，不认定通过 handover 净空门；转向效率、z=0 支持平面与视觉路面的高度差仍有局限。全场景 S4/S8/S10 及论文复现保持未完成。'
s=s.replace(old,new);p.write_text(s,encoding='utf-8')
for rel,link in [('benchmark/README.md','../docs/development/ugv-ogn/target-integration-20261018.json'),('docs/benchmark_zh.md','development/ugv-ogn/target-integration-20261018.json')]:
 p=root/rel;s=p.read_text(encoding='utf-8');head,body=s.split('\n',1)
 block='> 公交站目标接入进展（2026-10-18）：单个未审公交站实例已由真实 Nav2 驶近并停车，路径 8.859 m、最终误差 0.198 m；停车后的目标朝向诊断相机（1.2 m / HFOV 90°）取得五个不同渲染帧，每帧五条 PhysX 射线均无遮挡，OBB 表面距离 3.683 m。11 张原始 RGB 已检查，560 帧点云及 2,123 组里程计跨端核对通过，退出 0，临时资源已清理。尚未执行语义检测或验证机载相机控制，目标保持 verified=false / ground_reachable=unknown，正式 catalog 10/10 blocked、论文 episode=0；已保存 31 个论文实例审核队列与台账草稿。0.1 m 局部图最小保守外接圆净空 0.077 m，仍需正式 0.05 m 地图复核；转向效率和支持平面与视觉路面高度差也尚未解决。该结果只对应目标接入及审核辅助，不能关闭全场景 handover 验收。见[公交站目标接入证据]('+link+')。'
 p.write_text(head+'\n\n'+block+'\n'+body,encoding='utf-8')
p=root/'docs/development/ugv-ogn/README.md';s=p.read_text(encoding='utf-8')
old=next(l for l in s.splitlines() if '| `nav2-route-20261018.json`' in l)
s=s.replace(old,old+'\n| `target-integration-20261018.json` | 单个未审公交站接入、真实驶近、五帧目标 RGB/PhysX 可见性、11 张原图和 31 实例审核草稿；未执行语义检测，正式 episode=0 |')
p.write_text(s,encoding='utf-8')
print('Synchronized target integration scope, results, validation and limitations.')
