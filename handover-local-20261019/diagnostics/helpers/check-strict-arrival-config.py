from pathlib import Path
import importlib.util,json
import pytest,yaml
root=Path('D:/xprogram/RAVEN-AirGround-github');cache=Path('D:/xprogram/.raven-setup-cache')
path=root/'AirStack/simulation/isaac-sim/tests/test_nav2_params_generation.py'
spec=importlib.util.spec_from_file_location('params_test_helpers',path);helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)
out=cache/'full-nav-strict-v1/config-check';out.mkdir(exist_ok=False)
results=[]
for label,source in [('baseline',root/'AirStack/simulation/isaac-sim/tools/run_nav2_smoke.py'),('candidate',cache/'full-nav-strict-v1/air-stack/simulation/isaac-sim/tools/run_nav2_smoke.py')]:
 with pytest.MonkeyPatch.context() as patch:
  patch.setattr(helper,'RUNNER',source);runner=helper._load_runner(patch)
  target=out/(label+'.yaml');runner._write_nav2_params(target,'ugv',desired_linear_vel_mps=.2,max_linear_vel_mps=.25,max_angular_vel_radps=.35)
  runner.apply_local_planner_profile(target,'dwb',max_linear_vel_mps=.25,max_angular_vel_radps=.35,linear_accel_mps2=runner.DEFAULT_NAV2_LINEAR_ACCEL_MPS2,angular_accel_radps2=runner.DEFAULT_NAV2_ANGULAR_ACCEL_RADPS2)
  results.append(yaml.safe_load(target.read_text()))
def diffs(a,b,path=''):
 if isinstance(a,dict) and isinstance(b,dict):
  assert a.keys()==b.keys()
  return [r for k in a for r in diffs(a[k],b[k],path+'/'+k)]
 return [] if a==b else [{'path':path,'before':a,'after':b}]
changes=diffs(*results)
assert changes==[{'path':'//ugv/controller_server/ros__parameters/general_goal_checker/stateful','before':True,'after':False},{'path':'//ugv/controller_server/ros__parameters/FollowPath/xy_goal_tolerance','before':.25,'after':.10}],changes
report={'scope':'CPU configuration comparison, not navigation acceptance','only_two_intended_changes':changes,'formal_accepted':False}
(out/'result.json').write_text(json.dumps(report,indent=2));print(report)
