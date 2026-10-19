from pathlib import Path
import base64, hashlib, html, json, math, shutil, zipfile
import numpy as np
from PIL import Image

root=Path(r'D:\xprogram\RAVEN-AirGround-github');run=root/'runs/target_integration_20261018'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
job=next(p.name for p in sorted(run.glob('jackal-target-a??'),reverse=True) if read(p/'execution.json')['exit_code']==0)
frames=run/f'{job}-frames';wsl=run/f'{job}-wsl'
nav=read(frames/'jackal-nav2.json');confirm=read(frames/'target-confirmation.json')
ros=read(wsl/'ros-evidence.json');execution=read(run/job/'execution.json');render=read(frames/'report.json')
assert nav['passed'] and confirm['passed'] and ros['passed'] and render['status']=='passed'
assert len(ros['terminal_actions'])==1 and ros['terminal_actions'][0]['status']==4
cloud={round(i['sim_time_s']*1e9):i for i in nav['clouds']}
assert all(c['sha256']==cloud[round(c['sim_time_s']*1e9)]['sha256'] for c in ros['clouds'])
samples={round(i['sim_time_s']*1e9):i for i in nav['samples']}
assert all(math.dist([o['x'],o['y'],o['z']],samples[round(o['sim_time_s']*1e9)]['position'])<1e-6 for o in ros['odom'])
assert confirm['actual_consecutive_visible_frames']==5
assert all(f['metric']['ray_count']==5 for f in confirm['frames'])
assert all(1.5<=f['obb_surface_distance_m']<=8 for f in confirm['frames'])
assert not confirm['target']['verified'] and confirm['target']['ground_reachable']=='unknown'
assert all(b['sim_time_s']>a['sim_time_s'] and b['sim_time_s']-a['sim_time_s']<=.15 for a,b in zip(confirm['frames'],confirm['frames'][1:]))
source=read(run/'target-input.json');catalog=read(run/'task_catalog.blocked.json');binding=read(run/'binding-report.json')
assert catalog['blocked_count']==10
cleanup=read(run/'target-integration-cleanup-20261018.json');assert cleanup['isolated_wsl_stopped']
resources=[json.loads(l) for l in (run/job/'resources.jsonl').read_text().splitlines()]
report=run/'teacher-report';report.mkdir(exist_ok=True)
for name in ['paper31-review-queue.json','paper31-ledger.template.json','task_catalog.blocked.json']:
 shutil.copy2(run/name,report/name)
images=[]
for item in nav['images']+confirm['images']:
 path=frames/item['file'];shutil.copy2(path,report/path.name)
 with Image.open(path) as pic: assert pic.size==(960,600)
 images.append({**item,'sha256':sha(path),'original_rgb':True})

# Project the original annotation OBB into the diagnostic camera. This is a
# separate labelled SVG overlay; the original simulator RGB stays unchanged.
f=confirm['frames'][0];eye=np.array(f['camera_position_xyz_m']);yaw=f['camera_yaw_rad']
forward=np.array([math.cos(yaw),math.sin(yaw),0.]);right=np.array([math.sin(yaw),-math.cos(yaw),0.]);up=np.array([0.,0.,1.])
obb=confirm['target']['obb'];center=np.array(obb['center_xyz_m']);size=np.array(obb['size_xyz_m'])
assert obb['orientation_rpy_rad']==[0.,0.,0.]
corners=[center+size*np.array([x,y,z])/2 for x in (-1,1) for y in (-1,1) for z in (-1,1)]
def project(point):
 delta=point-eye;depth=delta@forward;assert depth>0
 return 480+480*(delta@right)/depth,300-480*(delta@up)/depth
edges=[]
for i in range(8):
 for bit in (1,2,4):
  j=i^bit
  if j>i:
   a,b=project(corners[i]),project(corners[j]);edges.append(f'<line x1="{a[0]:.2f}" y1="{a[1]:.2f}" x2="{b[0]:.2f}" y2="{b[1]:.2f}"/>')
image64=base64.b64encode((report/'target-confirmation-01.png').read_bytes()).decode()
(report/'target-obb-review.svg').write_text(f'<svg xmlns="http://www.w3.org/2000/svg" width="960" height="600"><image href="data:image/png;base64,{image64}" width="960" height="600"/><g stroke="#ff384c" stroke-width="3" fill="none">'+''.join(edges)+'</g></svg>',encoding='utf-8')

