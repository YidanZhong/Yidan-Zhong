import resource
resource.setrlimit(resource.RLIMIT_AS,(8*1024**3,8*1024**3))
from pathlib import Path
import argparse,hashlib,importlib.util,json,sys,time
root=Path('/mnt/d/xprogram/RAVEN-AirGround-github');sys.path.insert(0,str(root/'benchmark'))
from airground_benchmark.scenes import EXTRA_USD_ALIASES,paper_classes
from airground_benchmark.ground_truth import load_target_annotations,UsdPrimCandidateManifest,bind_target_annotations_to_usd_prims
p=argparse.ArgumentParser();p.add_argument('scene');args=p.parse_args();started=time.monotonic()
run=root/'runs/partial_scene_geometry_20261019';audit=json.loads((run/(args.scene+'.json')).read_text())
if not audit['mesh_count_read'] or audit['composition_errors']:raise RuntimeError('No readable complete composition for name candidates')
output=run/(args.scene+'-source-candidates');output.mkdir(exist_ok=False)
source=root/'AirStack/simulation/isaac-sim/tools/export_target_prim_candidates.py'
spec=importlib.util.spec_from_file_location('source_candidate_export',source);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
module.TARGET_ALIAS_TOKENS.update({k:tuple(v) for k,v in EXTRA_USD_ALIASES.items()})
target_file=root/f'runs/scene_gt_adaptation_20261017/{args.scene}/targets.unreviewed.json'
target_hash=hashlib.sha256(target_file.read_bytes()).hexdigest();targets=load_target_annotations(target_file)
assert all(not i.verified and i.usd_prim_path is None for i in targets.instances)
classes=tuple(sorted(set(paper_classes(args.scene))|{i.semantic_class for i in targets.instances}))
payload=module.export_candidates(Path(audit['source']),scene_id=args.scene,root_prefix='/',classes=classes,min_volume_m3=.1,generator_version='unreviewed-raw-source-paths-only')
(output/'prim-candidates.raw-source.json').write_text(json.dumps(payload,indent=2))
summary={'scope':'raw source path/name/AABB proposals, not runtime bindings or reviewed GT','scene':args.scene,
         'candidate_count':len(payload['candidates']),'classes_requested':classes,'scene_sha256':audit['scene_sha256'],
         'target_sha256':target_hash,'exporter_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
         'alias_source_sha256':hashlib.sha256((root/'benchmark/airground_benchmark/scenes.py').read_bytes()).hexdigest(),
         'formal_accepted':False,'bindings_applied':False,'known_empty_source_meshes':len(audit['mesh_errors'])}
if payload['candidates']:
    proposed,report=bind_target_annotations_to_usd_prims(targets,UsdPrimCandidateManifest.model_validate(payload),max_center_distance_m=3.)
    (output/'binding-proposals.raw-source.json').write_text(report.model_dump_json(indent=2))
    summary.update(proposed_count=sum(bool(i.usd_prim_path) for i in proposed.instances),ambiguous_count=report.ambiguous_count)
else:summary.update(proposed_count=0,ambiguous_count=0)
assert hashlib.sha256(target_file.read_bytes()).hexdigest()==target_hash
summary.update(targets_unchanged=True,elapsed_s=time.monotonic()-started,peak_rss_mib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024)
(output/'summary.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary),flush=True)
