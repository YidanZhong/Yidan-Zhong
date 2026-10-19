import hashlib
import json
from pathlib import Path
import zipfile

root = Path(r'D:\xprogram\RAVEN-AirGround-github')
runs = root / 'runs/second_pc_runtime_20261018'
path = root / 'docs/development/ugv-ogn/second-pc-runtime-20261018.json'
data = json.loads(path.read_text(encoding='utf-8'))
data['attempts'] = [a for a in data['attempts'] if a['id'] != 'cube-a08']
data['attempts'].append({
    'id': 'cube-a08',
    'execution': json.loads((runs / 'cube-a08/execution.json').read_text(encoding='utf-8')),
    'last_progress': json.loads((runs / 'cube-frames-a08/progress.json').read_text(encoding='utf-8')),
    'interpretation': 'D3D12 comparison timed out during application initialization. No camera acceptance was reached; this does not demonstrate a VRAM capacity limit.'
})
data['cleanup'] = {
    'verified_at': '2026-10-18T18:20:24+08:00',
    'remote_native_isaac_processes': 0,
    'temporary_probe_tasks_remaining': 0,
    'tasks_checked': ['RAVEN-Render-Probe-20261018', 'RAVEN-Vulkan-Probe-20261018'],
    'verification': 'Read-only SSH queries of Win32_Process and Get-ScheduledTask'
}
archive = runs / 'kit-runtime-logs-20261018.zip'
with zipfile.ZipFile(archive) as z:
    assert z.testzip() is None
    entries = len(z.infolist())
data['native_log_archive'] = {
    'path': str(archive.relative_to(root)).replace('\\', '/'),
    'sha256': hashlib.sha256(archive.read_bytes()).hexdigest(),
    'entries': entries,
    'crc_verified': True
}
data['diagnostic_script_sha256'] = {
    name: hashlib.sha256((root / name).read_bytes()).hexdigest()
    for name in data['diagnostic_scripts']
}
path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
assert len(data['attempts']) == 8
assert data['retro_physics_execution']['exit_code'] == 0
assert data['retro_physics_diagnostic']['status'] == 'passed'
assert data['scene1_reproduced'] is False
assert data['real_episode_count'] == 0
print('Evidence validated: 8 rendering attempts, real scene physics passed, full reproduction incomplete; archive CRC passed.')
