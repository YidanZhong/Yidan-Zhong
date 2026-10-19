from pathlib import Path
import hashlib,importlib.util,json,os
from pxr import Usd
root=Path('/mnt/d/xprogram/RAVEN-AirGround-github');os.environ['AIRGROUND_BENCHMARK_PACKAGE']=str(root/'benchmark/airground_benchmark')
source=root/'AirStack/simulation/isaac-sim/tools/validate_confirmation_visibility_raycast.py'
spec=importlib.util.spec_from_file_location('visibility_projection_evidence',source);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
rows=[]
for scene in ['RetroNeighborhood','ConstructionSite','AbandonedFactory']:
    asset=root/f'AirStack/scenes/{scene}/{scene}_Export.usd'
    annotations=(root/'runs/full_map_postprocess_20261019/source/targets.binding-corrected.unreviewed.json' if scene=='RetroNeighborhood' else root/f'runs/scene_gt_adaptation_20261017/{scene}/targets.unreviewed.json')
    before=annotations.read_bytes();manifest=module.load_target_annotations(annotations)
    stage=Usd.Stage.CreateInMemory();stage.DefinePrim('/World/stage').GetReferences().AddReference(str(asset))
    projected,mapping=module._project_reference_target_paths(manifest,stage,asset,'/World/stage')
    matched=module._validate_runtime_target_paths(projected,stage)
    assert annotations.read_bytes()==before
    for a,b in zip(manifest.instances,projected.instances):assert a.model_dump(exclude={'usd_prim_path'})==b.model_dump(exclude={'usd_prim_path'})
    rows.append({'scene':scene,'declared_bound_paths_checked':matched,'source_annotations_sha256':hashlib.sha256(before).hexdigest(),
                 'source_unchanged':True,'all_non_path_fields_equal':True,'mapping':mapping})
result={'scope':'real USD CPU composition and private path projection, not PhysX visibility','formal_accepted':False,'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'rows':rows}
out=root/'runs/additional_scene_preflight_20261019/reference-projection-check.json';assert not out.exists();out.write_text(json.dumps(result,indent=2))
print(json.dumps([{k:v for k,v in row.items() if k!='mapping'} for row in rows],indent=2))
