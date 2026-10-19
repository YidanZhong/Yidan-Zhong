import sys,types,json
from pathlib import Path
p=types.ModuleType('airground_benchmark')
p.__path__=[r'D:\RAVEN-4060\setup\target-benchmark\airground_benchmark']
sys.modules[p.__name__]=p
from airground_benchmark.ground_truth import TargetInstance,ConfirmationPose,RaycastConfirmationVisibilityConfig,_obb_surface_distance_2d
from airground_benchmark.isaac_los import make_isaac_physx_raycast_fn
c=json.loads(Path(r'D:\RAVEN-4060\setup\target-input.json').read_text())
i=TargetInstance.model_validate(c['target'])
assert not i.verified and i.ground_reachable=='unknown'
assert _obb_surface_distance_2d(*c['spawn_xy_m'],i.obb)>8
assert 1.5<_obb_surface_distance_2d(*c['goal_xy_m'],i.obb)<8
print('PASS: actual Isaac Python benchmark imports, target schema, start outside reach window, goal inside window.')
