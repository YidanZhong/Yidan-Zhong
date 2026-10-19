"""Bounded public API clock test; no candidate map, GT, or visibility acceptance."""
from pathlib import Path
from typing import Any
import json


def probe_clock(world: Any, stage: Any, output: Path) -> dict:
    from pxr import PhysxSchema
    world.set_simulation_dt(physics_dt=1/250, rendering_dt=1/250)
    hz = PhysxSchema.PhysxSceneAPI(stage.GetPrimAtPath('/World/PhysicsScene')).GetTimeStepsPerSecondAttr().Get()
    if hz != 250 or abs(float(world.get_rendering_dt()) - 1/250) > 1e-7:
        raise RuntimeError('Authored physics/render rates differ from original 250 Hz')
    result = {'scope': 'actual PhysX clock diagnosis only; no visibility or GT acceptance',
              'authored_hz': hz, 'sdk_getter_dt': float(world.get_physics_dt()),
              'required_steps_per_batch': 25, 'max_render_calls_per_batch': 40,
              'required_clock_delta_s': 0.1, 'max_allowed_gap_s': 0.15,
              'formal_gt_approved': False, 'batches': []}
    def save() -> None:
        (output / 'actual-clock-stride.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    save()
    for index in range(4):
        row = {'index': index, 'before_s': float(world.current_time),
               'before_step': int(world.current_time_step_index), 'calls': []}
        result['batches'].append(row)
        for _ in range(40):
            if int(world.current_time_step_index) - row['before_step'] >= 25:
                break
            world.step(render=True)
            row['calls'].append({'sim_time_s': float(world.current_time), 'step_index': int(world.current_time_step_index)})
            save()
        row.update(after_s=float(world.current_time), after_step=int(world.current_time_step_index))
        row['actual_delta_s'] = row['after_s'] - row['before_s']
        row['actual_steps'] = row['after_step'] - row['before_step']
        row['passed'] = row['actual_steps'] == 25 and abs(row['actual_delta_s'] - 0.1) <= 1e-5 and 0 < row['actual_delta_s'] <= 0.15
        save()
        if not row['passed']:
            raise RuntimeError('Bounded actual step/time verification failed')
    result['passed'] = True
    save()
    return result
