from pathlib import Path
import csv
import base64
import hashlib
import html
import json
import math
import shutil
import zipfile
import numpy as np
from PIL import Image

root=Path(r'D:\xprogram\RAVEN-AirGround-github')
run=root/'runs/nav2_local_goal_20261018'
def read(path): return json.loads(path.read_text(encoding='utf-8-sig'))
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
jobs=[]
for path in sorted(run.glob('jackal-nav2-a??')):
    execution=read(path/'execution.json')
    if execution.get('status')=='completed': jobs.append(path.name)
assert jobs,'No successful guarded native run'
job=jobs[-1]
frames=run/f'{job}-frames';wsl=run/f'{job}-wsl'
native=read(frames/'jackal-nav2.json');ros=read(wsl/'ros-evidence.json')
execution=read(run/job/'execution.json');render=read(frames/'report.json')
assert native['passed'] and ros['passed'] and execution['exit_code']==0
assert ros['tour']['goals'][0]['result_status']==4
clouds={round(c['sim_time_s']*1e9):c for c in native['clouds']}
cloud_matches=sum(c['sha256']==clouds.get(round(c['sim_time_s']*1e9),{}).get('sha256') for c in ros['clouds'])
assert cloud_matches==len(ros['clouds']) and cloud_matches>10
samples={round(s['sim_time_s']*1e9):s for s in native['samples']}
odom_matches=sum(math.dist([o['x'],o['y'],o['z']],samples.get(round(o['sim_time_s']*1e9),{'position':[1e9]*3})['position'])<1e-6 for o in ros['odom'])
assert odom_matches==len(ros['odom']) and odom_matches>10
resources=[json.loads(line) for line in (run/job/'resources.jsonl').read_text().splitlines()]
cleanup=read(run/'nav2-local-goal-cleanup-20261018.json')
assert cleanup['isolated_wsl_stopped'] and cleanup['temporary_firewall_rules_removed']
evidence={'task':'Local-Scene1-Reproduction / Second-PC-Runtime / Jackal-Nav2-LocalGoal',
    'date':'2026-10-18','job':job,'passed':True,'scope':'single local Nav2 goal diagnostic',
    'scene1_reproduced':False,'real_paper_episode_count':0,
    'simulator':'Isaac Sim 4.5.0 native Windows','ros':'Humble / domain 42 / FastDDS UDP',
    'hardware':'RTX 4060 Laptop 8 GiB / 32 GiB RAM / driver 577.02',
    'scene_sha256':render.get('scene_sha256'),
    'metrics':native['metrics'],'nav2_tour':ros['tour'],
    'map':native['map'],'cloud_subscribers':ros['cloud_subscribers'],'costmaps':ros['costmaps'],
    'cross_check':{'cloud_hash_matches':cloud_matches,'clouds_received':len(ros['clouds']),
        'odom_matches_physx':odom_matches,'odom_received':len(ros['odom']),
        'clock_count':ros['clock_count'],'clock_backwards':ros['clock_backwards'],
        'max_clock_publishers':ros['max_clock_publishers'],'planned_paths':len(ros['plans'])},
    'resources':{'peak_job_commit_gib':execution['peak_job_commit_gib'],
        'peak_gpu_memory_gib':max(s['gpu_memory_fraction'] for s in resources)*8188/1024,
        'min_physical_available_gib':min(s['available_gib'] for s in resources),
        'min_commit_available_gib':min(s['available_commit_gib'] for s in resources),
        'limits':execution['limits'],'exit_code':execution['exit_code'],'wall_seconds':execution['elapsed_s']},
    'limitations':['PhysX state odometry, no localization validation','CPU raycast cloud, not RTX lidar',
        '20 m local vertical projection, not reviewed traversability/GT','runtime z=0 support plane',
        'one short goal, no forced obstacle detour/dynamic obstacle acceptance',
        'No semantic search, UAV cooperation, reviewed episodes or paper score'],
    'cleanup':cleanup,'artifacts':'runs/nav2_local_goal_20261018/',
    'validation':{'native_command_file':f'runs/nav2_local_goal_20261018/{job}/execution.json',
        'wsl_command_file':f'runs/nav2_local_goal_20261018/{job}-wsl/command.json',
        'source_compile':'python -m py_compile scripts/probe_jackal_nav2.py scripts/probe_nav2_wsl_peer.py scripts/probe_windows_scene_render.py',
        'camera_images_visually_inspected':3,'image_dimensions':[960,600],
        'render_stability':[{'consecutive_valid_frames':f['consecutive_valid_frames'],'invalid_frames_after_first':f['invalid_frames_after_first']} for f in render['frames']]},
    'failed_attempts':[{ 'job':p.name, 'execution':read(p/'execution.json')} for p in sorted(run.glob('jackal-nav2-a??')) if p.name!=job],
    'source_sha256':{p.name:sha(p) for p in sorted((run/'source').glob('*.py'))}}
