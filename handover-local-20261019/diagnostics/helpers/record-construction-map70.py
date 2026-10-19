from pathlib import Path
import datetime, hashlib, json, shutil
root=Path('D:/xprogram/RAVEN-AirGround-github')
run=root/'runs/construction_adaptation_20261019'
evidence=run/'corrected-map70-evidence'
post=evidence/'logs/construction-groundpost-a01-frames'
report=json.loads((post/'report.json').read_text())
queue=json.loads((evidence/'logs/construction-ground-batches-20261019/progress.json').read_text())
candidate=root/'runs/arrival_candidates_20261019/ConstructionSite-a01'
index=json.loads((candidate/'index.unreviewed.json').read_text())
shutil.copy2(root/'scripts/prepare_unreviewed_arrival_candidates.py',candidate/'source.py')
record={'scope':'completed actual PhysX map and unreviewed geometry candidates, not formal acceptance',
 'scene_id':'ConstructionSite','formal_accepted':False,'formal_episode_count':0,
 'archive':'runs/construction_adaptation_20261019/construction-ground-map-complete70-evidence.zip',
 'archive_sha256':'5b4dd76a4cea279e9ae58cddc8256f2d859733fa277c8e047ed7b5b23582f0d0',
 'verified_files':241,'contract_sha256':report['contract_sha256'],'grid':report['grid'],
 'stitch':report['stitch'],'derivatives':report['derivatives'],
 'reference_comparison_passed':report['reference_comparison_passed'],
 'footprint_summary':report['footprint_summary'],'reach_summary':report['reach_summary'],
 'selected_component':report['selected_component'],
 'completed_jobs':[{'name':s['job'],'exit':s['execution']['exit_code'],'wall_s':s['execution']['elapsed_s'],'peak_commit_gib':s['execution']['peak_job_commit_gib']} for s in queue['steps']],
 's7':{k:index[k] for k in ['paper_target_count','input_annotation_count','sum_instance_cells','union_cells','overlap_cells','max_instances_per_cell','output_sha256','input_targets_unchanged','readback_equal','elapsed_s']},
 'limitations':report['limitations']+['S7 includes two unbound blue tarp instances as geometry only; S8 skips them.',
 'Nested export yaml_sha256 describes pre-portability path rewrite; final bytes are pinned by report.files and archive sha256.json. Original evidence preserved.']}
target=root/'docs/development/ugv-ogn/construction-full-map-20261019.json'
target.write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
progress_path=root/'runs/autonomous_handover_20261019/progress.json'
p=json.loads(progress_path.read_text(encoding='utf-8'))
p.update(updated_at=datetime.datetime.now().astimezone().isoformat(),phase='ConstructionSite修正全图完成，真实可见性诊断进行中',last_observed_process='construction-visibility-a01 已启动，14GiB/840s保护；非正式GT',remote_log='D:/RAVEN-4060/logs/construction-visibility-a01/execution.json')
p['construction_map']=dict(queue['final_sampling_progress'],full_map_generated=True,global_postprocess_complete=True,state='diagnostic_map_completed_pending_review')
p['completed_this_window'].append('ConstructionSite修正全图70/70块、4395972格已完成；拼接/导数/两个独立窗口对照通过，241文件回传校验。0.05m footprint/reach/Nav2诊断图及18目标S7完整候选已生成；人工审核未完成。')
p['next_step']='完成16目标/124观察位姿的5个真实PhysX时间可见性诊断并归档；随后串行推进其他场景几何预检、严格Nav2候选与渲染问题。'
progress_path.write_text(json.dumps(p,ensure_ascii=False,indent=2),encoding='utf-8')
note='ConstructionSite修正全图（2026-10-19）已完成70/70块、4,395,972格，0.05m footprint/reach/Nav2诊断产物与18个论文目标的S7完整候选均已生成，两个独立窗口及接缝校验通过；241文件回传核验。所有GT仍待审核，正式新场景验收=0；见 `docs/development/ugv-ogn/construction-full-map-20261019.json`。\n\n'
for rel in ['benchmark/README.md','docs/benchmark_zh.md']:
 f=root/rel;f.write_text(note+f.read_text(encoding='utf-8'),encoding='utf-8')
plan=root/'IMPLEMENTATION_PLAN.md';s=plan.read_text(encoding='utf-8')
anchor='  - [ ] S8 未审核诊断准备'
lines=s.splitlines();where=next(i for i,v in enumerate(lines) if 'S8 未审核' in v)
lines.insert(where,'  - S5–S7诊断完成（2026-10-19）：修正碰撞配置全图70/70块、4,395,972格，0.05m footprint/reach/Nav2导出通过；接缝与两独立窗口对照通过，241文件归档核验。18论文目标完整几何候选保留重叠，2个未绑定蓝篷布仅作为未审核几何；S4缺审核，因此正式S5–S7仍未勾选。证据 `docs/development/ugv-ogn/construction-full-map-20261019.json`。')
plan.write_text('\n'.join(lines)+'\n',encoding='utf-8')
readme=root/'docs/development/ugv-ogn/README.md'
readme.write_text(readme.read_text(encoding='utf-8')+'\n- [ConstructionSite完整修正诊断图](construction-full-map-20261019.json)：70块全图与18目标未审核S7候选，正式验收未完成。\n',encoding='utf-8')
print(json.dumps(record['s7']))
