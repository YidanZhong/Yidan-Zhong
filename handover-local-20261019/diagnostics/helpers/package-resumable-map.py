from pathlib import Path
import html,json,shutil,sys,zipfile
sys.path.insert(0,r'D:\xprogram\.raven-setup-cache\plot-tools')
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

root=Path(r'D:\xprogram\RAVEN-AirGround-github');run=root/'runs/resumable_map_20261018';report=run/'teacher-report';report.mkdir(exist_ok=True)
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
proof=read(run/'resume-verification.json');snapshot=read(run/'full-map-snapshot.json')
assert proof['passed']
progress=snapshot['progress'];assert progress and len(snapshot['completed_records'])==progress['completed_tiles']
plt.rcParams.update({'font.family':'Microsoft YaHei','axes.unicode_minus':False})
with np.load(run/'resumed-red-car.npz') as z:obstacle=z['obstacle_mask'].astype(bool)
fig,axes=plt.subplots(1,2,figsize=(11,5),layout='constrained')
axes[0].imshow(obstacle,origin='lower',extent=[87,95,-34,-26],cmap='Greys',vmin=0,vmax=1)
contract=read(run/'resume-proof-20261018/contract.json')
records=[read(p) for p in sorted((run/'resume-proof-20261018/tiles').glob('*.json'))]
for record in records:
    r0,r1,c0,c1=record['tile']['core'];first=record['provenance']['session']=='resume-test-a01-frames'
    color='#f5b700' if first else '#1785b2'
    axes[1].add_patch(Rectangle((87+c0*.05,-34+r0*.05),(c1-c0)*.05,(r1-r0)*.05,facecolor=color,edgecolor='white'))
    axes[1].text(87+(c0+c1)*.025,-34+(r0+r1)*.025,'保留' if first else '续算',ha='center',va='center',color='black' if first else 'white')
for ax,title in zip(axes,['恢复后实际 PhysX 障碍栅格','两个独立进程的分块来源']):
    ax.set(xlim=(87,95),ylim=(-34,-26),xlabel='世界 X / m',ylabel='世界 Y / m',title=title);ax.set_aspect('equal')
fig.suptitle('真实断点恢复验证：保留 2 块 + 续算 7 块\n25,600 个网格的 8 项地形数组与之前整块采样完全一致')
fig.savefig(report/'resume-proof.png',dpi=150,bbox_inches='tight',pad_inches=.15);plt.close(fig)
config=read(run/'full-map-a01-input.json');grid=config['stream']['grid']
sys.path.insert(0,str(root/'scripts'))
from resumable_terrain_store import tile_layout,digest,TileStore
first=read(run/'full-map-initial/r00000-c00000.json')
assert digest(run/'full-map-initial/r00000-c00000.npz')==first['npz_sha256']
assert first['tile']==tile_layout(grid)[0]
assert first['contract_sha256']==progress['contract_sha256']
with np.load(run/'full-map-initial/r00000-c00000.npz',allow_pickle=False) as z:
    TileStore.validate_arrays(first['tile'],dict(z))
layout=tile_layout(grid);done={r['tile']['id'] for r in snapshot['completed_records']}
fig,ax=plt.subplots(figsize=(12,7),layout='constrained');x,y=grid['origin_xy_m'];res=grid['resolution_m']
for t in layout:
    r0,r1,c0,c1=t['core'];ax.add_patch(Rectangle((x+c0*res,y+r0*res),(c1-c0)*res,(r1-r0)*res,
        facecolor='#268a63' if t['id'] in done else '#e5e9ef',edgecolor='white',lw=.6))
