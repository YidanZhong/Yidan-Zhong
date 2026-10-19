from pathlib import Path
import csv, hashlib, json, zipfile
from html.parser import HTMLParser

root = Path(r'D:\xprogram\RAVEN-AirGround-github')
run = root / 'runs/paper31_review_20261018'
report = run / 'teacher-report'
def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()
def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))

assert sha(root/'scripts/probe_windows_scene_render.py') == sha(run/'source/probe_windows_scene_render.py')
assert sha(run/'review-input.json') == sha(run/'source/paper31-review-input.json')
assert sha(report/'evidence.json') == sha(root/'docs/development/ugv-ogn/paper31-review-20261018.json')
evidence = read(report/'evidence.json')
assert len(evidence['images']) == 62
for frame in evidence['images']:
    assert sha(report/frame['file']) == frame['sha256'] == sha(run/'paper31-review-a01-frames'/frame['file'])
for archive in [run/'teacher-report.zip', run/'paper31-review-20261018.zip']:
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None

class Links(HTMLParser):
    def handle_starttag(self, tag, attrs):
        for key, value in attrs:
            if key in ('href', 'src') and value and not value.startswith('#'):
                assert (report/value).is_file(), value
Links().feed((report/'查看进展.html').read_text(encoding='utf-8'))
with (report/'审核填写表.csv').open(encoding='utf-8-sig', newline='') as f:
    rows = list(csv.DictReader(f))
assert len(rows) == 31
assert all(not row['decision_verify_or_exclude'] for row in rows)
inputs = read(run/'review-input.json')
assert all(row['target']['verified'] is False and row['target']['ground_reachable'] == 'unknown' for row in inputs['rows'])
assert evidence['validation']['visual_spot_check']['image_count'] == 16
assert evidence['reviewed_target_count'] == evidence['formal_episode_count'] == 0
assert not evidence['formal_map_created']
print('PASS: source/input hashes, 62 original-image hashes, 2 ZIP CRCs, HTML file references, 31 blank review rows, unapproved GT state, synchronized evidence.')
