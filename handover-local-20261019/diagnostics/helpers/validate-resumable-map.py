from pathlib import Path
from html.parser import HTMLParser
import hashlib,json,zipfile
root=Path(r'D:\xprogram\RAVEN-AirGround-github');run=root/'runs/resumable_map_20261018';report=run/'teacher-report'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
e=read(report/'evidence.json');p=e['full_job_snapshot']['progress']
assert e['resume_verification']['passed'] and p['completed_tiles']>0
assert not e['full_map_generated'] and not e['formal_gt_approved'] and e['formal_episode_count']==0
for name,value in e['resume_verification']['source_pins'].items():
    assert sha(root/'scripts'/name)==sha(run/'source'/name)==value
assert sha(report/'evidence.json')==sha(root/'docs/development/ugv-ogn/resumable-map-20261018.json')
for zpath in [run/'teacher-report.zip',run/'resume-proof-20261018.zip']:
    with zipfile.ZipFile(zpath) as z:assert z.testzip() is None
class Links(HTMLParser):
    def handle_starttag(self,tag,attrs):
        for key,val in attrs:
            if key in ('href','src') and val and not val.startswith('#'):assert (report/val).is_file(),val
Links().feed((report/'查看进展.html').read_text(encoding='utf-8'))
assert e['visual_qa']!='pending'
print('PASS: source pins, evidence identity, ZIP CRCs, HTML links, visual QA record, incomplete full-map/GT state.')
