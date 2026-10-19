from pathlib import Path
import json,datetime
root=Path('D:/xprogram/RAVEN-AirGround-github');run=root/'runs/autonomous_handover_20261019';read=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
s=read(run/'progress.json');old=read(root/'runs/construction_adaptation_20261019/baseline36-evidence/logs/construction-full-map-20261019/progress.json')
s.update(updated_at=datetime.datetime.now().astimezone().isoformat(),phase='ConstructionSite地形碰撞修正已验证，新配置从零采图',last_observed_process='construction-groundmap-a01 正在受保护运行；旧配置队列已停止且旧批次退出0',remote_log='D:/RAVEN-4060/logs/construction-groundmap-a01/',construction_map=read(run/'construction-ground-map-latest.json'),old_collision_baseline=old,next_step='新配置首批完成后尝试ConstructionSite审核图的同预算热缓存重跑，再启动有限续采/后处理；Nav2严格到达候选随后有界验证。',screenshots_entry='../construction_adaptation_20261019/teacher-report/查看进展.html')
s['completed_this_window'] += ['ConstructionSite两地形修正真实A/B通过：142.69s退出0、峰值6.129GiB；厕所窗口footprint 0→16219，空地14字段不变；旧36块原始数据110文件已备份，未混用。AirStack本地提交dca38441。','AbandonedFactory 199资产隔离传输校验，11目标22视角准备；10个原始未绑定实例面级候选完成，未做语义归属或GT批准。','S7候选31000个采样点经独立标量OBB距离公式核对通过；3项真实输入保护检查拒绝旧输出、目标哈希不符及metadata平移。']
s['findings'] += ['ConstructionSite地形分类修正已有真实证据，当前障碍不再仅是待验证推测；新全图仍在采样，原36/70基线不计入新图进度。','AbandonedFactory Ground.mdl仅绑定不可见且无碰撞辅助平面；依赖缺失仍记录，但不作为当前几何诊断硬阻塞。']
(run/'progress.json').write_text(json.dumps(s,ensure_ascii=False,indent=2),encoding='utf-8')
human=read(run/'human-inputs.json')
for row in human:
 if row['scene']=='AbandonedFactory' and 'Ground.mdl' in row['problem']:
  row.update(status='待资料完整性补充，非当前几何诊断硬阻塞',problem='Ground.mdl真实缺失，但只绑定/World/Environment/ground：invisible、无碰撞；实际可见工厂材质未因该项证明缺失。',request='如有完整原包可补齐该文件；当前先做有界渲染/几何诊断，不需要因此等待老师。',blocks='完整依赖打包审计；不阻塞目前的几何诊断，真实渲染仍需验证。',evidence='runs/additional_scene_preflight_20261019/AbandonedFactory-ground-material-usage.json')
if not any(r['scene']=='ConstructionSite高度策略' for r in human):
 human.append({'scene':'ConstructionSite高度策略','status':'待视觉对齐需求确认，不阻塞按handover继续','problem':'两处已测视觉地形z=-0.3m，强制支持平面z=0；错误凸分解已修正，视觉高差仍客观存在。','evidence':'docs/development/ugv-ogn/construction-ground-fix-20261019.json','request':'最终视觉要求若必须贴地，请确认老师基准是否同样使用z=0支撑、是否另有坐标校正/资产版本；当前不擅自整体平移场景。','owner':'用户/老师','blocks':'视觉地面对齐方案；不阻塞原坐标、z=0契约的未审核地图和运行诊断。'})
(run/'human-inputs.json').write_text(json.dumps(human,ensure_ascii=False,indent=2),encoding='utf-8')
evidence=read(root/'docs/development/ugv-ogn/construction-ground-fix-20261019.json');evidence.update(airstack_commit='dca38441',baseline_archive_sha256='0b53ad743fb178040f2851fece5d9e59d77c9f3d7a0ae76e089e4fdf725b20f7',baseline_raw_tiles_backed_up=36,new_contract_sha256='659129eb5189aeeaab7e7525956ce76c409a5215aae2f3359be5785069a749cd')
(root/'docs/development/ugv-ogn/construction-ground-fix-20261019.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2),encoding='utf-8')
factory={'scope':'isolated assets and unreviewed geometry preparation','transfer':read(root/'runs/factory_adaptation_20261019/factory-transfer-verification.json'),'review_input':{'targets':11,'views':22,'unbound':10,'status':'prepared_not_rendered'},'faces':read(root/'runs/factory_adaptation_20261019/face-candidate-summary.json'),'material_usage':read(root/'runs/additional_scene_preflight_20261019/AbandonedFactory-ground-material-usage.json'),'formal_accepted':False}
(root/'docs/development/ugv-ogn/factory-adaptation-20261019.json').write_text(json.dumps(factory,ensure_ascii=False,indent=2),encoding='utf-8')
for path in [root/'benchmark/README.md',root/'docs/benchmark_zh.md']:
 text=path.read_text(encoding='utf-8');text=''.join(line for line in text.splitlines(keepends=True) if not line.startswith('ConstructionSite 地形诊断（2026-10-19）：'))
 note='ConstructionSite 地形修正（2026-10-19）：真实A/B退出0，只有两地形碰撞近似改变；厕所窗口footprint 0→16219格，空地14字段不变，z=0支持及原USD/GT坐标保留。AirStack dca38441。旧36块已备份并停止续采，新contract 659129eb…下重新采图。S7 Retro31目标未审核逐实例候选及31000点独立距离检查通过，不是正式GT。AbandonedFactory199资产已传输校验；缺失Ground.mdl仅绑定不可见辅助平面，不再作为几何诊断阻塞。详见 construction-ground-fix / factory-adaptation / unreviewed-arrival-candidates-20261019.json。\n\n'
 path.write_text(note+text.lstrip('\n'),encoding='utf-8')
print(s['updated_at'],s['construction_map']['completed_tiles'],'new-profile tiles')
