from pathlib import Path
import base64
import csv
import hashlib
import html
import json
import math
import shutil
import zipfile
import numpy as np

root=Path(r'D:\xprogram\RAVEN-AirGround-github')
run=root/'runs/nav2_route_20261018'
def read(path): return json.loads(path.read_text(encoding='utf-8-sig'))
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
jobs=[p.name for p in sorted(run.glob('jackal-route-a??')) if read(p/'execution.json').get('status')=='completed']
assert jobs,'No passing guarded route run'
job=jobs[-1];frames=run/f'{job}-frames';wsl=run/f'{job}-wsl'
native=read(frames/'jackal-nav2.json');ros=read(wsl/'ros-evidence.json')
execution=read(run/job/'execution.json');render=read(frames/'report.json')
assert native['passed'] and ros['passed'] and execution['exit_code']==0
assert ros['tour']['reached_count']==3 and all(g['result_status']==4 for g in ros['tour']['goals'])
clouds={round(c['sim_time_s']*1e9):c for c in native['clouds']}
cloud_matches=sum(c['sha256']==clouds.get(round(c['sim_time_s']*1e9),{}).get('sha256') for c in ros['clouds'])
assert cloud_matches==len(ros['clouds']) and cloud_matches>10
samples={round(s['sim_time_s']*1e9):s for s in native['samples']}
odom_matches=sum(math.dist([o['x'],o['y'],o['z']],samples.get(round(o['sim_time_s']*1e9),{'position':[1e9]*3})['position'])<1e-6 for o in ros['odom'])
assert odom_matches==len(ros['odom']) and odom_matches>10
terminal=ros['terminal_actions'];assert len(terminal)==3
actions=[]
for goal,action in zip(native['goals_xy'],terminal):
    assert action['status']==4 and action['odom']
    o=action['odom'];error=math.dist(goal,[o['x'],o['y']]);assert error<.4
    near=min(native['samples'],key=lambda s:abs(s['sim_time_s']-o['sim_time_s']))
    x,y,z,w=near['quaternion_xyzw'];yaw=math.atan2(2*(w*z+x*y),1-2*(y*y+z*z))
    actions.append({'goal':goal,'action_status':4,'sim_time_s':action['sim_time_s'],
                    'observed_goal_error_m':error,'observed_goal_yaw_rad':yaw,'pose':near['position']})
first=[s for s in native['samples'] if s['sim_time_s']<=terminal[0]['sim_time_s']]
start=np.array(first[0]['position'][:2]);goal=np.array(native['goals_xy'][0]);direction=goal-start
cross_track=max(abs(direction[0]*(s['position'][1]-start[1])-direction[1]*(s['position'][0]-start[0]))/np.linalg.norm(direction) for s in first)
assert native['direct_legs'][0]['center_samples_on_obstacles']>0 and cross_track>.5
assert native['metrics']['map_geometry']['min_circumscribed_footprint_clearance_m']>0
resources=[json.loads(line) for line in (run/job/'resources.jsonl').read_text().splitlines()]
cleanup=read(run/'nav2-route-cleanup-20261018.json')
assert cleanup['isolated_wsl_stopped'] and cleanup['temporary_firewall_rules_removed']
evidence={'task':'Local-Scene1-Reproduction / Second-PC-Runtime / Jackal-Nav2-RouteCoverage',
    'date':'2026-10-18','job':job,'passed':True,'scope':'three goals with turning and static obstacle detour',
    'scene1_reproduced':False,'real_paper_episode_count':0,
    'simulator':'Isaac Sim 4.5.0 native Windows','ros':'Humble / domain 42 / FastDDS UDP',
    'hardware':'RTX 4060 Laptop 8 GiB / 32 GiB RAM / driver 577.02','scene_sha256':render['scene_sha256'],
    'metrics':native['metrics'],'nav2_tour':ros['tour'],'terminal_action_checks':actions,
    'direct_legs':native['direct_legs'],'first_leg_max_cross_track_m':float(cross_track),
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
    'limitations':['PhysX state odometry, not SLAM/localization','CPU raycast cloud, not RTX lidar',
        'Local vertical projection with runtime z=0 support plane, not reviewed GT',
        'Static obstacle detour on one route; no dynamic obstacle/general collision acceptance',
        'No semantic search, UAV cooperation, reviewed episodes or paper score'],
    'cleanup':cleanup,'artifacts':'runs/nav2_route_20261018/',
    'failed_attempts':[{'job':p.name,'execution':read(p/'execution.json')} for p in sorted(run.glob('jackal-route-a??')) if p.name!=job],
    'correction':'Removed diagnostic angular_accel=0.4 override; repository RPP default 20 retained. Angular speed, wheel torque, watchdog and resource limits unchanged.',
    'validation':{'native_command_file':f'{job}/execution.json','wsl_command_file':f'{job}-wsl/command.json',
        'source_compile':'python -m py_compile scripts/probe_jackal_nav2.py scripts/probe_nav2_wsl_peer.py scripts/probe_windows_scene_render.py'},
    'source_sha256':{p.name:sha(p) for p in sorted((run/'source').glob('*.py'))}}
