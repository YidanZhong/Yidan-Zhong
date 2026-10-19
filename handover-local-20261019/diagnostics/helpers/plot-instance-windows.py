from pathlib import Path
import sys,json
sys.path.insert(0,'D:/xprogram/.raven-setup-cache/plot-tools')
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
run=Path('D:/xprogram/RAVEN-AirGround-github/runs/construction_adaptation_20261019')
new=run/'instancewindows-a01-evidence/logs/construction-instancewindows-a01-frames'
old=run/'ground-v2-evidence/logs/construction-ground-a01-frames'
fig,axes=plt.subplots(2,3,figsize=(13,8),layout='constrained')
for i,name in enumerate(['Asphalt roller context','Biotoilet context']):
    before=np.load(old/f'window-{i}-reference.npz',allow_pickle=False)['footprint_mask'].astype(bool)
    after=np.load(new/f'window-{i}-reference.npz',allow_pickle=False)['footprint_mask'].astype(bool)
    meta=json.loads((new/f'window-{i}-metadata.json').read_text());x,y=meta['origin']['x_m'],meta['origin']['y_m'];extent=[x,x+8,y,y+8]
    diff=np.zeros(before.shape,dtype=np.uint8);diff[before & ~after]=1;diff[~before & after]=2
    for j,(data,title) in enumerate([(before,'Old map: INVALIDATED'),(after,'Restored instance colliders'),(diff,'Red: newly blocked footprint')]):
        axes[i,j].imshow(data,origin='lower',extent=extent,interpolation='nearest',vmin=0,vmax=2 if j==2 else 1,cmap=ListedColormap(['#eeeeee','#df3131','#1773b5']) if j==2 else ListedColormap(['#dddddd','#185d45']))
        axes[i,j].set_title(f'{name}\n{title}');axes[i,j].set_xlabel('X (m)');axes[i,j].set_ylabel('Y (m)')
fig.suptitle('Actual PhysX comparison / 0.05 m / same support plane and footprint\nGreen: passable. Diagnostic only; no GT approval or robot patrol.',fontsize=15)
fig.savefig(run/'teacher-report/instance-collider-window-comparison.png',dpi=140)
print(run/'teacher-report/instance-collider-window-comparison.png')
