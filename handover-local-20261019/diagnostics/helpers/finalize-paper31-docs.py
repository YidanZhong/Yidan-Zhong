from pathlib import Path
import json
root=Path(r'D:\xprogram\RAVEN-AirGround-github')
e=json.loads((root/'docs/development/ugv-ogn/paper31-review-20261018.json').read_text(encoding='utf-8'))
r=e['resources'];run='runs/paper31_review_20261018/'
p=root/'IMPLEMENTATION_PLAN.md';s=p.read_text(encoding='utf-8')
old=next(l for l in s.splitlines() if '- [ ] Scene1-Paper31-ReviewPacket' in l)
new=f'    - [x] Scene1-Paper31-ReviewPacket（2026-10-18）：`paper31-review-a01` 在受控原生 Isaac 4.5 中完成 31 个论文实例 / 8 类 / 62 张双视角原始 RGB，实际 USD 候选包围盒 31/31 与导出候选一致；每图连续 60 个有效缓冲帧。已生成可切换红色标注 OBB / 青色候选世界 AABB 的 HTML、XY 位置图、候选层级列表、空白审核 CSV 与待批准台账模板。24 个目标有绑定歧义；重点标出红车误绑 Object_9 零件（体积比 0.204，建议整车根，未应用）和黄车范围差异（3.293）。源码 `scripts/probe_windows_scene_render.py`；py_compile、62 图像完整性/哈希及 31 组包围盒核对通过，原生命令 `{run}paper31-review-a01/execution.json`，退出 0；峰值提交内存 {r["peak_job_commit_gib"]:.3f} GiB / 显存约 {r["peak_gpu_gib"]:.2f} GiB，限额保持，临时任务已清理，未启动 ROS/WSL 或新增网络规则。证据 `docs/development/ugv-ogn/paper31-review-20261018.json`，展示包 `{run}teacher-report.zip`，视觉抽查范围和遮挡限制见证据。全部 165 OBB + 2 m 的 0.05 m ROI 为 4137×7792 = 32,235,504 格；现有 `run_roi_analysis.py:host_sample` 要求 available RAM≥64 GiB，本机总内存 32 GB 不满足，正式入口与保护条件未修改；分块原生生成方案尚待实测。本项仅完成审核材料：人工审核仍 0/31、正式地图/到达集/episode 均未完成，不关闭 S4–S10。'
s=s.replace(old,new);p.write_text(s,encoding='utf-8')
for rel,link in [('benchmark/README.md','../docs/development/ugv-ogn/paper31-review-20261018.json'),('docs/benchmark_zh.md','development/ugv-ogn/paper31-review-20261018.json')]:
 p=root/rel;s=p.read_text(encoding='utf-8');head,body=s.split('\n',1)
 block=f'> 全部论文目标审核材料（2026-10-18）：已用原生 Isaac 4.5 渲染 31 实例 / 8 类 / 62 张双视角原始 RGB，生成标注框、实际候选包围盒、XY 位置和空白审核台账；31 组候选包围盒与静态导出一致，图像完整性与哈希核对通过。24 个绑定有歧义，红车 Object_9 零件误绑和黄车范围差异已重点标注，修正方案尚未应用；人工审核仍为 0/31。运行退出 0，峰值提交内存 {r["peak_job_commit_gib"]:.3f} GiB / 显存约 {r["peak_gpu_gib"]:.2f} GiB，临时资源已清理。正式 0.05 m 全图 ROI 为 32,235,504 格；既有入口的 64 GiB 可用内存门与本机 32 GB 不兼容，门禁未放宽，分块生成仍待实测。正式地图、到达集与论文 episode 尚未生成。见[目标审核包证据]({link})。'
 p.write_text(head+'\n\n'+block+'\n'+body,encoding='utf-8')
p=root/'docs/development/ugv-ogn/README.md';s=p.read_text(encoding='utf-8')
old=next(l for l in s.splitlines() if '| `target-integration-20261018.json`' in l)
s=s.replace(old,old+'\n| `paper31-review-20261018.json` | 全部 31 论文目标的 62 张真实双视角 RGB、24 个歧义、标注/候选框与待审表；全图 ROI 和本机 64 GiB 入口限制；未批准 GT |')
p.write_text(s,encoding='utf-8')
print('Plan and documentation synchronized.')
