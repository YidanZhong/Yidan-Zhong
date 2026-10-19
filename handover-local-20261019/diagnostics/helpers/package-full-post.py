from pathlib import Path
import hashlib,html,json,sys,zipfile
sys.path.insert(0,r'D:\xprogram\.raven-setup-cache\plot-tools')
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
from PIL import Image

root=Path(r'D:\xprogram\RAVEN-AirGround-github')
run=root/'runs/full_map_postprocess_20261019'
with zipfile.ZipFile(run/'full-post-a01-evidence.zip') as z:
    assert z.testzip() is None
    assert all(not Path(n).is_absolute() and '..' not in Path(n).parts for n in z.namelist())
    z.extractall(run)
frames=run/'full-post-a01-frames';report=run/'teacher-report';report.mkdir(exist_ok=True)
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as stream:
        for data in iter(lambda:stream.read(1024*1024),b''):h.update(data)
    return h.hexdigest()
r=read(frames/'report.json');e=read(run/'full-post-a01/execution.json');c=read(frames/'component-report.unreviewed.json')
assert r['status']=='passed' and e['exit_code']==0 and e['status']=='completed'
assert r['reference_comparison_passed'] and not r['formal_gt_approved']
for relative,record in r['files'].items():
    if relative.startswith('terrain/'):continue
    assert sha(frames/relative)==record['sha256'],relative
assert sha(run/'source/postprocess_terrain_tiles.py')==r['source_sha256']['postprocess_terrain_tiles.py']
assert not any(t['eligible_in_selected_component'] or t['formal_gt_approved'] for t in c['targets'])
map_checks={}
for name in ('footprint','reach'):
    folder=frames/name
    with np.load(folder/f'{name}.npz',allow_pickle=False) as z:
        mask=z['mask'].astype(bool)
        comp=z['component']
        assert np.all(comp[~mask]==-1) and np.all(comp[mask]>=0)
    image=np.asarray(Image.open(folder/f'{name}.unreviewed.pgm'))
    assert np.array_equal(np.flipud(image)==254,mask)
    map_checks[name]={'pgm_orientation_and_all_cells_match':True,'free_cells':int(mask.sum())}
    if name=='reach':
        selected_image=np.asarray(Image.open(frames/'selected/selected.unreviewed.pgm'))
        assert np.array_equal(np.flipud(selected_image)==254,comp==r['selected_component']['component_id'])
        map_checks['selected']={'pgm_orientation_and_all_cells_match':True,
                               'free_cells':int((comp==r['selected_component']['component_id']).sum())}
        del selected_image
    del mask,comp,image
with np.load(frames/'preview.npz') as z:preview=dict(z)
plt.rcParams.update({'font.family':'Microsoft YaHei','axes.unicode_minus':False})
grid=r['grid'];x,y=grid['origin_xy_m'];rows,cols=grid['shape'];res=grid['resolution_m']
extent=[x,x+cols*res,y,y+rows*res]
fig,axes=plt.subplots(3,1,figsize=(13,19),layout='constrained')
panels=[(preview['obstacle'].astype(int),ListedColormap(['#eef2f5','#293444']),'① 原始 PhysX 障碍投影（深色为障碍）'),
        (preview['footprint'].astype(int),ListedColormap(['#293444','#77afcf']),'② 车体可通行区域（蓝色）：0.508×0.430 m / 16 朝向 / 5 cm 台阶'),
        (np.where(preview['selected'],2,np.where(preview['reach'],1,0)),ListedColormap(['#293444','#e9a249','#42a171']),
         '③ 净空与连通区域：绿色为选定连通域，橙色为其他连通域，深色不可通行')]
for ax,(data,cmap,title) in zip(axes,panels):
    ax.imshow(data,origin='lower',extent=extent,cmap=cmap,interpolation='nearest',vmin=0,vmax=len(cmap.colors)-1)
    ax.set(title=title,xlabel='世界 X / m',ylabel='世界 Y / m')
fig.suptitle('场景一全场景地图后处理诊断\n完整数据 0.05 m；此总览以 4 倍抽样展示，不能据图判断窄缝通行。未审核，不是正式导航验收。',fontsize=15)
fig.savefig(report/'full-map-overview.png',dpi=130,bbox_inches='tight');plt.close(fig)
fig,ax=plt.subplots(figsize=(14,8),layout='constrained')
ax.imshow(panels[2][0],origin='lower',extent=extent,cmap=panels[2][1],vmin=0,vmax=2,interpolation='nearest')
for index,t in enumerate(c['targets'],1):
    tx,ty,_=t['obb']['center_xyz_m']
    ax.scatter([tx],[ty],s=30,c='#ffffff' if t['in_selected_component'] else '#ff3c54',edgecolors='black',linewidths=.6)
    offset={1:(-18,-12),2:(-18,12),3:(-20,12),4:(12,-15)}.get(index,(4,3))
    ax.annotate(str(index),(tx,ty),xytext=offset,textcoords='offset points',fontsize=8,
                arrowprops={'arrowstyle':'-','color':'white','linewidth':.6} if index in (1,2,3,4) else None,
                bbox={'facecolor':'white','alpha':.75,'edgecolor':'none','pad':.6})
