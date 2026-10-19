from pathlib import Path
import json,sys,html
root=Path('D:/xprogram/RAVEN-AirGround-github')
plan=root/'IMPLEMENTATION_PLAN.md';s=plan.read_text(encoding='utf-8')
note='  - S5–S7诊断完成（2026-10-19）：修正碰撞配置全图70/70块、4,395,972格，0.05m footprint/reach/Nav2导出通过；接缝与两独立窗口对照通过，241文件归档核验。18论文目标完整几何候选保留重叠，2个未绑定蓝篷布仅作为未审核几何；S4缺审核，因此正式S5–S7仍未勾选。证据 `docs/development/ugv-ogn/construction-full-map-20261019.json`。\n'
assert note not in s
s=s.replace('  - S8未审核诊断准备：',note+'  - S8未审核诊断准备：')
s=s.replace('全图尚未完成。图文证据','该首批为历史断点，现70/70完成，见下方S5–S7记录。图文证据')
plan.write_text(s,encoding='utf-8')
f=root/'docs/development/ugv-ogn/README.md';f.write_text(f.read_text(encoding='utf-8')+'\n- [ConstructionSite完整修正诊断图](construction-full-map-20261019.json)：70块全图与18目标未审核S7候选，正式验收未完成。\n',encoding='utf-8')
sys.path.insert(0,'D:/xprogram/.raven-setup-cache/plot-tools')
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
run=root/'runs/construction_adaptation_20261019'
post=run/'corrected-map70-evidence/logs/construction-groundpost-a01-frames'
r=json.loads((post/'report.json').read_text())
v=json.loads(Path('D:/xprogram/.raven-setup-cache/construction-visibility-v1/visibility-input.json').read_text())
height=np.load(post/'terrain/height.npy');a=np.load(post/'reach/reach.npz')
print('arrays',a.files)
mask=a['mask'];origin=r['grid']['origin_xy_m'];shape=mask.shape;res=.05
extent=[origin[0],origin[0]+shape[1]*res,origin[1],origin[1]+shape[0]*res]
fig,axes=plt.subplots(1,2,figsize=(15,7),layout='constrained')
axes[0].imshow(height,origin='lower',extent=extent,cmap='terrain',vmin=0,vmax=1)
axes[0].set_title('Actual PhysX support height (m)')
axes[1].imshow(mask,origin='lower',extent=extent,cmap='gray',vmin=0,vmax=1)
for i,row in enumerate(v['rows'],1):
 x,y,_=row['target']['obb']['center_xyz_m'];axes[1].plot(x,y,'rx',markersize=5);axes[1].annotate(str(i),(x,y),fontsize=7)
 for pose in row['poses']:
  px,py,_=pose['position_xyz_m'];axes[1].plot(px,py,'.',color='#00a1c9',markersize=2)
axes[1].set_title('Reach mask + unreviewed targets / private observers')
for ax in axes:ax.set_xlabel('map X (m)');ax.set_ylabel('map Y (m)')
fig.suptitle('ConstructionSite | 0.05 m | 70/70 tiles | DIAGNOSTIC ONLY',fontsize=15)
fig.savefig(run/'teacher-report/construction-complete-map.png',dpi=150);plt.close(fig)
rows=''.join('<tr><td>'+str(i)+'</td><td>'+html.escape(row['target']['instance_id'])+'</td><td>'+str(len(row['poses']))+'</td><td>'+html.escape(row['skip_reason'] or '待真实射线结果；绑定待人工审核')+'</td></tr>' for i,row in enumerate(v['rows'],1))
page='<!doctype html><meta charset="utf-8"><title>ConstructionSite 完整诊断图</title><style>body{max-width:1200px;margin:30px auto;font:17px/1.7 system-ui}img{width:100%}td{padding:8px;border:1px solid #ccc}table{border-collapse:collapse}</style><h1>ConstructionSite：完整诊断图已完成</h1><p>70/70块，4,395,972格，0.05m。全图拼接、导数和两个独立窗口对照通过。241个证据文件已校验。图为真实PhysX数据绘图，不是相机截图。</p><p>正式验收仍未完成：GT待人工审核，18目标仅几何候选；其中两个蓝篷布未绑定。当前图不证明实际UGV巡游或K=M。</p><img src="construction-complete-map.png"><table><tr><th>图中编号</th><th>未审核目标</th><th>待测观察位置数</th><th>状态</th></tr>'+rows+'</table><p><a href="../../../autonomous_handover_20261019/查看进展.html">总进展</a></p>'
page=page.replace('../../../autonomous_handover','../../autonomous_handover')
(run/'teacher-report/完整诊断图.html').write_text(page,encoding='utf-8')
