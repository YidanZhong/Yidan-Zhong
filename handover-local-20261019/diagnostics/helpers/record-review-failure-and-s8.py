from pathlib import Path
import datetime,hashlib,json
root=Path('D:/xprogram/RAVEN-AirGround-github');run=root/'runs/autonomous_handover_20261019'
evidence_root=root/'runs/construction_adaptation_20261019/review-a02-evidence'
execution=json.loads((evidence_root/'logs/construction-review-a02/execution.json').read_text())
report=json.loads((evidence_root/'logs/construction-review-a02-frames/report.json').read_text())
failure={'job':'construction-review-a02','status':report['status'],'error':report['error'],
         'elapsed_s':execution['elapsed_s'],'peak_job_commit_gib':execution['peak_job_commit_gib'],
         'camera_frames':len(report['frames']),'expected_camera_frames':56,'scheduled_task_result':1,
         'guard_child_exit_code':execution.get('exit_code'),
         'archive':'runs/construction_adaptation_20261019/construction-review-a02-evidence.zip',
         'archive_sha256':'1b5a04c81cf897c159f659ef74ea55f0456a8f5ff34af3f5dbc5f9cc27952e90','verified_files':21,
         'limits':execution['limits'],'formal_accepted':False,
         'interpretation':'Camera deadline reached while material compilation was still progressing; no measured GPU/RAM guard violation; underlying camera readiness still unresolved.'}
(root/'docs/development/ugv-ogn/construction-review-failure-20261019.json').write_text(json.dumps(failure,indent=2),encoding='utf-8')
p=json.loads((run/'progress.json').read_text(encoding='utf-8'))
p.update(updated_at=datetime.datetime.now().astimezone().isoformat(),phase='修正地图有限续采；截图首帧失败已归档；S8入口保护已补齐',last_observed_process='construction-groundmap-a02 由有限队列受保护运行；construction-review-a02 已失败退出并清理任务',remote_log='D:/RAVEN-4060/logs/construction-ground-batches-20261019/progress.json')
p['failed_results'].append('construction-review-a02 稳定首帧时限内返回空buffer，601.33s失败，0/56 RGB；峰值11.656GiB，21文件失败包已校验；不放宽时限。')
p['completed_this_window'].append('S8检查入口补充非Retro显式资产要求、已知场景错配/哈希不符拒绝及运行来源sidecar；5项CPU检查通过，AirStack e427fbf3。本项不是新场景真实可见性通过。')
p['next_step']='等待有限续采完成70块并运行原参数后处理；随后核验全图、导出未审核S7候选，并串行做合并网格真实射线/严格Nav2候选。截图重试须依据失败分析和缓存状态，保留原预算。'
(run/'progress.json').write_text(json.dumps(p,ensure_ascii=False,indent=2),encoding='utf-8')
note='2026-10-19 后续更新：ConstructionSite第二次审核渲染仍无目标RGB，601.33s触发稳定首帧失败（非显存保护退出），失败日志已归档；修正地图从20块继续有限串行采样。可见性检查入口已补充跨场景选择/哈希保护，AirStack e427fbf3，5项CPU检查通过；不等于真实S8完成。\n\n'
for relative in ['benchmark/README.md','docs/benchmark_zh.md']:
    path=root/relative;path.write_text(note+path.read_text(encoding='utf-8'),encoding='utf-8')
plan=root/'IMPLEMENTATION_PLAN.md';s=plan.read_text(encoding='utf-8')
anchor='纯CPU检查只验收入口保护，正式S8仍须审核输入和真实PhysX。'
s=s.replace(anchor,anchor+' 实现已本地提交AirStack e427fbf3，4项选择保护及1项既有adapter绑定检查通过；未运行新场景正式S8。')
anchor='两窗口真实 PhysX 对照随后通过；'
s=s.replace(anchor,'第二轮construction-review-a02在601.33s因Camera stable-frame deadline失败，0/56 RGB，峰值11.656GiB；21文件失败包已回传核验，任务结果1，guard未记录子进程exit_code，不臆造该值。两窗口真实 PhysX 对照随后通过；',1)
plan.write_text(s,encoding='utf-8')
tool=root/'AirStack/simulation/isaac-sim/tools/validate_confirmation_visibility_raycast.py'
selection={'scope':'CPU scene selection and provenance implementation; real S8 pending','commit':'e427fbf3','source_sha256':hashlib.sha256(tool.read_bytes()).hexdigest(),'checks_passed':5,'validation_command':'python -m pytest -q AirStack/simulation/isaac-sim/tests/test_visibility_scene_selection.py AirStack/simulation/isaac-sim/tests/test_asset_reports.py -k "visibility_scene_selection or confirmation_visibility_raycast_runner"','exit_code':0,'formal_accepted':False,'protocol_parameters_changed':False,'running_frozen_sources_changed':False}
(root/'docs/development/ugv-ogn/visibility-scene-selection-20261019.json').write_text(json.dumps(selection,indent=2),encoding='utf-8')
print(p['updated_at'])
