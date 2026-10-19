from pathlib import Path
import py_compile
cache=Path('D:/xprogram/.raven-setup-cache')
text=(cache/'package-construction-review.py').read_text(encoding='utf-8')
text=text.replace("job='construction-review-a01'","job='construction-review-a02';evidence_root=run/'review-a02-evidence'")
text=text.replace("frames=run/(job+'-frames');render=read(frames/'report.json');execution=read(run/job/'execution.json');inputs=read(run/'review-input.json')", "frames=evidence_root/'logs'/(job+'-frames');render=read(frames/'report.json');execution=read(evidence_root/'logs'/job/'execution.json');input_file=evidence_root/'setup/construction-review-v1/review-input.json';inputs=read(input_file)")
text=text.replace("sha(run/'review-input.json')","sha(input_file)")
text=text.replace("report=run/'teacher-report'", "report=run/'teacher-review-a02'")
text=text.replace("run/'teacher-report.zip'", "run/'teacher-review-a02.zip'")
text=text.replace("shutil.copy2(repo/'runs/scene_gt_adaptation_20261017/ConstructionSite/review.ledger.template.json',report/'review.ledger.template.json')", "ledger_file=repo/'runs/scene_gt_adaptation_20261017/ConstructionSite/review.ledger.template.json'\nassert read(ledger_file)['source_annotations_sha256']==inputs['source_sha256']['targets']\nshutil.copy2(ledger_file,report/'review.ledger.template.json')")
destination=cache/'package-construction-review-a02.py'
if destination.exists():raise FileExistsError(destination)
destination.write_text(text,encoding='utf-8');py_compile.compile(str(destination),doraise=True)
print('Packager ready; requires all 56 actual RGB frames and successful final execution')
