import json
from pathlib import Path
repo=Path(r'D:\xprogram\RAVEN-AirGround-github')
p=repo/'docs/development/ugv-ogn/second-pc-runtime-20261018.json'
d=json.loads(p.read_text(encoding='utf-8'))
logs=repo/'runs/second_pc_runtime_20261018'
for name in ('cube-a06','cube-a07'):
    execution=json.loads((logs/name/'execution.json').read_text(encoding='utf-8'))
    result=json.loads((logs/name.replace('cube-','cube-frames-')/'report.json').read_text(encoding='utf-8'))
    entry={'id':name,'execution':execution,'diagnostic_result':result}
    if name=='cube-a06':
        entry['interpretation']='The early 90-step camera check was insufficient; this prompted an explicit first-frame wait and separate physics evidence. Not conclusive hardware evidence.'
    d['attempts']=[a for a in d['attempts'] if a['id']!=name]+[entry]
d['empty_physics_verified']=True
d['real_retro_physics_verified']=True
d['retro_physics_diagnostic']=json.loads((logs/'retro-physics-result-a01/report.json').read_text(encoding='utf-8'))
d['retro_physics_execution']=json.loads((logs/'retro-physics-a01/execution.json').read_text(encoding='utf-8'))
d['raw_scene_query_limitations']='Two spot-check rays only; raw road height is about -0.19126 m. The benchmark z=0 support plane was not added. These samples are not a 0.05 m traversability map or reviewed GT.'
d['gpu_driver_or_vulkan_registry_configuration_modified']=d.pop('system_gpu_driver_or_registry_modified')
d['diagnostic_protection']['tests'] += ['A fresh status=passed result with exit 0 is accepted', 'A child reporting failure before hanging is terminated promptly']
d['remaining_blockers']=['RTX camera first-frame initialization remains unresolved under the tested configurations; no validated RGB image exists.', 'Windows Isaac to Linux ROS clock/sensor/action communication has not been tested.', 'Formal benchmark resource guards remain unchanged; a suitable runtime profile has not been validated.', 'Teacher-reviewed target/reach, 0.05 m map, paper episodes and launch configuration remain missing for exact reproduction.']
p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
