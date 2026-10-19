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
run=root/'runs/full_map_nav2_20261019'
def read(path): return json.loads(path.read_text(encoding='utf-8-sig'))
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
jobs=[p.name for p in sorted(run.glob('full-nav-a??')) if read(p/'execution.json').get('status')=='completed']
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
assert native['direct_legs'][0]['center_samples_outside_selected_map']>0 and cross_track>.5
assert native['metrics']['map_geometry']['min_circumscribed_footprint_clearance_m']>0
resources=[json.loads(line) for line in (run/job/'resources.jsonl').read_text().splitlines()]
cleanup=read(run/'full-nav-cleanup-20261019.json')
assert cleanup['isolated_wsl_stopped'] and cleanup['temporary_firewall_rules_removed']
evidence={'task':'Local-Scene1-Reproduction / Scene1-FullMap-Nav2Validation',
    'date':'2026-10-19','job':job,'passed':True,'scope':'full diagnostic map ingestion with three-goal local detour; not full-scene target coverage',
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
        'peak_gpu_memory_gib':max(s['gpu_memory_fraction'] for s in resources if s['gpu_memory_fraction'] is not None)*8188/1024,
        'min_physical_available_gib':min(s['available_gib'] for s in resources),
        'min_commit_available_gib':min(s['available_commit_gib'] for s in resources),
        'limits':execution['limits'],'exit_code':execution['exit_code'],'wall_seconds':execution['elapsed_s']},
    'limitations':['PhysX state odometry, not SLAM/localization','CPU raycast cloud, not RTX lidar',
        'Full tiled terrain center-space map with runtime z=0 support plane, not reviewed GT',
        'Static obstacle detour on one route; no dynamic obstacle/general collision acceptance',
        'No semantic search, UAV cooperation, reviewed episodes or paper score'],
    'cleanup':cleanup,'artifacts':'runs/full_map_nav2_20261019/',
    'failed_attempts':[{'job':p.name,'execution':read(p/'execution.json')} for p in sorted(run.glob('full-nav-a??')) if p.name!=job],
    'correction':'Full-map direct leg is footprint blocked. First run reached 2/3 before goal-2 120-s timeout; repeat increases only diagnostic per-goal budget to 180 s, preserving positions, orientations, tolerances, total wall deadlines and protections. This does not prove a controller fix.',
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
from PIL import Image
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
assert ros['costmaps']['map']['matches_full_source_map']
assert ros['costmaps']['map']['width']*ros['costmaps']['map']['height']==32235504
with np.load(wsl/'map-latest.npz') as snapshot:
 source=np.asarray(Image.open(frames/'local-map.pgm'))[::-1]
 assert np.array_equal(snapshot['data'],np.where(source==254,0,100).astype(np.int8))
 assert np.allclose(snapshot['origin'],native['map']['origin'])
with np.load(wsl/'global-latest.npz') as snapshot:
 assert list(snapshot['data'].shape)==native['map']['config']['grid']['shape']
 assert np.allclose(snapshot['origin'],native['map']['origin'])
assert native['metrics']['map_geometry']['center_samples_outside_selected_map']==0
m=native['metrics'];r=evidence['resources'];geo=m['map_geometry']
track=np.array([s['position'][:2] for s in native['samples']]);origin=np.array(native['map']['origin']);res=native['map']['resolution_m']
raw=np.asarray(Image.open(frames/'local-map.pgm'))[::-1]
low=np.maximum(0,np.floor((track.min(axis=0)-2-origin)/res).astype(int));high=np.minimum(raw.shape[::-1],np.ceil((track.max(axis=0)+2-origin)/res).astype(int))
fig,ax=plt.subplots(figsize=(9,7),layout='constrained')
ax.imshow(raw[low[1]:high[1],low[0]:high[0]],origin='lower',cmap='gray',vmin=0,vmax=254,extent=[origin[0]+low[0]*res,origin[0]+high[0]*res,origin[1]+low[1]*res,origin[1]+high[1]*res])
first=np.array(ros['plans'][0]['xy']);ax.plot(first[:,0],first[:,1],color='#2980d0',lw=2,label='First Nav2 plan')
ax.plot(track[:,0],track[:,1],color='#16a34a',lw=1.5,label='Actual PhysX trajectory')
ax.plot([track[0,0],native['goals_xy'][0][0]],[track[0,1],native['goals_xy'][0][1]],'r--',lw=1,label='Direct line: footprint blocked')
for i,g in enumerate(native['goals_xy'],1):
 ax.scatter(*g,color='#d33',s=35);ax.annotate(str(i),g,xytext=(8,8),textcoords='offset points',fontsize=13)
