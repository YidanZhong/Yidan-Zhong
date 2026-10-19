from pathlib import Path
import hashlib, html, json, shutil, zipfile, sys
sys.path.insert(0,r'D:\xprogram\.raven-setup-cache\plot-tools')
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
from matplotlib.patches import Rectangle

root=Path(r'D:\xprogram\RAVEN-AirGround-github'); run=root/'runs/tiled_map_validation_20261018'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
job=next(p.parent.name for p in sorted(run.glob('tile-map-a*/execution.json'),reverse=True) if read(p)['exit_code']==0)
frames=run/f'{job}-frames';result=read(frames/'tile-validation.json');execution=read(run/job/'execution.json')
assert result['passed'] and read(frames/'report.json')['status']=='passed'
report=run/'teacher-report';report.mkdir(exist_ok=True)
plt.rcParams.update({'font.family':'Microsoft YaHei','axes.unicode_minus':False,'font.size':10})
comparisons=[]
def map_state(arrays):
    state=np.zeros(arrays['mask'].shape,dtype=np.uint8)
    state[arrays['support_mask'].astype(bool)]=1
    state[arrays['obstacle_mask'].astype(bool)]=2
    state[arrays['footprint_mask'].astype(bool)]=3
    return state
for index,w in enumerate(result['windows']):
    with np.load(frames/f'window-{index}-reference.npz') as z:ref={k:z[k] for k in z.files}
    with np.load(frames/f'window-{index}-tiled.npz') as z:tile={k:z[k] for k in z.files}
    for key in ref:
        assert np.isfinite(ref[key]).all() and np.isfinite(tile[key]).all(), key
        np.testing.assert_allclose(ref[key],tile[key],atol=1e-5 if ref[key].dtype.kind=='f' else 0,rtol=0)
    a,b=map_state(ref),map_state(tile)
    m=w['metadata'];x,y=m['origin']['x_m'],m['origin']['y_m'];rows,cols=m['shape'];res=m['resolution_m']
    extent=[x,x+cols*res,y,y+rows*res]
    fig,axes=plt.subplots(1,3,figsize=(13,4.7),layout='constrained')
    cmap=ListedColormap(['#8d99ae','#f5d78e','#d65050','#397fba'])
    for ax,values,title in zip(axes,[a,b,(a!=b).astype(np.uint8)],['整块真实 PhysX 采样','分块采样后拼接','分类差异（白色 = 一致）']):
        if ax is axes[2]:ax.imshow(values,origin='lower',extent=extent,cmap=ListedColormap(['#fff','#dc2626']),vmin=0,vmax=1)
        else:ax.imshow(values,origin='lower',extent=extent,cmap=cmap,vmin=0,vmax=3)
        ax.set(title=title,xlabel='世界 X / m',ylabel='世界 Y / m')
        ax.set_aspect('equal')
    for box in w['tiles']:
        r0,r1,c0,c1=box['core'];axes[1].add_patch(Rectangle((x+c0*res,y+r0*res),(c1-c0)*res,(r1-r0)*res,fill=False,lw=.8,ec='#111'))
    label='公交站前方区域' if index==0 else '红车及围栏区域'
    fig.suptitle(f'{label} · 8×8 m · 0.05 m / 格 · {w["tile_count"]} 块\n灰：无支持；黄：有支持但未通过车体范围检查；红：高度带内障碍；蓝：通过车体范围检查',fontsize=12)
    fig.savefig(report/f'map-comparison-{index}.png',dpi=150);plt.close(fig)
    comparisons.append({'window':w['name'],'finite_arrays':True,'arrays_compared':len(ref),
        'exact_mismatch_values':sum(c['exact_mismatch_values'] for c in w['comparisons'].values()),
        'outside_tolerance':sum(c['outside_tolerance'] for c in w['comparisons'].values()),
        'seam_mismatch_values':sum(c['seam_mismatch_values'] for c in w['comparisons'].values())})
change=read(run/'binding-change.json');before=change['before'];bound=result['corrected_binding']
old=next(r for r in read(root/'runs/paper31_review_20261018/review-input.json')['rows'] if r['target']['instance_id']==before['instance_id'])['candidate']
fig,ax=plt.subplots(figsize=(7.5,6),layout='constrained')
for center,size,color,label in [(before['obb']['center_xyz_m'],before['obb']['size_xyz_m'],'#e83e56','原标注框（保持不变）'),(old['center_xyz_m'],old['size_xyz_m'],'#de9900','旧候选 Object_9 零件'),(bound['center'],bound['size'],'#007d9e','新候选：整车根节点')]:
    ax.add_patch(Rectangle((center[0]-size[0]/2,center[1]-size[1]/2),size[0],size[1],fill=False,ec=color,lw=2,label=label))
