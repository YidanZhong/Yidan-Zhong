from pathlib import Path
import hashlib,json,shutil,py_compile
cache=Path('D:/xprogram/.raven-setup-cache');source=cache/'construction-ground-v2';dest=cache/'construction-visibility-v1';dest.mkdir(exist_ok=False)
for filename in ['probe_windows_scene_render.py','probe_tiled_terrain.py','launch-tiles.py']:
    text=(source/filename).read_text(encoding='utf-8')
    if filename=='launch-tiles.py':text=text.replace('construction-ground-v2','construction-visibility-v1')
    if filename=='probe_tiled_terrain.py':
        needle='    query = omni.physx.get_physx_scene_query_interface()'
        assert text.count(needle)==1
        text=text.replace(needle,"    from probe_unreviewed_visibility import run_visibility\n    visibility = run_visibility(world, stage, output, config_path.with_name('visibility-input.json'))\n"+needle)
        text=text.replace("'config_sha256':sha(config_path),'setup':setup", "'visibility_diagnostic':visibility,'config_sha256':sha(config_path),'setup':setup")
    (dest/filename).write_text(text,encoding='utf-8');py_compile.compile(str(dest/filename),doraise=True)
shutil.copytree(source/'air-stack',dest/'air-stack')
shutil.copy2(cache/'probe_unreviewed_visibility.py',dest/'probe_unreviewed_visibility.py')
config=json.loads((source/'ground-input.json').read_text());config.pop('ray_audit_points_xy_m',None)
config['windows']=[{'name':'support_plane_context','origin':[-50.,-.05],'rows':2,'cols':2,'resolution_m':.05,'tile_cells':16}]
config['visibility_scope']='unreviewed private diagnostic only; five real PhysX samples, no formal GT'
(dest/'visibility-scene-input.json').write_text(json.dumps(config,indent=2))
job=json.loads((source/'construction-ground-a01.json').read_text());job['name']='construction-visibility-a01'
job['args']=[s.replace('construction-ground-v2','construction-visibility-v1').replace('/ground-input.json','/visibility-scene-input.json') for s in job['args']]
(dest/'construction-visibility-a01.json').write_text(json.dumps(job,indent=2))
print('Isolated job source prepared; visibility-input.json still requires completed map/candidate provenance')