report=run/'teacher-report';report.mkdir(exist_ok=True)
for i,name in enumerate(['start','moving','stopped'],1):
    shutil.copy2(frames/f'nav2-{name}.png',report/f'0{i}-{name}.png')
shutil.copy2(frames/'local-map.png',report/'local-map.png')
shutil.copy2(frames/'local-map.yaml',report/'local-map.yaml')
shutil.copy2(frames/'local-map.pgm',report/'local-map.pgm')
for name in ('local','global'):
    cost=read(wsl/f'{name}-latest.json')
    values=np.array(cost['data']).reshape(cost['height'],cost['width'])[::-1]
    rgb=np.zeros((*values.shape,3),dtype=np.uint8)
    rgb[:]=[240,242,245];rgb[values<0]=[128,128,128]
    positive=(values>0)&(values<99)
    rgb[positive]=np.stack([255*np.ones(positive.sum()),220-1.6*values[positive],220-1.6*values[positive]],axis=1).astype(np.uint8)
    rgb[values==99]=[240,145,25];rgb[values>=100]=[15,25,35]
    Image.fromarray(rgb).resize((800,800),Image.Resampling.NEAREST).save(report/f'{name}-costmap.png')
    static=np.array(Image.open(frames/'local-map.pgm'))
    coords=np.argwhere(values[::-1]==100)
    added=0
    for iy,ix in coords:
        x=cost['origin'][0]+(ix+.5)*cost['resolution'];y=cost['origin'][1]+(iy+.5)*cost['resolution']
        mx=int((x-native['map']['origin'][0])/.1);my=int((y-native['map']['origin'][1])/.1)
        if 0<=mx<200 and 0<=my<200 and static[199-my,mx]==254: added+=1
    evidence.setdefault('costmap_extra_lethal_over_static_free',{})[name]=added
origin=native['map']['origin']
def pixel(p): return ((p[0]-origin[0])*40,800-(p[1]-origin[1])*40)
def poly(points): return ' '.join(f'{pixel(p)[0]:.2f},{pixel(p)[1]:.2f}' for p in points)
plan=ros['plans'][0]['xy'];track=[s['position'][:2] for s in native['samples']]
sx,sy=pixel(track[0]);gx,gy=pixel(native['goal_xy'])
cloud=np.load(frames/'cloud-first.npz')['world_xyz']
circles=''.join(f'<circle cx="{pixel(p)[0]:.2f}" cy="{pixel(p)[1]:.2f}" r="1.5" fill="#8b38bb" opacity=".6"/>' for p in cloud)
svg=f'''<svg xmlns="http://www.w3.org/2000/svg" width="800" height="800" viewBox="0 0 800 800">
<image href="data:image/png;base64,{base64.b64encode((report/'local-map.png').read_bytes()).decode()}" width="800" height="800"/>{circles}
<polyline points="{poly(plan)}" fill="none" stroke="#006bea" stroke-width="5"/>
<polyline points="{poly(track)}" fill="none" stroke="#16a34a" stroke-width="2.5"/>
<circle cx="{sx}" cy="{sy}" r="5" fill="#16a34a"/><circle cx="{gx}" cy="{gy}" r="7" fill="none" stroke="#e63946" stroke-width="3"/>
</svg>'''
(report/'map-route.svg').write_text(svg,encoding='utf-8')
with (report/'trajectory.csv').open('w',newline='',encoding='utf-8-sig') as f:
    writer=csv.writer(f);writer.writerow(['sim_time_s','x_m','y_m','z_m','cmd_v_mps','cmd_w_radps'])
    for sample in native['samples']:writer.writerow([sample['sim_time_s'],*sample['position'],*sample['applied_command']])
