from pathlib import Path
import datetime
import json

root = Path('D:/xprogram/RAVEN-AirGround-github')
docs = root / 'docs/development/ugv-ogn'
run = root / 'runs/construction_adaptation_20261019'
evidence = run / 'instances-a02-evidence/logs'
execution = json.loads((evidence / 'construction-instances-a02/execution.json').read_text())
frames = evidence / 'construction-instances-a02-frames'
audit = json.loads((frames / 'raw-ray-audit.json').read_text())
coverage = json.loads((frames / 'collision-coverage.json').read_text())
assert execution['exit_code'] == 0 and execution['diagnostic_status'] == 'passed' and not coverage['missing_visible']
hits = {h['prim_path'] for p in audit['points'] for h in p['down_hits']}
assert '/World/stage/ConstructionSite/Biotoilet2/SM_Biotoilet/Mesh' in hits
assert '/World/stage/ConstructionSite/AsphaltRoller2/SM_AsphaltRoller/Section0/Mesh' in hits
result = {'scope': 'actual PhysX small-window collider restoration; not full map or human GT approval',
          'execution': execution, 'coverage': coverage, 'restored_target_hits': sorted(p for p in hits if 'Biotoilet2' in p or 'AsphaltRoller2' in p),
          'reference_cells': 8, 'raw_ray_audit_points': 5, 'archive_sha256': '9b64249067da551237e7ecdd22fb731bec5461e536a7f8a324d357420ff67b17',
          'verified_files': 38, 'next': '51200-cell independent whole/tiled windows before a fresh full-map contract', 'old_map_still_invalidated': True}
p = docs / 'construction-instance-colliders-20261019.json'
d = json.loads(p.read_text(encoding='utf-8'))
d['real_expanded_PhysX'] = 'a02 completed exit 0; restored real clone hits, 5758 colliders including support plane, no visible scene mesh missing collision'
d['a02_candidate']['runtime'] = result
p.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding='utf-8')
p = root / 'IMPLEMENTATION_PLAN.md'
s = p.read_text(encoding='utf-8').replace('真实PhysX有界预检进行中。见 `construction-instance-colliders-20261019.json`。', '真实PhysX a02预检已退出0/380.03s/峰值8.207GiB：5757场景网格及支持平面共5758碰撞体、缺失0，厕所2/压路机2实际命中恢复，38文件核验；已准备51,200格整块/分块验证，仍须新契约重采。见 `construction-instance-colliders-20261019.json`。')
s = s.replace('S5–S7诊断完成（2026-10-19）：修正碰撞配置全图', 'S5–S7历史诊断（后发现实例漏碰撞，产物已INVALIDATED，不可验收）：当时修正碰撞配置全图')
p.write_text(s, encoding='utf-8')
p = root / 'runs/autonomous_handover_20261019/progress.json'
d = json.loads(p.read_text(encoding='utf-8'))
d.update(updated_at=datetime.datetime.now().astimezone().isoformat(), last_observed_process='fireacademy-windows-a01 正在进行49,152格窗口验证；ConstructionSite实例补全a02已正常结束', remote_log='D:/RAVEN-4060/logs/fireacademy-windows-a01/execution.json')
d['completed_this_window'].append('ConstructionSite实例补全真实PhysX预检退出0/380.03s/8.207GiB，5758碰撞体无可见网格遗漏；厕所2和压路机2射线恢复，38文件回传核验。51,200格窗口扩大测试已冻结准备。')
d['reader_summary'][1] = 'ConstructionSite旧完整图因5075实例漏碰撞已失效；补全后真实预检通过，下一步扩大窗口验证并重采全图。'
d['reader_summary'][2] = 'FireAcademy局部三角碰撞和双面查询已有源面命中证据，49,152格扩大验证正在运行；此前一轮关闭异常仍单独保留。'
d['findings'] = [x for x in d['findings'] if not x.startswith('ConstructionSite地形分类修正已有') and not x.startswith('离线发现FireAcademy')]
d['findings'].append('FireAcademy和Factory真实射线已证明大型合并网格凸体高度失真，局部静态三角碰撞须逐场景验证，不能推广为全部场景已修复。')
p.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding='utf-8')
note = '''> 本机 handover 当前状态（2026-10-19）：后续场景正式验收仍为0。ConstructionSite旧70块图/S7候选因5075实例漏碰撞已标记INVALIDATED；精确几何原型补全的真实PhysX预检已通过（380.03s、峰值8.207GiB），正在扩大窗口验证，之后须新契约重采。FireAcademy三角碰撞/双面查询已恢复局部源面，扩大窗口验证进行中；Factory单个合并地面修正待实测。Retro三轮导航严格位姿7/9，尚未通过稳定性。原资产、人工审核位及验收阈值均保留。当前状态只维护于IMPLEMENTATION_PLAN.md，详细结果见docs/development/ugv-ogn内construction-instance-colliders、fireacademy-collision、factory-collision、nav2-dwb-stability证据文件；历史完整图记录不代表当前可验收。

'''
# Consolidate only the generated 2026-10-19 notes preceding the existing title.
for rel in ['benchmark/README.md', 'docs/benchmark_zh.md']:
    p = root / rel
    s = p.read_text(encoding='utf-8')
    title = s.index('# RAVEN-AirGround Benchmark')
    assert '碰撞覆盖补充（2026-10-19）' in s[:title]
    p.write_text(note + s[title:], encoding='utf-8')
print('Recorded actual collider restoration; formal status unchanged; stale generated preface consolidated.')
