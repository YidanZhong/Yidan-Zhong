from pathlib import Path
import json,datetime,hashlib,subprocess
r=Path('D:/xprogram/RAVEN-AirGround-github');run=r/'runs/construction_adaptation_20261019'
pre=json.loads((run/'construction-static-preflight-a02.json').read_text(encoding='utf-8'))
now=datetime.datetime.now().astimezone().isoformat()
e={'updated_at':now,'scope':'ConstructionSite preparation and cross-scene code; runtime acceptance pending',
 'transfer':{'files':332,'sha256':'25f1cbedbb6f322fb89187d3f4a11aff4e3b0d1247f7b439fcff6079105407fc','destination':'D:/RAVEN-4060/assets/handover-scenes-20261019'},
 'static_preflight':{'prims':pre['prim_count'],'meters_per_unit':pre['meters_per_unit'],'up_axis':pre['up_axis'],
 'coordinate_candidates_matched':25,'unbound':3,'all_dependency_scan_passed':False,'unresolved_attribute_count':964,
 'unresolved_attributes':'All observed unresolved asset properties are info:unreal:sourceAsset; not yet a rendered appearance acceptance'},
 'code':['Native review preserves null prims and renders OBB context without approving them.',
 'Native terrain metadata/contract/postprocess take scene_id and target hashes; new snapshot cannot resume legacy contract.',
 'Native small-window footprint validation now explicitly uses 0.05 m max step, matching full-map postprocessing.',
 'ROI scene path/name and CUDA target identity gate follow target manifest; default resolution 0.05 m; server memory guard unchanged.',
 'Shared raycast generator accepts explicit scene_id/scene_usd; non-Retro missing asset argument rejected before runtime import.',
 'Navigation map comparison uses scene-specific paper classes and rejects mixed scene metadata; Retro 31 gate retained.'],
 'validation':{'wsl_scene1_env':'58 passed, cpu-tests-scene1-env.log','review_boundary_unittest':'3 passed','tile_stitch_unittest':'3 passed',
 'earlier_environment_failures':'Windows Anaconda lacked pxr and lightweight namespace lacked resource spec; WSL raven-core lacked pxr (4 failed/53 passed/1 skipped). Full rerun in existing raven-scene1 passed.',
 'live_map_sampling':'prepared, not started while GPU review runs','formal_container_runtime':'not executed on 32GB hardware; unchanged 64GiB preflight'},
 'air_stack_local_commit':subprocess.check_output(['git','-C',str(r/'AirStack'),'rev-parse','HEAD'],text=True).strip(),
 'remote_publication':'not performed; local work and evidence only',
 'human_verified':0,'formal_episodes':0,'new_scene_formal_acceptance':False,
 'source_sha256':{str(p.relative_to(r)):hashlib.sha256(p.read_bytes()).hexdigest() for p in
 [r/'scripts/run_roi_analysis.py',r/'scripts/probe_windows_scene_render.py',r/'scripts/probe_tiled_terrain.py',r/'scripts/probe_resumable_terrain.py',r/'scripts/postprocess_terrain_tiles.py',r/'benchmark/airground_benchmark/navigation_map_validation.py']}}
(r/'docs/development/ugv-ogn/construction-adaptation-20261019.json').write_text(json.dumps(e,ensure_ascii=False,indent=2),encoding='utf-8')
p=r/'IMPLEMENTATION_PLAN.md';t=p.read_text(encoding='utf-8');marker='下一有界阶段：ConstructionSite'
if 'S0/runtime 本轮代码' not in t:
 t=t.replace('  - [x] 资产准备：','  - S0/runtime 本轮代码（2026-10-19）：原生分块/后处理及地图比较已参数化 scene_id/目标哈希/论文类别；正式 ROI 默认 0.05 m、动态文件名/路径和精确目标身份校验，共享 AirGround raycast 接收显式资产。Retro 31 目标与所有资源门保留。58 项 CPU 回归通过；原生新场景 PhysX/双机器人实测尚未完成，不勾选 S0/runtime。证据 `docs/development/ugv-ogn/construction-adaptation-20261019.json`。\n  - [x] 资产准备：',1)
p.write_text(t,encoding='utf-8')
for name in ['benchmark/README.md','docs/benchmark_zh.md']:
 p=r/name;t=p.read_text(encoding='utf-8');p.write_text('> 2026-10-19 ConstructionSite：332 文件已复制到第二台隔离目录并逐文件验证；25 个候选坐标匹配、3 个未绑定，尚无人工批准。场景路径/metadata/论文类别参数化的 58 项 CPU 测试通过；首次真实渲染正在受保护批次中，结果以运行证据为准。见 `construction-adaptation-20261019.json` 与唯一计划。\n\n'+t,encoding='utf-8')
p=r/'runs/autonomous_handover_20261019/progress.json';s=json.loads(p.read_text(encoding='utf-8'));s.update(updated_at=now,phase='ConstructionSite 首次渲染与S0参数化',last_observed_process='construction-review-a01 仍在受保护材质编译；最近观测740 s，无图像。840 s总时限，未同时运行其他仿真。',remote_log='D:/RAVEN-4060/logs/construction-review-a01/',next_step='先归档本批渲染结果，之后运行已准备的两块真实PhysX对照；人工绑定仅记录不批准。');s['completed_this_window']+=['ConstructionSite 332文件传输校验、25候选坐标核对、tarp实例代理材质候选','跨场景代码参数化，58项CPU测试通过；3项审核边界与3项拼接保护检查通过'];p.write_text(json.dumps(s,ensure_ascii=False,indent=2),encoding='utf-8')
print('Checkpoint written',now)
