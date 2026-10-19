from pathlib import Path

root = Path(r'D:\xprogram\RAVEN-AirGround-github')
p = root / 'IMPLEMENTATION_PLAN.md'
s = p.read_text(encoding='utf-8')
s = s.replace('局部地图与点云接入后的单目标 Nav2 导航已验收；正式全图、复杂避障、多目标和论文 episode 尚未验收', '局部地图与点云接入后的单目标导航、连续三目标转弯与一次静态障碍绕行已验收；正式全图、动态障碍、语义任务和论文 episode 尚未验收')
s = s.replace('已通过实际渲染、ROS、轮式运动和局部单目标 Nav2；', '已通过实际渲染、ROS、轮式运动、局部单目标 Nav2 和连续三目标静态绕障；')
old = next(line for line in s.splitlines() if '- [ ] Jackal-Nav2-RouteCoverage：' in line)
new = '    - [x] Jackal-Nav2-RouteCoverage（2026-10-18）：复用实际 20×20 m 局部地图，扩展为连续三个目标（含转弯、穿树木碰撞投影直线的绕行、返回起点），`jackal-route-a02` 全部 SUCCEEDED（4），目标间无重置/传送。实际轨迹 22.062 m，最终误差 0.242 m，停车速度 0.00230 m/s；首段相对穿障直线偏离最大 1.621 m，扣除车体外接圆后的静态保守净空最小 0.384 m，轨迹中心无障碍/未知栅格命中。WSL 收到的 1,051 帧点云哈希和 3,986 组里程计逐条匹配源数据，单时钟无倒退；保存 187 条规划、代价地图证据及七张已检查的 960×600 原始 RGB。首次 a01 因诊断角加速度覆盖值 0.4 导致停驻转向死锁而超时，保留失败证据；移除覆盖、恢复仓库默认 20 后通过，角速度/轮扭矩/失联停车及资源上限未放宽。源码 `scripts/probe_jackal_nav2.py`、`scripts/probe_nav2_wsl_peer.py`、`scripts/probe_windows_scene_render.py`，验证 `python -m py_compile` 和两端数据交叉审计；原生命令 `runs/nav2_route_20261018/jackal-route-a02/execution.json`、WSL 命令 `jackal-route-a02-wsl/command.json`，两端退出 0。证据 `docs/development/ugv-ogn/nav2-route-20261018.json`，展示包 `runs/nav2_route_20261018/teacher-report.zip`；峰值提交内存 10.934 GiB / 显存约 3.35 GiB，临时进程、任务和网络规则已清理，专用 WSL 已停止。本项只验收这条静态路线，第二段路径效率尚未优化；继续使用 PhysX 里程计、CPU 点云、未审局部投影及 z=0 支持平面，未验收定位、RTX 雷达、动态障碍、语义搜索或论文 episode。下一阶段按 handover 接入正式目标绑定和任务输入。'
s = s.replace(old, new)
p.write_text(s, encoding='utf-8')

for rel, link in [('benchmark/README.md', '../docs/development/ugv-ogn/nav2-route-20261018.json'), ('docs/benchmark_zh.md', 'development/ugv-ogn/nav2-route-20261018.json')]:
    p = root / rel
    s = p.read_text(encoding='utf-8')
    head, body = s.split('\n', 1)
    block = '> 连续三目标与静态绕障进展（2026-10-18）：同一段真实仿真中完成三个 Nav2 目标，均 SUCCEEDED（4），包含转弯、绕开树木碰撞投影和返回起点，目标间无重置/传送。路径 22.062 m，最终误差 0.242 m，停车速度 0.00230 m/s；实际轨迹扣除车体外接圆后的最小静态净空 0.384 m，中心未进入已测障碍或未知区。1,051 帧接收点云哈希和 3,986 组里程计全部匹配源记录，保存 187 条规划及七张已检查的原始截图。恢复仓库默认角加速度解决首次停驻转向死锁，失败证据保留；其他速度、轮扭矩和资源保护未放宽。成功运行退出 0，峰值提交内存 10.934 GiB / 显存约 3.35 GiB，临时资源已清理。此项仅验收一条静态路线，第二段路径效率仍待优化；使用 PhysX 里程计、CPU 点云、未审局部地图和支持平面，定位、RTX 雷达、动态障碍、语义任务和正式论文 episode 尚未验收。见[三目标绕障证据](' + link + ')。以下为此前阶段记录。'
    p.write_text(head + '\n\n' + block + '\n' + body, encoding='utf-8')

p = root / 'docs/development/ugv-ogn/README.md'
s = p.read_text(encoding='utf-8')
old = next(line for line in s.splitlines() if '| `nav2-local-goal-20261018.json`' in line)
s = s.replace(old, old + '\n| `nav2-route-20261018.json` | 连续三目标、转弯、静态树木绕行并返回起点；1,051 帧点云与 3,986 组里程计交叉核对、七张原始截图及首次失败记录；仅验收该路线，正式论文 episode 仍为 0 |')
p.write_text(s, encoding='utf-8')
print('Synchronized route evidence in plan and three documentation files.')
