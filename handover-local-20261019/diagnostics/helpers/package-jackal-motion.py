import hashlib
import html
import json
import math
from pathlib import Path
import shutil
import zipfile

root=Path(r'D:\xprogram\RAVEN-AirGround-github')
run=root/'runs/jackal_motion_20261018'
data=json.loads((run/'evidence.json').read_text(encoding='utf-8'))
assert data['passed'] and data['cleanup']['ros_peer_absent']
target=run/'teacher-report';target.mkdir(exist_ok=True)
metrics=data['metrics'];checks=data['checks']
summary=f'''场景一复现进展：Jackal 实际运动与 ROS 里程计/TF 验证通过
日期：2026-10-18

可向老师汇报：
已在第二台 RTX 4060 电脑上完成真实场景一中的 Jackal 低速运动验证：Linux ROS 发出的速度指令通过 Windows Isaac 的四轮关节驱动车辆，实际前进、转向、停止及指令断流后的自动停车均通过检查。Linux 接收的里程计和 TF 已与仿真端真实物理状态逐条比对。已保存四张真实相机截图、轨迹和两端运行日志。下一步是接入障碍物点云和规划地图，再运行 Nav2 目标点导航；完整论文实验尚未完成。

本轮实测：
• 前进距离 {metrics['forward_distance_m']:.3f} m；正向指令 0.25 m/s，持续约 4 秒仿真时间。
• 转向角 {metrics['turn_angle_rad']:.3f} rad（约 {math.degrees(metrics['turn_angle_rad']):.1f}°）。本轮验证有真实转向，不代表角速度跟踪已经精确标定。
• 停止段最大平移速度 {metrics['max_stopped_speed_mps']:.5f} m/s、偏航角速度 {checks['max_stopped_abs_yaw_rate_radps']:.5f} rad/s。
• 故意停止发送速度消息，超过看门狗时限后车轮收到零速度，车辆停下。
• Linux 收到 {checks['odom_received']} 组里程计和 TF，{checks['physx_odom_tf_exact_matches']}/{checks['odom_received']} 的时间戳、位置与四元数均与 PhysX 状态一致。
• 357 条仿真时钟，无倒退、只有一个发布者；仿真端收到 325 条速度指令。
• 有界运动诊断持续 19 秒仿真时间；整体程序含启动耗时 83.25 秒，正常退出 0。
• 峰值进程提交内存约 10.715 GiB，采样峰值显存约 3.40 GiB；保护限制未放宽。

图像说明：
01-start.png、02-forward.png、03-turn.png、04-stopped.png 分别是起步前、前进后、转向后、最终停止阶段的原始 960×600 相机图像。相机跟随车辆取景，位移应以物理轨迹和周围地标核对，不能用车辆在画面中的像素移动直接量距。图像未编辑。

实现与限制：
使用官方 Jackal 资产及仓库包装层、差速参数、轮胎接触和摩擦设置；运动期间仅控制四个车轮关节，未用修改车体 pose 的方式移动机器人。采用 120 Hz CPU 物理诊断，沿用仓库 z=0 隐形支持平面；此前可视道路抽样约 z=-0.191 m，因此截图中车轮可能显得高于可视路面，完整地图与地面高度仍需后续核验。
里程计来源是 PhysX 车体状态，不是编码器或定位算法；map→ugv/odom 是诊断恒等变换，ugv/odom→ugv/base_link 是实际物理位姿。尚未接入车载障碍点云，尚未运行 Nav2，也未取得正式 episode 成绩。
首轮因末端记录只有 18.97 秒触发时长门失败，已修正终点采样并重跑；另一次显卡状态查询超时被保护门停止，随后查询恢复，保持原限制重试通过。失败记录完整保留。
本轮测试进程、临时任务和两条测试防火墙规则均已清理，专用 RAVEN WSL 已停止，VPN 配置未变。

接下来要补齐：
机器人障碍物 PointCloud2 与传感器 TF、可用的规划地图、Nav2 启动及 NavigateToPose 实测。正式对比老师结果还需要相同版本的审核 GT、地图与 episode 输入。
'''
(target/'进展说明.txt').write_text(summary,encoding='utf-8-sig')
names=[('jackal-start.png','01-start.png','起步前'),('jackal-forward.png','02-forward.png','前进后'),
       ('jackal-turn.png','03-turn.png','转向后'),('jackal-stopped.png','04-stopped.png','最终停止')]