selected=r['selected_component'];inside=sum(t['in_selected_component'] for t in c['targets'])
ax.set(title=f'31 个论文目标的几何候选覆盖：{inside}/31\n按目标覆盖数、面积选择连通域 C{selected["component_id"]}；白点有候选到达区域，红点无候选。',xlabel='世界 X / m',ylabel='世界 Y / m')
fig.savefig(report/'target-coverage.png',dpi=140,bbox_inches='tight');plt.close(fig)
evidence={'task':'Local-Scene1-Reproduction / Scene1-FullMap-Completion','postprocessing_passed':True,
 'execution':e,'report':r,'local_export_checks':map_checks,
 'tests':{'stitch_checks_passed':2,'command':'python -m unittest discover -s tests -p test_terrain_tile_stitch.py -v',
          'environments':['main PC bundled Python','RTX 4060 Isaac 4.5 Python'],
          'scope':'disk assembly checks, separate from real PhysX data comparisons'},
 'transferred_non_terrain_files_hashes_verified':True,'archive_sha256':sha(run/'full-post-a01-evidence.zip'),
 'original_terrain_location':'D:/RAVEN-4060/logs/full-post-a01-frames/terrain',
 'postrun_cli_hardening':{'change':'Refuse pre-existing output before exception handler to preserve old reports; numerical processing unchanged.',
     'current_source_sha256':sha(root/'scripts/postprocess_terrain_tiles.py'),
     'validation':'Local 3-test suite including pre-existing report preservation; runtime numerical source snapshot retained separately.'},
 'formal_gt_approved':False,'formal_episode_count':0,'visual_qa':'pending'}
(run/'postprocess-evidence.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2),encoding='utf-8')
table=''.join(f'<tr><td>{i}</td><td>{html.escape(t["instance_id"])}</td><td>{"有候选" if t["in_selected_component"] else "暂无候选"}</td><td>待审核</td></tr>' for i,t in enumerate(c['targets'],1))
text=f'''场景一：全图拼接与可通行性后处理
完成：527 块 / 32,235,504 格，分辨率 0.05 m。8 项原始字段逐块磁盘回读一致；覆盖无遗漏、无重叠。
全图重算坡度、台阶与分块结果一致（容差 1e-5），块缝超差值为 0；两个先前真实 PhysX 小窗口的原始字段及 5 cm 台阶配置下可通行/净空 mask 对照通过（排除局部窗口边界影响）。这不是整张图的独立重采样对照。
车体：0.508×0.430 m，16 朝向均须通过，坡度≤15°，台阶≤0.05 m，顶部余量≥0.5 m。净空图基于车体可通行图，再应用 0.1075 m 净空及 8 连通规则。
车体可通行网格：{r['footprint_summary']['traversable_cells']:,}；净空图网格：{r['reach_summary']['passable_cells']:,}；净空连通区域：{r['reach_summary']['component_count']} 个。
选定区域 C{selected['component_id']}，面积 {selected['area_m2']:,.2f} 平方米；31 个论文目标中 {inside} 个的 OBB 表面 1.5–8 m 几何候选区域与其相交。这里不是实际到达 K/M，也不是检测准确率；所有目标仍需人工审核。
原生后处理退出码 {e['exit_code']}；耗时 {e['elapsed_s']:.1f} 秒，进程树峰值提交内存 {e['peak_job_commit_gib']:.3f} GiB，守护上限 14 GiB。采样使用 Isaac Sim 4.5 / RTX 4060 / 577.02 驱动；本轮仅对真实采样数据做 CPU 后处理，无新增仿真、ROS 话题或机器人轨迹。
已生成 footprint、reach 和选定区域的未审核 Nav2 YAML/PGM；本地验证导出 PGM 的全部格点及上下方向与 NPZ 一致。完整地图在上一层 full-post-a01-frames 文件夹，原始拼接 NPY 保存在第二台电脑。
仍待完成：人工目标绑定/框审核，真实导航与转角通行验证、可见性与到达集验收、正式 episode。沿用 z=0 支持平面和现有碰撞近似，尚未与老师地图比对。现有正式入口 64 GiB 资源门未修改。
'''
(report/'进展说明.txt').write_text(text,encoding='utf-8-sig')
page='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>场景一全图后处理进展</title><style>body{max-width:1200px;margin:32px auto;padding:0 24px;font:16px/1.8 system-ui,"Microsoft YaHei";background:#f1f5f9;color:#172438}section{background:white;padding:24px;border-radius:12px;margin:20px 0}img{width:100%;height:auto}pre{white-space:pre-wrap;font:inherit}table{border-collapse:collapse;width:100%}td,th{border:1px solid #cbd5e1;padding:6px;text-align:left}a{color:#1659a3}</style><h1>场景一：全图拼接与可通行性后处理已完成</h1><section><b>已完成地图诊断，尚未完成论文复现验收。</b><p><a href="进展说明.txt">进展说明</a> · <a href="evidence.json">验证证据</a></p><pre>'''+html.escape(text)+'''</pre></section><section><h2>地图总览</h2><img src="full-map-overview.png"></section><section><h2>论文目标几何候选覆盖</h2><img src="target-coverage.png"><table><tr><th>编号</th><th>实例</th><th>选定区域内</th><th>人工审核</th></tr>'''+table+'''</table></section></html>'''
(report/'查看进展.html').write_text(page,encoding='utf-8')
print(json.dumps({'covered':inside,'targets':31,'footprint_cells':r['footprint_summary']['traversable_cells'],
 'reach_cells':r['reach_summary']['passable_cells'],'reach_components':r['reach_summary']['component_count'],
 'selected':selected,'peak_gib':e['peak_job_commit_gib'],'elapsed_s':e['elapsed_s']},ensure_ascii=False))
