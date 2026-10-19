from pathlib import Path
import hashlib, json, sys, types, zipfile
from html.parser import HTMLParser
root=Path(r'D:\xprogram\RAVEN-AirGround-github');run=root/'runs/tiled_map_validation_20261018';report=run/'teacher-report'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
sys.path.insert(0,r'D:\xprogram\.raven-setup-cache\target-tools')
package=types.ModuleType('airground_benchmark');package.__path__=[str(root/'benchmark/airground_benchmark')];sys.modules['airground_benchmark']=package
from airground_benchmark.ground_truth import load_target_annotations
manifest=load_target_annotations(run/'targets.binding-corrected.unreviewed.json')
assert len(manifest.instances)==165
original=read(root/'runs/target_integration_20261018/targets.auto-bound.json')
corrected=read(run/'targets.binding-corrected.unreviewed.json')
changes=[(a,b) for a,b in zip(original['instances'],corrected['instances']) if a!=b]
assert len(changes)==1
before,after=changes[0]
assert before['instance_id']==after['instance_id']=='RetroNeighborhood.red_car.0000'
assert {k for k in before if before[k]!=after[k]}=={'usd_prim_path'}
assert not any(t['verified'] for t in corrected['instances'])
assert all(t['ground_reachable']=='unknown' for t in corrected['instances'])
e=read(report/'evidence.json');assert e['passed'] and not e['formal_gt_approved'] and not e['full_map_generated']
assert e['cleanup']['task_removed'] and not e['cleanup']['processes']
assert sha(report/'evidence.json')==sha(root/'docs/development/ugv-ogn/tiled-map-validation-20261018.json')
for name in ['probe_windows_scene_render.py','probe_tiled_terrain.py']:
    assert sha(root/'scripts'/name)==sha(run/'source'/name)
assert sha(run/'tile-input.json')==sha(run/'source/tile-input.json')
for n in [12,13,58,59]:
    assert sha(report/f'previous-rgb-{n}.png')==sha(root/f'runs/paper31_review_20261018/teacher-report/view-{n}.png')
for p in [run/'teacher-report.zip',run/'tile-map-20261018.zip']:
    with zipfile.ZipFile(p) as z:assert z.testzip() is None
class Links(HTMLParser):
    def handle_starttag(self,tag,attrs):
        for key,val in attrs:
            if key in ('href','src') and val and not val.startswith('#'):assert (report/val).is_file(),val
Links().feed((report/'查看进展.html').read_text(encoding='utf-8'))
print('PASS: annotation schema, only one prim binding changed, all 165 unapproved, source/input/RGB/evidence hashes, ZIP CRCs, HTML links, cleanup.')
