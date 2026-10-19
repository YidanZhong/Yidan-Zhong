from pathlib import Path
import json,hashlib,html,math,shutil,zipfile,csv
import numpy as np
from PIL import Image

root=Path(r'D:\xprogram\RAVEN-AirGround-github');run=root/'runs/paper31_review_20261018'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
job='paper31-review-a01';frames=run/f'{job}-frames';render=read(frames/'report.json')
execution=read(run/job/'execution.json');inputs=read(run/'review-input.json');mapping=read(run/'mapping-readiness.json')
cleanup=read(run/'paper31-review-cleanup-20261018.json')
assert render['status']=='passed' and execution['exit_code']==0 and cleanup['task_removed']
assert len(render['frames'])==62 and len(render['review_targets'])==31
assert render['scene_sha256']==inputs['scene_sha256'] and render['review_manifest_sha256']==sha(run/'review-input.json')
assert render['review_status']=='pending_human_review'
report=run/'teacher-report';report.mkdir(exist_ok=True)
actual={i['instance_id']:i for i in render['review_targets']}
red_proposal=read(run/'red-car-root-proposal.json')
by_id={i['target']['instance_id']:[] for i in inputs['rows']}
images=[]
for frame in render['frames']:
 assert frame['consecutive_valid_frames']>=60
 path=frames/frame['file'];shutil.copy2(path,report/path.name)
 with Image.open(path) as image:assert image.size==(960,600)
 row={**frame,'sha256':sha(path),'original_rgb':True};by_id[frame['instance_id']].append(row);images.append(row)
assert all(len(v)==2 and {f['view_index'] for f in v}=={0,1} for v in by_id.values())

def corners(center,size,rpy):
 roll,pitch,yaw=rpy;cr,sr,cp,sp,cy,sy=math.cos(roll),math.sin(roll),math.cos(pitch),math.sin(pitch),math.cos(yaw),math.sin(yaw)
 rot=np.array([[cy*cp,cy*sp*sr-sy*cr,cy*sp*cr+sy*sr],[sy*cp,sy*sp*sr+cy*cr,sy*sp*cr-cy*sr],[-sp,cp*sr,cp*cr]])
 signs=np.array([[x,y,z] for x in (-1,1) for y in (-1,1) for z in (-1,1)])
 return (signs*np.array(size)/2)@rot.T+np.array(center)

def wire(frame,points,color):
 eye=np.array(frame['eye']);forward=np.array(frame['target'])-eye;forward/=np.linalg.norm(forward)
 right=np.cross(forward,[0,0,1]);right/=np.linalg.norm(right);up=np.cross(right,forward)
 k=frame['camera_intrinsics'];fx=960*k['focal_length']/k['horizontal_aperture'];fy=600*k['focal_length']/k['vertical_aperture']
 def project(point):
  delta=point-eye;depth=delta@forward
  if depth<=.05:return None
  return [480+fx*(delta@right)/depth,300-fy*(delta@up)/depth]
 center=project(np.array(frame['target']));assert np.allclose(center,[480,300],atol=1e-5)
 p=[project(v) for v in points];lines=[]
 for i in range(8):
  for bit in (1,2,4):
   j=i^bit
   if j>i and p[i] is not None and p[j] is not None:
    lines.append(f'<line x1="{p[i][0]:.2f}" y1="{p[i][1]:.2f}" x2="{p[j][0]:.2f}" y2="{p[j][1]:.2f}"/>')
 return f'<g stroke="{color}" stroke-width="3" fill="none">'+''.join(lines)+'</g>'