# Map with actual trajectory; target lies beyond this local diagnostic window.
mapinfo=nav['map'];origin=mapinfo['origin'];res=mapinfo['resolution_m'];scale=4
shutil.copy2(frames/'local-map.png',report/'local-map.png')
def pixel(p):return ((p[0]-origin[0])/res*scale,800-(p[1]-origin[1])/res*scale)
track=' '.join(f'{pixel(s["position"])[0]:.2f},{pixel(s["position"])[1]:.2f}' for s in nav['samples'])
(report/'route-map.svg').write_text('<svg xmlns="http://www.w3.org/2000/svg" width="800" height="800"><image href="data:image/png;base64,'+base64.b64encode((report/'local-map.png').read_bytes()).decode()+'" width="800" height="800"/><polyline fill="none" stroke="#14915b" stroke-width="4" points="'+track+'"/></svg>',encoding='utf-8')

evidence={'task':'Local-Scene1-Reproduction / Scene1-Target-Integration','date':'2026-10-18',
 'job':job,'passed':True,'scope':'one unreviewed bus-stop target, navigation and actual RGB/PhysX visibility diagnostic',
 'formal_episode_count':0,'scene1_reproduced':False,'scene_sha256':render['scene_sha256'],
 'target_input':source,'automatic_binding':{k:v for k,v in binding.items() if k!='bindings'},
 'task_catalog':{k:catalog[k] for k in ('task_count','runnable_count','blocked_count')},
 'navigation_metrics':nav['metrics'],'nav2_tour':ros['tour'],'confirmation':confirm,
 'cross_check':{'cloud_sha_matches':len(ros['clouds']),'odom_matches_physx':len(ros['odom']),
                'clock_backwards':ros['clock_backwards'],'max_clock_publishers':ros['max_clock_publishers']},
 'resources':{'peak_job_commit_gib':execution['peak_job_commit_gib'],
              'peak_gpu_gib':max(r['gpu_memory_fraction'] for r in resources)*8188/1024,
              'wall_seconds':execution['elapsed_s'],'exit_code':execution['exit_code'],'limits':execution['limits']},
 'cleanup':cleanup,'images':images,'artifacts':'runs/target_integration_20261018/',
 'limitations':['Single known target supplied by diagnostic orchestrator; no semantic detector/search.',
  'Observer yaw is aimed at known target, not a validated onboard camera mount.',
  'PhysX odometry, CPU cloud, unreviewed local map and z=0 support plane.',
  'No reviewed full map, arrival set, human approval or formal paper episode.',
  'Minimum conservative circular-footprint clearance is 0.077 m on a 0.1 m diagnostic map; formal 0.05 m map and clearance gate not accepted.',
  'Five visibility frames use continuing Isaac world time after navigation ROS monitor exits; no visibility ROS topic acceptance.'],
 'source_sha256':{p.name:sha(p) for p in sorted((run/'source').glob('*')) if p.is_file()},
 'validation':{'compile':'python -m py_compile scripts/probe_windows_scene_render.py scripts/probe_target_confirmation.py',
  'native_command':f'{job}/execution.json','wsl_command':f'{job}-wsl/command.json',
  'actual_frame_ids':[i['rendering_frame'] for i in confirm['images'][:5]],
  'image_review':'11 original RGB images visually inspected; human target approval still pending',
  'browser_preview':'blocked by file protocol policy; HTML references checked offline'}}
