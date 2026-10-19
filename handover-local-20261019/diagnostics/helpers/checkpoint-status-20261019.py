from pathlib import Path
from collections import Counter
import json,hashlib,datetime
root=Path('D:/xprogram/RAVEN-AirGround-github');run=root/'runs/autonomous_handover_20261019'
now=datetime.datetime.now().astimezone().isoformat()
snapshot=json.loads((run/'handover-status-20261019-0533.json').read_text(encoding='utf-8-sig'))
progress=snapshot['map_progress'];execution=snapshot['execution']
face_path=root/'runs/fireacademy_adaptation_20261019/face-candidates-a02/report.json'
face=json.loads(face_path.read_text(encoding='utf-8'))
assert len(face['meshes'])==2 and not face['formal_accepted']
f=root/'docs/development/ugv-ogn/additional-scene-preflight-20261019.json'
d=json.loads(f.read_text(encoding='utf-8'));d['updated_at']=now
d['scenes']['FireAcademy'].update(transfer=snapshot['fireacademy'],face_diagnostic={
 'report':'runs/fireacademy_adaptation_20261019/face-candidates-a02/report.json',
 'sha256':hashlib.sha256(face_path.read_bytes()).hexdigest(),'geometry_root':'/World/stage',
 'main_mesh_faces':face['meshes'][0]['faces'],'annotations_with_geometric_candidates':13,
 'unit_tests':'2 geometry boundary/rotation checks passed','process_exit_code':0,
 'earlier_attempt':'First audit included default environment helpers; retained separately. a02 explicitly restricts scene geometry root.',
 'human_ownership_approved':False})
f.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
f=root/'docs/development/ugv-ogn/construction-adaptation-20261019.json';d=json.loads(f.read_text(encoding='utf-8'));d['updated_at']=now
d['first_full_map_batch']={'progress':progress,'exit_code':execution['exit_code'],'elapsed_s':execution['elapsed_s'],'peak_job_commit_gib':execution['peak_job_commit_gib'],'archive_sha256':'593f2a624246461e14af5aa9dbc44270087aa22530d50d0a01a91a5fb77c4364','archive_files_verified':31,'raw_tile_store':'D:/RAVEN-4060/logs/construction-full-map-20261019','full_map_complete':False}
d['validation']['live_map_sampling']='first bounded batch completed normally; 19/70 tiles, 1224192/4395972 cells (27.85%); resumable, not currently sampling'
d['two_window_physx']['observed_limitation']='biotoilet_context has zero footprint-traversable cells; equivalence pass is not navigation suitability. Preserve current geometry/thresholds pending full-map diagnosis.'
f.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
f=root/'IMPLEMENTATION_PLAN.md';s=f.read_text(encoding='utf-8')
s=s.replace('全图 4,395,972 格/70 块的首批断点采样已启动，未完成。','全图 4,395,972 格/70 块首批已正常结束，保存19块/1,224,192格（27.85%），全图未完成。')
s=s.replace('`construction-map-a01` 已启动，最多20新块/900 s采样、14 GiB/1200 s总保护；','`construction-map-a01` 已正常退出0，19/70块（27.85%）、990.27 s、峰值6.185 GiB；保持最多20新块/900 s采样、14 GiB/1200 s总保护，原始断点保存于第二台 `logs/construction-full-map-20261019`；')
s=s.replace('并传输377个 FireAcademy 原始资产到隔离副本（校验完成前不称可运行）','并完成377个 FireAcademy 原始资产到隔离副本的传输/CRC/SHA逐文件校验（不等于渲染通过）')
s=s.replace('  - S2–S3 下一独立准备：FireAcademy 合并 mesh 的原标注 OBB 面级候选清单（面中心/全顶点包含、材质子集及哈希），保留边界不确定性；只辅助人工归属审核，不写入 usd_prim_path 或 verified。',
 '  - S2–S3 面级候选诊断（2026-10-19）：`audit_annotation_mesh_faces.py` 在 `/World/stage` 范围审计 FireAcademy 3,966,071面主体及96面圆柱；13个原标注均得到几何候选，保存OBB局部AABB粗筛/顶点均值包含/全顶点包含面ID与材质子集、USD/源码哈希。旋转/跨边界2项测试通过，实际只读诊断exit0。初版包含默认环境辅助mesh，保留后以显式场景根复跑a02；输出 `runs/fireacademy_adaptation_20261019/face-candidates-a02/`。不证明语义归属，不写入绑定或verified，仍需真实图像和人工审核。')
s=s.replace('只在 ConstructionSite GPU 批次之间单独运行，单次成功仍不记作稳定性通过。','只在 ConstructionSite GPU 批次之间单独运行，单次成功仍不记作稳定性通过。2026-10-19 11:59 已启动 `full-nav-dwb-a01`（14GiB/1200s保护），待实际结果。')
f.write_text(s,encoding='utf-8')
for f in [root/'benchmark/README.md',root/'docs/benchmark_zh.md']:
 s=f.read_text(encoding='utf-8')
 s=s.replace('首批全图采样已启动（未完成）','首批全图采样正常退出，19/70块/27.85%（全图未完成）')
 note='FireAcademy 准备更新：377个原始文件已传输并逐项校验；13个标注获得合并网格的面级几何候选，尚未审核语义归属、未修改绑定。\n\n'
 if note not in s:s=note+s
 f.write_text(s,encoding='utf-8')
f=run/'progress.json';s=json.loads(f.read_text(encoding='utf-8'))
s.update(updated_at=now,phase='场景一 DWB 末端收敛对照已启动，ConstructionSite首批已结束',
 last_observed_process='full-nav-dwb-a01 计划任务已启动；具体进程状态另见最新运行快照',
 remote_log='D:/RAVEN-4060/logs/full-nav-dwb-a01/',
 next_step='完成原目标/朝向/容差/120s预算DWB对照；随后续采ConstructionSite剩余51块，并进行一次原840s预算缓存渲染重试。')
s['construction_map']=progress
s['completed_this_window']+=['ConstructionSite首批19/70块、1,224,192格、27.85%，990.27秒退出0并保存断点',
 'FireAcademy 377文件传输/哈希校验完成；13目标面级几何候选和26视角清单已准备，全部待审核']
s['findings'].append('ConstructionSite厕所局部窗口的footprint可通行格为0；需全图与碰撞来源诊断，不能因分块一致性通过就宣称可导航。')
f.write_text(json.dumps(s,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('Saved completed batch, additional scene preparation, and next running diagnostic without changing formal acceptance counts.')
