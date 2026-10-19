from pathlib import Path
import datetime,hashlib,json
root=Path('D:/xprogram/RAVEN-AirGround-github');docs=root/'docs/development/ugv-ogn'
correction=json.loads((root/'runs/window_reach_correction_20261019/report.json').read_text())
(docs/'window-reach-correction-20261019.json').write_text(json.dumps(correction,ensure_ascii=False,indent=2),encoding='utf-8')
for name in ['construction-instance-colliders-20261019.json','fireacademy-collision-20261019.json']:
    p=docs/name;d=json.loads(p.read_text(encoding='utf-8'));d['window_reach_correction']='Historical window reach_component used unswept seed; corrected from preserved raw actual terrain in runs/window_reach_correction_20261019. Footprint/ray evidence unchanged; active full-map postprocessor already uses swept footprint.';p.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
p=root/'IMPLEMENTATION_PLAN.md';s=p.read_text(encoding='utf-8');needle='  - [ ] S5碰撞覆盖修正：';at=s.index(needle)
s=s[:at]+'  - S6小窗口派生字段更正：历史window reach_component从support/obstacle种子生成，未接车体footprint；现根scripts/probe_tiled_terrain.py已改为footprint后0.1075m/8连通，增加子集检查。五个真实窗口原始采样的CPU重算通过，整块/分块一致；原归档不改。全图后处理本来使用footprint并重算窗口参考，当前冻结采样不受影响；详见window-reach-correction-20261019.json。\n'+s[at:]
s=s.replace('新契约/独立数据集已准备，仍须重采。','新契约dc30bf4a…/独立数据集已启动重采；首批20块/900s采样、14GiB/1200s保护，已启动等待首批通过后至多4批的有限串行续采，失败停止，70块齐全后才后处理。')
p.write_text(s,encoding='utf-8')
p=root/'runs/autonomous_handover_20261019/progress.json';s=json.loads(p.read_text(encoding='utf-8'))
s.update(updated_at=datetime.datetime.now().astimezone().isoformat(),last_observed_process='16:03:48核查：construction-instancemap-a01采样中，4/70块；有限续采等待进程也实际运行，等待首批退出0，不并行第二个GPU',remote_log='D:/RAVEN-4060/logs/construction-instance-map-20261019/progress.json')
s['current_map']={'contract_sha256':'dc30bf4ac8d061ceb549233a18a7a8206b29380bac5d97acebcc205c909e0366','last_observed_tiles':4,'total_tiles':70,'old_map_invalidated':True,'finite_continuation':'D:/RAVEN-4060/logs/construction-instance-continuation-wait-20261019/progress.json','worker_progress_after_initial_pass':'D:/RAVEN-4060/logs/construction-instance-batches-20261019/progress.json','maximum_additional_batches':4,'source_files_pinned':73,'final_postprocess_requires_complete_70_tiles':True}
s['completed_this_window'].append('发现小窗口reach派生绕过footprint，已修正诊断入口并基于5个真实窗口重算，整体/分块仍一致、reach均为footprint子集；原归档保留，全图后处理原本正确。')
s['prepared_next']['ConstructionSite']='全图首批正在采样；等待首批完成的有限续采进程已实际启动，首批失败即停止，否则最多4批并在70/70后后处理。'
p.write_text(json.dumps(s,ensure_ascii=False,indent=2),encoding='utf-8')
p=root/'runs/autonomous_handover_20261019/human-inputs.json';d=json.loads(p.read_text(encoding='utf-8'))
for item in d:
    if item['scene']=='ConstructionSite':
        item.update(status='待人工审核（已有部分真实图片，继续补拍）',evidence='runs/construction_adaptation_20261019/teacher-review-a03/查看进展.html；review-a03-visual-qa.json；construction-binding-proposals-with-proxies.json',request='可先审阅前6个候选的12张原图；view-2/10/11有明显遮挡，不能据此批准不可见目标。其余目标图待补拍；仍需核对原标注、塔吊层级及tarp网格归属，不把候选数量当成确认结果。')
p.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
for rel in ['benchmark/README.md','docs/benchmark_zh.md']:
    p=root/rel;s=p.read_text(encoding='utf-8');s=s.replace('当前状态只维护于IMPLEMENTATION_PLAN.md','小窗口reach派生已纠正并用五个真实窗口重算，原全图后处理正确；旧归档保留。当前状态只维护于IMPLEMENTATION_PLAN.md');p.write_text(s,encoding='utf-8')
p=docs/'README.md';s=p.read_text(encoding='utf-8')+'\n- [小窗口reach派生更正](window-reach-correction-20261019.json)：从保存的真实地形重算，原归档不改，当前全图流程不受影响。\n';p.write_text(s,encoding='utf-8')
print('Saved finite active queue, partial review links, and window derivation correction.')
