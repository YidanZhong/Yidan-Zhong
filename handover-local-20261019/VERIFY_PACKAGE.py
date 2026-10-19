from pathlib import Path
import hashlib,json
root=Path(__file__).resolve().parent
manifest=json.loads((root/'SHA256SUMS.json').read_text(encoding='utf-8'))
for name,digest in manifest.items():
    path=(root/name).resolve()
    if not path.is_relative_to(root):raise ValueError('Unsafe manifest path')
    if hashlib.sha256(path.read_bytes()).hexdigest()!=digest:raise ValueError('Changed or missing file: '+name)
print('Verified',len(manifest),'files; no simulation started.')
