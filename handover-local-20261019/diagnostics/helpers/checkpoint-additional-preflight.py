from pathlib import Path
from collections import Counter
import json,hashlib,datetime
root=Path('D:/xprogram/RAVEN-AirGround-github');run=root/'runs/additional_scene_preflight_20261019'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
summary={'scope':'read-only offline USD 0.26.8 audit in isolated main-PC WSL; not Isaac 4.5 rendering/PhysX acceptance','updated_at':datetime.datetime.now().astimezone().isoformat(),'scenes':{},'formal_accepted':False}
for name in ['AbandonedFactory','FireAcademy']:
 p=run/(name+'.json');d=json.loads(p.read_text(encoding='utf-8'))
 summary['scenes'][name]={'prims':d['prim_count'],'source_scene_sha256':d['scene_sha256'],'coordinate_candidate_status':dict(Counter(x['status'] for x in d['targets'])),'unresolved_attributes':dict(Counter(x['attribute'] for x in d['unresolved_asset_attributes'])),'report':str(p.relative_to(root)).replace('\\','/'),'report_sha256':sha(p),'process_exit_code':int((run/(name+'.exit.txt')).read_text()),'real_rendering_verified':False}
summary['scenes']['AbandonedFactory']['missing_runtime_asset']='SubUSDs/materials/Ground.mdl, /World/Environment/Looks/Ground/Shader.info:mdl:sourceAsset'
summary['scenes']['FireAcademy']['runtime_material_check']='OmniPBR.mdl exists in installed Isaac 4.5 kit/mdl/core/Base (15,591 bytes); offline pxr-only resolution does not include MDL search paths. Actual material render still pending.'
summary['scenes']['FireAcademy']['review_preparation']='13 unbound original annotations, 26 camera views prepared. No merged mesh was assigned to an individual target.'
doc=root/'docs/development/ugv-ogn/additional-scene-preflight-20261019.json'
doc.write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
plan=root/'IMPLEMENTATION_PLAN.md';s=plan.read_text(encoding='utf-8')
line='  - 其他场景独立预检（2026-10-19）：AbandonedFactory 1,643 prim，1候选坐标一致/10未绑定；确认为真实 MDL 缺失的仅 `Ground.mdl`，另348项为 Unreal 来源元数据。FireAcademy 198 prim/13未绑定，离线未解析的 `OmniPBR.mdl` 已确认存在于 Isaac 4.5 内置 MDL 目录，尚未做真实材质渲染。已准备13目标/26视角上下文清单并传输377个 FireAcademy 原始资产到隔离副本（校验完成前不称可运行）。两份只读 pxr 预检 exit 2 如实保留，不冒充通过；证据 `docs/development/ugv-ogn/additional-scene-preflight-20261019.json`。\n'
if line not in s:s=s.replace('  - [ ] S4：',line+'  - [ ] S4：',1)
plan.write_text(s,encoding='utf-8')
p=root/'runs/autonomous_handover_20261019/human-inputs.json';items=json.loads(p.read_text(encoding='utf-8'))
for item in items:
 if item['scene']=='AbandonedFactory':item['evidence']='runs/additional_scene_preflight_20261019/AbandonedFactory.json；/World/Environment/Looks/Ground/Shader 引用 ./SubUSDs/materials/Ground.mdl'
if not any(i['scene']=='Shipyard' and 'ship silo' in i['problem'] for i in items):
 items.append({'scene':'Shipyard','status':'待任务原文解释确认','problem':"Table A.3 的 Type II 查询写为 ship silo，没有逗号；当前代码保留原文并暂解释为 ship + silo，尚未协议审核。",'evidence':'benchmark/airground_benchmark/scenes.py / SCENE_REVIEW_NOTES','request':'确认该查询是否指 ship 和 silo 两类目标，提供老师采用的任务定义或论文补充说明。','owner':'用户/老师','blocks':'相应任务的正式 catalog 与 episode 验收；不阻塞资产与地图诊断。'})
p.write_text(json.dumps(items,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
for p in [root/'benchmark/README.md',root/'docs/benchmark_zh.md']:
 s=p.read_text(encoding='utf-8');line='其他场景预检（2026-10-19）：AbandonedFactory 的 `Ground.mdl` 缺失已定位到材质属性；FireAcademy 的 OmniPBR 为 Isaac 内置材质，离线未解析不等于外部缺文件。实例审核与正式验收仍未完成。\n\n'
 if line not in s:p.write_text(line+s,encoding='utf-8')
p=root/'docs/development/ugv-ogn/README.md';s=p.read_text(encoding='utf-8');line='[其他场景离线依赖与坐标预检](additional-scene-preflight-20261019.json)。'
if line not in s:p.write_text(s+'\n'+line+'\n',encoding='utf-8')
print('Recorded offline failures, actual missing material, built-in material distinction and pending task wording.')
