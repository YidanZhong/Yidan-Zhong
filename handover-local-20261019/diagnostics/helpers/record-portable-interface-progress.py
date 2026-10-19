from pathlib import Path
import datetime
import hashlib
import json

root = Path('D:/xprogram/RAVEN-AirGround-github')
run = root/'runs/construction_adaptation_20261019'
docs = root/'docs/development/ugv-ogn'
cpu = json.loads((run/'portable-instance-runtime-cpu.json').read_text(encoding='utf-8'))
evidence = {
    'scope':'S0/S5 explicit runtime instance collider interface; CPU and prepared GPU diagnostics',
    'source_commit':'c01d33b1',
    'cpu_actual_asset':cpu,
    'tests':{'passed':20, 'environment':'local WSL RAVEN-Ubuntu-22.04, USD 26.8',
        'command':'PYTHONNOUSERSITE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 /home/raven/.venvs/raven-scene1/bin/python -m pytest -q tests/test_scene_instance_colliders.py tests/test_scene_physics_profile.py tests/test_visibility_scene_selection.py tests/test_asset_reports.py::test_retro_neighborhood_launch_uses_profiled_colliders_not_blanket_mesh_sweep',
        'scope':'10 helper protection tests, 3 physics profile tests, 6 visibility scene selection tests, 1 launch source contract'},
    'gpu_probe':{'status':'prepared_not_run','job':'construction-portable-a01','source':'D:/RAVEN-4060/setup/construction-portable-v1','memory_gib':14,'timeout_s':840,
        'checks':'Exact prior real-PhysX collider list equality, two 2x2 windows, five raw ray points, footprint-derived reach',
        'limitations':'Native-stage helper only; shared Pegasus launcher and actual UGV patrol still require separate validation'},
    'first_batch_archive':{'path':'runs/construction_adaptation_20261019/construction-instance-prefix20-evidence.zip',
        'sha256':'9536c52a58f9ae33dd000b7f1bda4a09a0b53635b0af29bfdeedde6bd47000f4',
        'verified_files':120,'tiles':20,'cells':1268736,'scope':'Immutable committed prefix; live mutable progress omitted'},
    'formal_accepted':False}
for name in ['portable-instance-runtime-cpu.json','static-instance-collision-manifest.unreviewed.json']:
    evidence.setdefault('evidence_sha256',{})[name] = hashlib.sha256((run/name).read_bytes()).hexdigest()
(docs/'static-instance-runtime-interface-20261019.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2),encoding='utf-8')
plan = root/'IMPLEMENTATION_PLAN.md'
text = plan.read_text(encoding='utf-8')
needle = '  - [ ] S0/S5运行时碰撞接口：'
position = text.index('\n',text.index(needle))
line = '\n  - S0/S5接口阶段结果（2026-10-19）：AirStack airground提交c01d33b1加入显式manifest与可选运行入口，20项CPU检查通过；真实Construction USD原生/引用两种挂载均补全5075网格、5757场景碰撞列表与此前真实PhysX完全一致，源资产未改，CPU峰值322.184MiB。这仍不是新接口的真实PhysX或UGV巡游验收；独立construction-portable-a01已冻结准备，等待单GPU队列空闲。新图a01/a02均正常退出0，40/70块、2537472格；a03继续。首20块120文件已回传逐文件核验，归档SHA9536c52a…。详见static-instance-runtime-interface-20261019.json。'
assert line not in text
plan.write_text(text[:position]+line+text[position:],encoding='utf-8')
index = docs/'README.md'
text = index.read_text(encoding='utf-8')
text = '- [静态实例运行接口 CPU 校验与新地图首批归档](static-instance-runtime-interface-20261019.json)：c01d33b1，20项检查通过，原生/引用挂载结果一致；新接口真实PhysX验证待执行。\n\n'+text
index.write_text(text,encoding='utf-8')
for file in [root/'benchmark/README.md',root/'docs/benchmark_zh.md']:
    text = file.read_text(encoding='utf-8')
    text = text.replace('新契约首批正在重采。','新契约a01/a02正常退出0，已40/70块，有限队列继续；首20块120文件已回传核验。显式运行时碰撞manifest接口c01d33b1通过20项CPU检查及实际USD双挂载对照，新接口真实PhysX尚待独立测试。',1)
    file.write_text(text,encoding='utf-8')
progress = root/'runs/autonomous_handover_20261019/progress.json'
state = json.loads(progress.read_text(encoding='utf-8'))
state['updated_at'] = datetime.datetime.now().astimezone().isoformat()
state['phase'] = 'ConstructionSite新碰撞全图40/70；运行时碰撞接口CPU校验完成'
state['last_observed_process'] = '16:32:01核查：a02退出0/962.27s/峰值8.183GiB，40/70块；a03于16:31:03启动，有限单GPU队列继续。'
state['current_map'].update(last_observed_tiles=40,last_observed_cells=2537472,last_checked_at='2026-10-19T16:32:01+08:00')
state['completed_this_window'].append('显式运行时碰撞manifest接口c01d33b1通过20项CPU检查，真实USD双挂载均与旧PhysX碰撞清单一致；新接口真实物理验证尚未运行。首20块原始数据120文件已回传核验；a02正常退出0，新图累计40/70。')
state['reader_summary'][1] = 'ConstructionSite新碰撞地图a01/a02通过，累计40/70块（57.72%），a03继续；首20块已备份核验，旧图仍无效。'
state['reader_summary'].insert(2,'通用运行入口已支持显式碰撞继承manifest，20项CPU检查和实际USD双挂载对照通过；独立真实PhysX验证已准备，尚未运行。')
state['next_step'] = '继续当前有限地图批次，70/70后独立窗口对照后处理并归档；新图通过后重建S7诊断候选。单GPU空闲后运行实际时钟计数、通用碰撞接口、Factory三角碰撞和小批次审核渲染；人工未审核输入不进入正式验收。'
state['prepared_next']['ConstructionSite'] = 'a01/a02完成，a03运行，有限队列最多a05；70/70才后处理。'
state['prepared_next']['portable_collision_interface'] = 'construction-portable-a01已冻结及传输，原生挂载真实PhysX等价性待运行'
progress.write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'written':str(docs/'static-instance-runtime-interface-20261019.json'),'formal_accepted':False}))
