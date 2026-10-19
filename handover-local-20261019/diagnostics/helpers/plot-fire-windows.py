from pathlib import Path
import sys, json
sys.path.insert(0,'D:/xprogram/.raven-setup-cache/plot-tools')
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
root=Path('D:/xprogram/RAVEN-AirGround-github/runs/additional_scene_preflight_20261019')
frames=root/'fireacademy-windows-a01-evidence/logs/fireacademy-windows-a01-frames'
fig,axes=plt.subplots(3,3,figsize=(12,11),layout='constrained')
for i in range(3):
    data=np.load(frames/f'window-{i}-reference.npz',allow_pickle=False)
    meta=json.loads((frames/f'window-{i}-metadata.json').read_text())
    x,y=meta['origin']['x_m'],meta['origin']['y_m'];extent=[x,x+6.4,y,y+6.4]
    for j,(key,title) in enumerate([('height','Ground height (m)'),('obstacle_mask','Obstacle band (0.05-1 m)'),('footprint_mask','UGV footprint passable')]):
        ax=axes[i,j];im=ax.imshow(data[key],origin='lower',extent=extent,cmap='viridis' if j==0 else 'gray_r',interpolation='nearest')
        ax.set_title(f'Window {i+1}: {title}');ax.set_xlabel('X (m)');ax.set_ylabel('Y (m)')
        if j==0:fig.colorbar(im,ax=ax,shrink=.8)
fig.suptitle('FireAcademy: actual PhysX, 0.05 m / 49,152 cells\nDiagnostic map data only - unreviewed; not camera screenshots',fontsize=15)
fig.savefig(root/'fireacademy-windows-comparison.png',dpi=140)
page='''<!doctype html><meta charset="utf-8"><title>FireAcademy扩大窗口诊断</title><style>body{max-width:1200px;margin:32px auto;font:17px/1.8 system-ui}img{width:100%}p{padding:12px;background:#eef3f7}</style><h1>FireAcademy：真实PhysX局部扩大验证</h1><p>三个6.4×6.4m窗口，分辨率0.05m，共49,152格；14字段整块与分块比较、块缝差异均为0。运行152.70秒正常退出，峰值提交内存6.824GiB。数据来自真实物理射线，不是相机截图；语义目标未审核，不能作为全场景地图或正式验收。</p><img src="fireacademy-windows-comparison.png"><p>白色=否，黑色=是。中列表示障碍，右列表示车体可通行；两列含义不同。三个窗口分别有4,180、13,456、12,219个车体可通行格。此前关闭异常记录保留，本轮正常退出。</p><a href="fireacademy-windows-a01-evidence/logs/fireacademy-windows-a01/execution.json">运行及资源保护记录</a> · <a href="fireacademy-windows-a01-evidence/logs/fireacademy-windows-a01-frames/tile-validation.json">逐字段校验记录</a>'''
(root/'查看窗口验证.html').write_text(page,encoding='utf-8')
print(root/'fireacademy-windows-comparison.png')
