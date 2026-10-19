from pathlib import Path
import datetime,json
root=Path('D:/xprogram/RAVEN-AirGround-github');run=root/'runs/construction_adaptation_20261019'
record={'scope':'failed private PhysX visibility diagnostics; no formal acceptance','attempts':[],'root_cause_evidence':{
 'sdk_physics_context':'Isaac 4.5 physics_context.py constructor reuses first existing physics scene despite requested path; setter uses that stored API, getter delegates to SimulationManager last registered scene.',
 'a01_actual_frame_gap_s':.41666668839752674,'max_allowed_frame_gap_s':.15,
 'a02_result':'Reapplying requested 1/250s through World did not make getter report 1/250s; stopped before collecting frames.',
 'next_candidate':'Disable extra source PhysicsScene prims before World initialization, then verify actual 250Hz and 25-step time gaps.',
 'source_assets_modified':False}}
for number,sha in [('a01','eb81aa15e2881362b55933527b847dfb9dec01d977131e3eff36a8b1d03ad697'),('a02','58830537fe5f07e14ae5e44dd85bd4703d82a0d10c53977fc984341db6d27095')]:
 execution=json.loads((run/f'visibility-{number}-evidence/logs/construction-visibility-{number}/execution.json').read_text())
 record['attempts'].append({'job':'construction-visibility-'+number,'execution':execution,'archive_sha256':sha,'child_exit_code':'not recorded by guard; do not infer'})
(root/'docs/development/ugv-ogn/construction-visibility-timing-20261019.json').write_text(json.dumps(record,indent=2))
p=root/'runs/autonomous_handover_20261019/progress.json';state=json.loads(p.read_text(encoding='utf-8'))
state.update(updated_at=datetime.datetime.now().astimezone().isoformat(),last_observed_process='construction-visibility-a03 已启动，有界验证World创建前物理场景隔离；FireAcademy几何基线已完成',remote_log='D:/RAVEN-4060/logs/construction-visibility-a03/execution.json')
state['failed_results'].extend(['construction-visibility-a01：真实620次观察样本时间间隔0.417s超0.15s，失败包26文件已核验。','construction-visibility-a02：重新设置World步长仍未返回250Hz，93.05s安全退出；失败包25文件已核验。'])
state['completed_this_window'].append('FireAcademy真实碰撞基线143.66s退出0，峰值8.793GiB，38文件归档核验；三点合并网格均出现零距离内部命中，与源三角形表面不符，独立三角碰撞A/B准备。ConstructionSite候选18000点独立标量距离复核通过。')
p.write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf-8')
note='真实碰撞诊断（2026-10-19）：FireAcademy三点证实合并凸体内部零距离命中，与源几何不符；正在准备保持其他配置的独立静态三角网格A/B。ConstructionSite可见性首轮时间间隔0.417s超0.15s失败，第二轮步长设置未生效；已定位World复用资产物理场景的初始化顺序，修正候选保留全部阈值。详见 `docs/development/ugv-ogn/construction-visibility-timing-20261019.json`。\n\n'
for rel in ['benchmark/README.md','docs/benchmark_zh.md']:
 p=root/rel;p.write_text(note+p.read_text(encoding='utf-8'),encoding='utf-8')
