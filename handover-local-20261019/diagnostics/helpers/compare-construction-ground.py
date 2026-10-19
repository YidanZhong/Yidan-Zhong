from pathlib import Path
import json,hashlib,sys,html,zipfile
sys.path.insert(0,'D:/xprogram/.raven-setup-cache/plot-tools')
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
root=Path('D:/xprogram/RAVEN-AirGround-github');run=root/'runs/construction_adaptation_20261019'
old=run/'tile-validation-evidence';new=run/'ground-v2-evidence/logs/construction-ground-a01-frames'
read=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
before=read(old/'tile-validation.json');after=read(new/'tile-validation.json');execution=read(new.parent/'construction-ground-a01/execution.json')
assert before['passed'] and after['passed'] and execution['exit_code']==0
oc={x['path']:x for x in read(old/'colliders.json')};nc={x['path']:x for x in read(new/'colliders.json')};assert oc.keys()==nc.keys()
changed=[{'path':p,'before':oc[p],'after':nc[p]} for p in oc if oc[p]!=nc[p]]
assert {x['path'] for x in changed}=={'/World/stage/ConstructionSite/Land/Landscape/Landscape_0','/World/stage/ConstructionSite/Land/Landscape2/Landscape2'}
assert all(x['before']['enabled']==x['after']['enabled']==True and x['before']['approximation']=='convexDecomposition' and x['after']['approximation']=='meshSimplification' for x in changed)
assert before['setup']['support_plane']==after['setup']['support_plane']
with zipfile.ZipFile(run/'construction-tiles-a01-evidence.zip') as archive:
 oldconfig_bytes=archive.read('setup/construction-tiles-v1/tile-input.json')
 assert hashlib.sha256(oldconfig_bytes).hexdigest()==before['config_sha256']
 oldconfig=json.loads(oldconfig_bytes)
newconfig=read(run/'ground-v2-evidence/setup/construction-ground-v2/ground-input.json')
assert oldconfig['scene_sha256']==newconfig['scene_sha256'] and oldconfig['targets_sha256']==newconfig['targets_sha256']
assert oldconfig['windows']==newconfig['windows']
assert [p for p in oldconfig['source_sha256'] if oldconfig['source_sha256'][p]!=newconfig['source_sha256'][p]]==['AirStack/simulation/isaac-sim/utils/scene_audit.py']
assert before['terrain_config']==after['terrain_config']
assert before['setup']['physics_profile']['physx_scene_attrs']==after['setup']['physics_profile']['physx_scene_attrs']
windows=[];fig,axes=plt.subplots(2,4,figsize=(14,7),layout='constrained')
for i in (0,1):
 with np.load(old/f'window-{i}-reference.npz') as a,np.load(new/f'window-{i}-reference.npz') as b:
  diffs={k:int(np.count_nonzero(a[k]!=b[k])) for k in a.files}
  if i==0:assert not any(diffs.values()),diffs
  windows.append({'name':before['windows'][i]['name'],'changed_values_by_field':diffs,'before_footprint_cells':int(a['footprint_mask'].sum()),'after_footprint_cells':int(b['footprint_mask'].sum()),'before_obstacle_cells':int(a['obstacle_mask'].sum()),'after_obstacle_cells':int(b['obstacle_mask'].sum())})
  for j,(label,grid) in enumerate([('Old obstacle',a['obstacle_mask']),('New obstacle',b['obstacle_mask']),('Old footprint',a['footprint_mask']),('New footprint',b['footprint_mask'])]):
   axes[i,j].imshow(grid,origin='lower',cmap='gray',vmin=0,vmax=1);axes[i,j].set_title(windows[-1]['name']+'\n'+label);axes[i,j].set_xlabel('0.05 m grid columns');axes[i,j].set_ylabel('rows')
assert windows[1]['before_footprint_cells']==0 and windows[1]['after_footprint_cells']>0
raw=read(new/'raw-ray-audit.json')
for point in raw['points'][:2]:
 hits=[h for h in point['down_hits'] if '/Land/Landscape2/' in h['prim_path']]
 assert len(hits)==1 and abs(hits[0]['position_xyz_m'][2]+.3)<1e-5 and not point['absolute_obstacle_band_up_hits']
