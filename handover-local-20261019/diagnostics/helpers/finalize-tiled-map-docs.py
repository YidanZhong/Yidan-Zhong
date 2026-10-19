from pathlib import Path
import json
root=Path(r'D:\xprogram\RAVEN-AirGround-github')
e=json.loads((root/'docs/development/ugv-ogn/tiled-map-validation-20261018.json').read_text(encoding='utf-8'))
assert e['passed'] and e['visual_qa']!='pending'
r=e['execution'];c=e['comparison']
summary=f"两个 8×8 m 区域 / 0.05 m 分辨率 / {e['reference_cells']:,} 个参考网格，真实 PhysX 射线 {e['actual_rays']:,} 次；整块与带一圈 halo 的分块地形、全窗口 seed/footprint/reach 连通结果超差值 {sum(x['outside_tolerance'] for x in c)}，块缝超差值 {sum(x['seam_mismatch_values'] for x in c)}"
p=root/'IMPLEMENTATION_PLAN.md';s=p.read_text(encoding='utf-8')
old=next(l for l in s.splitlines() if '- [ ] Scene1-TiledMap-Validation' in l)
new=f"    - [x] Scene1-TiledMap-Validation（2026-10-18）：{summary}。原生 Windows Isaac 4.5 使用现有 profiled collider、z=0 无限支持平面和 terrain 算法，源码哈希锁定；红车在独立未审核副本中改绑整车根，实际 USD 包围盒核对通过，165 条标注仅该 prim 路径变化，原 OBB 不变。源码 `scripts/probe_tiled_terrain.py` 和 `scripts/probe_windows_scene_render.py`；py_compile、真实数组比较、离线有限性/哈希/目标 schema/副本差异/ZIP CRC/报告链接检查通过。命令和退出 0 见 `runs/tiled_map_validation_20261018/{e['job']}/execution.json`；耗时 {r['elapsed_s']:.2f} s，峰值提交内存 {r['peak_job_commit_gib']:.3f} GiB / 显存约 {e['peak_gpu_gib']:.3f} GiB，14 GiB 进程保护保持，临时任务已清理。证据 `docs/development/ugv-ogn/tiled-map-validation-20261018.json`、图文包 `runs/tiled_map_validation_20261018/teacher-report.zip`。只证明两个窗口的分块一致性；未实测全图峰值内存、未与老师地图比对，正式 64 GiB 入口保护未修改；人工 GT 审核仍 0/31、正式地图/到达集/episode 未完成。下一阶段为可断点续跑的全图诊断生成与全局后处理验证。"
p.write_text(s.replace(old,new),encoding='utf-8')
for rel,link in [('benchmark/README.md','../docs/development/ugv-ogn/tiled-map-validation-20261018.json'),('docs/benchmark_zh.md','development/ugv-ogn/tiled-map-validation-20261018.json')]:
    p=root/rel;s=p.read_text(encoding='utf-8');head,body=s.split('\n',1)
    block=f"> 本机分块验证（2026-10-18）：{summary}。红车整车根绑定已写入独立未审核副本，原标注框不变；所有目标仍未获人工批准。真实运行退出 0，峰值提交内存 {r['peak_job_commit_gib']:.3f} GiB，资源保护与 64 GiB 正式入口门禁未放宽。小范围结果不能替代全图、老师地图对比或正式 episode；下一步仍需全图诊断生成和审核。见[分块地图验证证据]({link})。"
    p.write_text(head+'\n\n'+block+'\n'+body,encoding='utf-8')
p=root/'docs/development/ugv-ogn/README.md';s=p.read_text(encoding='utf-8')
old=next(l for l in s.splitlines() if '| `paper31-review-20261018.json`' in l)
p.write_text(s.replace(old,old+'\n| `tiled-map-validation-20261018.json` | 两个真实 PhysX 小区域的整块/分块等价对比、halo 块缝与连通性验证；红车绑定独立副本修正；未生成正式全图 |'),encoding='utf-8')
print('Plan and documentation synchronized.')
