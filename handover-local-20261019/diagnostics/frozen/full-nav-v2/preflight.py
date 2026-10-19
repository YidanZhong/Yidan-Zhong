from pathlib import Path
import json,numpy as np
from probe_full_map_nav2 import load_map,geometry
out=Path('D:/RAVEN-4060/logs/full-nav-preflight-b');out.mkdir(exist_ok=False)
info=load_map(Path(__file__).with_name('manifest.json'),out,[-30,-21.5],[[-35.5,-26],[-35.5,-20.5],[-30,-21.5]])
check=geometry(out,info,np.linspace([-30,-21.5],[-35.5,-26],300).tolist())
assert check['center_samples_outside_selected_map']>0,check
print(json.dumps({'map':{k:v for k,v in info.items() if k!='config'},'direct_leg':check},indent=2))
