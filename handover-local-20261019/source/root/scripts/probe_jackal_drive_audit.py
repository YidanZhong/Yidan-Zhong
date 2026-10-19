"""Bounded real-PhysX comparison of velocity state writes and actuator targets."""
from __future__ import annotations
import json
import math
from pathlib import Path
from typing import Any


def run_audit(world: Any, robot: Any, drive: Any, output: Path, backend: str) -> dict:
    import numpy as np
    import omni.physx
    from omni.isaac.dynamic_control import _dynamic_control
    from isaacsim.core.utils.types import ArticulationAction
    dc=_dynamic_control.acquire_dynamic_control_interface()
    body=dc.get_rigid_body('/World/ugv/base_link')
    if not body or body==_dynamic_control.INVALID_HANDLE:raise RuntimeError('Missing real Jackal body')
    indices=np.array([robot.get_dof_index(n) for n in drive.config.wheel_joint_names],dtype=np.int32)
    def command(v: float,w: float) -> list:
        speeds=drive.wheel_velocities(v,w)
        values=np.array([speeds[n] for n in drive.config.wheel_joint_names])
        if backend=='direct':robot.set_joint_velocities(values,joint_indices=indices)
        elif backend=='actions':robot.apply_action(ArticulationAction(joint_velocities=values,joint_indices=indices))
        else:raise ValueError(backend)
        return values.tolist()
    def state() -> dict:
        p=dc.get_rigid_body_pose(body);x,y,z,w=p.r.x,p.r.y,p.r.z,p.r.w
        return {'position':list(p.p),'quaternion_xyzw':[x,y,z,w],
                'yaw':math.atan2(2*(w*z+x*y),1-2*(y*y+z*z)),
                'up_z':1-2*(x*x+y*y),'linear_world':list(dc.get_rigid_body_linear_velocity(body)),
                'angular_world':list(dc.get_rigid_body_angular_velocity(body)),
                'wheel_velocity':robot.get_joint_velocities(joint_indices=indices).tolist()}
    report={'backend':backend,'scope':'real_physics_drivetrain_diagnostic_not_navigation_acceptance',
            'segments':[],'samples':[],'passed':False}
    initial=state();start=initial['position']
    query=omni.physx.get_physx_scene_query_interface()
    rays=[]
    for dx,dy in [(0,0),(.5,0),(-.5,0),(0,.5),(0,-.5)]:
        hits=[]
        def on_hit(hit):
            path=str(hit.rigid_body or hit.collision)
            if not path.startswith('/World/ugv'):
                hits.append({'body':str(hit.rigid_body),'collision':str(hit.collision),
                             'position':list(hit.position),'distance':float(hit.distance)})
            return True
        query.raycast_all((start[0]+dx,start[1]+dy,8.),(0.,0.,-1.),10.,on_hit)
        rays.append({'xy':[start[0]+dx,start[1]+dy],'hits':sorted(hits,key=lambda x:x['distance'])})
    report['initial_ground_rays']=rays
    report['initial_body']=initial
    report['wheel_centers_initial']={}
    for name in ('front_left','front_right','rear_left','rear_right'):
        handle=dc.get_rigid_body('/World/ugv/'+name+'_wheel_link')
        report['wheel_centers_initial'][name]=list(dc.get_rigid_body_pose(handle).p)
    dt=float(world.get_physics_dt())
    sequence=[('settle',3.,0.,0.),('forward',8.,.15,0.),('stop-forward',3.,0.,0.),
              ('turn-left',18.,0.,.2625),('stop-left',3.,0.,0.),
              ('turn-right',18.,0.,-.2625),('stop-right',3.,0.,0.)]
    try:
        for name,duration,v,w in sequence:
            first=state();segment_samples=[]
            for step in range(round(duration/dt)):
                ramp=min(1.,step*dt/2.) if name in ('forward','turn-left','turn-right') else 1.
                targets=command(v*ramp,w*ramp)
                world.step(render=False)
                current=state()
                if current['up_z']<math.cos(.5) or current['position'][2]<-.1:
                    raise RuntimeError('Tilt/ground guard exceeded')
                if math.dist(current['position'][:2],start[:2])>4.:
                    raise RuntimeError('Drivetrain diagnostic displacement guard exceeded')
                if step%6==0:
                    sample={'segment':name,'sim_time_s':float(world.current_time),'command':[v*ramp,w*ramp],
                            'wheel_targets':targets,**current}
                    report['samples'].append(sample);segment_samples.append(sample)
            last=state();yaws=np.unwrap([first['yaw']]+[s['yaw'] for s in segment_samples]+[last['yaw']])
            segment={'name':name,'start':first,'end':last,'sim_duration_s':duration,
                     'yaw_change_rad':float(yaws[-1]-yaws[0]),
                     'max_displacement_m':max(math.dist(first['position'][:2],s['position'][:2]) for s in segment_samples),
                     'path_m':sum(math.dist(a['position'][:2],b['position'][:2]) for a,b in zip(segment_samples,segment_samples[1:])),
                     'final_speed_mps':math.hypot(*last['linear_world'][:2])}
            report['segments'].append(segment)
        report['passed']=True
    finally:
        command(0.,0.)
        (output/'drive-audit.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    return report