ax.set(xlabel='map X (m)',ylabel='map Y (m)',title='Full 0.05 m map / bounded three-goal navigation')
ax.legend(loc='best');ax.set_aspect('equal');fig.savefig(report/'route-map.png',dpi=160);plt.close(fig)
Image.open(frames/'local-map.pgm').resize((1558,827)).save(report/'full-map.png')
with (report/'trajectory.csv').open('w',newline='',encoding='utf-8-sig') as f:
 writer=csv.writer(f);writer.writerow(['sim_time_s','x_m','y_m','z_m'])
 for s in native['samples']:writer.writerow([s['sim_time_s'],*s['position']])
text=f'''场景一：完整地图接入与三目标实际导航验证（2026-10-19）

完整地图 7792×4137、0.05 m，共 32,235,504 格，ROS 接收端逐格匹配源地图；全尺寸全局代价地图及实时局部代价地图均取得证据。
连续三个 Nav2 目标均成功，目标之间未重置或传送。路径 {m['path_length_m']:.3f} m，最终误差 {m['final_goal_error_m']:.3f} m，停车速度 {m['final_speed_mps']:.5f} m/s。
第一段直线进入车体不可通行区，实际最大横向偏离 {cross_track:.3f} m。全程采样轨迹未进入选定图的不可通行格，扣除车体外接圆后的保守最小障碍净空 {geo['min_circumscribed_footprint_clearance_m']:.3f} m。
收到的 {cloud_matches} 帧点云哈希、{odom_matches} 组里程计全部与仿真端匹配；单时钟无倒退。保存 {len(images)} 张未经修改的相机 RGB。
运行退出 0；Isaac 作业内存峰值 {r['peak_job_commit_gib']:.3f} GiB（不含 WSL），显存采样峰值约 {r['peak_gpu_memory_gib']:.2f} GiB。任务耗时 {r['wall_seconds']:.1f} s。运行资源、临时 ROS 防火墙规则和专用 WSL 已清理。

验收范围：全图载入 + 一条局部三目标路线，不等于全场景 31 个目标实跑。全局代价地图使用静态图，局部代价地图使用实时 CPU PhysX 点云。
仍使用 PhysX 状态里程计和 z=0 支持平面，尚未验收 SLAM/定位、RTX 雷达、语义搜索或 UAV 协同。部分原始截图有悬浮观感，支持平面与视觉路面高度尚未对齐；本次净空检查是水平地图几何证据，不代表轮地视觉/碰撞高度已校准。
31 个目标的几何候选仍全部未审核；人工 GT、正式到达集及论文 episode 尚未验收，不能报告论文 K=M 或正式成绩。
下一步：先定位并改善末端转向收敛波动，校准支持平面与视觉路面的高度差；随后结合目标绑定与可达性人工审核，把通过审核的实例转换为正式任务输入。未审核条目保持 blocked。与老师结果对齐需要审核后的 GT/目标表、episode 和启动配置。
初次 a01 的第二目标 120 s 超时，严格成功 2/3；该次失败完整保留。本次仅把单目标诊断预算改为 180 s，未改速度、容差、路线、目标朝向或整轮截止，也未修改正式 episode 预算。第二段复测实际 93 s，仍小于原来的 120 s，因此延长预算不是本次通过的已证实原因。不能据此声称已修复转向漂移或完成导航效率优化。规划器偶尔低于设定的 5 Hz。
运行编号：{job}；详细命令、源码、地图哈希和跨端证据位于上级目录。
'''
(report/'进展说明.txt').write_text(text,encoding='utf-8-sig')
captions={'nav2-start.png':'出发位置','nav2-moving.png':'开始行驶','nav2-en-route.png':'绕行途中','nav2-after-goal-01.png':'第一目标到达后','nav2-after-goal-02.png':'第二目标到达后','nav2-after-goal-03.png':'第三目标到达后','nav2-stopped.png':'停车'}
figures=''.join(f'<figure><img src="{i["file"]}"><figcaption>{html.escape(captions.get(i["file"][3:],i["file"]))} · 仿真 {i["sim_time_s"]:.2f} s</figcaption></figure>' for i in images)
page=f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>全图 Nav2 验证</title><style>body{{max-width:1120px;margin:36px auto;padding:0 24px;font:17px/1.75 system-ui,"Microsoft YaHei";background:#f3f6fa;color:#172438}}section{{background:white;border-radius:14px;padding:24px;margin:20px 0}}img{{width:100%;height:auto}}.grid{{display:grid;grid-template-columns:1fr 1fr;gap:20px}}pre{{white-space:pre-wrap;font:inherit}}figure{{margin:0}}figcaption{{font-size:14px}}@media(max-width:700px){{.grid{{display:block}}}}</style><h1>完整地图接入，连续三个导航目标通过</h1><p>2026-10-19 · Isaac Sim 4.5 / Humble · RTX 4060 Laptop</p><section><b>3 / 3 目标成功 · 路径 {m['path_length_m']:.2f} m · 完整地图 32,235,504 格逐格匹配</b><p>本次仅验收完整地图上的局部导航；全场景论文任务尚未完成。</p></section><section><h2>实际地图与轨迹</h2><img src="route-map.png"><p>由实际地图、Nav2 规划和 PhysX 轨迹绘制。灰黑区域不可通行；红虚线为车身余量不足的直线。</p><details><summary>查看完整地图</summary><img src="full-map.png"></details></section><section><h2>原始运行截图</h2><div class="grid">{figures}</div></section><section><h2>可向老师汇报</h2><pre>{html.escape(text)}</pre><a href="evidence.json">结构化证据</a> · <a href="trajectory.csv">实际轨迹</a> · <a href="进展说明.txt">文字说明</a></section></html>'''
(report/'查看进展.html').write_text(page,encoding='utf-8')
evidence['validation']['html_render_verified']=False
evidence['first_attempt_analysis']=read(run/'a01-failure-analysis.json')
evidence['diagnostic_goal_budget_s']=180
evidence['second_goal_repeat_duration_s']=ros['tour']['goals'][1]['sim_time_s']
evidence['timeout_extension_causality']='Not demonstrated: repeat goal 2 finished in 93 simulation seconds, below the original 120-s budget. Run-to-run convergence remains variable.'
evidence['validation']['offline_map_contract_tests']={'main_pc':3,'second_pc':3,'passed':True}
evidence['validation']['full_map_binary_snapshot_independently_compared']=True
evidence['limitations'].append('Visual road and z=0 support plane height mismatch remains; screenshots can appear floating. Ground-height alignment not accepted.')
evidence['limitations'].append('Planner sometimes misses configured 5 Hz; final pose convergence is slow. First run timed out at goal 2 after 120 simulation seconds.')
for p in [report/'evidence.json',run/'full-nav-evidence.json',root/'docs/development/ugv-ogn/full-map-nav2-20261019.json']:
 p.write_text(json.dumps(evidence,ensure_ascii=False,indent=2),encoding='utf-8')
with zipfile.ZipFile(run/'teacher-report.zip','w',zipfile.ZIP_DEFLATED) as z:
 for p in sorted(report.iterdir()):z.write(p,p.name)
print(json.dumps({'job':job,'metrics':m,'actions':actions,'cross_track':float(cross_track),'cross_check':evidence['cross_check'],'resources':r,'images':len(images)},ensure_ascii=False,indent=2))