out=run/'teacher-report';out.mkdir(exist_ok=True);fig.savefig(out/'ground-collision-comparison.png',dpi=150)
result={'scope':'actual PhysX collision-profile A/B; not human GT or complete scene acceptance','status':'passed_bounded_ground_profile_comparison','execution':execution,'changed_colliders':changed,'source_scene_sha256':oldconfig['scene_sha256'],'targets_sha256':oldconfig['targets_sha256'],'raw_assets_changed':False,'support_plane_unchanged':True,'terrain_parameters_unchanged':True,'windows':windows,'real_ray_matches_source_triangles':True,'archive_sha256':'cff78d7ef5123a1a3147a6c8daf93efd7c7b55a4f6c746a0567fd0000a3bf0c0','formal_gt_approved':False,'limitations':['Only two 8x8m windows and three ray points; new full map must be sampled.','No target binding/OBB approval; all remain unreviewed.','At measured points visual ground is -.3m while mandatory support plane remains0.','This is an actual-data plot, not camera RGB or robot navigation evidence.']}
(root/'docs/development/ugv-ogn/construction-ground-fix-20261019.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');(out/'ground-evidence.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
result.update(contact_material_note='The two meshes also switch from the existing obstacle contact material to the existing ground contact material as part of the profile; physical constants were not retuned.',physics_profile_before=before['setup']['physics_profile'],physics_profile_after=after['setup']['physics_profile'],airstack_commit='dca38441',baseline_archive_sha256='0b53ad743fb178040f2851fece5d9e59d77c9f3d7a0ae76e089e4fdf725b20f7',baseline_raw_tiles_backed_up=36,new_contract_sha256='659129eb5189aeeaab7e7525956ce76c409a5215aae2f3359be5785069a749cd')
for path in (root/'docs/development/ugv-ogn/construction-ground-fix-20261019.json',out/'ground-evidence.json'):
 path.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
rows=''.join(f'<tr><td>{html.escape(w["name"])}</td><td>{w["before_obstacle_cells"]} → {w["after_obstacle_cells"]}</td><td>{w["before_footprint_cells"]} → {w["after_footprint_cells"]}</td></tr>' for w in windows)
(out/'查看进展.html').write_text('<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>ConstructionSite 地形碰撞对照</title><style>body{max-width:1200px;margin:35px auto;font:17px/1.8 system-ui;padding:20px}img{width:100%}td,th{border:1px solid #bbb;padding:10px}table{border-collapse:collapse}</style><h1>ConstructionSite 地形碰撞修正对照</h1><p>原规则把两块地形当作障碍做凸分解，填平了凹地形；仅将这两块已核查的地形改为 ground 的网格简化碰撞。原始USD、目标坐标、z=0支持平面及采样参数不变。</p><p>真实PhysX射线已从错误的z=1.211m恢复到与源三角形一致的z=-0.3m，0.05–1m障碍带的虚假命中消失。两个窗口的整块与分块比较均通过，原空地窗口所有字段保持一致。</p><table><tr><th>8×8m窗口</th><th>障碍格：修正前→后</th><th>footprint可通行格：修正前→后</th></tr>'+rows+'</table><img src="ground-collision-comparison.png"><p>图中白色为对应mask的真值；这是实际射线数据图，非相机截图。</p><p><strong>仍未完成：</strong>新配置完整地图、人工目标审核、真实可见性、正式episode与UGV巡游。旧配置36块基线已完整备份，不与新图混用。两处视觉地面仍比z=0支持平面低0.3m，未通过移动资产或机器人掩盖。</p><a href="ground-evidence.json">真实命令、参数、退出码与原始证据索引</a></html>',encoding='utf-8')
print(json.dumps(windows,indent=2))
page=out/'查看进展.html';page.write_text(page.read_text(encoding='utf-8').replace('原始USD、目标坐标、z=0支持平面及采样参数不变。','这两块地形同时按既有ground规则绑定地面接触材质；没有重新调节物理常量。原始USD、目标坐标、z=0支持平面及采样参数不变。'),encoding='utf-8')
