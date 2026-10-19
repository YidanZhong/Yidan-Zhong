from pathlib import Path
import json,html,shutil,sys,datetime
sys.path.insert(0,'D:/xprogram/.raven-setup-cache/plot-tools')
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from PIL import Image
root=Path('D:/xprogram/RAVEN-AirGround-github');run=root/'runs/nav2_dwb_stability_20261019';out=run/'teacher-report';out.mkdir(exist_ok=True)
summaries=[json.loads(p.read_text(encoding='utf-8')) for p in sorted(run.glob('full-nav-dwb-a??-summary.json'))]
assert summaries
baselines=[]
for job in ('full-nav-a01','full-nav-a02'):
 base=root/'runs/full_map_nav2_20261019';tour=json.loads((base/(job+'-wsl')/'tour.json').read_text());cmd=json.loads((base/(job+'-wsl')/'command.json').read_text());native=json.loads((base/(job+'-frames')/'jackal-nav2.json').read_text())
 baselines.append({'job':job,'planner':'rpp','configured_goal_budget_s':float(cmd[cmd.index('--tour-goal-timeout-s')+1]),'goals':tour['goals'],'metrics':native['metrics']})
fig,ax=plt.subplots(figsize=(9,7),layout='constrained');sections=[]
for number,r in enumerate(summaries):
 job=r['job'];frames=run/job/'logs'/(job+'-frames');native=json.loads((frames/'jackal-nav2.json').read_text())
 track=np.asarray([s['position'][:2] for s in native['samples']])
 if number==0:
  origin=np.asarray(native['map']['origin']);res=native['map']['resolution_m'];raw=np.asarray(Image.open(frames/'local-map.pgm'))[::-1]
  lo=np.maximum(0,np.floor((track.min(axis=0)-2-origin)/res).astype(int));hi=np.minimum(raw.shape[::-1],np.ceil((track.max(axis=0)+2-origin)/res).astype(int))
  ax.imshow(raw[lo[1]:hi[1],lo[0]:hi[0]],origin='lower',cmap='gray',vmin=0,vmax=254,extent=[origin[0]+lo[0]*res,origin[0]+hi[0]*res,origin[1]+lo[1]*res,origin[1]+hi[1]*res])
 ax.plot(track[:,0],track[:,1],label=job,lw=1.7)
 goals=np.asarray(native['goals_xy']);ax.scatter(goals[:,0],goals[:,1],marker='x',s=50,color='red')
 images=[]
 for image in r['images']:
  name=job+'-'+image['file'];target=out/name
  if not target.exists():shutil.copy2(run/image['path'],target)
  images.append(f'<figure><img loading="lazy" src="{name}"><figcaption>{html.escape(image["file"])} · 仿真 {image["sim_time_s"]:.3f} s · 原始RGB</figcaption></figure>')
 rows=''.join(f'<tr><td>{i+1}</td><td>{a["action_status"]}</td><td>{a["goal_duration_sim_s"]:.3f}</td><td>{a["observed_xy_error_m"]:.4f}</td><td>{a["observed_yaw_error_rad"]:.4f}</td><td>{a["observed_within_original_tolerances"]}</td></tr>' for i,a in enumerate(r['actions']))
 sections.append(f'<section><h2>{job}</h2><p>路径 {r["metrics"]["path_length_m"]:.3f} m；停车速度 {r["metrics"]["final_speed_mps"]:.5f} m/s；{r["cloud_hash_matches"]}帧点云及{r["odom_matches_physx"]}组里程计交叉一致。</p><table><tr><th>目标</th><th>action状态</th><th>耗时/s</th><th>位置误差/m</th><th>朝向误差/rad</th><th>原容差内</th></tr>{rows}</table><div class="grid">{"".join(images)}</div></section>')
