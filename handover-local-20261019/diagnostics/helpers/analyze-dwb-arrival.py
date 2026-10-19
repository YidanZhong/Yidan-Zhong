"""Read-only examination of terminal message timing and actual PhysX poses."""
from pathlib import Path
import json,math,sys
sys.path.insert(0,'D:/xprogram/.raven-setup-cache/plot-tools')
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
base=Path('D:/xprogram/RAVEN-AirGround-github/runs/nav2_dwb_stability_20261019')
rows=[]
fig,axes=plt.subplots(3,2,figsize=(12,10),layout='constrained')
for i,job in enumerate(('full-nav-dwb-a01','full-nav-dwb-a02','full-nav-dwb-a03')):
    logs=base/job/'logs'
    native=json.loads((logs/(job+'-frames')/'jackal-nav2.json').read_text())
    ros=json.loads((logs/(job+'-wsl')/'ros-evidence.json').read_text())
    for j,event in enumerate(ros['terminal_actions']):
        end=event['odom']['sim_time_s'];goal=native['goals_xy'][j]
        samples=[s for s in native['samples'] if end-8<=s['sim_time_s']<=end+1]
        t=np.array([s['sim_time_s']-end for s in samples])
        xy=np.array([math.dist(s['position'][:2],goal) for s in samples])
        yaw=np.array([abs(math.atan2(2*(s['quaternion_xyzw'][3]*s['quaternion_xyzw'][2]+s['quaternion_xyzw'][0]*s['quaternion_xyzw'][1]),1-2*(s['quaternion_xyzw'][1]**2+s['quaternion_xyzw'][2]**2))) for s in samples])
        pre=t<=0;near=(t>=-1)&pre
        row={'job':job,'goal_index':j+1,'terminal_status_received_sim_s':event['sim_time_s'],'last_odom_stamp_sim_s':end,'status_minus_odom_s':event['sim_time_s']-end,'last_second_xy_min_m':float(xy[near].min()),'last_second_xy_max_m':float(xy[near].max()),'last_second_both_tolerances_count':int(((xy<=.25)&(yaw<=.30)&near).sum()),'last_second_samples':int(near.sum()),'last_eight_seconds_min_xy_m':float(xy[pre].min()),'observed_xy_at_status_m':float(xy[np.argmin(abs(t))]),'internal_controller_decision_time_known':False}
        rows.append(row)
        axes[i,0].plot(t,xy,label=f'goal {j+1}');axes[i,1].plot(t,yaw,label=f'goal {j+1}')
    for k,limit in enumerate((.25,.30)):
        axes[i,k].axhline(limit,color='red',ls='--',label='original tolerance')
        axes[i,k].axvline(0,color='black',ls=':');axes[i,k].set_title(job)
        axes[i,k].set_xlabel('Seconds relative to terminal status / latest odometry');axes[i,k].grid(alpha=.2)
        axes[i,k].set_ylabel('Position error (m)' if k==0 else 'Yaw error (rad)');axes[i,k].legend(fontsize=8)
fig.savefig(base/'teacher-report/arrival-errors.png',dpi=150)
result={'scope':'Read-only diagnostic, no success reclassification','rows':rows,'finding':'Original SimpleGoalChecker stateful=true permits XY latching; DWB RotateToGoal also latches in_window and rotating. These mechanisms can preserve success after planar drift. This is a supported mechanism, not proof of the exact internal decision pose. Do not fix by relaxing tolerances. Turning off only goal-checker stateful can leave a latched rotation critic unable to correct position, so a coordinated design and bounded real retest are needed.'}
(base/'arrival-analysis.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps(rows[-3:],indent=2))
