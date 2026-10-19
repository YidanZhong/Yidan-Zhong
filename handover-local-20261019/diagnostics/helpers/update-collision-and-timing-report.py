from pathlib import Path
import datetime,json,sys
root=Path('D:/xprogram/RAVEN-AirGround-github');run=root/'runs/construction_adaptation_20261019'
p=root/'docs/development/ugv-ogn/construction-visibility-timing-20261019.json';d=json.loads(p.read_text())
for number,sha in [('a03','5b4a80e8c1d2cd12a6e05dde65c1b7303c66b4251dad059db4090e0d9d004083'),('a04','c7f70187fbc3921bea17c8997585efb47fe0131405adba0b01a3996f0dc98c09')]:
 frames=run/f'visibility-{number}-evidence/logs/construction-visibility-{number}-frames'
 d['attempts'].append({'job':'construction-visibility-'+number,'archive_sha256':sha,'execution':json.loads((frames.parent/f'construction-visibility-{number}/execution.json').read_text()),'timing':json.loads((frames/'visibility-timing.json').read_text())})
d['root_cause_evidence']['conclusion']='Not merely duplicate scenes. A04 records one active 250Hz scene but an empty SDK manager registry; getter falls back to 60Hz. Three actual app updates advance 0.012s while getter stays 60Hz.'
d['root_cause_evidence']['next_candidate']='Public World.step(render=True) for each of 25 steps, requiring actual step index +25 and actual clock +0.1s per batch; retain max gap 0.15s and all distance/visibility gates.'
p.write_text(json.dumps(d,indent=2))
p=root/'runs/autonomous_handover_20261019/progress.json';s=json.loads(p.read_text(encoding='utf-8'))
s.update(updated_at=datetime.datetime.now().astimezone().isoformat(),phase='新场景真实碰撞A/B与可见性时序定位',last_observed_process='fireacademy-triangle-a02 已启动；Construction可见性a04已失败归档，a05已准备未启动',remote_log='D:/RAVEN-4060/logs/fireacademy-triangle-a02/execution.json')
s['failed_results'].extend(['construction-visibility-a03：World前隔离仍返回60Hz，72.73s失败，26文件核验。','construction-visibility-a04：事件更新后SDK场景记录仍为空、getter仍60Hz；实际3次应用更新推进0.012s。278.30s失败、峰值9.412GiB，26文件核验。'])
s['completed_this_window'].extend(['FireAcademy单个静态三角碰撞候选140.56s退出0，峰值8.122GiB；3点向下命中与源面误差<1e-4m，38文件核验。向上背面射线漏检正在做独立双面对照。','Windows Nav2 YAML换行哈希问题实文件重现并修复；Windows/Linux各2项检查通过，既有归档保持原样。'])
s['next_step']='完成FireAcademy双面射线局部对照；随后ConstructionSite以实测有效250Hz步进做5帧可见性检查，再做Factory几何基线与严格Nav2/审核渲染。'
p.write_text(json.dumps(s,ensure_ascii=False,indent=2),encoding='utf-8')
sys.path.insert(0,'D:/xprogram/.raven-setup-cache/plot-tools')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
doc=json.loads((root/'docs/development/ugv-ogn/fireacademy-collision-20261019.json').read_text())
fig,axes=plt.subplots(1,3,figsize=(12,5),layout='constrained')
for ax,row in zip(axes,doc['rows']):
 for z in row['source_surface_z_m']:ax.plot([-.3,.3],[z,z],color='black',lw=2)
 ax.scatter([1],[8],color='#c74835',marker='x',s=100,label='Convex: ray starts inside')
 ax.scatter([2],[row['triangle_down_z_m']],color='#007c91',s=70,label='Triangle: actual first hit')
 ax.set_xticks([0,1,2],['Source faces','Convex baseline','Triangle candidate'],rotation=15)
 ax.set_ylim(-.5,8.7);ax.set_ylabel('map Z (m)');ax.set_title('XY '+str(row['xy_m']));ax.grid(axis='y',alpha=.2)
fig.suptitle('FireAcademy | actual PhysX local A/B | NOT full-map acceptance')
folder=root/'runs/additional_scene_preflight_20261019';fig.savefig(folder/'fireacademy-collision-comparison.png',dpi=140);plt.close(fig)
(folder/'查看碰撞诊断.html').write_text('<!doctype html><meta charset="utf-8"><title>FireAcademy碰撞诊断</title><style>body{max-width:1200px;margin:30px auto;font:18px/1.7 system-ui}img{width:100%}</style><h1>FireAcademy：发现合并凸体失真，局部三角碰撞对照通过</h1><p>原配置三点均在凸体内部立即命中；仅将Ds_001改为静态三角碰撞后，向下射线恢复模型表面。图为真实射线数据，不是RGB截图。</p><img src="fireacademy-collision-comparison.png"><p>尚未验收全图、目标审核或UGV巡游。向上射线仍漏检背面，已单独安排bothSides=True的有界对照；未修改原资产。</p>',encoding='utf-8')
