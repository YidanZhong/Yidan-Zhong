from pathlib import Path
import ast,csv,hashlib,html,json,math,shutil,zipfile
import numpy as np
from PIL import Image
repo=Path('D:/xprogram/RAVEN-AirGround-github');run=repo/'runs/construction_adaptation_20261019';job='construction-review-a02';evidence_root=run/'review-a02-evidence'
read=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
frames=evidence_root/'logs'/(job+'-frames');render=read(frames/'report.json');execution=read(evidence_root/'logs'/job/'execution.json');input_file=evidence_root/'setup/construction-review-v1/review-input.json';inputs=read(input_file)
assert render['status']=='passed' and execution['exit_code']==0
assert len(render['frames'])==56 and len(render['review_targets'])==28
assert render['review_manifest_sha256']==sha(input_file) and render['scene_sha256']==inputs['scene_sha256']
assert all(not r['target']['verified'] and r['target']['ground_reachable']=='unknown' for r in inputs['rows'])
report=run/'teacher-review-a02';report.mkdir(exist_ok=False)
# Reuse the already checked camera projection functions, without executing the
# old Retro packaging script or importing its scene-specific state.
tree=ast.parse(Path('D:/xprogram/.raven-setup-cache/package-paper31-review.py').read_text(encoding='utf-8'))
for f in tree.body:
 if isinstance(f,ast.FunctionDef) and f.name in ('corners','wire'):
  exec(compile(ast.Module(body=[f],type_ignores=[]),'<review-projection>','exec'))
actual={t['instance_id']:t for t in render['review_targets']};group={r['target']['instance_id']:[] for r in inputs['rows']}
images=[]
for frame in render['frames']:
 assert frame['consecutive_valid_frames']>=60
 p=frames/frame['file']
 with Image.open(p) as im:assert im.size==(960,600);im.verify()
 shutil.copy2(p,report/p.name)
 group[frame['instance_id']].append(frame);images.append({**frame,'sha256':sha(p),'original_rgb':True})
sections=[];geometry=[]
for index,row in enumerate(inputs['rows'],1):
 t=row['target'];key=t['instance_id'];a=actual[key];obb=t['obb'];candidate=row['candidate'];notes=[]
 if candidate:
  assert math.dist(candidate['center_xyz_m'],a['actual_candidate_center_xyz_m'])<.02
  assert math.dist(candidate['size_xyz_m'],a['actual_candidate_size_xyz_m'])<.02
  delta=math.dist(obb['center_xyz_m'],a['actual_candidate_center_xyz_m']);ratio=math.prod(a['actual_candidate_size_xyz_m'])/math.prod(obb['size_xyz_m'])
  notes.append(f'中心差 {delta:.3f} m；候选/标注体积比 {ratio:.3f}')
  if not .5<=ratio<=2:notes.append('模型层级或标注范围差异较大，需重点核对')
 else:
  delta=ratio=None;notes.append('未绑定：仅按原标注位置拍摄上下文，青色候选框不存在')
 if row['binding']['issues']:notes.append('绑定问题：'+', '.join(row['binding']['issues']))
 figures=[]
 assert len(group[key])==2
 for frame in group[key]:
  overlay=wire(frame,corners(obb['center_xyz_m'],obb['size_xyz_m'],obb['orientation_rpy_rad']),'#ff354b')
  if candidate:overlay+=wire(frame,corners(a['actual_candidate_center_xyz_m'],a['actual_candidate_size_xyz_m'],[0,0,0]),'#00c9ef')
  figures.append(f'<figure><div class="view"><img loading="lazy" src="{frame["file"]}"><svg class="overlay" viewBox="0 0 960 600">{overlay}</svg></div><figcaption>视角 {frame["view_index"]+1} · 实际渲染帧 {frame["rendering_frame"]} · <a href="{frame["file"]}">原图</a></figcaption></figure>')
 cx,cy=obb['center_xyz_m'][:2];span=max(20.,max(obb['size_xyz_m'][:2])*1.5)
 points=''.join(f'<circle cx="{150+(other["target"]["obb"]["center_xyz_m"][0]-cx)*140/span:.2f}" cy="{150-(other["target"]["obb"]["center_xyz_m"][1]-cy)*140/span:.2f}" r="4" fill="#999"/>' for other in inputs['rows'] if abs(other['target']['obb']['center_xyz_m'][0]-cx)<=span and abs(other['target']['obb']['center_xyz_m'][1]-cy)<=span)
 xy=f'<svg width="260" viewBox="0 0 300 300"><rect width="300" height="300" fill="#edf2f8"/>{points}<circle cx="150" cy="150" r="6" fill="#f33"/><text x="12" y="285" font-size="12">XY +/-{span:.1f} m; NOT a traversability map</text></svg>'
 alternatives='<br>'.join(html.escape(p['prim_path']) for p in row['near_center_alternatives']) or '无同中心候选。'
 sections.append(f'<section id="target-{index}"><h2>{index:02d} · {html.escape(key)}</h2><p class="pending">待人工审核：{html.escape("；".join(notes))}</p><div class="grid">{"".join(figures)}</div><p>标注中心 {obb["center_xyz_m"]}；尺寸 {obb["size_xyz_m"]}；候选 {html.escape(t.get("usd_prim_path") or "未绑定")}</p>{xy}<details><summary>同中心候选层级</summary><p>{alternatives}</p></details></section>')
 geometry.append({'instance_id':key,'candidate_center_delta_m':delta,'candidate_volume_ratio':ratio,'notes':notes,'human_review':'pending'})
