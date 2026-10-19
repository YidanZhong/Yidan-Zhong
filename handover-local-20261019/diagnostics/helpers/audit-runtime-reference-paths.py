"""CPU reproduction of Pegasus load_asset AddReference, not a simulator run."""
from pathlib import Path
import hashlib,json
from pxr import Usd,UsdGeom
root=Path('/mnt/d/xprogram/RAVEN-AirGround-github');rows=[]
for scene in ['RetroNeighborhood','ConstructionSite','FireAcademy','AbandonedFactory']:
    source=root/f'AirStack/scenes/{scene}/{scene}_Export.usd';original=Usd.Stage.Open(str(source))
    target_file=root/f'runs/scene_gt_adaptation_20261017/{scene}/targets.unreviewed.json'
    if scene=='RetroNeighborhood':target_file=root/'runs/full_map_postprocess_20261019/source/targets.binding-corrected.unreviewed.json'
    targets=json.loads(target_file.read_text());runtime=Usd.Stage.CreateInMemory();UsdGeom.SetStageMetersPerUnit(runtime,1.);UsdGeom.SetStageUpAxis(runtime,UsdGeom.Tokens.z)
    runtime.DefinePrim('/World','Xform');runtime.DefinePrim('/World/stage','Xform').GetReferences().AddReference(str(source))
    default=original.GetDefaultPrim();mapping=[]
    for target in targets['instances']:
        path=target['usd_prim_path']
        if path is None:continue
        translated='/World/stage'+path[len(str(default.GetPath())):] if default and path.startswith(str(default.GetPath())+'/') else None
        mapping.append({'instance_id':target['instance_id'],'source_prim':path,'source_exists':bool(original.GetPrimAtPath(path)),
                        'same_path_exists_after_reference':bool(runtime.GetPrimAtPath(path)),
                        'candidate_remapped_path':translated,'remapped_exists':bool(runtime.GetPrimAtPath(translated)) if translated else False})
    rows.append({'scene_id':scene,'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'default_prim':str(default.GetPath()),
                 'root_prims':[str(p.GetPath()) for p in original.GetPseudoRoot().GetChildren()],
                 'bound_target_count':len(mapping),'same_path_exists_count':sum(r['same_path_exists_after_reference'] for r in mapping),
                 'remapped_exists_count':sum(r['remapped_exists'] for r in mapping),'mapping':mapping})
out=root/'runs/additional_scene_preflight_20261019/runtime-reference-paths.json';assert not out.exists()
out.write_text(json.dumps({'scope':'CPU reference namespace reproduction only; no targets changed','formal_accepted':False,'rows':rows},indent=2))
print(json.dumps([{k:v for k,v in r.items() if k!='mapping'} for r in rows],indent=2))