report=run/'teacher-report';report.mkdir(exist_ok=True)
images=[]
for i,entry in enumerate(native['images'],1):
    name=f'{i:02d}-'+entry['file'];shutil.copy2(frames/entry['file'],report/name)
    images.append({**entry,'file':name,'sha256':sha(report/name),'unaltered_camera_rgb':True})
evidence['images']=images
evidence['validation']['manually_inspected_original_rgb_images']=7
evidence['validation']['image_resolution_px']=[960,600]
for name in ['local-map.png','local-map.pgm','local-map.yaml']:
    shutil.copy2(frames/name,report/name)
origin=native['map']['origin']
def pixel(p):return ((p[0]-origin[0])*40,800-(p[1]-origin[1])*40)
def poly(points):return ' '.join(f'{pixel(p)[0]:.2f},{pixel(p)[1]:.2f}' for p in points)
planned=ros['plans'][0]['xy'];track=[s['position'][:2] for s in native['samples']]
labels=''
for i,g in enumerate(native['goals_xy'],1):
    x,y=pixel(g);labels+=f'<circle cx="{x}" cy="{y}" r="8" fill="#e63946"/><text x="{x+12}" y="{y-10}" font-size="22" font-weight="bold" fill="#b91c1c">{i}</text>'
svg=f'''<svg xmlns="http://www.w3.org/2000/svg" width="800" height="800" viewBox="0 0 800 800">
<image href="data:image/png;base64,{base64.b64encode((report/'local-map.png').read_bytes()).decode()}" width="800" height="800"/>
<polyline points="{poly([track[0],native['goals_xy'][0]])}" fill="none" stroke="#e63946" stroke-width="3" stroke-dasharray="8 6"/>
<polyline points="{poly(planned)}" fill="none" stroke="#1670dd" stroke-width="5"/>
<polyline points="{poly(track)}" fill="none" stroke="#16a34a" stroke-width="2.5"/>{labels}</svg>'''
(report/'route-map.svg').write_text(svg,encoding='utf-8')
with (report/'trajectory.csv').open('w',newline='',encoding='utf-8-sig') as f:
    writer=csv.writer(f);writer.writerow(['sim_time_s','x_m','y_m','z_m','cmd_v_mps','cmd_w_radps'])
    for s in native['samples']:writer.writerow([s['sim_time_s'],*s['position'],*s['applied_command']])
