from pathlib import Path
import json,hashlib
root=Path('D:/xprogram/RAVEN-AirGround-github');source=root/'runs/scene_gt_adaptation_20261017/AbandonedFactory/targets.unreviewed.json';targets=json.loads(source.read_text())
omitted=[t['instance_id'] for t in targets['instances'] if t['usd_prim_path']]
targets['instances']=[t for t in targets['instances'] if not t['usd_prim_path']]
targets['diagnostic_input_provenance']={'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'omitted_bound_instances':omitted,'bindings_modified':False,'scope':'ten originally unbound instances only'}
out=root/'runs/factory_adaptation_20261019/targets.originally-unbound-subset.json';assert not out.exists();out.write_text(json.dumps(targets,indent=2),encoding='utf-8');print(len(targets['instances']),omitted)