m=native['metrics'];g=ros['tour']['goals'][0];r=evidence['resources']
text=f'''场景一：本机 Nav2 单目标导航验证（2026-10-18）

本次完成：真实 RetroNeighborhood 场景中，Nav2 接收目标、规划路径、输出速度，驱动 Jackal 四轮运动并返回 SUCCEEDED（状态 4）。
目标：(-27.5, -21.5) m；初始位置约 (-30, -21.5) m。
实际平面位移 {m['displacement_m']:.3f} m，轨迹长度 {m['path_length_m']:.3f} m，最终目标误差 {m['final_goal_error_m']:.3f} m。
Nav2 目标阶段耗时 {g['sim_time_s']:.3f} 仿真秒；停车速度 {m['final_speed_mps']:.5f} m/s。

真实数据：20×20 m、0.1 m 分辨率局部碰撞查询地图，包含 {native['map']['occupied_cells']} 个障碍栅格。
Windows 发布 CPU PhysX 射线点云，WSL 收到 {len(ros['clouds'])} 帧，{cloud_matches}/{len(ros['clouds'])} 数据哈希与发送端一致。
WSL 收到 {len(ros['odom'])} 条里程计，{odom_matches}/{len(ros['odom'])} 与 PhysX 记录一致；单时钟、无倒退。
Nav2 发布 {len(ros['plans'])} 条规划路径，局部和全局代价地图均有障碍标记。点云订阅节点：{', '.join(ros['cloud_subscribers'])}。
本测试没有安排必须绕行的障碍，因此不把单次到达宣传为完整避障能力验收。

资源与运行：Isaac Sim 4.5.0 原生 Windows + WSL Ubuntu 22.04 / ROS Humble；RTX 4060 Laptop 8 GiB，32 GiB 内存。
峰值 Isaac 作业提交内存 {r['peak_job_commit_gib']:.3f} GiB、显存约 {r['peak_gpu_memory_gib']:.2f} GiB；全流程 {r['wall_seconds']:.2f} 秒、退出 0。
内存/显存/超时保护保留；临时仿真、ROS、计划任务、防火墙规则已清理。

边界：这是单目标本机导航诊断，不是论文场景一完整复现。使用仿真状态里程计，未验证 SLAM/定位；CPU 射线点云不代表 RTX 激光雷达已验收。
地图是未审核的局部垂直投影，运行沿用 z=0 支持平面。正式论文 episode 为 0；尚未完成语义搜索、UAV 协同、10任务×3出生点评测。
下一阶段：扩展可通行地图，做转弯和障碍绕行，再接入 handover 的目标/任务；要与老师结果精确对齐仍需审核后的 GT、地图、episode 和运行配置。

截图说明：01–03 是实际相机原始 RGB；地图/轨迹图和代价地图由实际记录的数据绘制，不是相机截图。原图未做内容修改。
运行编号：{job}；完整日志、命令、数据和来源哈希保存在上级目录。
'''
(report/'进展说明.txt').write_text(text,encoding='utf-8-sig')
page=f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>场景一：Nav2 单目标导航进展</title>
<style>body{{max-width:1120px;margin:36px auto;padding:0 24px;font:17px/1.75 system-ui,"Microsoft YaHei";background:#f3f6fa;color:#172438}}h1{{line-height:1.3}}section{{background:white;border-radius:14px;padding:24px;margin:20px 0}}img{{width:100%;height:auto}}.grid{{display:grid;grid-template-columns:1fr 1fr;gap:20px}}.metric{{font-size:24px;font-weight:700;color:#125b41}}pre{{white-space:pre-wrap;font:inherit}}figure{{margin:0}}figcaption{{font-size:15px;color:#49566a}}@media(max-width:700px){{.grid{{display:block}}}}</style>
<h1>场景一：Nav2 已完成一次真实目标导航</h1><p>2026-10-18 · RTX 4060 Laptop · Isaac Sim 4.5 / ROS Humble</p>
<section class="grid"><div class="metric">实际位移 {m['displacement_m']:.3f} m</div><div class="metric">最终误差 {m['final_goal_error_m']:.3f} m</div><div>NavigateToPose 返回 SUCCEEDED（4）</div><div>正式论文实验尚未完成</div></section>
<section><h2>实际运行截图</h2><div class="grid"><figure><img src="01-start.png"><figcaption>启动位置：原始相机 RGB</figcaption></figure><figure><img src="02-moving.png"><figcaption>Nav2 驱动车轮行驶中</figcaption></figure></div><figure><img src="03-stopped.png"><figcaption>目标附近到达并停车：原始相机 RGB</figcaption></figure></section>
<section><h2>真实地图、点云和路径</h2><div class="grid"><figure><img src="map-route.svg"><figcaption>20×20 m 局部地图；黑色为障碍，紫色为首帧射线点云，蓝线为首条规划，绿线为实际轨迹，红圈为目标。</figcaption></figure><figure><img src="local-costmap.png"><figcaption>Nav2 实际发布的局部代价地图。黑色：致命障碍；橙色：内接区域；浅红：膨胀代价。两图覆盖范围不同。</figcaption></figure></div></section>
<section><h2>可直接向老师汇报</h2><pre>{html.escape(text)}</pre><p><a href="evidence.json">结构化证据</a> · <a href="trajectory.csv">轨迹 CSV</a> · <a href="进展说明.txt">文字说明</a></p></section></html>'''
(report/'查看进展.html').write_text(page,encoding='utf-8')
evidence['images']=[{'file':p.name,'sha256':sha(p),'unaltered_camera_rgb':True} for p in sorted(report.glob('0*.png'))]
(report/'evidence.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2),encoding='utf-8')
(root/'docs/development/ugv-ogn/nav2-local-goal-20261018.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2),encoding='utf-8')
with zipfile.ZipFile(run/'teacher-report.zip','w',zipfile.ZIP_DEFLATED) as z:
    for p in sorted(report.iterdir()): z.write(p,p.name)
print(json.dumps({'job':job,'metrics':m,'cross_check':evidence['cross_check'],'resources':r,
                  'extra_lethal':evidence['costmap_extra_lethal_over_static_free']},ensure_ascii=False,indent=2))