m=native['metrics'];r=evidence['resources'];geo=m['map_geometry']
goal_lines='\n'.join(f"目标 {i+1} {g['goal_xy_m']}：{g['outcome']}（状态 {g['result_status']}），{g['sim_time_s']:.3f} 仿真秒；到达状态附近误差 {actions[i]['observed_goal_error_m']:.3f} m。" for i,g in enumerate(ros['tour']['goals']))
text=f'''场景一：连续三目标、转弯与静态障碍绕行（2026-10-18）

本次完成：真实 RetroNeighborhood 场景中，Jackal 在连续仿真内完成三个 Nav2 目标，均返回 SUCCEEDED（4）；全程使用速度命令驱动车轮，未在目标间重置/传送。
{goal_lines}
全诊断路径 {m['path_length_m']:.3f} m，仿真时长 {m['sim_duration_s']:.3f} s；返回起点的最终误差 {m['final_goal_error_m']:.3f} m，停车速度 {m['final_speed_mps']:.5f} m/s。

绕行证据：第一段直线穿过场景树木的真实碰撞投影，Nav2 自行规划绕行。实际第一段相对直线的最大横向偏离为 {cross_track:.3f} m。
轨迹中心到已测障碍栅格边缘的最小距离 {geo['min_center_clearance_m']:.3f} m；扣除车体外接圆半径后的保守净空 {geo['min_circumscribed_footprint_clearance_m']:.3f} m。
轨迹中心没有进入已测障碍或未知区。此为静态地图几何检查，不声称已完成动态障碍或通用碰撞验收。
第二段存在较多转向和额外路径；本次验证到达与绕行能力，尚未优化导航效率。

真实数据：20×20 m、0.1 m 局部地图。WSL 收到 {len(ros['clouds'])} 帧 CPU 射线点云，哈希全部与发送端一致；{len(ros['odom'])} 条里程计全部匹配 PhysX，单时钟无倒退。保存 {len(ros['plans'])} 条规划和 {len(images)} 张原始相机图像。
资源：峰值 Isaac 作业提交内存 {r['peak_job_commit_gib']:.3f} GiB，显存约 {r['peak_gpu_memory_gib']:.2f} GiB；全流程 {r['wall_seconds']:.2f} s，退出 0。内存、显存、超时和失联停车保护保留，临时进程、任务和防火墙规则已清理。

复现边界：本次仍是本机导航诊断，使用 PhysX 状态里程计、CPU 点云、未审局部地图和 z=0 支持平面。未验收 SLAM/定位、RTX 雷达、语义目标搜索或 UAV 协同；正式论文 episode 仍为 0。
下一阶段：将地图范围、目标绑定和任务输入扩展到 handover 的场景一任务。与老师结果精确对齐仍需要老师审核的 GT、地图、episode 和启动配置。

截图均为实际相机原始 RGB。路线图由实际地图、规划和 PhysX 轨迹绘制：红虚线为穿障直线，蓝色为首条规划，绿色为完整实际轨迹，数字为目标顺序（3 为返回起点）。
运行编号：{job}。上级目录保存两端完整日志、命令、资源与源码哈希。
'''
(report/'进展说明.txt').write_text(text,encoding='utf-8-sig')
captions={'nav2-start.png':'出发位置','nav2-moving.png':'转向后开始行驶',
          'nav2-en-route.png':'绕行途中','nav2-after-goal-01.png':'第一目标到达后',
          'nav2-after-goal-02.png':'第二目标到达后','nav2-after-goal-03.png':'第三目标到达后',
          'nav2-stopped.png':'返回起点并停车'}
figures=''.join(f'<figure><img src="{i["file"]}"><figcaption>{html.escape(captions.get(i["file"][3:],i["file"]))} · 仿真 {i["sim_time_s"]:.2f} s</figcaption></figure>' for i in images)
page=f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>场景一：三目标与绕障进展</title>
<style>body{{max-width:1120px;margin:36px auto;padding:0 24px;font:17px/1.75 system-ui,"Microsoft YaHei";background:#f3f6fa;color:#172438}}h1{{line-height:1.3}}section{{background:white;border-radius:14px;padding:24px;margin:20px 0}}img{{width:100%;height:auto}}.grid{{display:grid;grid-template-columns:1fr 1fr;gap:20px}}.metric{{font-size:25px;font-weight:700;color:#125b41}}pre{{white-space:pre-wrap;font:inherit}}figure{{margin:0}}figcaption{{font-size:14px;color:#49566a}}@media(max-width:700px){{.grid{{display:block}}}}</style>
<h1>场景一：连续三个目标与静态障碍绕行通过</h1><p>2026-10-18 · RTX 4060 Laptop · Isaac Sim 4.5 / ROS Humble</p>
<section class="grid"><div class="metric">目标成功 3 / 3</div><div class="metric">实际路径 {m['path_length_m']:.2f} m</div><div>第一段自动绕开树木障碍区</div><div>正式论文实验尚未完成</div></section>
<section><h2>真实地图和轨迹</h2><img src="route-map.svg" style="max-width:800px"><p>红虚线：穿障直线；蓝线：首条 Nav2 规划；绿线：完整实际轨迹；数字：三个目标。</p></section>
<section><h2>原始运行截图</h2><div class="grid">{figures}</div></section>
<section><h2>可向老师汇报</h2><pre>{html.escape(text)}</pre><p><a href="evidence.json">结构化证据</a> · <a href="trajectory.csv">轨迹 CSV</a> · <a href="进展说明.txt">文字说明</a></p></section></html>'''
(report/'查看进展.html').write_text(page,encoding='utf-8')
for p in [report/'evidence.json',root/'docs/development/ugv-ogn/nav2-route-20261018.json']:
    p.write_text(json.dumps(evidence,ensure_ascii=False,indent=2),encoding='utf-8')
with zipfile.ZipFile(run/'teacher-report.zip','w',zipfile.ZIP_DEFLATED) as z:
    for p in sorted(report.iterdir()):z.write(p,p.name)
print(json.dumps({'job':job,'metrics':m,'actions':actions,'cross_track':float(cross_track),
                  'cross_check':evidence['cross_check'],'resources':r,'images':len(images)},ensure_ascii=False,indent=2))