sections=[];summary=[];class_counts={}
for index,row in enumerate(inputs['rows'],1):
 t=row['target'];identifier=t['instance_id'];c=t['semantic_class'];class_counts[c]=class_counts.get(c,0)+1
 a=actual[identifier];candidate=row['candidate'];obb=t['obb']
 assert math.dist(candidate['center_xyz_m'],a['actual_candidate_center_xyz_m'])<.02
 assert math.dist(candidate['size_xyz_m'],a['actual_candidate_size_xyz_m'])<.02
 distance=math.dist(obb['center_xyz_m'],a['actual_candidate_center_xyz_m'])
 ratio=math.prod(a['actual_candidate_size_xyz_m'])/math.prod(obb['size_xyz_m'])
 notes=[]
 if row['binding']['issues']:notes.append('自动绑定存在歧义')
 if distance>1:notes.append('中心偏移超过 1 m，需核对')
 if not .5<=ratio<=2:notes.append('候选/标注体积差异较大，需核对模型层级')
 if not notes:notes.append('仍需人工核对类别、范围和实例层级')
 if identifier==red_proposal['instance_id']:notes.append('建议由 Object_9 改绑整车根节点；方案未应用')
 summary.append({'instance_id':identifier,'semantic_class':c,'center_delta_m':distance,'volume_ratio':ratio,'binding_issues':row['binding']['issues'],'review_notes':notes,'review_status':'pending'})
 figures=[]
 for frame in by_id[identifier]:
  overlay=wire(frame,corners(obb['center_xyz_m'],obb['size_xyz_m'],obb['orientation_rpy_rad']),'#ff354b')
  overlay+=wire(frame,corners(a['actual_candidate_center_xyz_m'],a['actual_candidate_size_xyz_m'],[0,0,0]),'#00c9ef')
  figures.append(f'<figure><div class="view"><img loading="lazy" src="{frame["file"]}"><svg class="overlay" viewBox="0 0 960 600">{overlay}</svg></div><figcaption>视角 {frame["view_index"]+1} · 原始渲染帧 {frame["rendering_frame"]} · <a href="{frame["file"]}">打开原图</a></figcaption></figure>')
 # World XY mini-map: contextual annotation geometry, explicitly not a traversability map.
 span=max(20.,max(obb['size_xyz_m'][:2])*1.5);cx,cy=obb['center_xyz_m'][:2]
 points=[]
 for other in inputs['rows']:
  x,y=other['target']['obb']['center_xyz_m'][:2]
  if abs(x-cx)<=span and abs(y-cy)<=span:
   points.append(f'<circle cx="{150+(x-cx)*140/span:.2f}" cy="{150-(y-cy)*140/span:.2f}" r="4" fill="#9ca3af"/>')
 xy=f'<svg viewBox="0 0 300 300" class="xy"><rect x="10" y="10" width="280" height="280" fill="#f1f5f9"/>'+''.join(points)+f'<circle cx="150" cy="150" r="6" fill="#ef3340"/><text x="15" y="285" font-size="11">XY +/-{span:.1f}m; target center ({cx:.1f},{cy:.1f})</text></svg>'
 alternatives=''.join('<li>'+html.escape(p['prim_path'])+'</li>' for p in row['near_center_alternatives']) or '<li>无同中心近邻候选；仍需看图审核。</li>'
 if identifier==red_proposal['instance_id']:
  alternatives+='<li>优先核对整车候选（已有仓库修复记录支持，未应用）：'+html.escape(red_proposal['source_candidate']['prim_path'])+'</li>'
 sections.append(f'''<section id="target-{index}" data-search="{html.escape(identifier+' '+c)}"><h2>{index:02d} · {html.escape(identifier)}</h2><p class="pending">待人工审核 · {'；'.join(notes)}</p><div class="grid">{''.join(figures)}</div><div class="details"><div><p>类别：{html.escape(c)}<br>标注中心：{obb['center_xyz_m']}<br>标注尺寸：{obb['size_xyz_m']}<br>实际候选中心：{a['actual_candidate_center_xyz_m']}<br>实际候选尺寸：{a['actual_candidate_size_xyz_m']}<br>中心差：{distance:.3f} m；体积比：{ratio:.3f}</p><p class="path">候选 prim：{html.escape(t['usd_prim_path'])}</p></div>{xy}</div><details><summary>展开同中心近邻层级（辅助信息，不代表可互换）</summary><ul class="path">{alternatives}</ul></details></section>''')

queue=root/'runs/target_integration_20261018/paper31-ledger.template.json'
shutil.copy2(run/'red-car-root-proposal.json',report/'red-car-root-proposal.json')
shutil.copy2(queue,report/queue.name);shutil.copy2(run/'mapping-readiness.json',report/'mapping-readiness.json')
with (report/'审核填写表.csv').open('w',newline='',encoding='utf-8-sig') as f:
 writer=csv.writer(f);writer.writerow(['instance_id','semantic_class','candidate_prim','decision_verify_or_exclude','corrected_prim','excluded_reason','notes'])
 for row in inputs['rows']:writer.writerow([row['target']['instance_id'],row['target']['semantic_class'],row['target']['usd_prim_path'],'','','',''])