ax.set(xlim=(87.5,94),ylim=(-33.5,-26),xlabel='世界 X / m',ylabel='世界 Y / m',title='红车绑定修正：实际 USD 世界包围盒 XY 投影\n仅修正独立未审核副本，原标注框尚待审核')
ax.set_aspect('equal');ax.legend(loc='lower left');ax.grid(alpha=.2)
fig.savefig(report/'red-car-binding.png',dpi=150);plt.close(fig)
for n in [12,13,58,59]:
    shutil.copy2(root/f'runs/paper31_review_20261018/teacher-report/view-{n}.png',report/f'previous-rgb-{n}.png')
for name in ['binding-change.json','targets.binding-corrected.unreviewed.json','tile-input.json']:
    shutil.copy2(run/name,report/name)
shutil.copy2(frames/'tile-validation.json',report/'tile-validation.json')
samples=[json.loads(line) for line in (run/job/'resources.jsonl').read_text().splitlines()]
cells=sum(np.prod(w['metadata']['shape']) for w in result['windows'])
seconds=sum(w['tiled_seconds'] for w in result['windows'])
full_cells=read(root/'runs/paper31_review_20261018/mapping-readiness.json')['cell_count']
evidence={'task':'Local-Scene1-Reproduction / Scene1-TiledMap-Validation','job':job,'passed':True,
    'scope':'small-window native PhysX tile equivalence; not formal GT or full-scene validation',
    'scene_sha256':read(frames/'report.json')['scene_sha256'],'binding_change':change,
    'window_count':len(result['windows']),'reference_cells':int(cells),'actual_rays':result['ray_count'],
    'comparison':comparisons,'execution':execution,'cleanup':read(run/'tile-map-cleanup-20261018.json'),
    'peak_gpu_gib':max(s['gpu_memory_fraction'] for s in samples)*8188/1024,
    'runtime':{'isaac_sim':'4.5','os':'native Windows','gpu':'RTX 4060 Laptop 8 GB','driver':'577.02','container_tag':None,'ros_topics_tf':'not applicable; static PhysX queries'},
    'source_sha256':{p.name:sha(p) for p in (run/'source').iterdir() if p.is_file()},
    'terrain_source_sha256':read(run/'tile-input.json')['source_sha256'],
    'full_scene_extrapolation':{'cells':full_cells,'seconds_per_cell_measured':seconds/int(cells),
        'sampling_only_estimated_hours':seconds/int(cells)*full_cells/3600,
        'scope':'linear extrapolation from two small windows; not a full-map runtime measurement; excludes startup, global processing and scene complexity changes'},
    'formal_gt_approved':False,'full_map_generated':False,'formal_episode_count':0,
    'visual_qa':{'checked_images':['map-comparison-0.png','map-comparison-1.png','red-car-binding.png'],
        'result':'All three plots directly inspected: labels readable, map axes aligned, seam lines visible and difference panels empty as expected.',
        'browser_preview':'not attempted; local file URL automation is blocked'},'limitations':result['limitations']}
