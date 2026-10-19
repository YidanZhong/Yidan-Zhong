from pathlib import Path
import datetime,json,hashlib
root=Path('D:/xprogram/RAVEN-AirGround-github');run=root/'runs/construction_adaptation_20261019';docs=root/'docs/development/ugv-ogn'
doc=docs/'construction-instance-colliders-20261019.json';d=json.loads(doc.read_text(encoding='utf-8'))
d['a01_failure']={'reason':'Expansion alone leaves 3853 uncategorized +15 visual-only paths without collision; guard refuses 3868 missing visible meshes',
 'wall_s':103.59,'peak_commit_gib':5.937744140625,'archive_sha256':'b53575f49b2a952299bafc7e49e6194eed565c4173b1e1fb73464811a05abd5f','verified_files':24}
d['a02_candidate']={'donor_matching':'All 5075 proxy meshes match an existing collidable donor by exact vertices/topology bytes; no ambiguous geometry profile matches.',
 'source_property_matching':'Strict source-property matching had zero matches because export flattened prototypes into distinct authored properties; geometry matching is an explicitly separate evidence level.',
 'profile_overrides':34,'profile_policy':'Use donor collision role for all matched instances, including 34 RoadBlock/Fence name disagreements; physics material and approximation use same override.',
 'cpu_check':json.loads((run/'instance-seeding-check.json').read_text()),'runtime':'construction-instances-a02 currently running; source hash guard passed after excluding generated Python bytecode from source manifest'}
d['s7_invalidated_input_guard']={'result':'Rejected invalidated ConstructionSite map with ValueError before writing output','unwanted_output_created':False}
doc.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
pre=root/'runs/additional_scene_preflight_20261019';frames=pre/'factory-a01-evidence/logs/factory-geometry-a01-frames';audit=json.loads((frames/'raw-ray-audit.json').read_text());source=json.loads((pre/'AbandonedFactory-source-ray-baseline.json').read_text());rows=[]
for actual,expected in zip(audit['points'],source['points']):
 hits=[h for h in actual['down_hits'] if h['prim_path']=='/World/stage/AbandonedFactory/MergedMeshes/merged_38'];original=next(h['z_m'] for h in expected['source_hits'] if h['prim']=='/World/stage/AbandonedFactory/MergedMeshes/merged_38');assert actual['xy_m']==expected['xy_m']
 rows.append({'xy_m':actual['xy_m'],'source_mesh_z_m':original,'convex_collision_z_m':[h['position_xyz_m'][2] for h in hits]})
result={'scope':'actual PhysX baseline vs readonly source surface, not GT acceptance','scene_id':'AbandonedFactory','rows':rows,
 'archive_sha256':'82a9a2b4186cb7abf8fb255305e26ef073980f952288ceed3d43e73d74b10aa3','verified_files':38,
 'execution':json.loads((pre/'factory-a01-evidence/logs/factory-geometry-a01/execution.json').read_text()),
 'next_candidate':'Only merged_38 -> static triangle collision, queries bothSides=True; other colliders unchanged; prepared not started',
 'limitations':['Three points only; the other 15 large convex meshes remain separate risks.','No asset, human GT flag, map protocol parameter, or acceptance criterion changed.']}
(docs/'factory-collision-20261019.json').write_text(json.dumps(result,indent=2))
p=root/'runs/autonomous_handover_20261019/progress.json';s=json.loads(p.read_text(encoding='utf-8'));s.update(updated_at=datetime.datetime.now().astimezone().isoformat(),last_observed_process='construction-instances-a02 已启动；CPU精确几何原型补全覆盖5757网格，真实烹制/射线仍待完成',remote_log='D:/RAVEN-4060/logs/construction-instances-a02/execution.json')
s['completed_this_window'].append('四个完整导出资产的实例覆盖交叉审计：Retro/FireAcademy/Factory没有ConstructionSite这种缺碰撞实例代理；Retro原生4280网格/4278带CollisionAPI，既有Retro地图未因本问题失效。Factory真实基线247.44s退出0，峰值6.727GiB，38文件核验，merged_38三点凸体高度严重偏离源面。')
s['failed_results'].append('construction-instances-a01：仅展开实例仍有3868未分类/visual-only网格缺碰撞，103.59s停止，24文件已核验；追加精确几何原型碰撞继承候选，未放宽覆盖门。')
s['reader_summary']=['正式完成的后续场景仍为0；没有把未审核GT、诊断地图或单次导航写成论文验收。','ConstructionSite旧完整图发现5075实例代理缺碰撞，已标记失效。精确几何原型补全CPU检查通过，正在做真实预检，随后必须重采地图。','FireAcademy静态三角碰撞局部对照已恢复源面；双面查询找回漏检，但第二轮退出异常，更大窗口验证待运行。','AbandonedFactory真实基线证实合并地面凸体高度失真，局部三角碰撞修正已准备。','场景一原预算三轮导航9/9 action成功，但严格位姿7/9；严格收敛候选仍待实测。','人工目标审核、缺失资产和35个大目标距离口径问题仍待处理，已记录在下方台账。']
p.write_text(json.dumps(s,ensure_ascii=False,indent=2),encoding='utf-8')
note='碰撞覆盖补充（2026-10-19）：ConstructionSite已准备精确几何原型继承方案，CPU核验5757场景网格均有碰撞、34处名称角色冲突按原型处理；真实预检待完成。Retro/FireAcademy/Factory未发现同类实例代理漏碰撞。Factory真实三点基线证实merged_38凸体高度偏离源表面，修正对照已准备。详见construction-instance-colliders和factory-collision两份证据。\n\n'
for rel in ['benchmark/README.md','docs/benchmark_zh.md']:
 p=root/rel;p.write_text(note+p.read_text(encoding='utf-8'),encoding='utf-8')
p=docs/'README.md';p.write_text(p.read_text(encoding='utf-8')+'\n- [Factory合并地面碰撞基线](factory-collision-20261019.json)：三点源面/真实凸体差异，修正候选待实测。\n',encoding='utf-8')
