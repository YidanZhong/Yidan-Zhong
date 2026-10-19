from pathlib import Path
import importlib.util,json,hashlib,shutil
root=Path('/mnt/d/xprogram/RAVEN-AirGround-github');source=root/'scripts/prepare_unreviewed_arrival_candidates.py'
spec=importlib.util.spec_from_file_location('candidate_export',source);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
post=root/'runs/full_map_postprocess_20261019/full-post-a01-frames';targets=root/'runs/full_map_postprocess_20261019/source/targets.binding-corrected.unreviewed.json'
base=root/'runs/arrival_candidates_20261019/guard-check';base.mkdir(exist_ok=False)
existing=root/'runs/arrival_candidates_20261019/RetroNeighborhood-a02';before={p.name:module.digest(p) for p in existing.iterdir() if p.is_file()}
checks=[]
try:module.export_candidates(post,targets,existing)
except FileExistsError:checks.append('existing output refused')
else:raise AssertionError('Existing output overwritten')
assert before=={p.name:module.digest(p) for p in existing.iterdir() if p.is_file()}
changed=base/'changed-target-copy.json';changed.write_bytes(targets.read_bytes()+b' ')
try:module.export_candidates(post,changed,base/'bad-target-output')
except ValueError as e:assert 'Target hash' in str(e);checks.append('target hash mismatch refused')
else:raise AssertionError('Changed targets accepted')
badmap=base/'metadata-fixture';(badmap/'reach').mkdir(parents=True)
for name in ('report.json','component-report.unreviewed.json'):shutil.copy2(post/name,badmap/name)
metadata=json.loads((post/'reach/reach.metadata.yaml').read_text());metadata['origin']['x_m']+=1
(badmap/'reach/reach.metadata.yaml').write_text(json.dumps(metadata))
try:module.export_candidates(badmap,targets,base/'bad-map-output')
except ValueError as e:assert 'metadata hash' in str(e);checks.append('metadata displacement refused')
else:raise AssertionError('Changed metadata accepted')
assert not (base/'bad-target-output').exists() and not (base/'bad-map-output').exists()
(base/'result.json').write_text(json.dumps({'scope':'CPU guard checks using actual map metadata','checks':checks,'original_outputs_unchanged':True,'source_sha256':module.digest(source),'formal_accepted':False},indent=2));print(checks)
