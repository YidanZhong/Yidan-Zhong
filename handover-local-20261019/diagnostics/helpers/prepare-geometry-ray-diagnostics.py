"""Prepare isolated unreviewed geometry-only diagnostic snapshots."""
from pathlib import Path
import hashlib,json,shutil,py_compile

cache=Path('D:/xprogram/.raven-setup-cache');root=Path('D:/xprogram/RAVEN-AirGround-github')
template=cache/'construction-audit-v1';base_config=json.loads((template/'audit-input.json').read_text())
for scene,prefix in [('FireAcademy','fireacademy'),('AbandonedFactory','factory')]:
    name=prefix+'-geometry-v1';dest=cache/name;dest.mkdir(exist_ok=False)
    baseline=json.loads((root/f'runs/additional_scene_preflight_20261019/{scene}-source-ray-baseline.json').read_text())
    for filename in ['probe_windows_scene_render.py','probe_tiled_terrain.py','probe_resumable_terrain.py','resumable_terrain_store.py','launch-tiles.py']:
        text=(template/filename).read_text()
        if filename=='launch-tiles.py':text=text.replace('construction-audit-v1',name)
        if filename=='probe_tiled_terrain.py':
            old="if scene_id not in SCENE_IDS or not config['corrected_target']['instance_id'].startswith(scene_id+'.'):"
            assert old in text
            text=text.replace(old,"if scene_id not in SCENE_IDS or config.get('scope') != 'geometry_anchor_diagnostic_only':")
            text=text.replace("    if len(config['targets_sha256'])!=64:\n        raise ValueError('A pinned target manifest is required')", "    if config.get('formal_gt_approved') is not False or config.get('mode') == 'resumable_sampling':\n        raise ValueError('Only unapproved bounded geometry diagnostics are allowed')")
            start=text.index("    target = config['corrected_target']");end=text.index('    world.reset()',start)
            text=text[:start]+'''    anchor = config['geometry_anchor']
    if anchor.get('semantic_binding') is not False:
        raise RuntimeError('Geometry anchor must not claim semantic binding')
    prim = stage.GetPrimAtPath(anchor['prim_path'])
    if not prim.IsValid() or not prim.IsA(UsdGeom.Mesh):
        raise RuntimeError('Pinned geometry mesh missing')
    box = bounds.ComputeWorldBound(prim).ComputeAlignedRange()
    binding = {'prim': str(prim.GetPath()), 'center': list(box.GetMidpoint()),
               'size': list(box.GetSize()), 'semantic_binding': False}
    if not np.allclose(binding['center'], anchor['center_xyz_m'], atol=.02, rtol=0):
        raise RuntimeError('Geometry anchor center differs from source baseline')
    if not np.allclose(binding['size'], anchor['size_xyz_m'], atol=.02, rtol=0):
        raise RuntimeError('Geometry anchor size differs from source baseline')
'''+text[end:]
            text=text.replace("'corrected_binding':binding", "'geometry_anchor':binding")
        (dest/filename).write_text(text,encoding='utf-8');py_compile.compile(str(dest/filename),doraise=True)
    config=json.loads(json.dumps(base_config))
    for key in ['corrected_target','expected_bounds','targets_sha256']:config.pop(key)
    config.update(scene_id=scene,scene_sha256=baseline['scene_sha256'],scope='geometry_anchor_diagnostic_only',formal_gt_approved=False,
                  geometry_anchor=baseline['geometry_anchor'],ray_audit_points_xy_m=[p['xy_m'] for p in baseline['points']])
    config['windows']=[{'name':f'geometry_context_{i}','origin':[p['xy_m'][0]-.025,p['xy_m'][1]-.025], 'rows':2,'cols':2,'resolution_m':.05,'tile_cells':16} for i,p in enumerate(baseline['points'])]
    for relative in list(config['source_sha256']):
        if relative.startswith('AirStack/'):
            source=root/relative;target=dest/'air-stack'/relative[len('AirStack/'):];target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)
            config['source_sha256'][relative]=hashlib.sha256(source.read_bytes()).hexdigest()
    (dest/'geometry-input.json').write_text(json.dumps(config,indent=2))
    shutil.copy2(root/f'runs/additional_scene_preflight_20261019/{scene}-source-ray-baseline.json',dest/'source-ray-baseline.json')
    job={'name':prefix+'-geometry-a01','timeout':840,'memory_gib':14,'ros2':False,'env':{},'args':['--graphics-api','vulkan','--defer-stage','--cpu-threads','16','--shader-concurrency','1','--disable-motion-bvh','--async-loads','--physics-only','--scene',f'D:/RAVEN-4060/assets/handover-scenes-20261019/{scene}/{scene}_Export.usd','--tile-validation',f'D:/RAVEN-4060/setup/{name}/geometry-input.json','--air-stack-root',f'D:/RAVEN-4060/setup/{name}/air-stack','--benchmark-package','D:/RAVEN-4060/setup/tile-benchmark/airground_benchmark']}
    (dest/(job['name']+'.json')).write_text(json.dumps(job,indent=2))
    manifest={f.relative_to(dest).as_posix():hashlib.sha256(f.read_bytes()).hexdigest() for f in dest.rglob('*') if f.is_file() and '__pycache__' not in f.parts}
    (dest/'source-sha256.json').write_text(json.dumps(manifest,indent=2))
    print(name,len(manifest),'prepared, not executed')