resources=[json.loads(l) for l in (run/job/'resources.jsonl').read_text().splitlines()]
ambiguity=sum(bool(r['binding']['issues']) for r in inputs['rows'])
spot_check={'image_count':16,'class_count':8,'files':[f'view-{i}.png' for i in [0,1,8,9,14,15,50,51,52,53,56,57,58,59,60,61]],'method':'Direct visual inspection of original RGB files; artifact quality only, not human GT approval.','observations':['view-9: bus shelter partly occluded by foliage.','view-51: rear tunnel view exposes the back of the scene asset; not a traversability check.','view-56: red container partly occluded by perimeter wall; view-57 shows the opposite side.','view-58 and view-59: red car visible with partial fence occlusion; candidate Object_9 remains a part-level binding.','view-60: yellow car partly occluded by foliage; view-61 is viewed through chain-link fence.']}
evidence={'task':'Local-Scene1-Reproduction / Scene1-Paper31-ReviewPacket','job':job,'passed':True,
 'scope':'static review material generated; not human target approval','scene_sha256':render['scene_sha256'],
 'runtime':{'isaac_sim':'4.5','platform':'native Windows','container_tag':None,'gpu':'NVIDIA GeForce RTX 4060 Laptop GPU','driver':'577.02','graphics_api':'Vulkan','command':execution['command'],'ros_topics_tf':'not applicable: static review, no ROS launched','log':f'{job}/stdout.log'},
 'target_count':31,'image_count':62,'ambiguous_target_count':ambiguity,'class_counts':class_counts,
 'reviewed_target_count':0,'formal_map_created':False,'formal_episode_count':0,'human_review_status':'pending',
 'target_geometry':summary,'images':images,'mapping_readiness':mapping,
 'red_car_binding_proposal':red_proposal,
 'resources':{'peak_job_commit_gib':execution['peak_job_commit_gib'],'peak_gpu_gib':max(r['gpu_memory_fraction'] for r in resources)*8188/1024,'wall_seconds':execution['elapsed_s'],'exit_code':execution['exit_code'],'limits':execution['limits']},
 'cleanup':cleanup,'source_sha256':{p.name:sha(p) for p in sorted((run/'source').glob('*')) if p.is_file()},
 'validation':{'frame_buffer_checks':62,'candidate_bounds_compared':31,'visual_spot_check':spot_check,'python_compile':'scripts/probe_windows_scene_render.py','native_command':f'{job}/execution.json','browser_preview':'not attempted: local file URL policy blocks browser automation'},
 'limitations':['Static camera locations may be occluded; raw image quality does not prove semantic correctness.','Red wire is annotation OBB; cyan wire is candidate world AABB, not a semantic segmentation mask.','All human review decisions are blank. No formal map, arrival regions or episodes generated.'],
 'artifacts':'runs/paper31_review_20261018/'}
