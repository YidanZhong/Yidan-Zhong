from pathlib import Path
import hashlib,json,shutil
root=Path(r'D:\xprogram\RAVEN-AirGround-github')
run=root/'runs/resumable_map_20261018'
recovery=run/'recovery-20261019'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
proof=read(recovery/'full-map-a02-recovery-verified.json')
snapshot=read(run/'full-map-snapshot.json')
assert proof['status']=='passed' and proof['preserved_tiles']==133
assert snapshot['job_name']=='full-map-a02' and snapshot['task_state']=='Running'
assert snapshot['execution'] is None and snapshot['processes']
p=snapshot['progress'];assert p['new_tiles_this_session']>0 and p['skipped_existing_tiles']==133
assert proof['guard_sha256']==sha(root/'scripts/run_windows_probe.py')==sha(recovery/'run_windows_probe.py')
for name,value in proof['generator_sha256'].items():
    assert sha(root/'scripts'/name)==value
e={'task':'Local-Scene1-Reproduction / Scene1-FullMap-TelemetryRecovery',
   'recovery_started_and_verified':True,'full_map_complete':False,
   'a01_exit':read(recovery/'a01-execution.json'),
   'a01_task_cleanup':read(recovery/'a01-task-cleanup.json'),
   'preflight':read(recovery/'full-map-a02-preflight.json'),
   'live_resume_verification':proof,'snapshot':snapshot,
   'guard_tests':{'passed':5,'environments':['main PC bundled Python','RTX 4060 PC anaconda Python'],
     'command':'python -m unittest discover -s tests -p test_windows_probe_telemetry.py -v',
     'remote_command':'python D:/RAVEN-4060/setup/telemetry-v2/test_windows_probe_telemetry.py -v',
     'scope':'fault injection of GPU telemetry only; real Isaac resume verified separately'},
   'source_sha256':{p.name:sha(p) for p in recovery.glob('*.py')},
   'limits':{'job_memory_gib':14,'cpu_percent':60,'min_available_gib':4,'min_available_commit_gib':2,
             'max_gpu_fraction':.8,'gpu_query_timeout_s':8,'max_missing_gpu_samples':2,
             'timeout_s':28800,'preflight_requires_gpu':True},
   'job_config':read(recovery/'full-map-a02.json'),
   'limitations':['Cause of the original nvidia-smi delay is unknown; current query recovered.',
     'After two missing readings the third failure still stops the process; missing GPU values are null.',
     'Task has no trigger and will not repeat itself. Registration may remain Ready after exit.',
     'No full map, global postprocessing, reviewed GT or formal episode acceptance.']}
(recovery/'recovery-evidence.json').write_text(json.dumps(e,ensure_ascii=False,indent=2),encoding='utf-8')
shutil.copy2(recovery/'recovery-evidence.json',root/'docs/development/ugv-ogn/full-map-recovery-20261019.json')
plan=root/'IMPLEMENTATION_PLAN.md';text=plan.read_text(encoding='utf-8')
lines=text.splitlines()
for i,line in enumerate(lines):
    if '- [ ] Scene1-FullMap-TelemetryRecovery' in line:
        lines[i]=f'      - [x] Scene1-FullMap-TelemetryRecovery（2026-10-19）：a01 在 133/527 块后因单次 GPU 查询超时退出；`run_windows_probe.py` 现为每次查询 8 s、最多容忍连续两次失败，第三次停止，预检仍严格，未知读数记 null，内存/总时限检查与全部资源门保持。5 项故障注入测试在主机和第二台均通过（非真实物理证据）。133 块的哈希/形状/类型/有限值全部通过预检；真实 Isaac a02 跳过 133 块，新提交块已验证，原 133 块记录及 NPZ 哈希未变。{snapshot["observed_at"]} 快照 {p["completed_tiles"]}/527 块（{p["fraction"]:.2%}），后台运行中。源码、命令和失败证据见 `runs/resumable_map_20261018/recovery-20261019/`；证据 `docs/development/ugv-ogn/full-map-recovery-20261019.json`。a01 自清理因 Limited 用户权限失败，现同名无触发器任务运行 a02，结束后可能保留 Ready；不会自动重复执行。仅验收修复及续跑启动，全图完成项保持未勾选。'
        break
else:raise RuntimeError('Pending recovery plan item not found')
text='\n'.join(lines)+'\n'
text=text.replace('恢复测试计划任务已移除，全图任务仍在运行，配置结束后移除自身注册。','恢复测试计划任务已移除；全图任务在本条启动快照时运行，后续 a01 中断及自清理失败已在 TelemetryRecovery 项记录。')
text=text.replace('跟踪 `full-map-a01` 的实际退出和 527 块完整性','跟踪 `full-map-a02`（续接 a01）的实际退出和 527 块完整性')
plan.write_text(text,encoding='utf-8')
for path,link in [(root/'benchmark/README.md','../docs/development/ugv-ogn/full-map-recovery-20261019.json'),
                  (root/'docs/benchmark_zh.md','development/ugv-ogn/full-map-recovery-20261019.json')]:
    text=path.read_text(encoding='utf-8');lines=text.splitlines()
    for i,line in enumerate(lines):
        if line.startswith('> 本机断点采样'):
            lines[i]=f'> 本机断点采样恢复（2026-10-19）：a01 在 133/527 块后因 `nvidia-smi` 查询超时中断；已保留失败证据、完整校验 133 块并启动 a02。监控最多容忍连续两次查询失败，第三次停止；预检仍须有效显存读数，所有资源门和运行时限保持。两台电脑的 5 项故障注入检查通过；真实续跑跳过 133 块，原记录/哈希未变，新块实际落盘。{snapshot["observed_at"]} 快照 {p["completed_tiles"]}/527 块（{p["fraction"]:.2%}），仍在运行。此项只验收监控修复及恢复启动，全图后处理、审核 GT 与正式 episode 未完成。见[中断与恢复证据]({link})。'
            break
    else:raise RuntimeError('Status paragraph not found')
    path.write_text('\n'.join(lines)+'\n',encoding='utf-8')
index=root/'docs/development/ugv-ogn/README.md'
text=index.read_text(encoding='utf-8')
text += '\n全图采样中断及续跑（2026-10-19）：[监控修复和真实恢复证据](full-map-recovery-20261019.json)，仅验收跳过已保存块并继续提交；全图及论文复现仍待完成。\n'
index.write_text(text,encoding='utf-8')
print(json.dumps({'completed_tiles':p['completed_tiles'],'fraction':p['fraction'],'observed_at':snapshot['observed_at']}))
