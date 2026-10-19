from pathlib import Path
import hashlib,json
root=Path('D:/xprogram/RAVEN-AirGround-github');run=root/'runs/additional_scene_preflight_20261019'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
baseline=run/'fireacademy-a01-evidence/logs/fireacademy-geometry-a01-frames'
candidate=run/'fireacademy-triangle-a01-evidence/logs/fireacademy-triangle-a01-frames'
source=json.loads((run/'FireAcademy-source-ray-baseline.json').read_text())
old=json.loads((baseline/'raw-ray-audit.json').read_text());new=json.loads((candidate/'raw-ray-audit.json').read_text());rows=[]
for src,b,a in zip(source['points'],old['points'],new['points']):
 assert src['xy_m']==b['xy_m']==a['xy_m']
 source_z=next(h['z_m'] for h in src['source_hits'] if h['prim']=='/World/stage/Ds/Ds_001')
 hits=[h for h in a['down_hits'] if h['prim_path']=='/World/stage/Ds/Ds_001'];assert len(hits)==1
 actual=hits[0]['position_xyz_m'][2];error=abs(actual-max(source_z));assert error<1e-4
 rows.append({'xy_m':a['xy_m'],'source_surface_z_m':source_z,'baseline_inside_hits':sum(h['distance_m']==0 for h in b['down_hits']+b['absolute_obstacle_band_up_hits']),
              'triangle_down_z_m':actual,'top_surface_error_m':error,'triangle_up_hits':a['absolute_obstacle_band_up_hits']})
colliders_old=json.loads((baseline/'colliders.json').read_text());colliders_new=json.loads((candidate/'colliders.json').read_text())
changes=[{'before':b,'after':a} for b,a in zip(colliders_old,colliders_new) if b!=a];assert len(changes)==1
result={'scope':'actual PhysX local collision comparison, not full map or GT acceptance','scene_id':'FireAcademy','checks_passed':True,
 'baseline_archive_sha256':'d729e482264dfcf0744b69c6430d41875358d41414709cde627937c9460f3eed',
 'candidate_archive_sha256':'0037af0b578af362390f47462d65d569ea74552564280724a2b8716342c72545',
 'verified_files_each':38,'source_baseline_sha256':sha(run/'FireAcademy-source-ray-baseline.json'),'rows':rows,'collider_changes':changes,
 'candidate_execution':json.loads((run/'fireacademy-triangle-a01-evidence/logs/fireacademy-triangle-a01/execution.json').read_text()),
 'limitations':['Only three sparse points and 12 grid cells tested; no full traversability or navigation.',
 'The upward 0.05–1m ray misses a source face at z=0.872m. SDK raycast_all defaults bothSides=False; a separate two-sided query A/B is prepared before wider mapping.',
 'Static triangle mode is isolated in memory. No asset or target flags changed; no production profile rollout.']}
(root/'docs/development/ugv-ogn/fireacademy-collision-20261019.json').write_text(json.dumps(result,indent=2))
post=root/'runs/construction_adaptation_20261019/corrected-map70-evidence/logs/construction-groundpost-a01-frames'
r=json.loads((post/'report.json').read_text());checks=[]
for name in ['footprint','reach','selected']:
 f=post/name/(name+'.unreviewed.yaml');data=f.read_bytes();declared=r['selected_nav2']['yaml_sha256'] if name=='selected' else r['exports'][name]['nav2']['yaml_sha256']
 assert hashlib.sha256(data.replace(b'\r\n',b'\n')).hexdigest()==declared
 assert sha(f)==r['files'][name+'/'+f.name]['sha256']
 checks.append({'file':name+'/'+f.name,'declared_lf_sha256':declared,'actual_crlf_sha256':sha(f),'archive_integrity_passed':True})
record={'scope':'Windows newline serialization integrity correction; grid parameters unchanged','before':'Windows real-file regression 1 failed/1 passed: YAML text LF digest differed from written CRLF bytes','after':'2 Windows tests and 2 Linux tests passed; deterministic UTF-8 LF byte serialization','checks':checks,'existing_outputs':'preserved; archive manifests pin actual bytes',
        'source_sha256':sha(root/'benchmark/airground_benchmark/traversability.py')}
(root/'docs/development/ugv-ogn/nav2-yaml-integrity-20261019.json').write_text(json.dumps(record,indent=2))
p=root/'docs/development/ugv-ogn/construction-full-map-20261019.json';d=json.loads(p.read_text());d['limitations']=[x for x in d['limitations'] if not x.startswith('Nested export')]+['Nested export YAML digest hashes LF text while Windows wrote CRLF; final bytes remain pinned by report.files and archive manifest. See nav2-yaml-integrity-20261019.json.'];p.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
p=root/'IMPLEMENTATION_PLAN.md';s=p.read_text(encoding='utf-8');s=s.replace('- [ ] S6导出完整性：修复Windows文本换行转换导致Nav2 YAML声明SHA与实际文件不一致的问题，使用确定的UTF-8字节写入并核验；不改地图参数、不覆盖已有证据包。','- [x] S6导出完整性：Windows实文件回归已重现CRLF导致YAML声明SHA不符；改为确定UTF-8 LF字节写入，Windows/Linux各2项检查通过。现有3份图的实际SHA均与归档manifest一致，原包保留；详见 `nav2-yaml-integrity-20261019.json`。不代表地图正式审核完成。')
s=s.replace('通过之前不扩散到正式运行时或其他场景。','三个向下命中已与源面一致（误差<1e-4m），仅一个碰撞体变化；140.56s退出0、峰值8.122GiB，38文件归档核验。仍需双面射线排查向上射线漏检0.872m表面及更大窗口验证，不扩散到正式运行时或其他场景。')
p.write_text(s,encoding='utf-8')
note='新增局部实测与导出修复：FireAcademy三角碰撞A/B已使三点向下命中恢复源几何高度；向上背面射线漏检仍待单独验证，尚无全图。Nav2 YAML的Windows CRLF哈希不符已用确定UTF-8 LF写入修复，Windows/Linux各2项回归通过；原证据包及参数不变。证据 `fireacademy-collision-20261019.json` / `nav2-yaml-integrity-20261019.json`。\n\n'
for rel in ['benchmark/README.md','docs/benchmark_zh.md']:
 p=root/rel;p.write_text(note+p.read_text(encoding='utf-8'),encoding='utf-8')
p=root/'docs/development/ugv-ogn/README.md';p.write_text(p.read_text(encoding='utf-8')+'\n- [FireAcademy碰撞A/B](fireacademy-collision-20261019.json)：三点真实对照及双面射线剩余问题。\n- [Windows Nav2 YAML完整性](nav2-yaml-integrity-20261019.json)：实文件回归与跨系统修复。\n- [ConstructionSite可见性时序诊断](construction-visibility-timing-20261019.json)：保留失败证据与定位过程。\n',encoding='utf-8')
print('Recorded triangle A/B and Windows byte-level integrity regression')