m=nav['metrics'];v=confirm['frames'][0]['metric'];surface=f['obb_surface_distance_m']
text=f'''场景一：公交站目标接入诊断（2026-10-18）

已完成：小车从 (-30,-24) 实际驶近标注中的公交站 RetroNeighborhood.bus_stop.0002，Nav2 返回 SUCCEEDED（4），到达 (-30,-18) 附近后停车。实际路径 {m['path_length_m']:.3f} m，目标点误差 {m['final_goal_error_m']:.3f} m，停车速度 {m['final_speed_mps']:.5f} m/s；没有目标间传送。
路线转向较多，路径效率尚未优化。在 0.1 m 诊断地图上的最小外接圆净空为 {m['map_geometry']['min_circumscribed_footprint_clearance_m']:.3f} m，仍需正式 0.05 m 地图复核，不能据此认定通过 handover 的 0.1075 m 净空验收。图中车轮与视觉道路有高度差，来自当前 z=0 隐形支持平面；此配置尚不等同于真实路面接触验收。

目标对应论文任务 retro-type-i-bus-stop。该类共有三个标注实例，本次仅验证其中一个；没有完成整个任务，也未生成正式论文 episode。
模型绑定候选：{confirm['target']['usd_prim_path']}。运行时重新读取世界包围盒，与此前 USD 导出结果核对通过。

停车后的目标观察相机位于实际到达 XY、支持平面上方 1.2 m，水平视场 90°，朝向由已知目标位置指定。实际连续五帧、每帧五条 PhysX 射线；可见比例为 {[i['metric']['visible_fraction'] for i in confirm['frames']]}，时间戳和渲染帧编号均不同。首帧目标中心距离 {v['distance_to_target_m']:.3f} m，OBB 表面平面距离 {surface:.3f} m，均在 1.5–8 m 内。保存每条射线原始命中路径，不使用占位 visible_fraction=1 来证明可见。
这证明该位姿可以观察该候选模型；未运行自动语义识别，也未验证真实机载相机安装与转向控制。可见性采样沿用同一 Isaac 仿真时间，但发生在导航 ROS 记录退出后，不计入 ROS 可见性话题验收。

两端交叉核对：{len(ros['clouds'])} 帧接收点云哈希全部匹配发送端，{len(ros['odom'])} 组里程计全部匹配 PhysX；单时钟无倒退。保留 {len(images)} 张原始相机截图；红线 OBB 图是单独生成的审核辅助图，原图未改动。
峰值提交内存 {execution['peak_job_commit_gib']:.3f} GiB，显存约 {evidence['resources']['peak_gpu_gib']:.2f} GiB，退出 0。运行限额保持，测试进程及临时网络规则已清理。

GT 状态：165 个实例自动绑定，但 154 个存在歧义；自动绑定不等于审核。选中公交站仍 verified=false / ground_reachable=unknown，未伪造人审、到达集或任务 M。正式任务目录 10/10 blocked，formal episode=0。
已整理论文涉及的 31 个实例审核队列与台账草稿；草稿格式不能直接作为审核通过台账应用。
本次对应 handover S3 绑定辅助、S4 图像审核材料和 S8 单实例可见性预检，不表示全场景 S4/S8/S10 完成。

继续推进需要的输入：老师已审核的 targets.reviewed.with_regions.json、arrival_regions.npz、region_index.json；0.05 m 完整地图包（NPZ、metadata.yaml、Nav2 YAML/PGM）；任务目录和 30 集 manifest；对应场景 SHA、启动参数和版本。若拿不到，则需本地逐实例审核并重新生成全图、到达集和 episode。当前生成的是诊断用局部地图，不能代替这些文件。
老师参考目录：
runs/p1_05_targets/p1_05_red_car_binding_20260930/reach_recalibrated/
runs/p1_03_traversability/p1_03_single_gpu_0p05_full_20260930_r2_native/package/
runs/p1_09_episode/paper_protocol_20261005/
'''
(report/'进展说明.txt').write_text(text,encoding='utf-8-sig')
figures=''.join(f'<figure><img src="{i["file"]}"><figcaption>{html.escape(i["file"])} · 仿真 {i["sim_time_s"]:.3f} s</figcaption></figure>' for i in images)
page=f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>场景一：公交站目标接入</title><style>body{{max-width:1120px;margin:36px auto;padding:0 24px;background:#f3f6fa;color:#172438;font:17px/1.75 system-ui,"Microsoft YaHei"}}section{{background:white;border-radius:14px;padding:24px;margin:20px 0}}img{{width:100%;height:auto}}pre{{white-space:pre-wrap;font:inherit}}.grid{{display:grid;grid-template-columns:1fr 1fr;gap:20px}}figure{{margin:0}}figcaption{{font-size:14px;color:#49566a}}@media(max-width:700px){{.grid{{display:block}}}}</style>
<h1>从坐标导航推进到公交站目标验证</h1><p>真实驶近 · 停车观察 · 五帧 PhysX 遮挡证据 · 目标审核仍待完成</p>
<section><h2>目标与标注核对</h2><img src="target-obb-review.svg"><p>红线为原始标注 OBB 的投影，供审核位置与类别；尚未签署 verify。原始图像另行保存。</p><img src="target-context.png"><p>环境视角：小车与公交站的空间关系。</p></section>
<section><h2>实际路线</h2><img style="max-width:700px" src="route-map.svg"><p>绿色为实际 PhysX 轨迹。公交站本体在本次局部地图上沿之外；该图只支持驶近路线，不能作为全场景 GT。</p></section>
<section><h2>原始运行截图</h2><div class="grid">{figures}</div></section>
<section><h2>向老师汇报</h2><pre>{html.escape(text)}</pre><a href="evidence.json">结构化证据</a> · <a href="进展说明.txt">文字说明</a></section></html>'''
(report/'查看进展.html').write_text(page,encoding='utf-8')
for path in [report/'evidence.json',root/'docs/development/ugv-ogn/target-integration-20261018.json']:
 path.write_text(json.dumps(evidence,ensure_ascii=False,indent=2),encoding='utf-8')
with zipfile.ZipFile(run/'teacher-report.zip','w',zipfile.ZIP_DEFLATED) as z:
 for path in sorted(report.iterdir()):z.write(path,path.name)
print(json.dumps({'job':job,'navigation':m,'visibility':v,'surface_distance':surface,'images':len(images),'resources':evidence['resources'],'cross_check':evidence['cross_check']},indent=2))
