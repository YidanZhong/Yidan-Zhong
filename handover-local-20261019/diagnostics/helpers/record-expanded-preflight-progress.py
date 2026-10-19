from pathlib import Path
import datetime,hashlib,json
root=Path('D:/xprogram/RAVEN-AirGround-github');run=root/'runs/autonomous_handover_20261019'
p=json.loads((run/'progress.json').read_text(encoding='utf-8'))
p.update(updated_at=datetime.datetime.now().astimezone().isoformat(),phase='修正地图第三批续采；六场景几何与S8路径契约准备完成')
p['last_observed_process']='construction-groundmap-a03 受有限队列保护运行；已确认58/70块（14:31快照）'
p['completed_this_window'].extend(['六个不完整资产包的全网格CPU读取审计完成：四场景无读取错误，DowntownWest28空mesh、SnowyVillage197缺失资产；五场景原始路径候选/建议已输出但未应用，45文件归档校验。','S8显式路径映射在Retro165/ConstructionSite25/Factory1目标上验证世界矩阵/包围盒不变；7项CPU检查通过，本地提交250474bc。原GT和所有非路径字段不变，不代表真实PhysX验收。'])
p['findings'].append('S8现有代码按目标中心计算1.5–8m，handover明确到达集按OBB表面；35个大尺寸论文标注的必要距离条件不相容，未改参数或排除目标，待确认老师采用的可见性口径。ConstructionSite无此尺寸必要条件冲突，可继续其诊断。')
(run/'progress.json').write_text(json.dumps(p,ensure_ascii=False,indent=2),encoding='utf-8')
human_path=run/'human-inputs.json';human=json.loads(human_path.read_text(encoding='utf-8'))
human.append({'scene':'AbandonedCity/AbandonedFactory/MilitaryBase/Shipyard/SnowyVillage：大尺寸实例','status':'待协议口径确认，未排除任何目标','problem':'共35个当前未审核论文目标：到OBB表面≥1.5m时，到中心的理论最小距离已经>8m；现有可见性代码按中心距离≤8m，handover对可见性距离未明确参考点。','evidence':'runs/additional_scene_preflight_20261019/visibility-distance-compatibility.json','request':'请确认老师S8使用中心距离还是OBB表面距离，或提供已验证的可见性校验器版本/命令。保持当前阈值不变，不自动把这些目标设为不可达或排除。','owner':'老师/协议维护者','blocks':'这些实例的正式S8判断；不阻塞地图、未审核候选及ConstructionSite等无该必要条件冲突的诊断。'})
human_path.write_text(json.dumps(human,ensure_ascii=False,indent=2),encoding='utf-8')
doc=root/'docs/development/ugv-ogn/visibility-scene-selection-20261019.json';d=json.loads(doc.read_text());source=root/'AirStack/simulation/isaac-sim/tools/validate_confirmation_visibility_raycast.py'
d.update(commit='250474bc',source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),checks_passed=7,reference_projection='explicit opt-in, source default prim to chosen mount; in-memory paths only',projection_evidence='runs/additional_scene_preflight_20261019/reference-projection-check.json',runtime_execution='not yet performed for this shared launcher tool')
doc.write_text(json.dumps(d,indent=2),encoding='utf-8')
note='补充预检（2026-10-19）：六个不完整场景根USD的全网格CPU审计和五场景原始路径候选已归档；DowntownWest28空mesh、SnowyVillage197缺失引用须补资料。S8路径选择/显式引用映射7项CPU检查通过（250474bc），191条路径世界几何一致，正式S8尚未运行。另有35个大尺寸标注的中心/表面距离口径冲突待协议确认；未改阈值或排除实例。\n\n'
for relative in ['benchmark/README.md','docs/benchmark_zh.md']:
    file=root/relative;file.write_text(note+file.read_text(encoding='utf-8'),encoding='utf-8')
plan=root/'IMPLEMENTATION_PLAN.md';s=plan.read_text(encoding='utf-8');s=s.replace('下一步提供显式reference-root映射，只在内存中投影目标路径，同时校验源/运行时世界矩阵及包围盒一致，保存映射来源；','显式reference-root映射已实现，仅在内存投影路径；世界矩阵/包围盒及原GT非路径字段检查通过，共191条路径，7项CPU检查通过，提交250474bc；真实共享启动器尚待验证。')
needle='占位 `visible_fraction=1` 不算验证。';s=s.replace(needle,needle+' 原代码可见性距离按中心算，handover可达性明确按OBB表面算：35个大尺寸未审核论文目标在两种窗口下无交集的必要条件已记录，见visibility-distance-compatibility.json。等待协议确认，不改阈值、不排除目标；ConstructionSite无该尺寸必要条件冲突。')
plan.write_text(s,encoding='utf-8')
print(p['updated_at'])
