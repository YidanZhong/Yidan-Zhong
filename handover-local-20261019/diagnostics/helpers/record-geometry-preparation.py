from pathlib import Path
import datetime,hashlib,json
root=Path('D:/xprogram/RAVEN-AirGround-github');run=root/'runs/autonomous_handover_20261019'
p=json.loads((run/'progress.json').read_text(encoding='utf-8'))
p.update(updated_at=datetime.datetime.now().astimezone().isoformat(),phase='新碰撞配置地图20/70已归档，ConstructionSite审核渲染有界重试',last_observed_process='construction-review-a02 正在受保护运行，仍在材质编译；UI启动截图不计作目标RGB',remote_log='D:/RAVEN-4060/logs/construction-review-a02/')
p['construction_map']=json.loads((root/'runs/construction_adaptation_20261019/corrected-map20-evidence/logs/construction-ground-map-20261019/progress.json').read_text())
p['completed_this_window']=[item for item in p['completed_this_window'] if '候选尚未真实运行' not in item]
p['completed_this_window'].append('修正配置首批20/70、1268736格/28.86%，752.49s退出0/峰值6.102GiB；完整20块与76个文件已回传逐文件校验，SHA003d511f…。')
p['completed_this_window'].append('FireAcademy/AbandonedFactory源三角形3点基线完成；不制造目标绑定的独立几何锚点PhysX诊断已准备，尚未执行。')
p['findings']=[s for s in p['findings'] if '当前正在完成的是原碰撞基线' not in s and '需全图与碰撞来源诊断' not in s]
p['findings'].append('离线发现FireAcademy 1个、AbandonedFactory 16个大型复杂网格使用convexDecomposition；仅风险提示，尚无这两场景真实碰撞错误证据。')
(run/'progress.json').write_text(json.dumps(p,ensure_ascii=False,indent=2),encoding='utf-8')
evidence={'scope':'offline preparation only, not actual PhysX/semantic approval','formal_accepted':False,'scenes':{}}
for scene in ['FireAcademy','AbandonedFactory']:
    risk=root/f'runs/additional_scene_preflight_20261019/{scene}-collision-risk.json'
    baseline=root/f'runs/additional_scene_preflight_20261019/{scene}-source-ray-baseline.json'
    r=json.loads(risk.read_text());b=json.loads(baseline.read_text())
    evidence['scenes'][scene]={'large_complex_candidates':sum(m['wide_complex_convex_candidate'] for m in r['meshes']),
      'risk_file':str(risk.relative_to(root)),'risk_sha256':hashlib.sha256(risk.read_bytes()).hexdigest(),
      'baseline_file':str(baseline.relative_to(root)),'baseline_sha256':hashlib.sha256(baseline.read_bytes()).hexdigest(),
      'scene_sha256':b['scene_sha256'],'points':b['points'],'limitations':['Prototype library excluded; actual instance placement not inferred','Polygon fan triangulation; no full-scene equality claim','Ray jobs prepared but not run; target manifests unchanged']}
(root/'docs/development/ugv-ogn/merged-mesh-collision-preflight-20261019.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2),encoding='utf-8')
note='ConstructionSite 修正配置采样更新：首批20/70块（28.86%）已正常结束，76文件完整断点包逐一SHA核验。原碰撞基线36块单独保留，不计入新图。FireAcademy/AbandonedFactory大型合并网格离线风险与三点源表面交点已记录；真实射线比较尚未运行，不据此修改碰撞或批准GT。证据 merged-mesh-collision-preflight-20261019.json。\n\n'
for relative in ['benchmark/README.md','docs/benchmark_zh.md']:
    path=root/relative;text=path.read_text(encoding='utf-8');path.write_text(note+text,encoding='utf-8')
plan=root/'IMPLEMENTATION_PLAN.md';text=plan.read_text(encoding='utf-8');needle='首批groundmap-a01已启动，未宣称全图完成。'
assert needle in text;text=text.replace(needle,'首批groundmap-a01已退出0/752.49s/峰值6.102GiB，20/70块、1,268,736格/28.86%；76文件完整原始断点包回传核验通过，SHA003d511f3d79ea4ed5ccbb83d6e27cecb3368c5b1dfa1c27d47ec065bb80a582。全图尚未完成。')
plan.write_text(text,encoding='utf-8')
print(p['updated_at'])
