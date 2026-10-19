from pathlib import Path
import datetime,json,sys
sys.path.insert(0,'D:/xprogram/.raven-setup-cache/plot-tools')
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
root=Path('D:/xprogram/RAVEN-AirGround-github')
run=root/'runs/construction_adaptation_20261019'
tile=run/'tile-validation-evidence'
r=json.loads((tile/'tile-validation.json').read_text(encoding='utf-8'))
e=json.loads((tile/'execution.json').read_text(encoding='utf-8'))
assert r['passed'] and e['exit_code']==0
fig,axes=plt.subplots(2,3,figsize=(13,8))
for i,w in enumerate(r['windows']):
 with np.load(tile/f'window-{i}-reference.npz') as data:
  origin=w['metadata']['origin'];res=w['metadata']['resolution_m'];rows,cols=w['metadata']['shape']
  ext=[origin['x_m'],origin['x_m']+cols*res,origin['y_m'],origin['y_m']+rows*res]
  for ax,key in zip(axes[i],['height','obstacle_mask','footprint_mask']):
   im=ax.imshow(data[key],origin='lower',extent=ext,interpolation='nearest',cmap='viridis')
   ax.set_title(w['name']+' / '+key);ax.set_xlabel('World X (m)');ax.set_ylabel('World Y (m)');fig.colorbar(im,ax=ax,shrink=.75)
fig.suptitle('ConstructionSite: actual PhysX raycast diagnostic | unreviewed | 0.05 m\nTwo windows: whole vs tiled exact equality, including seams')
fig.tight_layout();fig.savefig(run/'tile-validation.png',dpi=150);plt.close(fig)
now=datetime.datetime.now().astimezone().isoformat()
summary={'job':'construction-tiles-a01','status':'passed','scope':'two-window diagnostic, not formal scene acceptance','cells':51200,'ray_count':r['ray_count'],'all_arrays_exactly_equal':True,'elapsed_s':e['elapsed_s'],'peak_job_commit_gib':e['peak_job_commit_gib'],'archive_sha256':'15312bf1580a1117f718fb6130a7595f72a57333b850f032deb81419c048b765','warnings':['PhysX thin-mesh convex decomposition adjusted thickness; one Plywood mesh reported GPU-incompatible cooking fallback to CPU. Raw log retained.'],'formal_gt_approved':False}
doc=root/'docs/development/ugv-ogn/construction-adaptation-20261019.json'
d=json.loads(doc.read_text(encoding='utf-8'));d['updated_at']=now;d['two_window_physx']=summary;d['validation']['live_map_sampling']='construction-map-a01 started with 14GiB/1200s guard; max20 new tiles/900s sampling; not complete'
doc.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
plan=root/'IMPLEMENTATION_PLAN.md';s=plan.read_text(encoding='utf-8')
s=s.replace('原生新场景 PhysX/双机器人实测尚未完成','原生 ConstructionSite 两窗口 PhysX 对照通过；完整双机器人实测尚未完成')
s=s.replace('已转向独立的两窗口真实 PhysX 对照；全图 4,395,972 格的断点配置仅准备未运行。','两窗口真实 PhysX 对照随后通过；全图 4,395,972 格/70 块的首批断点采样已启动，未完成。')
entry='  - S5 诊断进展（2026-10-19）：ConstructionSite `construction-tiles-a01` 两个 160×160 窗口/51,200 格/314,976 射线，14 字段整块与分块逐值完全一致（含块缝）；0.05 m 台阶、z=0 支持平面核对通过。exit 0、483.12 s、峰值提交 6.640 GiB；原始日志保留薄网格凸分解和 Plywood CPU 碰撞回退警告。归档 `runs/construction_adaptation_20261019/construction-tiles-a01-evidence.zip`（29 文件哈希/CRC 已校验）。`construction-map-a01` 已启动，最多20新块/900 s采样、14 GiB/1200 s总保护；不批准未审核 GT，S5 正式项保持未勾选。\n'
if entry not in s:s=s.replace('  - [ ] S6–S7：',entry+'  - [ ] S6–S7：',1)
plan.write_text(s,encoding='utf-8')
for p in [root/'benchmark/README.md',root/'docs/benchmark_zh.md']:
 s=p.read_text(encoding='utf-8');note='ConstructionSite 2026-10-19：两窗口真实 PhysX 整块/分块 14 字段逐值一致，首批全图采样已启动（未完成）。GT 仍未审核；0 个新场景正式验收。证据见 `construction-adaptation-20261019.json` 与主计划。\n\n'
 if note not in s:p.write_text(note+s,encoding='utf-8')
index=root/'docs/development/ugv-ogn/README.md';s=index.read_text(encoding='utf-8')
for line in ['[ConstructionSite 参数化、真实 PhysX 对照与失败渲染证据](construction-adaptation-20261019.json)。','[轮控 A/B 与支持平面高度审计](drive-ground-audit-20261019.json)。']:
 if line not in s:s+='\n'+line+'\n'
index.write_text(s,encoding='utf-8')
p=root/'runs/autonomous_handover_20261019/progress.json';s=json.loads(p.read_text(encoding='utf-8'))
s.update(updated_at=now,phase='ConstructionSite 全图断点采样首批',last_observed_process='construction-map-a01 已启动，14GiB/1200秒保护；尚未完成',remote_log='D:/RAVEN-4060/logs/construction-map-a01/',next_step='逐块核查采样；本批结束后准备原预算 DWB 导航对照和 ConstructionSite 渲染重试。')
s['completed_this_window'].append('ConstructionSite 两窗口51,200格/314,976真实射线，14字段整块与分块完全一致，483.12秒正常退出')
s['screenshots_entry']='../construction_adaptation_20261019/tile-validation.png（真实采样数据图，非RGB截图）；真实RGB参见此前场景一图文包'
p.write_text(json.dumps(s,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(summary,ensure_ascii=False))
