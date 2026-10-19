from pathlib import Path
import json
root=Path(r'D:\xprogram\RAVEN-AirGround-github')
e=json.loads((root/'docs/development/ugv-ogn/resumable-map-20261018.json').read_text(encoding='utf-8'))
assert e['implementation_and_launch_passed'] and e['visual_qa']!='pending'
snp=e['full_job_snapshot'];p=snp['progress']
assert p['completed_tiles']>0 and snp['task_state']=='Running' and snp['processes'] and snp['execution'] is None
plan=root/'IMPLEMENTATION_PLAN.md';s=plan.read_text(encoding='utf-8')
old=next(l for l in s.splitlines() if '- [ ] Scene1-ResumableMap-Launch' in l)
new=f"    - [x] Scene1-ResumableMap-Launch（2026-10-18）：`resumable_terrain_store.py` / `probe_resumable_terrain.py` 实现原子 NPZ+完成记录、哈希/形状/有限性/参数与源码校验、OS 写锁、磁盘 8 GiB 预留、批次数/时长预算及恢复进度；由 `probe_tiled_terrain.py` 复用已验收真实 PhysX 配置。`resume-test-a01` 保存 2 块退出 0，独立 `resume-test-a02` 校验跳过 2 块并新采 7 块退出 0，首次 2 块记录/哈希不变；25,600 格 × 8 原始字段与此前实际整块参考完全一致。`python -m unittest discover -s tests -p test_resumable_terrain_store.py -v` 6 项通过（持久化失败检查，不冒充真实 PhysX）。命令/退出结果与数据 `runs/resumable_map_20261018/`，证据 `docs/development/ugv-ogn/resumable-map-20261018.json`。已启动第二台 `full-map-a01` 全图后台诊断，{snp['observed_at']} 快照 {p['completed_tiles']}/{p['total_tiles']} 块、{p['completed_cells']:,}/{p['total_cells']:,} 格；不是完成结论。守护进程保持 14 GiB 内存/60% CPU/物理内存 4 GiB/提交 2 GiB/GPU 80% 门限，总时限 8 h、采样预算 7.5 h，逐块保存，临时防自动休眠后恢复；正式服务器 64 GiB 门未改。恢复测试计划任务已移除，全图任务仍在运行，配置结束后移除自身注册。当前仅验收恢复和启动，未完成全图后处理、人工 GT 审核或正式 episode。"
future="    - [ ] Scene1-FullMap-Completion：跟踪 `full-map-a01` 的实际退出和 527 块完整性；若受时限/资源保护中断则校验后续跑；完成后验证磁盘拼接、块缝和全局连通/车体范围后处理及内存峰值。不得把采样齐全当作正式地图/GT/episode 批准。"
plan.write_text(s.replace(old,new+'\n'+future),encoding='utf-8')
for rel,link in [('benchmark/README.md','../docs/development/ugv-ogn/resumable-map-20261018.json'),('docs/benchmark_zh.md','development/ugv-ogn/resumable-map-20261018.json')]:
    path=root/rel;txt=path.read_text(encoding='utf-8');head,body=txt.split('\n',1)
    block=f"> 本机断点采样（2026-10-18）：两个独立 Isaac 4.5 进程完成 2 块保存 → 跳过 2 块并续算 7 块；25,600 格 × 8 原始字段与真实整块参考完全一致，6 项持久化检查通过。全图 `full-map-a01` 已启动，{snp['observed_at']} 快照 {p['completed_tiles']}/{p['total_tiles']} 块，仍在运行；总时限 8 h，采样预算 7.5 h，14 GiB 内存保护不变。此项只验收恢复及启动，全图后处理、审核 GT 与正式 episode 未完成。见[恢复及采样启动证据]({link})。"
    path.write_text(head+'\n\n'+block+'\n'+body,encoding='utf-8')
path=root/'docs/development/ugv-ogn/README.md';s=path.read_text(encoding='utf-8')
old=next(l for l in s.splitlines() if '| `tiled-map-validation-20261018.json`' in l)
path.write_text(s.replace(old,old+'\n| `resumable-map-20261018.json` | 两次独立真实进程的断点续跑验证、6 项持久化检查及全图后台采样启动快照；非完成结论 |'),encoding='utf-8')
print('Plan and docs synchronized; full-map completion remains unchecked.')
