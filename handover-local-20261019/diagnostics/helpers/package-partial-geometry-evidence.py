from pathlib import Path
import collections,datetime,hashlib,html,json,shutil,zipfile
root=Path('D:/xprogram/RAVEN-AirGround-github');run=root/'runs/partial_scene_geometry_20261019';cache=root.parent/'.raven-setup-cache'
source=run/'source';source.mkdir(exist_ok=False)
for name in ['audit-partial-scene-geometry.py','run-partial-geometry-audits.py','inspect-partial-geometry-gaps.py','export-partial-source-candidates.py','run-partial-source-candidates.py']:
    shutil.copy2(cache/name,source/name)
shutil.copy2(root/'AirStack/simulation/isaac-sim/tools/export_target_prim_candidates.py',source/'export_target_prim_candidates.py')
shutil.copy2(root/'benchmark/airground_benchmark/scenes.py',source/'scene-definitions.py')
rows=[]
for job in json.loads((run/'progress.json').read_text())['rows']:
    scene=job['scene'];data=json.loads((run/(scene+'.json')).read_text());candidate=run/(scene+'-source-candidates/summary.json')
    proposal=json.loads(candidate.read_text()) if candidate.exists() else None
    rows.append({'scene':scene,'geometry_exit_code':job['exit_code'],'valid_meshes':data['mesh_count_read'],'mesh_read_errors':len(data['mesh_errors']),
                 'composition_errors':len(data['composition_errors']),'faces':data['face_count'],'max_rss_mib':data['peak_rss_mib'],
                 'scene_sha256':data['scene_sha256'],'targets':len(data['target_aabb_candidates']),
                 'raw_source_candidate_count':proposal['candidate_count'] if proposal else 0,
                 'proposed_bindings_not_applied':proposal['proposed_count'] if proposal else 0,
                 'ambiguous_proposals':proposal['ambiguous_count'] if proposal else 0})
snow=json.loads((run/'SnowyVillage.json').read_text());references=collections.Counter(e.split('@')[1] for e in snow['composition_errors'] if '@' in e)
(run/'SnowyVillage-missing-references.json').write_text(json.dumps({'scope':'deduplicated missing composition references from local root USD','occurrences':len(snow['composition_errors']),'unique_assets':len(references),'references':[{'path':k,'occurrences':v} for k,v in sorted(references.items())]},indent=2))
summary={'scope':'offline incomplete-asset geometry and raw-source proposals; no formal scene acceptance','rows':rows,'snowy_missing_unique_assets':len(references),'formal_accepted':False,'original_assets_and_targets_unchanged':True,'new_approved_bindings':0,'limitations':['pxr 0.26.8 on main WSL; not proof of Isaac 4.5 runtime compatibility','AABB/name matching is tentative; raw paths require runtime remount verification','Missing textures/materials and DowntownWest empty mesh declarations remain unresolved','SnowyVillage has no resolved meshes; no geometry-only map can be claimed from its root file']}
(run/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
body=''.join('<tr>'+''.join('<td>'+html.escape(str(r[k]))+'</td>' for k in ['scene','valid_meshes','mesh_read_errors','composition_errors','raw_source_candidate_count','proposed_bindings_not_applied','ambiguous_proposals'])+'</tr>' for r in rows)
page='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>不完整资产包：几何审计</title><style>body{max-width:1150px;margin:32px auto;font:16px/1.7 system-ui;color:#182538}td,th{padding:12px;border:1px solid #bbb}table{border-collapse:collapse}strong{color:#a54d00}</style><h1>六个不完整资产包的几何审计</h1><p><strong>只有CPU只读诊断，没有真实RGB、PhysX、正式绑定或场景验收。</strong>原USD、标注和审核位均未修改。</p><table><tr><th>场景</th><th>可读取网格</th><th>网格异常</th><th>组合引用错误</th><th>名称候选</th><th>未应用绑定建议</th><th>有歧义建议</th></tr>'''+body+'''</table><p>名称候选包含不同层级、子网格和粗匹配，不能按候选数量计算实例数量。路径为原始USD路径，尚未验证运行时挂载。</p><p>DowntownWest 的28个mesh声明缺少points、面数和索引；不是只缺贴图。SnowyVillage发生745条组合引用错误，未读到有效mesh。</p><p>请提供缺失依赖和与论文对应的完整导出版本。其余四个场景虽可读取现有几何，仍不能证明完整依赖或显卡运行能力。</p><p><a href="summary.json">详细结果与资产哈希</a> · <a href="geometry-gap-detail.json">空网格详情</a> · <a href="SnowyVillage-missing-references.json">SnowyVillage缺失引用清单</a></p></html>'''
(run/'查看几何预检.html').write_text(page,encoding='utf-8')
files=[p for p in run.rglob('*') if p.is_file() and p.name!='evidence.zip']
hashes={p.relative_to(run).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
with zipfile.ZipFile(run/'evidence.zip','x',zipfile.ZIP_DEFLATED,6) as z:
    for p in files:z.write(p,p.relative_to(run).as_posix())
    z.writestr('sha256.json',json.dumps(hashes,indent=2))
with zipfile.ZipFile(run/'evidence.zip') as z:
    assert z.testzip() is None
    for name,digest in hashes.items():assert hashlib.sha256(z.read(name)).hexdigest()==digest
summary['archive_sha256']=hashlib.sha256((run/'evidence.zip').read_bytes()).hexdigest();summary['archived_files']=len(hashes);summary['evidence_dir']=str(run.relative_to(root))
(root/'docs/development/ugv-ogn/partial-scene-geometry-20261019.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
human_path=root/'runs/autonomous_handover_20261019/human-inputs.json';human=json.loads(human_path.read_text(encoding='utf-8'))
for item in human:
    if item['scene']=='SnowyVillage' and item['status']=='待人工/外部资料':
        item.update(problem=f'根USD可打开，但745条组合引用报错涉及{len(references)}个缺失资产，未读取到有效网格。',evidence='runs/partial_scene_geometry_20261019/SnowyVillage-missing-references.json',request='提供Library/Stages/SnowyVillage下完整Props及其依赖，或同版本完整离线资产包。')
    if item['scene']=='DowntownWest' and item['status']=='待人工/外部资料':
        item.update(problem='6026个mesh可读取；另28个mesh声明没有顶点/面数/索引，涉及wood_fence_playground、ground_mod_tile_a24、两个灯光StaticMesh等。材质依赖也未补齐。',evidence='runs/partial_scene_geometry_20261019/geometry-gap-detail.json',request='提供论文版本完整场景导出，确认这些空mesh是否有意保留；若需碰撞，提供实际几何，不能只补材质。')
human_path.write_text(json.dumps(human,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'scenes':len(rows),'files':len(hashes),'archive_sha256':summary['archive_sha256'],'snowy_unique_missing':len(references)}))
