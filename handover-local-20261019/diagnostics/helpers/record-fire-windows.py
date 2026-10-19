from pathlib import Path
import datetime, json
root=Path('D:/xprogram/RAVEN-AirGround-github')
docs=root/'docs/development/ugv-ogn'
logs=root/'runs/additional_scene_preflight_20261019/fireacademy-windows-a01-evidence/logs'
frames=logs/'fireacademy-windows-a01-frames'
report=json.loads((frames/'tile-validation.json').read_text())
execution=json.loads((logs/'fireacademy-windows-a01/execution.json').read_text())
assert report['passed'] and execution['exit_code']==0
windows=[]
for w in report['windows']:
    assert all(c['outside_tolerance']==0 and c['seam_mismatch_values']==0 for c in w['comparisons'].values())
    windows.append({k:w[k] for k in ['name','metadata','comparisons','terrain_summary','footprint_summary','reach_summary','passed']})
p=docs/'fireacademy-collision-20261019.json';d=json.loads(p.read_text(encoding='utf-8'))
d['larger_windows']={'scope':'actual PhysX static triangle + two-sided query diagnostic, not formal map','execution':execution,'windows':windows,'archive_sha256':'f2f45b72492a06ce34108af6d99d44f501a5b4f37d442c75f925b763ecd9d24e','verified_files':38,'reference_cells':49152,'compared_fields':14,'old_shutdown_failure_retained':True,'formal_gt_approved':False}
p.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
p=docs/'construction-visibility-timing-20261019.json';d=json.loads(p.read_text())
d['a05_render_calls_evidence']={'archive_sha256':'a08b47f304bb0a73a2de6b25d7af9691c4dfd0743d9adafbdf137657be041e18','verified_files':27,'wall_s':378.11,'peak_commit_gib':10.885834,'render_calls':25,'actual_physics_steps':23,'actual_delta_s':0.09200000436976552,'passed':False}
d['root_cause_evidence']['next_candidate']='Separate clock-only test: at most 40 public render calls to obtain exactly 25 actual PhysX steps and 0.1s, four batches. Uses completed instance collision preparation and no invalidated map or visibility candidate input. Prepared, not started.'
p.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
p=root/'IMPLEMENTATION_PLAN.md';s=p.read_text(encoding='utf-8')
s=s.replace('三128×128窗口验证已准备，不扩散到正式运行时。','三128×128窗口/49,152格扩大验证已退出0/152.70s/峰值6.824GiB；14字段整块/分块/接缝差异均0，38文件回传核验。局部诊断通过，不等于全图或正式GT；暂不扩散到其他场景。')
p.write_text(s,encoding='utf-8')
p=root/'runs/autonomous_handover_20261019/progress.json';d=json.loads(p.read_text(encoding='utf-8'))
d.update(updated_at=datetime.datetime.now().astimezone().isoformat(),last_observed_process='construction-instancewindows-a01 正在进行51,200格验证；FireAcademy扩大窗口已正常退出',remote_log='D:/RAVEN-4060/logs/construction-instancewindows-a01/execution.json')
d['completed_this_window'].append('FireAcademy三窗口49,152格扩大验证正常退出0/152.70s/6.824GiB，14字段整块/分块与块缝差异均0，38文件回传核验；三窗口footprint可通行格4180/13456/12219。仍非全图/正式GT。')
d['reader_summary'][2]='FireAcademy静态三角碰撞和双面查询已通过49,152格扩大验证，152.70s正常退出；尚未生成全图或批准目标。'
p.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
for rel in ['benchmark/README.md','docs/benchmark_zh.md']:
    p=root/rel;s=p.read_text(encoding='utf-8').replace('FireAcademy三角碰撞/双面查询已恢复局部源面，扩大窗口验证进行中','FireAcademy三角碰撞/双面查询已通过49,152格扩大验证（14字段差异0，152.70s退出0）')
    p.write_text(s,encoding='utf-8')
print('Saved larger-window actual result and timing failure; no formal acceptance changed.')
