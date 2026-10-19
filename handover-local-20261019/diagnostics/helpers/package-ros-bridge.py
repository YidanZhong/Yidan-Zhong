import hashlib
import html
import json
from pathlib import Path
import shutil
import zipfile

root=Path(r'D:\xprogram\RAVEN-AirGround-github')
run=root/'runs/ros_bridge_20261018'
data=json.loads((run/'evidence.json').read_text(encoding='utf-8'))
assert data['passed'] and data['cleanup']['ros_peer_absent']
target=run/'teacher-report'
target.mkdir(exist_ok=True)
text='''场景一复现进展：Windows 与 Linux ROS 双向通信已通过
日期：2026-10-18

可向老师汇报：
在已完成场景加载和 RTX 出图的基础上，已接通第二台 RTX 4060 电脑上的 Windows Isaac Sim 4.5 与 WSL Ubuntu 22.04 / ROS Humble。Linux 端收到了真实仿真时钟、相机图像与相机内参；Windows 仿真端收到了 Linux 发出的前进、转向和停止速度消息。当前完成的是消息链路验证，尚未把速度消息接到 Jackal 车轮，也尚未完成 Nav2 导航和论文实验。

实测证据：
• /clock 收到 488 条，只有一个发布者，时间没有倒退；接收范围 6.883333692–15.000000782 仿真秒。
• 实际相机输出 162 帧，Linux 收到 160 帧 480×300 RGB。收到的 160 帧像素 SHA-256 全部与发送端一致；未宣称零丢帧。
• CameraInfo 收到 162 条；图像时间戳与相机内参可配对。
• Windows 收到 166 条 /ugv/cmd_vel，包含 (0.1 m/s, 0 rad/s)、(0 m/s, 0.05 rad/s)、停止；末尾指令为停止。
• 双向运行标识回执匹配，双方正常退出。通信阶段约 35 秒墙钟；完整诊断含启动约 206.27 秒。
• 峰值进程提交内存 10.099 GiB；采样峰值显存约 3.08 GiB；最低可用物理内存 12.877 GiB。

实现与边界：
使用 Isaac 4.5 自带的 ROS 2 Bridge / rclpy、Fast DDS UDP、domain 42 和 WSL NAT 内网定向发现；未改 VPN。真实传感器缓冲区来自 Camera.get_rgba，时钟来自 World.current_time。截图文件 received-camera.png 是 Linux 通过 ROS 接收后保存的图像，未经编辑。
这不是完整 OmniGraph 机器人启动、机器人运动、TF/里程计、Nav2 或正式评分验收。35 秒低速诊断也不证明完整传感器与算法负载可实时运行。日志保留了内置 rosidl_generator_py 缺少可选代码生成依赖 em 的导入提示；本次现成消息类型运行成功，未验证自定义消息生成。
测试进程、临时任务及本轮两条限定来源的防火墙规则均已清理，专用 RAVEN WSL 已停止。

下一步：
接入仓库 Jackal 资产及差速驱动，验证真实前进/转向/停止、里程计与 TF；然后接入 Nav2。正式复现老师结果仍需对应的审核 GT、地图和 episode 输入。
'''
(target/'进展说明.txt').write_text(text,encoding='utf-8-sig')
shutil.copy2(run/'ros-bridge-a01-wsl/received-camera.png',target/'received-camera.png')
shutil.copy2(run/'evidence.json',target/'evidence.json')
page='<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>场景一 ROS 通信验证</title><style>body{max-width:1000px;margin:40px auto;padding:0 24px;font:17px/1.7 "Microsoft YaHei",sans-serif;background:#f4f6f8;color:#183247}img{max-width:100%;background:white}pre{white-space:pre-wrap;font:16px/1.8 "Microsoft YaHei",sans-serif;background:white;padding:24px}</style><h1>场景一：Windows ↔ Linux ROS 通信验证通过</h1><p>以下图像由 Linux 通过 ROS 接收并保存；160 帧收到的像素数据全部与发送端哈希一致。</p><img src="received-camera.png" alt="Linux ROS 实际接收的场景一图像"><pre>'+html.escape(text)+'</pre></html>'
(target/'查看进展.html').write_text(page,encoding='utf-8')
with zipfile.ZipFile(run/'teacher-report.zip','w',zipfile.ZIP_DEFLATED) as z:
    for p in sorted(target.iterdir()): z.write(p,p.name)
with zipfile.ZipFile(run/'teacher-report.zip') as z: assert z.testzip() is None
for relative,prefix in [('benchmark/README.md','../docs/development/ugv-ogn/'),('docs/benchmark_zh.md','development/ugv-ogn/')]:
    p=root/relative
    body=p.read_text(encoding='utf-8')
    body=body.replace('跨系统 ROS、导航与正式 episode 尚未验收。','跨系统 ROS 已由后续专项验证，导航与正式 episode 尚未验收。')
    line='> ROS 通信进展（2026-10-18）：Windows Isaac 4.5 ↔ WSL Humble 在独立 domain 42 实测通过：488 条仿真时钟无倒退、160 张 480×300 RGB 与发送端像素哈希全部一致、162 条 CameraInfo、166 条反向速度消息及运行标识回执；退出 0，内存与显存保护保留。仅验证消息链路，未驱动车轮、未验收 TF/里程计、Nav2 或 episode。临时进程、任务和两条测试防火墙规则均已清理。见[ROS 双向通信证据]('+prefix+'ros-bridge-20261018.json)。\n\n'
    if '> ROS 通信进展（2026-10-18）' not in body:
        head,rest=body.split('\n\n',1)
        body=head+'\n\n'+line+rest
    p.write_text(body,encoding='utf-8')
plan=root/'IMPLEMENTATION_PLAN.md'
body=plan.read_text(encoding='utf-8')
body=body.replace('跨系统 ROS、正式地图、导航与 episode 尚未验收，精确复现仍缺审核输入','跨系统 ROS 消息链路已验收，正式地图、机器人运动、导航与 episode 尚未验收，精确复现仍缺审核输入')
plan.write_text(body,encoding='utf-8')
for p in [root/'scripts/probe_isaac_ros_bridge.py',root/'scripts/probe_ros_wsl_peer.py',root/'scripts/probe_windows_scene_render.py']:
    shutil.copy2(p,run/p.name)
cache=Path(r'D:\xprogram\.raven-setup-cache')
for name in ['ros-bridge-a01.json','launch-raven-probe.py','run-ros-wsl-peer.sh','prepare-ros-bridge.ps1']:
    shutil.copy2(cache/name,run/name)
print(json.dumps({'report_zip_bytes':(run/'teacher-report.zip').stat().st_size,'passed':data['passed']}))
