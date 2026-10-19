from pathlib import Path
import datetime,hashlib,json
root=Path('D:/xprogram/RAVEN-AirGround-github');run=root/'runs/construction_adaptation_20261019'
audit=json.loads((run/'instance-collider-audit.json').read_text());check=json.loads((run/'instance-expansion-check.json').read_text())
record={'status':'invalidated_for_navigation_or_acceptance','time':datetime.datetime.now().astimezone().isoformat(),
 'contract_sha256':'659129eb5189aeeaab7e7525956ce76c409a5215aae2f3359be5785069a749cd',
 'reason':'5075 visible instance-proxy meshes have no runtime collider; current recursive GetChildren preparation skips instance descendants.',
 'evidence':'runs/construction_adaptation_20261019/instance-collider-audit.json',
 'original_artifacts':'Preserved without rewriting. This additive sidecar marks invalidity discovered after completed sampling.',
 'required_next_step':'Verify in-memory instance expansion with real PhysX, then use a new scene contract and resample; regenerate candidates/visibility after new map.',
 'formal_accepted':False}
for folder in [run/'corrected-map70-evidence/logs/construction-groundpost-a01-frames',root/'runs/arrival_candidates_20261019/ConstructionSite-a01']:
 with (folder/'INVALIDATED.json').open('x',encoding='utf-8') as f:json.dump(record,f,ensure_ascii=False,indent=2)
doc={'scope':'actual-runtime collider manifest plus full source geometry audit','invalidation':record,
 'mesh_count':audit['mesh_count'],'proxy_mesh_count':audit['instance_proxy_meshes'],'missing_visible_colliders':audit['visible_meshes_missing_runtime_colliders'],
 'bound_targets_without_colliders':[r['instance_id'] for r in audit['target_rows'] if r['mesh_count'] and not r['runtime_colliders']],
 'offline_expansion':{k:v for k,v in check.items() if k!='expansion'},'expanded_roots':len(check['expansion']['changed_roots']),
 'evidence_sha256':{name:hashlib.sha256((run/name).read_bytes()).hexdigest() for name in ['instance-collider-audit.json','instance-expansion-check.json']},
 'real_expanded_PhysX':'construction-instances-a01 running; not yet validated'}
(root/'docs/development/ugv-ogn/construction-instance-colliders-20261019.json').write_text(json.dumps(doc,ensure_ascii=False,indent=2),encoding='utf-8')
p=root/'docs/development/ugv-ogn/construction-full-map-20261019.json';d=json.loads(p.read_text());d['later_invalidation']=record;d['navigation_eligible']=False;p.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
p=root/'runs/autonomous_handover_20261019/progress.json';d=json.loads(p.read_text(encoding='utf-8'));d.update(updated_at=record['time'],phase='ConstructionSite实例碰撞缺失修正；旧完整诊断图已标记失效',last_observed_process='construction-instances-a01 已启动，14GiB/840s保护下核验实例碰撞补全',remote_log='D:/RAVEN-4060/logs/construction-instances-a01/execution.json')
d['construction_map']['later_invalidation']=record;d['construction_map']['navigation_eligible']=False
d['findings'].append('ConstructionSite 5075个可见实例代理网格缺运行时碰撞，旧70块图/S7候选不可用于后续导航验收，已添加INVALIDATED侧文件；原数据保留。展开实例的CPU核验5759网格几何/世界变换/可见性字节一致，269MiB峰值，真实碰撞预检进行中。')
d['failed_results'].append('construction-visibility-a05：25次render调用只产生23个实际PhysX步、0.092s，实际步数检查拒绝；378.11s失败，峰值10.886GiB。SDK初始化时render调用与物理步并非一一对应；保留证据，不放宽5帧门。')
d['next_step']='核验展开实例后的真实碰撞/资源占用；通过后做窗口对照、新契约全图重采。FireAcademy大窗口、Factory基线和严格Nav2候选仍可独立串行推进；旧Construction图仅保留诊断基线。'
p.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
p=root/'IMPLEMENTATION_PLAN.md';s=p.read_text(encoding='utf-8');needle='  - [ ] S5碰撞覆盖审计：';lines=s.splitlines();i=next(i for i,x in enumerate(lines) if x.startswith(needle));lines[i]='  - [ ] S5碰撞覆盖修正：已确认ConstructionSite 5,075个可见实例代理网格缺运行时碰撞（总网格5,759）；旧70块全图/S7候选已加INVALIDATED侧文件，不能用于导航/验收，须新契约重采。内存展开5,075实例后全部网格几何/变换/可见性字节一致，原USD未变、CPU峰值269MiB；真实PhysX有界预检进行中。见 `construction-instance-colliders-20261019.json`。'
p.write_text('\n'.join(lines)+'\n',encoding='utf-8')
note='重要更正（2026-10-19）：ConstructionSite旧70块完整诊断图发现5,075个可见实例代理网格缺碰撞，地图与S7候选已标记失效，不可用于后续导航或正式验收。原文件保留；内存展开CPU几何不变核验已通过，需真实碰撞预检和新契约重采。见 `docs/development/ugv-ogn/construction-instance-colliders-20261019.json`。\n\n'
for rel in ['benchmark/README.md','docs/benchmark_zh.md']:
 p=root/rel;p.write_text(note+p.read_text(encoding='utf-8'),encoding='utf-8')
p=root/'docs/development/ugv-ogn/README.md';p.write_text(p.read_text(encoding='utf-8')+'\n- [ConstructionSite实例碰撞覆盖与旧图失效](construction-instance-colliders-20261019.json)：5,075代理网格缺碰撞，需补全重采。\n',encoding='utf-8')
p=run/'teacher-report/完整诊断图.html';s=p.read_text(encoding='utf-8');banner='<div style="background:#ffe2df;border:3px solid #b12818;padding:18px"><strong>后续检查发现：此图已失效，不能用于导航或验收。</strong> 5,075个可见实例代理网格缺碰撞；下图仅保留原采样证据。修正后需重新采图。</div>';s=s.replace('<h1>',banner+'<h1>',1);p.write_text(s,encoding='utf-8')
print('Invalidation saved without changing archived evidence bytes')