with (report/'审核填写表.csv').open('w',encoding='utf-8-sig',newline='') as f:
 w=csv.writer(f);w.writerow(['instance_id','semantic_class','candidate_prim','decision_verify_or_exclude','corrected_prim','excluded_reason','notes'])
 for r in inputs['rows']:w.writerow([r['target']['instance_id'],r['target']['semantic_class'],r['target'].get('usd_prim_path'),'','','',''])
ledger_file=repo/'runs/scene_gt_adaptation_20261017/ConstructionSite/review.ledger.template.json'
assert read(ledger_file)['source_annotations_sha256']==inputs['source_sha256']['targets']
shutil.copy2(ledger_file,report/'review.ledger.template.json')
evidence={'scope':'ConstructionSite static review material only','target_count':28,'original_image_count':56,'unbound_count':3,'ambiguous_bound_count':25,
 'human_verified_count':0,'formal_episodes':0,'formal_accepted':False,'scene_sha256':inputs['scene_sha256'],
 'input_sha256':sha(input_file),'images':images,'geometry':geometry,
 'runtime':{'isaac_sim':'4.5.0','ros':'not used','gpu':'RTX 4060 Laptop 8GB','exit_code':execution['exit_code'],
 'elapsed_s':execution['elapsed_s'],'peak_job_commit_gib':execution['peak_job_commit_gib'],'limits':execution['limits'],'command':execution['command']},
 'limitations':['All decisions remain blank; rendering is not human verification.','Overview views may be occluded or distant; no synthetic pixels substituted.','Unreal-sourceAsset warnings retained; shader warnings require visual review.','No map, arrival set, episode, actual patrol or K=M acceptance in this packet.'],
 'visual_inspection':'pending direct inspection of generated image samples'}
(report/'evidence.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2),encoding='utf-8')
page='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>ConstructionSite 未审核目标材料</title><style>body{max-width:1350px;margin:32px auto;padding:24px;background:#f3f6fa;font:16px/1.65 system-ui,"Microsoft YaHei";color:#172438}section,header{background:white;padding:24px;margin:20px 0;border-radius:12px}h2,p{overflow-wrap:anywhere}.grid{display:grid;grid-template-columns:1fr 1fr;gap:16px}figure{margin:0}.view{position:relative}.view img{width:100%;display:block}.overlay{position:absolute;inset:0;width:100%;height:100%;pointer-events:none}.hide .overlay{display:none}.pending{color:#975a00}figcaption{font-size:13px}@media(max-width:800px){.grid{display:block}}</style><header><h1>ConstructionSite：28 个目标 / 56 张真实 RGB</h1><p>全部待人工审核；25 个候选有歧义，3 个 tarp 未绑定。红线是原标注 OBB，青线是候选世界 AABB；并非实例分割。</p><p>高大目标采用较远的相机视角，局部遮挡或尺寸差异应记录为审核问题。此处不宣称正式 GT、地图或巡游通过。</p><label><input type="checkbox" checked onchange="document.body.classList.toggle('hide',!this.checked)">显示标注/候选框</label><p><a href="审核填写表.csv">空白审核表</a> · <a href="review.ledger.template.json">未批准台账模板</a> · <a href="evidence.json">运行证据</a></p></header>'''+''.join(sections)+'</html>'
(report/'查看进展.html').write_text(page,encoding='utf-8')
with zipfile.ZipFile(run/'teacher-review-a02.zip','x',zipfile.ZIP_DEFLATED) as z:
 for p in report.iterdir():z.write(p,p.name)
print(json.dumps({'images':len(images),'targets':len(geometry),'wall_s':execution['elapsed_s'],'peak_gib':execution['peak_job_commit_gib']}))
