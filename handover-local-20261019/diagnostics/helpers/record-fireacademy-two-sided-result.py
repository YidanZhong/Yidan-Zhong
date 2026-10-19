from pathlib import Path
import datetime,json
root=Path('D:/xprogram/RAVEN-AirGround-github');run=root/'runs/additional_scene_preflight_20261019'
frames=run/'fireacademy-triangle-a02-evidence/logs/fireacademy-triangle-a02-frames'
raw=json.loads((frames/'raw-ray-audit.json').read_text());hits=raw['points'][0]['absolute_obstacle_band_up_hits']
hit=next(h for h in hits if h['prim_path']=='/World/stage/Ds/Ds_001');assert abs(hit['position_xyz_m'][2]-.8720466)<1e-4
correction={'time':datetime.datetime.now().astimezone().isoformat(),
 'scope':'correction to operator-stop record; original archive remains immutable',
 'actual_stopped_process':'PID6476 was the Python resource guard, not the Isaac child. Its command line contained the child command and matched the broad pattern.',
 'effect':'Guard termination closed its kill-on-close Job Object and reclaimed the whole task; launcher exited 4294967295 without execution.json.',
 'sampling_status':'report passed and raw ray records saved before shutdown',
 'normal_exit_verified':False,'child_exit_code':None,
 'prevention':'Do not use command-substring matches for manual child termination. Leave bounded shutdown to the existing timeout guard unless exact executable/parent identity is separately established.',
 'archive_sha256':'8bd56427a85013754859815f4b37960a3d95dffc451dd679ba05fd89b676c838','verified_files':39}
(run/'fireacademy-triangle-a02-stop-correction.json').write_text(json.dumps(correction,indent=2))
doc=root/'docs/development/ugv-ogn/fireacademy-collision-20261019.json';d=json.loads(doc.read_text())
d['two_sided_query']={'sampling_passed':True,'first_point_up_surface_z_m':hit['position_xyz_m'][2],
 'topology_change_from_triangle_a01':'none; only PhysX raycast_all bothSides=True',
 'archive_sha256':correction['archive_sha256'],'verified_files':39,'shutdown':correction,
 'next':'Three 128x128 real windows with whole/tiled comparison prepared; not yet started'}
d['limitations'][1]='Two-sided A02 query detects z=0.8720466 source face, but normal process exit was not achieved. Larger three-window validation remains pending.'
doc.write_text(json.dumps(d,indent=2))
plan=root/'IMPLEMENTATION_PLAN.md';s=plan.read_text(encoding='utf-8')
s=s.replace('仍需双面射线排查向上射线漏检0.872m表面及更大窗口验证，不扩散到正式运行时或其他场景。','双面查询a02已检出0.8720466m源表面；采样报告通过但关闭卡住，终止时匹配到guard导致作业回收且无execution.json，39文件包及更正记录已保存，不计正常退出。三128×128窗口验证已准备，不扩散到正式运行时。')
plan.write_text(s,encoding='utf-8')
p=root/'runs/autonomous_handover_20261019/progress.json';s=json.loads(p.read_text(encoding='utf-8'));s.update(updated_at=datetime.datetime.now().astimezone().isoformat(),last_observed_process='construction-visibility-a05 已启动并进行实际渲染步进；FireAcademy双面诊断采样完成、关闭异常已归档',remote_log='D:/RAVEN-4060/logs/construction-visibility-a05/execution.json')
s['failed_results'].append('fireacademy-triangle-a02：采样报告通过，关闭等待USD资源超过180s；手动终止误匹配到guard，触发作业回收，启动器4294967295，无execution.json。39文件已核验、更正记录已写，未记正常退出。')
p.write_text(json.dumps(s,ensure_ascii=False,indent=2),encoding='utf-8')
note='FireAcademy双面查询已检出原漏检的0.8720466m源面。该轮采样报告通过，但关闭阶段卡住；终止匹配选中guard并回收作业，未产生execution.json，已明确记录退出异常与更正，不计完整运行验收。见 `fireacademy-collision-20261019.json`。\n\n'
for rel in ['benchmark/README.md','docs/benchmark_zh.md']:
 p=root/rel;p.write_text(note+p.read_text(encoding='utf-8'),encoding='utf-8')