provenance=[]
for source,dest,label in names:
    p=run/'jackal-motion-a03-frames'/source
    shutil.copy2(p,target/dest)
    provenance.append({'file':dest,'source':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'label':label})
for name in ['evidence.json','trajectory.csv']: shutil.copy2(run/name,target/name)
(target/'image-provenance.json').write_text(json.dumps(provenance,ensure_ascii=False,indent=2),encoding='utf-8')
cards=''.join(f'<figure><img src="{dest}" alt="{label}：实际相机图像"><figcaption>{label} · 960×600 原始相机图像</figcaption></figure>' for _,dest,label in names)
page='<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>Jackal 真实运动验证</title><style>body{max-width:1050px;margin:35px auto;padding:0 24px;font:17px/1.7 "Microsoft YaHei",sans-serif;background:#f3f6f9;color:#163247}h1{font-size:30px}.status{background:#e0f0e7;padding:18px}figure{background:white;padding:16px;margin:24px 0}img{max-width:100%;display:block;margin:auto}figcaption{margin-top:10px}pre{white-space:pre-wrap;background:white;padding:24px;font:15px/1.8 "Microsoft YaHei",sans-serif}</style><h1>场景一：Jackal 已实际运动</h1><p class="status">前进 0.976 米 · 转向 49.3° · 停止与断流停车通过 · 357 组里程计/TF 匹配<br>尚未验收 Nav2 导航与论文实验。</p>'+cards+'<h2>运行说明</h2><pre>'+html.escape(summary)+'</pre></html>'
(target/'查看进展.html').write_text(page,encoding='utf-8')
with zipfile.ZipFile(run/'teacher-report.zip','w',zipfile.ZIP_DEFLATED) as z:
    for p in sorted(target.iterdir()): z.write(p,p.name)
with zipfile.ZipFile(run/'teacher-report.zip') as z: assert z.testzip() is None
for name in ['probe_windows_scene_render.py','probe_jackal_motion.py','probe_jackal_wsl_peer.py','run_windows_probe.py']:
    shutil.copy2(root/'scripts'/name,run/name)
shutil.copy2(root/'scripts/probe_jackal_motion.py',run/'probe_jackal_motion-final.py')
cache=Path(r'D:\xprogram\.raven-setup-cache')
for name in ['jackal-motion-a01.json','jackal-motion-a02.json','jackal-motion-a03.json','run-jackal-wsl-peer.sh','prepare-ros-bridge.ps1']:
    shutil.copy2(cache/name,run/name)
for relative,prefix in [('benchmark/README.md','../docs/development/ugv-ogn/'),('docs/benchmark_zh.md','development/ugv-ogn/')]:
    p=root/relative;body=p.read_text(encoding='utf-8')
    line='> Jackal 运动进展（2026-10-18）：真实 Retro 场景中的四轮关节驱动通过：前进 0.976 m、转向 49.3°、停止和断流停车成功；WSL 收到 357 组里程计/TF，逐条与 PhysX 位姿一致，单时钟无倒退。保存四张 960×600 原始图像，程序退出 0，峰值提交内存 10.715 GiB、显存约 3.40 GiB。120 Hz 诊断使用仓库支持平面；里程计是仿真状态、map→odom 为诊断恒等变换，未验收定位、障碍点云、Nav2 或正式 episode。见[真实运动证据]('+prefix+'jackal-motion-20261018.json)。\n\n'
    if '> Jackal 运动进展（2026-10-18）' not in body:
        head,rest=body.split('\n\n',1);body=head+'\n\n'+line+rest
    p.write_text(body,encoding='utf-8')
p=root/'IMPLEMENTATION_PLAN.md';body=p.read_text(encoding='utf-8')
body=body.replace('跨系统 ROS 消息链路已验收，正式地图、机器人运动、导航与 episode 尚未验收','跨系统 ROS 和有界 Jackal 运动/里程计/TF 已验收，正式地图、Nav2 导航与 episode 尚未验收')
p.write_text(body,encoding='utf-8')
print(json.dumps({'teacher_zip_bytes':(run/'teacher-report.zip').stat().st_size,'images':4,'passed':data['passed']}))