notes=f'''场景一：31 个论文目标审核材料（2026-10-18）

已生成：31 个实例、8 类目标、62 张 Isaac Sim 4.5 原始 RGB；每目标两个相反方位视角。实际运行时逐一核对候选 prim 包围盒，全部与先前导出结果一致。每张图保存前要求连续 60 个有效相机缓冲帧。未修改场景或目标 verified / ground_reachable 字段。

红框：原始标注 OBB；青框：当前候选 prim 的世界 AABB；灰点 XY 小图是标注位置关系，不是可通行地图。按每项的两路 RGB、两种框与候选层级一起核对，不能仅凭自动匹配给出 verify。24 个论文目标存在自动绑定歧义，所有 31 个目标均待人工审核。表中的体积比和中心距离只是排查线索。
重点问题：红车自动绑定到了 Object_9 零件，其包围盒体积仅为标注框约 20.4%；已有仓库修复记录支持改用 Nissan_Fairlady_Z_S30240Z_1978 整车根节点，候选修正方案另存 red-car-root-proposal.json，尚未应用。黄车当前模型世界 AABB 体积约为原标注框的 3.29 倍，需要结合 RGB 核对边界，不能仅按距离近就判定准确。

图像检查：全部 62 张通过有效缓冲帧和文件完整性检查；直接视觉抽查了覆盖 8 类的 16 张原图，具体文件见 evidence.json。公交站 view-9 和黄车 view-60 有树叶遮挡；红箱 view-56 被围墙部分遮挡，另一个视角可补充观察；红车视角有栅栏遮挡；黄车 view-61 隔着铁丝网。隧道背面视角显示场景资产后部。这些是待审材料的限制，不构成目标识别、可见性判定或人工 GT 批准。

审核填写表.csv 的 decision 留空：确认类别/对象/范围正确后填 verify；需要排除时填 exclude 并写清理由；绑定错误应先修正 prim/OBB，不应直接排除。CSV 是收集意见的表格，不会直接应用到 GT。paper31-ledger.template.json 也只是模板，不能冒充已批准台账。

地图准备：全部 165 个原始 OBB 外扩 2 m，0.05 m 栅格范围 {mapping['roi']['origin_xy_m']} 至 {mapping['roi']['upper_xy_m']}，形状 {mapping['roi']['shape']}，共 {mapping['cell_count']:,} 格。基础数组估计 {mapping['raw_array_estimate_bytes']/1024**3:.3f} GiB 只是存储下界，不是运行峰值。
现有 run_roi_analysis.py 要求可用内存至少 64 GiB；当前第二台电脑总内存 32 GB，不能直接运行该正式入口。保护条件未放宽。后续可验证本机分块 PhysX 生成方案，但需保持支持平面、碰撞体与参数一致并取得实际验证证据，当前未生成正式地图。

受控渲染退出 0；峰值提交内存 {evidence['resources']['peak_job_commit_gib']:.3f} GiB，显存约 {evidence['resources']['peak_gpu_gib']:.2f} GiB，耗时 {evidence['resources']['wall_seconds']:.2f} s。仅使用 Windows Isaac，未启动 WSL/ROS 或新增网络规则，临时任务已清理。
当前只完成审核材料；人工审核 0/31、正式地图/到达集未生成、正式论文 episode=0。
'''
(report/'进展说明.txt').write_text(notes,encoding='utf-8-sig')
links=' · '.join(f'<a href="#target-{i}">{i:02d}</a>' for i in range(1,32))
page='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>场景一：31 个论文目标审核包</title><style>body{max-width:1300px;margin:30px auto;padding:0 22px;background:#f3f6fa;color:#172438;font:16px/1.7 system-ui,"Microsoft YaHei"}section,.intro{background:white;border-radius:12px;padding:24px;margin:22px 0}h1,h2{line-height:1.35}h2{font-size:21px;overflow-wrap:anywhere}.grid{display:grid;grid-template-columns:1fr 1fr;gap:16px}figure{margin:0}.view{position:relative}.view img{width:100%;display:block}.overlay{position:absolute;inset:0;width:100%;height:100%;pointer-events:none}.hide-boxes .overlay{display:none}.details{display:grid;grid-template-columns:1fr 260px;gap:24px}.path{overflow-wrap:anywhere;font-size:13px}.pending{color:#995b00}.xy{width:100%}figcaption{font-size:13px;color:#526277}input[type=search]{padding:10px;width:330px;max-width:90%}pre{font:inherit;white-space:pre-wrap}a{color:#1559a2}@media(max-width:760px){.grid,.details{display:block}}</style>
<h1>场景一：31 个论文目标双视角审核包</h1><div class="intro"><p>62 张真实 RGB · 24 个绑定歧义 · 全部待人工审核</p><p>红线为标注 OBB，青线为候选世界 AABB。可关闭叠加框查看原图；图像来自静态审核相机，不是机器人巡游或目标识别结果。</p><label><input type="checkbox" checked onchange="document.body.classList.toggle('hide-boxes',!this.checked)">显示标注与候选框</label><p><input type="search" placeholder="筛选类别或实例 ID" oninput="document.querySelectorAll('section[data-search]').forEach(s=>s.hidden=!s.dataset.search.toLowerCase().includes(this.value.toLowerCase()))"></p><p>'''+links+'''</p><p><a href="审核填写表.csv">审核填写表 CSV</a> · <a href="paper31-ledger.template.json">未批准台账模板</a> · <a href="mapping-readiness.json">地图规模与运行条件</a> · <a href="进展说明.txt">进展说明</a> · <a href="evidence.json">结构化证据</a></p></div>'''+''.join(sections)+'<section><h2>本次结果与限制</h2><pre>'+html.escape(notes)+'</pre></section></html>'
(report/'查看进展.html').write_text(page,encoding='utf-8')
for p in [report/'evidence.json',root/'docs/development/ugv-ogn/paper31-review-20261018.json']:
 p.write_text(json.dumps(evidence,ensure_ascii=False,indent=2),encoding='utf-8')
with zipfile.ZipFile(run/'teacher-report.zip','w',zipfile.ZIP_DEFLATED) as z:
 for p in sorted(report.iterdir()):z.write(p,p.name)
print(json.dumps({'targets':31,'images':62,'ambiguous':ambiguity,'resources':evidence['resources']},indent=2))