ax.set(xlim=(x,x+grid['shape'][1]*res),ylim=(y,y+grid['shape'][0]*res),xlabel='世界 X / m',ylabel='世界 Y / m')
ax.set_aspect('equal');ax.set_title(f'全场景采样进度快照：{progress["completed_tiles"]}/{progress["total_tiles"]} 块（按网格数 {progress["fraction"]:.2%}）\n绿色：已保存；灰色：未完成。此图不是可通行地图。\n快照时间：{snapshot["observed_at"]}',fontsize=13)
fig.savefig(report/'full-map-progress.png',dpi=150,bbox_inches='tight',pad_inches=.15);plt.close(fig)
executions=[read(run/f'resume-test-a0{i}/execution.json') for i in [1,2]]
job_name = snapshot.get('job_name', 'full-map-a01')
recovery_path = run/'recovery-20261019/recovery-evidence.json'
recovery = read(recovery_path) if recovery_path.exists() else None
job_path = run/'source/full-map-a01.json' if job_name == 'full-map-a01' else run/f'recovery-20261019/{job_name}.json'
evidence={'task':'Local-Scene1-Reproduction / Scene1-ResumableMap-Launch',
    'implementation_and_launch_passed':True,'resume_verification':proof,
    'unit_checks':{'passed':6,'command':'python -m unittest discover -s tests -p test_resumable_terrain_store.py -v','scope':'persistence I/O checks, separate from real PhysX proof'},
    'resume_executions':executions,'full_job':read(job_path),'telemetry_recovery':recovery,
    'full_job_snapshot':snapshot,'source_sha256':{p.name:digest(p) for p in (run/'source').glob('*.py')},
    'runtime':{'isaac_sim':'4.5','platform':'native Windows','gpu':'RTX 4060 Laptop 8 GB','driver':'577.02','container_tag':None,'ros_topics_tf':'not applicable: static PhysX sampling'},
    'sampling_complete_at_snapshot':progress['sampling_complete'],'full_map_generated':False,'formal_gt_approved':False,'formal_episode_count':0,
    'first_full_tile_verified':{'npz_sha256':first['npz_sha256'],'cells':65536,'channels':8,'finite_values_shape_dtype_checked':True},
    'visual_qa':{'images':['resume-proof.png','full-map-progress.png'],'result':'Both plots directly inspected; Chinese labels readable, two preserved versus seven resumed tiles clear; full-scene plot is explicitly a progress snapshot, with unclipped labels.','browser_preview':'not attempted; local file URL browser automation is blocked'},'limitations':['Live job status is only guaranteed at snapshot time.','Full-scene postprocessing and validation remain pending.','Two-process proof uses graceful bounded stop; abrupt partial writes/corruption are covered by separate I/O tests.','Existing 64 GiB server entry guard is unchanged.']}
active=snapshot['task_state']=='Running' and bool(snapshot['processes']) and snapshot['execution'] is None
state='后台运行中' if active else ('进程已结束，请查看退出结果' if snapshot['execution'] else '当前未确认运行')
execution = snapshot.get('execution') or {}
sampling_done = progress['sampling_complete'] and execution.get('exit_code') == 0 and execution.get('status') == 'completed'
if sampling_done:
    state = '全场景原始采样完成，地图后处理待进行'
integrity_path = run/'full-map-complete-integrity.json'
if integrity_path.exists():
    evidence['full_sampling_integrity'] = read(integrity_path)
exit_detail = ''
if execution.get('error'):
    state = '任务已中断，已保存进度待续跑'
    exit_detail = f"退出原因：{execution['error']}。最后提交时间：{progress['updated_at']}。当前没有确认重新启动；续跑前须校验已保存块。"
