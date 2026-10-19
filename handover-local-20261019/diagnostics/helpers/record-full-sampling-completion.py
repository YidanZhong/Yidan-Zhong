from pathlib import Path
import json
root=Path(r'D:\xprogram\RAVEN-AirGround-github')
run=root/'runs/resumable_map_20261018'
snapshot=json.loads((run/'full-map-snapshot.json').read_text(encoding='utf-8-sig'))
check=json.loads((run/'full-map-complete-integrity.json').read_text(encoding='utf-8'))
assert check['status']=='passed' and check['completed_tiles']==527
assert snapshot['execution']['exit_code']==0
plan=root/'IMPLEMENTATION_PLAN.md'
lines=plan.read_text(encoding='utf-8').splitlines()
for i,line in enumerate(lines):
    if '- [ ] Scene1-FullMap-Completion：' in line:
        lines[i]='    - [ ] Scene1-FullMap-Completion：2026-10-19 03:42:04 +08:00 全部 527 块 / 32,235,504 格原始采样完成；a02 退出 0，保留 a01 的 133 块、新增 394 块。全部块合同、SHA-256、8 字段类型/形状/有限值及原 133 块记录检查通过；峰值提交内存 8.356 GiB，单次 GPU 查询故障已恢复。证据 `runs/resumable_map_20261018/full-map-complete-integrity.json` 与 `docs/development/ugv-ogn/resumable-map-20261018.json`。下一步仍须验证磁盘拼接、块缝和全局连通/车体范围后处理及内存峰值，故本项保持未勾选；采样齐全不代表正式地图/GT/episode 批准。进程已退出，计划任务保留为无触发器 Ready。'
        break
else:raise RuntimeError('Plan item missing')
plan.write_text('\n'.join(lines)+'\n',encoding='utf-8')
for path,link in [(root/'benchmark/README.md','../docs/development/ugv-ogn/resumable-map-20261018.json'),
                  (root/'docs/benchmark_zh.md','development/ugv-ogn/resumable-map-20261018.json')]:
    lines=path.read_text(encoding='utf-8').splitlines()
    for i,line in enumerate(lines):
        if line.startswith('> 本机断点采样'):
            lines[i]=f'> 本机全图原始采样完成（2026-10-19 03:42 +08:00）：527/527 块、32,235,504 格，a02 退出 0；保留并验证 a01 的 133 块，新采 394 块。全部块哈希、8 字段类型/形状/有限值及数据合同检查通过；峰值提交内存 8.356 GiB，GPU 查询的一次短暂失败已恢复。当前无采样进程，地图拼接、全局后处理、审核 GT 和正式 episode 仍未完成，不能宣称场景一论文复现完成。见[采样及完整性证据]({link})。'
            break
    else:raise RuntimeError('Status paragraph missing')
    path.write_text('\n'.join(lines)+'\n',encoding='utf-8')
print('Sampling completion recorded; map postprocessing remains pending.')
