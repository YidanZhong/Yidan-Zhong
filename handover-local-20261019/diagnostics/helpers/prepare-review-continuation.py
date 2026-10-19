"""Small batches skip unusable views while retaining strict image validity checks."""
from pathlib import Path
import ast, copy, hashlib, json, shutil
base=Path('D:/xprogram/.raven-setup-cache');old=base/'construction-review-v2';new=base/'construction-review-v3'
new.mkdir(exist_ok=False)
for name in ['probe_windows_scene_render.py','launch-review.py']:
    shutil.copy2(old/name,new/name)
p=new/'probe_windows_scene_render.py';s=p.read_text(encoding='utf-8')
s=s.replace('deadline = time.monotonic() + args.first_frame_timeout', 'deadline = time.monotonic() + (min(args.first_frame_timeout, 60.) if review_views else args.first_frame_timeout)')
old_failure="            if consecutive_valid < required_valid:\n                raise RuntimeError(f'Camera stable-frame deadline exceeded; output shape: {rgba.shape}')"
new_failure="""            if consecutive_valid < required_valid:
                if review_views:
                    failure = {**review_views[index], 'eye': eye, 'target': target,
                        'error': 'No 60 consecutive useful frames within bounded review view budget',
                        'shape': list(rgba.shape), 'consecutive_valid_frames': consecutive_valid,
                        'per_view_deadline_s': min(args.first_frame_timeout,60.),
                        'formal_gt_approved': False, 'review_image_accepted': False}
                    if rgba.shape == expected_shape:
                        rejected = args.output / f'rejected-view-{index}.png'
                        Image.fromarray(rgba[..., :3].astype(np.uint8)).save(rejected)
                        failure.update(raw_rejected_file=rejected.name,
                            nonblack_fraction=float(np.mean(np.max(rgba[..., :3],axis=2)>8)),
                            std=float(rgba[..., :3].std()))
                    report.setdefault('review_view_failures',[]).append(failure)
                    save_phase('review_view_failed_retained_and_skipped')
                    continue
                raise RuntimeError(f'Camera stable-frame deadline exceeded; output shape: {rgba.shape}')"""
assert s.count(old_failure)==1;s=s.replace(old_failure,new_failure)
s=s.replace("        report['status'] = 'passed'\n        save_phase('frames_complete')", "        report['status'] = 'partial_review' if report.get('review_view_failures') else 'passed'\n        save_phase('frames_complete')")
p.write_text(s,encoding='utf-8');ast.parse(s)
p=new/'launch-review.py';p.write_text(p.read_text().replace('construction-review-v2',new.name),encoding='utf-8')
master=json.loads((old/'review-input.json').read_text())
# Do not retry the stalled target blindly. Isolate it; continue later targets first.
batches=[('a04',7,15),('a05',15,23),('a06',23,28),('a07',6,7)]
for suffix,start,end in batches:
    manifest=copy.deepcopy(master);manifest['rows']=master['rows'][start:end]
    manifest['batch_provenance']={'master_sha256':hashlib.sha256((old/'review-input.json').read_bytes()).hexdigest(),
        'row_slice':[start,end],'scope':'same unreviewed targets and original camera poses; per-view timeout failures are retained, skipped, and never approved'}
    (new/f'review-input-{suffix}.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    job=json.loads((old/'construction-review-a03.json').read_text());job['name']='construction-review-'+suffix
    job['args']=[v.replace('construction-review-v2',new.name).replace('review-input.json',f'review-input-{suffix}.json') for v in job['args']]
    job['retry_basis']='Continue independent remaining targets in <=8-target batches. Keep 14GiB/840s outer, 960x600, 90 warmup and 60 consecutive useful frames. 60s per-view limit records rejected buffers/failure and skips; partial batch remains non-success.'
    (new/(job['name']+'.json')).write_text(json.dumps(job,indent=2),encoding='utf-8')
    start_script=(base/'start-construction-review-a03.ps1').read_text(encoding='utf-8-sig').replace('construction-review-v2',new.name).replace('construction-review-a03',job['name']).replace('RAVEN-Construction-Review-A03-20261019','RAVEN-Construction-Review-'+suffix.upper()+'-20261019')
    (base/f'start-construction-review-{suffix}.ps1').write_text(start_script,encoding='utf-8-sig')
hashes={p.relative_to(new).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in new.rglob('*') if p.is_file()}
(new/'source-sha256.json').write_text(json.dumps(hashes,indent=2),encoding='utf-8')
p=base/'archive-scene-diagnostic.py';p.write_text(p.read_text().replace("'construction-review-v2',","'construction-review-v2','construction-review-v3',"),encoding='utf-8')
print(json.dumps({'prepared_not_started':str(new),'batches':batches,'accepted_frame_criteria_unchanged':True}))