windowrows=''.join(f'<tr><td>{html.escape(w["name"])}</td><td>{w["metadata"]["shape"][0]*w["metadata"]["shape"][1]:,}</td><td>{w["tile_count"]}</td><td>{w["reference_seconds"]:.2f} s</td><td>{w["tiled_seconds"]:.2f} s</td><td>{sum(c["outside_tolerance"] for c in w["comparisons"].values())}</td></tr>' for w in result['windows'])
notes=f'''场景一：本机分块地形验证（2026-10-18）
已完成两个 8×8 m 区域、0.05 m 分辨率的真实 PhysX 整块/分块对比，共 {int(cells):,} 个参考网格、{result['ray_count']:,} 次实际射线查询。每块补采样一圈 halo 后裁剪拼接；连通分量、车体范围和 reach 运算在完整拼接窗口计算，不能直接拼接每块的分量编号。
逐项比较高度、法向、支持面、障碍、净空、坡度、台阶高度，以及 seed mask/component、footprint mask/component、reach component；浮点阈值 1e-5，整数及布尔字段要求完全一致。块缝也单独检查。结果见表及结构化数据。
使用仓库现有 profiled collider 配置、z=0 无限支持平面与 terrain 算法。模型/源码哈希、碰撞体清单、命令及资源记录均保留；并未加载老师的已审核地图进行对比，不能据此声称与老师结果完全一致。
红车仅在 targets.binding-corrected.unreviewed.json 中改绑整车根节点，实际 USD 包围盒复核通过；保留全部 165 条记录和原 OBB，verified=false、ground_reachable=unknown。原始文件不变，人工批准仍为 0/31。
运行退出 0，耗时 {execution['elapsed_s']:.2f} s；峰值提交内存 {execution['peak_job_commit_gib']:.3f} GiB、显存约 {evidence['peak_gpu_gib']:.3f} GiB。保留 14 GiB 进程上限，未启动 ROS/WSL，临时任务已清理。
按这两个区域的采样速度线性外推，全图 {full_cells:,} 格仅采样约需 {evidence['full_scene_extrapolation']['sampling_only_estimated_hours']:.2f} 小时。这不是全图实测，未计启动、全图连通/车体范围计算和场景复杂度变化。当前结果只说明小区域分块计算可行，全图内存峰值仍未验证。
下一步：实现可断点续跑、磁盘保存分块结果的全图诊断生成，再验证全图拼接与后处理；同时完成逐实例绑定和标注框审核。现有服务器正式入口的 64 GiB 可用内存要求保持不变。尚未生成正式全图、到达集或论文 episode。
'''
(report/'进展说明.txt').write_text(notes,encoding='utf-8-sig')
page='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>场景一：本机分块地图验证</title><style>body{max-width:1200px;margin:32px auto;padding:0 24px;font:16px/1.8 system-ui,"Microsoft YaHei";color:#172438;background:#f1f5f9}section{background:white;padding:26px;margin:24px 0;border-radius:12px}img{max-width:100%;height:auto}table{border-collapse:collapse;width:100%}td,th{padding:10px;border-bottom:1px solid #ddd;text-align:left}.grid{display:grid;grid-template-columns:1fr 1fr;gap:20px}pre{white-space:pre-wrap;font:inherit}a{color:#145ba3}@media(max-width:700px){.grid{display:block}}</style><h1>场景一：本机分块地图验证</h1><section><h2>两个小区域的真实 PhysX 计算对比</h2><p>这是地图生成方法验证，不是机器人运行成绩或正式全场景地图。参考网格与分块网格均来自真实 PhysX 射线查询。</p><table><tr><th>区域</th><th>网格数</th><th>分块数</th><th>整块采样</th><th>分块采样</th><th>超差字段值</th></tr>'''+windowrows+'''</table><p><a href="evidence.json">运行证据</a> · <a href="tile-validation.json">逐字段对比</a> · <a href="进展说明.txt">进展说明</a></p></section>'''
for i in range(len(result['windows'])): page+=f'<section><img src="map-comparison-{i}.png"></section>'
page+='''<section><h2>红车：候选绑定已修正，标注仍待审核</h2><img src="red-car-binding.png"><p>下方为上一次审核包保存的原始 RGB，未重新拍摄或修改。</p><div class="grid"><img src="previous-rgb-58.png"><img src="previous-rgb-59.png"></div><p><a href="binding-change.json">修正前后记录</a> · <a href="targets.binding-corrected.unreviewed.json">完整未审核副本</a></p></section><section><h2>公交站现场参考</h2><p>下方同样为上一阶段的原始 RGB，用于对应位置；本次计算未启用相机。</p><div class="grid"><img src="previous-rgb-12.png"><img src="previous-rgb-13.png"></div></section><section><h2>结论与后续</h2><pre>'''+html.escape(notes)+'</pre></section></html>'
(report/'查看进展.html').write_text(page,encoding='utf-8')
for p in [report/'evidence.json',root/'docs/development/ugv-ogn/tiled-map-validation-20261018.json']:
    p.write_text(json.dumps(evidence,ensure_ascii=False,indent=2),encoding='utf-8')
with zipfile.ZipFile(run/'teacher-report.zip','w',zipfile.ZIP_DEFLATED) as z:
    for p in sorted(report.iterdir()):z.write(p,p.name)
print(json.dumps({'job':job,'comparisons':comparisons,'full_sampling_estimate_hours':evidence['full_scene_extrapolation']['sampling_only_estimated_hours']},indent=2))
