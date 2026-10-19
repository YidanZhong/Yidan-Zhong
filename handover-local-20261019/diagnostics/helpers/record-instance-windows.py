from pathlib import Path
import datetime, json
import numpy as np
root=Path('D:/xprogram/RAVEN-AirGround-github');run=root/'runs/construction_adaptation_20261019'
new=run/'instancewindows-a01-evidence/logs/construction-instancewindows-a01-frames'
old=run/'ground-v2-evidence/logs/construction-ground-a01-frames'
d=json.loads((new/'tile-validation.json').read_text())
execution=json.loads((new.parent/'construction-instancewindows-a01/execution.json').read_text())
assert d['passed'] and execution['exit_code']==0
changes=[]
for i,w in enumerate(d['windows']):
    assert all(c['outside_tolerance']==0 and c['seam_mismatch_values']==0 for c in w['comparisons'].values())
    before=np.load(old/f'window-{i}-reference.npz',allow_pickle=False)
    after=np.load(new/f'window-{i}-reference.npz',allow_pickle=False)
    changes.append({'name':w['name'],'changed_values':{k:int(np.count_nonzero(before[k]!=after[k])) for k in before.files},
                    'footprint_before':int(before['footprint_mask'].sum()),'footprint_after':int(after['footprint_mask'].sum()),
                    'obstacles_before':int(before['obstacle_mask'].sum()),'obstacles_after':int(after['obstacle_mask'].sum()),
                    'newly_blocked_footprint':int(np.count_nonzero(before['footprint_mask'] & ~after['footprint_mask'])),
                    'newly_free_footprint':int(np.count_nonzero(~before['footprint_mask'] & after['footprint_mask']))})
result={'scope':'actual PhysX 51200-cell instance collider coverage diagnostic, no formal approval','execution':execution,'reference_cells':51200,'ray_count':d['ray_count'],'fields':14,'all_window_and_seam_differences_zero':True,'old_vs_new':changes,'archive_sha256':'0b391207567507170da23b6d2b9677d141f311ec608c8a04d0c5a56477e9925e','verified_files':38,'old_map_remains_invalidated':True,'next':'Fresh construction-instance-map-20261019 dataset; no previous blocks reused'}
(run/'instance-window-comparison.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
p=root/'docs/development/ugv-ogn/construction-instance-colliders-20261019.json';record=json.loads(p.read_text(encoding='utf-8'));record['larger_windows']=result;p.write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
p=root/'IMPLEMENTATION_PLAN.md';s=p.read_text(encoding='utf-8').replace('已准备51,200格整块/分块验证，仍须新契约重采。','51,200格/314,986射线扩大验证已退出0/265.62s/峰值8.211GiB，14字段及块缝差异0、38文件核验；两个窗口footprint分别减少2090/4328格，确认旧图低估障碍。新契约/独立数据集已准备，仍须重采。');p.write_text(s,encoding='utf-8')
p=root/'runs/autonomous_handover_20261019/progress.json';s=json.loads(p.read_text(encoding='utf-8'));s.update(updated_at=datetime.datetime.now().astimezone().isoformat(),last_observed_process='construction-review-a03 正在尝试56视角真实截图；ConstructionSite扩大碰撞窗口已通过',remote_log='D:/RAVEN-4060/logs/construction-review-a03/execution.json')
s['completed_this_window'].append('ConstructionSite 51,200格/314,986射线扩大验证退出0/265.62s/8.211GiB，14字段及接缝差异0；补全碰撞使两个窗口可通行格减少2090/4328，旧地图须作废重采。38文件归档核验。')
s['reader_summary'][1]='ConstructionSite碰撞补全通过真实51,200格扩大验证；旧图低估了障碍，现已准备独立数据集重采，当前尝试56视角真实审核截图。'
p.write_text(json.dumps(s,ensure_ascii=False,indent=2),encoding='utf-8')
for rel in ['benchmark/README.md','docs/benchmark_zh.md']:
    p=root/rel;s=p.read_text(encoding='utf-8').replace('正在扩大窗口验证，之后须新契约重采','51,200格扩大验证也已通过（265.62s、14字段差异0），须新契约重采');p.write_text(s,encoding='utf-8')
print(json.dumps(changes,ensure_ascii=False,indent=2))
