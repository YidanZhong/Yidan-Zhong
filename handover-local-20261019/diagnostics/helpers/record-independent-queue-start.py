from pathlib import Path
import datetime
import hashlib
import json

root=Path('D:/xprogram/RAVEN-AirGround-github')
run=root/'runs/autonomous_handover_20261019'
cache=Path('D:/xprogram/.raven-setup-cache')
observed=json.loads((run/'independent-diagnostics-launch-snapshot.json').read_text())
assert observed['status']=='waiting_for_existing_map_queue' and not observed['steps']
state=json.loads((run/'progress.json').read_text(encoding='utf-8'))
state['updated_at']=datetime.datetime.now().astimezone().isoformat()
state['phase']='ConstructionSite新图44/70采样中；四项独立诊断队列已启动等待GPU'
state['last_observed_process']='16:38:08核查：新图44/70块、2799616格（63.69%），a03正在采样；有限后续队列pythonw PID42424实际存活并等待地图任务，steps为空，尚未启动后续GPU诊断。'
state['current_map'].update(last_observed_tiles=44,last_observed_cells=2799616,last_checked_at='2026-10-19T16:38:08+08:00')
state['reader_summary'][1]='ConstructionSite新碰撞地图已44/70块（63.69%），a03正在采样；首20块120文件及8个原始数组通道已校验，旧图仍无效。'
state['prepared_next']['independent_finite_queue']={'status':'started_waiting_existing_map_queue','observed_at':'2026-10-19T16:38:08+08:00','pid':42424,'task':'RAVEN-IndependentDiagnostics-20261019','jobs':['construction-portable-a01','construction-clock-a01','factory-triangle-a01','construction-review-a04'],'already_run_jobs':0,'progress':'D:/RAVEN-4060/logs/independent-diagnostics-20261019/progress.json','stop_before_next_job':'D:/RAVEN-4060/logs/independent-diagnostics-20261019/STOP','limits':'four jobs at most, no retries, 14GiB/840s each, wait at most3600s; resource/launch guard failure stops queue'}
state['next_step']='地图完成后核验全图/独立窗口对照并回传归档，重建S7未审核候选。已启动的有限串行队列会等待GPU释放，再依次进行通用碰撞接口、实际物理时钟、Factory三角碰撞、Construction剩余目标首小批拍图；检查每项真实结果后再决定后续，不把等待状态写成任务已运行。'
(run/'progress.json').write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf-8')
doc=root/'docs/development/ugv-ogn/static-instance-runtime-interface-20261019.json'
d=json.loads(doc.read_text(encoding='utf-8'))
d['first_batch_archive']['raw_array_validation']='runs/construction_adaptation_20261019/instance-prefix20-array-validation.json'
d['first_batch_archive']['raw_array_validation_passed']=True
d['gpu_probe']['status']='queued_waiting_existing_map_queue_not_yet_run'
d['gpu_probe']['remote_frozen_hash_and_isaac_python_compile_passed']=True
d['finite_independent_queue']={'startup_observation':observed,'preflight':json.loads((run/'independent-diagnostics-preflight.json').read_text()),'code_sha256':hashlib.sha256((cache/'run-independent-diagnostics.py').read_bytes()).hexdigest(),'config_sha256':hashlib.sha256((cache/'independent-diagnostics.json').read_bytes()).hexdigest(),'source_files':50,'jobs':state['prepared_next']['independent_finite_queue']['jobs']}
doc.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
plan=root/'IMPLEMENTATION_PLAN.md'
t=plan.read_text(encoding='utf-8')
needle='队列运行不代表四项已经实测或通过。'
assert needle in t
t=t.replace(needle,needle+' 16:38:08已核实等待进程PID42424和任务Running；当前地图44/70、2799616格，队列steps为空。首20块8通道shape/dtype/有限值及SHA全部通过。',1)
plan.write_text(t,encoding='utf-8')
for p in [root/'benchmark/README.md',root/'docs/benchmark_zh.md']:
    t=p.read_text(encoding='utf-8')
    t=t.replace('已40/70块，有限队列继续；','16:38核查已44/70块，有限队列继续；',1)
    t=t.replace('新接口真实PhysX尚待独立测试。','新接口真实PhysX尚待独立测试；四项有限诊断队列已实际启动等待当前地图释放GPU，尚未执行新诊断。',1)
    p.write_text(t,encoding='utf-8')
print(state['last_observed_process'])