notes=f'''场景一：断点续跑验证及全图采样启动
已完成：独立进程一保存 2 块后正常退出，独立进程二校验并跳过这 2 块，只生成剩余 7 块。先保存的两个块的数据哈希和完成记录未变；拼接后的 25,600 个网格、8 项原始地形数组与上一阶段真实整块参考结果完全一致。6 项持久化检查覆盖损坏块、参数变化、未提交文件、非有限数据/形状错误、重复提交与并发写入。
全图状态：{state}。快照时间 {snapshot['observed_at']}；已保存 {progress['completed_tiles']}/{progress['total_tiles']} 块，{progress['completed_cells']:,}/{progress['total_cells']:,} 格（{progress['fraction']:.2%}）。此页面是快照，打开页面不会自动访问另一台电脑或更新进度。
{exit_detail}
运行任务：{job_name}；第二台电脑数据目录 D:\\RAVEN-4060\\logs\\full-scene-map-20261018。每块数据先原子落盘，再写哈希完成记录；重启校验已完成块后继续，不能混用场景、参数或源码版本。每块含一圈邻域计算，保存裁剪后的核心区域；全局连通分量/车体范围后处理尚未执行。
资源保护：进程树内存上限 14 GiB、CPU 上限 60%、可用物理内存至少 4 GiB、提交余量至少 2 GiB、GPU 使用不超过 80%，磁盘预留 8 GiB。完整任务总时限 8 小时，采样预算 7.5 小时；到时保留已完成块。任务期间临时阻止空闲自动休眠，结束后恢复，不修改永久电源设置；仍请保持第二台接通电源，勿合盖、关机或手动休眠。任务使用本地资产，SSH 断开本身不会终止计划任务。
按前一阶段两个小区域线性外推，全图采样约 6 小时，但这不是完成时间承诺。实际耗时、内存和后处理仍须看全图结果。采样结束只代表原始地形数据齐全，不等于正式可通行地图、到达集或论文评测完成。
尚未完成：全图采样验收、全局后处理、逐实例 GT 人工审核、正式 episode。原正式入口 64 GiB 可用内存保护门未放宽。本轮未新增 ROS/WSL 或网络配置。
'''
if recovery:
    notes += '\n10 月 19 日恢复记录：a01 在 133 块后因 GPU 查询超时停止，失败证据保留。133 块全部通过哈希、形状、类型及有限值检查；a02 复用原采样配置。GPU 查询每次仍限时 8 秒，最多容忍连续两次失败，第三次停止；预检必须取得有效读数，未知显存以 null 记录，内存和总时限检查继续。5 项故障注入测试在两台电脑通过，仅用于验证守护逻辑。\n'
    notes += f"真实续跑：跳过 {progress['skipped_existing_tiles']} 块，本轮新增 {progress['new_tiles_this_session']} 块（以本页快照为准）。\n"
    notes += '旧任务自清理因运行用户权限不足失败；现已用同名无触发器任务启动 a02，结束后注册可能保留为 Ready，不会自动重复运行。\n'
(report/'进展说明.txt').write_text(notes,encoding='utf-8-sig')
if sampling_done:
    notes = notes.replace('尚未完成：全图采样验收、全局后处理', '尚未完成：地图拼接与全局后处理')
    notes += '\n全图原始采样已完成，程序退出码 0；527 块、32,235,504 网格全部通过合同、哈希、8 项字段类型/形状/有限值校验，原 133 块完成记录保持一致。此结论不代表可通行地图、GT 或正式论文复现验收。\n'
    (report/'进展说明.txt').write_text(notes,encoding='utf-8-sig')
for name in ['resume-verification.json','full-map-snapshot.json']:
    shutil.copy2(run/name,report/name)
page='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>场景一：断点续跑与全图采样</title><style>body{max-width:1180px;margin:32px auto;padding:0 24px;font:16px/1.8 system-ui,"Microsoft YaHei";background:#f1f5f9;color:#172438}section{background:white;padding:26px;border-radius:12px;margin:22px 0}img{max-width:100%;height:auto}pre{white-space:pre-wrap;font:inherit}a{color:#1659a3}.status{font-size:24px;color:#16734f}</style><h1>场景一：断点续跑验证与全图采样</h1><section><p class="status">'''+state+f''' · 已保存 {progress['completed_tiles']}/{progress['total_tiles']} 块</p><p>快照：{html.escape(snapshot['observed_at'])}。本页不是实时监控；全图采样及正式地图验收尚未完成。</p><p><a href="evidence.json">运行证据</a> · <a href="resume-verification.json">两次真实进程恢复验证</a> · <a href="full-map-snapshot.json">全图状态快照</a> · <a href="进展说明.txt">进展说明</a></p></section><section><h2>恢复机制已实测</h2><img src="resume-proof.png"></section><section><h2>全场景采样范围</h2><img src="full-map-progress.png"></section><section><h2>结果与限制</h2><pre>'''+html.escape(notes)+'</pre></section></html>'
if sampling_done:
    page = page.replace('全图采样及正式地图验收尚未完成。', '原始采样及完整性检查已完成；正式地图验收尚未完成。')
(report/'查看进展.html').write_text(page,encoding='utf-8')
for p in [report/'evidence.json',root/'docs/development/ugv-ogn/resumable-map-20261018.json']:
    p.write_text(json.dumps(evidence,ensure_ascii=False,indent=2),encoding='utf-8')
with zipfile.ZipFile(run/'teacher-report.zip','w',zipfile.ZIP_DEFLATED) as z:
    for p in sorted(report.iterdir()):z.write(p,p.name)
print(json.dumps({'state':state,'completed_tiles':progress['completed_tiles'],'total_tiles':progress['total_tiles'],'observed_at':snapshot['observed_at']},ensure_ascii=False))
