from pathlib import Path
import json,hashlib,zipfile,datetime,sys
sys.path.insert(0,'D:/xprogram/.raven-setup-cache/plot-tools')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
root=Path('D:/xprogram/RAVEN-AirGround-github');run=root/'runs/drive_audit_20261019'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
archive=run/'drive-audit-evidence-20261019.zip'
assert sha(archive)=='597f9cddc5018ab8390d73af5ecc5f7536d45e8f765ca0fb11df3f838ff5f8d8'
with zipfile.ZipFile(archive) as z:
 assert z.testzip() is None
 manifest=json.loads(z.read('sha256.json'))
 for name,digest in manifest.items():assert hashlib.sha256(z.read(name.replace('\\','/'))).hexdigest()==digest,name
 executions={j:json.loads(z.read(f'logs/{j}/execution.json')) for j in ('drive-audit-a01','drive-audit-a02','drive-audit-a03')}
summary={'scope':'真实 PhysX 诊断，不是导航稳定性或正式场景验收','runs':{},'archive_sha256':sha(archive),'source_hashes':{}}
fig,axes=plt.subplots(1,2,figsize=(11,5))
for backend,job in [('direct','drive-audit-a03'),('actions','drive-audit-a02')]:
 data=json.loads((run/f'{backend}.json').read_text())
 summary['runs'][backend]={'job':job,'segments':[{k:v for k,v in s.items() if k not in ('start','end')} for s in data['segments']],
  'execution':executions[job]}
 for ax,name in zip(axes,['turn-left','turn-right']):
  points=[s['position'] for s in data['samples'] if s['segment']==name]
  origin=next(s['start']['position'] for s in data['segments'] if s['name']==name)
  ax.plot([p[0]-origin[0] for p in points],[p[1]-origin[1] for p in points],label=backend)
  ax.set_title(name+' / 18 sim seconds');ax.set_xlabel('World X displacement (m)');ax.set_ylabel('World Y displacement (m)');ax.axis('equal');ax.grid(True);ax.legend()
fig.suptitle('Real PhysX turn traces — both interfaces still drift');fig.tight_layout();fig.savefig(run/'turn-drift.png',dpi=160);plt.close(fig)
summary['findings']=['动作接口没有消除原地转向平移，暂不改变默认轮控接口。','五个真实 PhysX 射线位置显示 z=0 支持平面与原道路 z≈-0.19126 m 并存；轮心 z≈0.098 m，与轮半径吻合。','静态 USD 中轮胎 authored extent 方向与圆柱 schema 不一致；schema axis=Z 经 X 轴90度旋转后与车轮关节轴一致，不能把缓存包围盒异常解释成实际轮轴装反。','原三目标/朝向/容差/120 s 下的稳定性重复验收仍未完成。']
summary['unresolved']=['转向摩擦、驱动力与控制/规划重置对末端漂移的相对影响未确定。','Nav2 Humble 上游 setPlannerPath 重置 goal checker；与本机安装二进制和失败时序尚未完整对照，不能当作已证明根因。','未修改支持平面、场景坐标、机器人碰撞几何或 GT；视觉高差仍存在。']
summary['references']=['https://raw.githubusercontent.com/ros-navigation/navigation2/humble/nav2_controller/src/controller_server.cpp','https://raw.githubusercontent.com/ros-navigation/navigation2/humble/nav2_regulated_pure_pursuit_controller/src/regulated_pure_pursuit_controller.cpp']
summary['failed_attempt']={'job':'drive-audit-a01','reason':'CLI缺少必须的ray-origin，应用启动前退出；证据保留','execution':executions['drive-audit-a01']}
summary['cleanup']='三次诊断均已退出；临时计划任务已移除，无本轮仿真后台进程。'
for p in [root/'scripts/probe_jackal_drive_audit.py',root/'scripts/probe_windows_scene_render.py',run/'drive-asset-audit.json']:summary['source_hashes'][str(p.relative_to(root))]=sha(p)
(run/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
(root/'docs/development/ugv-ogn/drive-ground-audit-20261019.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
plan=root/'IMPLEMENTATION_PLAN.md';text=plan.read_text(encoding='utf-8');old='通过实际短测后才选择候选接口做原 120 s 三目标回归。'
text=text.replace(old,old+' 2026-10-19 已完成 direct/actions 两个真实 56 s 有界对照，左右转向最大平移分别约 0.387/0.389 m 与 0.362/0.347 m；动作接口未解决漂移，未切换默认或声称稳定性通过。归档及图见 `runs/drive_audit_20261019/`，证据 `docs/development/ugv-ogn/drive-ground-audit-20261019.json`。')
text=text.replace('不为修图直接移动机器人或篡改截图。','不为修图直接移动机器人或篡改截图。 2026-10-19 已记录五处真实射线：支持平面约 z=0、原道路 z=-0.19126 m，轮心约 z=0.098 m；轮胎 schema/关节轴一致，缓存 extent 异常不作为实际碰撞错误结论。未改变任何坐标或原始资产，视觉高差仍未消除。')
text=text.replace('不得把其他场景的 legacy PX4 launch 当作双机器人模板。','不得把其他场景的 legacy PX4 launch 当作双机器人模板。 下一有界阶段：ConstructionSite 在独立副本完成传输哈希/依赖/坐标预检，再以现有 14 GiB 原生诊断入口生成未审核两视角材料；缺失绑定保持未绑定，优先暴露真实资产问题。')
plan.write_text(text,encoding='utf-8')
for name in ['benchmark/README.md','docs/benchmark_zh.md']:
 p=root/name;t=p.read_text(encoding='utf-8');p.write_text('> 2026-10-19 转向/地面诊断：direct/actions 均出现约 0.35–0.39 m 转向平移，未认定修复；z=0 支持平面与原道路相差约 0.191 m。证据 `docs/development/ugv-ogn/drive-ground-audit-20261019.json`；正式状态以 `IMPLEMENTATION_PLAN.md` 为准。正在转向 ConstructionSite 的隔离资产/坐标与未审核材料准备。\n\n'+t,encoding='utf-8')
progress=root/'runs/autonomous_handover_20261019/progress.json';s=json.loads(progress.read_text());s.update(updated_at=datetime.datetime.now().astimezone().isoformat(),phase='ConstructionSite 资源/坐标预检；转向问题保留未闭合',last_observed_process='drive-audit-a02/a03 已退出0，临时任务已移除；ConstructionSite传输包在主机准备',completed_this_window=['真实轮控A/B、支持平面/路面高度审计、源码与日志哈希归档'],findings=summary['findings'],next_step='ConstructionSite 独立资产副本预检、运行参数及双视角审核材料');progress.write_text(json.dumps(s,ensure_ascii=False,indent=2),encoding='utf-8')
print('Archive hashes checked; drive report and plan synchronized.')
