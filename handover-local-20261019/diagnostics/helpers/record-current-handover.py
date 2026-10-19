from pathlib import Path
import json,datetime
root=Path('D:/xprogram/RAVEN-AirGround-github');run=root/'runs/autonomous_handover_20261019'
p=run/'progress.json';s=json.loads(p.read_text(encoding='utf-8'))
s.update(updated_at=datetime.datetime.now().astimezone().isoformat(),phase='ConstructionSite有限队列续采；地形碰撞修正候选和S7诊断准备',last_observed_process='ConstructionBatches有限队列正在运行construction-map-a02；已验证跳过原19块，逐块保存新数据',remote_log='D:/RAVEN-4060/logs/construction-batches-20261019/progress.json',next_step='完成原碰撞基线图后，在独立源码副本验证ConstructionSite地形分类修正；新碰撞配置必须重新采图。随后继续审核出图与未审核到达集。')
s['construction_map']=json.loads((run/'construction-map-latest.json').read_text())
s['completed_this_window'] += [
 'DWB三轮有界复测及完整归档完成：9/9 action成功，但第三轮前两目标回报位姿超出0.25m，严格7/9、整轮2/3，未通过稳定性；ROS临时规则/任务/专用WSL已清理。',
 'ConstructionSite真实射线与源三角形对照，发现地形被凸分解填平凹处；原始证据32文件逐一哈希核验。',
 '只针对两块地形的ground分类候选已准备，3项CPU回归通过，包括原Retro完整场景审计；候选尚未真实运行。',
 'S7未审核几何工具已在Retro全图完成31个论文目标的完整逐实例候选导出，469261个重叠格保留；不修改GT，不冒充正式arrival_regions。']
s['findings']=[x for x in s['findings'] if x!='原三目标/朝向/容差/120 s 下的稳定性重复验收仍未完成。']
s['findings'] += ['三轮重复检查已完成，但a03前两目标回报位置误差0.252/0.265m；stateful到达与转向状态锁存是有源码支持的解释，内部判定时间尚未记录。','ConstructionSite同XY视觉地面-0.3m与碰撞上表面1.211m不一致；当前正在完成的是原碰撞基线诊断，不能直接用于正式地图验收。']
p.write_text(json.dumps(s,ensure_ascii=False,indent=2),encoding='utf-8')
a=json.loads((root/'runs/arrival_candidates_20261019/RetroNeighborhood-a02/index.unreviewed.json').read_text(encoding='utf-8'))
summary={k:v for k,v in a.items() if k not in ('entries','metadata')}
summary.update(output='runs/arrival_candidates_20261019/RetroNeighborhood-a02/',earlier_a01='Preserved all-annotation diagnostic (165 entries); a02 correctly restricts Table A.3 paper classes (31). No formal artifacts were written.',validation_command='timeout 180 /home/raven/.venvs/raven-scene1/bin/python scripts/prepare_unreviewed_arrival_candidates.py --postprocess runs/full_map_postprocess_20261019/full-post-a01-frames --targets runs/full_map_postprocess_20261019/source/targets.binding-corrected.unreviewed.json --output runs/arrival_candidates_20261019/RetroNeighborhood-a02',exit_code=0)
(root/'docs/development/ugv-ogn/unreviewed-arrival-candidates-20261019.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
for path in [root/'benchmark/README.md',root/'docs/benchmark_zh.md']:
 text=path.read_text(encoding='utf-8');note='ConstructionSite 地形诊断（2026-10-19）：真实射线发现 Landscape2 凸分解表面1.211m，而相同XY源三角形为-0.3m；仅两块地形的明确ground分类候选通过3项CPU回归，真实A/B待运行。现有全图为旧碰撞基线，修正后必须重采。S7已生成Retro31个未审核逐实例几何候选，保留469261个共享格；不是正式arrival_regions、visibility或GT。证据见 construction-ground-diagnostic / unreviewed-arrival-candidates-20261019.json。\n\n'
 if note not in text:path.write_text(note+text,encoding='utf-8')
print('Recorded snapshot',s['updated_at'], 'tiles',s['construction_map']['completed_tiles'])