ax.set(xlabel='World X (m)',ylabel='World Y (m)',title='Actual PhysX trajectories | same goals, yaw, tolerance and 120 s/goal');ax.legend();ax.grid(alpha=.3);ax.set_aspect('equal');fig.savefig(out/'trajectories.png',dpi=150);plt.close(fig)
summary={'updated_at':datetime.datetime.now().astimezone().isoformat(),'completed_repetitions':len(summaries),'planned_bounded_repetitions':3,'goals_per_run':3,'runs':summaries,'formal_scene_accepted':False,'limitations':['Same static route only; not general stability or K=M.','PhysX odometry and CPU raycast cloud, not SLAM/RTX lidar.','Unreviewed map and existing z=0/visual-road height difference.','Existing direct joint velocity actuation retained; authored joint force limit is not proof of commanded-state torque bounding.'],'visual_inspection':{'full-nav-dwb-a01':['nav2-start.png','nav2-after-goal-02.png','nav2-stopped.png']}}
summary['strict_pose_checks_passed']=sum(a['observed_within_original_tolerances'] for r in summaries for a in r['actions'])
summary['strict_repetitions_passed']=sum(all(a['observed_within_original_tolerances'] for a in r['actions']) for r in summaries)
summary['strict_stability_accepted']=False
summary['visual_inspection'].update({'full-nav-dwb-a02':['nav2-stopped.png'],'full-nav-dwb-a03':['nav2-after-goal-02.png']})
summary['arrival_finding']='All nine actions succeeded, but a03 goals 1/2 had latest odometry errors 0.251970/0.264959 m when terminal status was received. Strict pose-at-success repeatability is not accepted. Stateful goal checker and rotation critic latch their near-goal state; controller decision time vs status receipt time must be distinguished.'
summary['source_references']=['https://raw.githubusercontent.com/ros-navigation/navigation2/humble/nav2_controller/plugins/simple_goal_checker.cpp','https://raw.githubusercontent.com/ros-navigation/navigation2/humble/nav2_dwb_controller/dwb_critics/src/rotate_to_goal.cpp']
summary['prior_rpp_runs']=baselines
summary['comparison_caveat']='RPP a01 used 120s and goal2 timed out; a02 configured 180s but goal2 actually completed in 93s. Budget increase is not established as cause of success. DWB repetitions all use original 120s; conclusions are limited to this route.'
(out/'evidence.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
page=f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>DWB 原预算有界导航复测</title><style>body{{max-width:1300px;margin:30px auto;padding:20px;background:#f3f6fa;color:#182538;font:16px/1.7 system-ui,"Microsoft YaHei"}}section,header{{background:white;padding:24px;border-radius:12px;margin:20px 0}}.grid{{display:grid;grid-template-columns:1fr 1fr;gap:16px}}img{{max-width:100%}}figure{{margin:0}}td,th{{padding:8px;border:1px solid #ccc}}table{{border-collapse:collapse}}@media(max-width:700px){{.grid{{display:block}}}}</style><header><h1>DWB 原预算导航复测</h1><p>已归档 {len(summaries)}/3 次计划内复测。本页仅是保存时的结果，不代表当前有任务运行。</p><p>目标位置和朝向不变，位置/朝向容差0.25 m / 0.30 rad，单目标预算120 s。action状态4表示SUCCEEDED；几何接近不代替action成功。</p><p>仅验证同一静态路线；未审核地图、PhysX里程计、CPU点云、视觉地面高差及既有轮控方式均保留，不代表正式场景复现或K=M。</p><a href="evidence.json">完整运行与原图哈希</a><p><img src="trajectories.png"></p></header>{''.join(sections)}</html>'''
comparison=''.join(f'<tr><td>{b["job"]} (RPP)</td><td>{b["configured_goal_budget_s"]:.0f}</td><td>{sum(g["result_status"]==4 for g in b["goals"])}/3</td><td>{b["goals"][1]["sim_time_s"]:.3f}</td><td>{b["metrics"]["path_length_m"]:.3f}</td></tr>' for b in baselines)
comparison+=''.join(f'<tr><td>{r["job"]} (DWB)</td><td>120</td><td>3/3</td><td>{r["actions"][1]["goal_duration_sim_s"]:.3f}</td><td>{r["metrics"]["path_length_m"]:.3f}</td></tr>' for r in summaries)
page=page.replace('</header>','<h2>同一路线的历史对照</h2><table><tr><th>运行</th><th>配置预算/s</th><th>action成功</th><th>第二目标耗时/s</th><th>路径/m</th></tr>'+comparison+'</table><p>RPP第二轮虽配置180秒，但第二目标实测93秒；不能把其成功归因于延长预算。DWB均使用原120秒预算。这里只报告观测差异，不推断已修复全部轮胎滑移或所有路线稳定性。</p></header>')
page=page.replace('</header>',f'<p><strong>严格稳定性尚未通过：</strong>{summary["strict_pose_checks_passed"]}/9 个 action 回报时的最新位姿同时满足原容差；第三轮前两目标位置误差0.252/0.265 m，超过0.25 m。全部9个action成功不能替代严格位姿检查。当前记录时刻是状态消息到达时，不是控制器内部判断时刻。</p></header>')
if (out/'arrival-errors.png').exists():
 page=page.replace('</header>','<p><img src="arrival-errors.png"></p><p><a href="../arrival-analysis.json">回报前后位姿分析数据</a>。第三轮前两目标回报前1秒采样未同时满足两个原容差。<a href="https://github.com/ros-navigation/navigation2/blob/humble/nav2_controller/plugins/simple_goal_checker.cpp">SimpleGoalChecker源码</a>与<a href="https://github.com/ros-navigation/navigation2/blob/humble/nav2_dwb_controller/dwb_critics/src/rotate_to_goal.cpp">RotateToGoal源码</a>支持状态锁存这一解释，尚需控制器内部时刻验证。</p></header>')
(out/'查看进展.html').write_text(page,encoding='utf-8')
(root/'docs/development/ugv-ogn/nav2-dwb-stability-20261019.json').write_text(json.dumps({k:v for k,v in summary.items() if k!='runs'}|{'runs':[{'job':r['job'],'actions':r['actions'],'metrics':r['metrics'],'archive_sha256':r['source_archive_sha256']} for r in summaries]},ensure_ascii=False,indent=2),encoding='utf-8')
for p in [root/'benchmark/README.md',root/'docs/benchmark_zh.md']:
 s=p.read_text(encoding='utf-8');note='DWB 有界对照（2026-10-19）：三轮共9个action均在原120s预算内成功，点云/PhysX里程计/全图交叉一致；但第三轮前两目标在状态回报时位置误差0.252/0.265m，超出原0.25m，严格位姿仅7/9、整轮2/3，稳定性不通过。默认控制器未改，不代表K=M。证据 `nav2-dwb-stability-20261019.json`。\n\n'
 lines=s.splitlines(keepends=True);s=''.join(line for line in lines if not line.startswith('DWB 有界对照（2026-10-19）：'))
 p.write_text(note+s.lstrip('\n'),encoding='utf-8')
print('Saved',len(summaries),'verified repetitions and original screenshots.')
