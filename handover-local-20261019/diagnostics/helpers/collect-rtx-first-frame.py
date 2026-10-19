import hashlib
import html
import json
from pathlib import Path
import shutil
import zipfile

root = Path(r'D:\xprogram\RAVEN-AirGround-github')
run = root / 'runs/rtx_first_frame_20261018'
old = root / 'runs/second_pc_runtime_20261018'
for name in ('cube-a09', 'cube-a09-frames'):
    if not (run / name).exists():
        shutil.copytree(old / name, run / name)

def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig')) if path.exists() else None

data = {
    'task': 'Local-Scene1-Reproduction / RTX-First-Frame / Screenshots',
    'date': '2026-10-18',
    'scope': 'Real native Isaac 4.5 diagnostics, not a benchmark acceptance',
    'hardware': 'Second PC RTX 4060 Laptop 8 GiB, 32 GiB RAM, Windows 11, NVIDIA 577.02',
    'runs': [],
    'pagefile_before': read(run / 'pagefile-before-rtx-20261018.json'),
    'pagefile_after': read(run / 'pagefile-after-rtx-20261018.json'),
    'pagefile_authorization': 'User explicitly approved applying the prepared configuration; no reboot performed by the agent.',
    'pagefile_observation': 'New 16 GiB D: pagefile became active immediately; total commit capacity rose from about 33.61 to 49.61 GiB.',
    'formal_benchmark_guards_changed': False,
    'diagnostic_limit': 'Default 8 GiB; 10/14 GiB comparisons. All retain 4 GiB physical and 2 GiB commit reserve, GPU memory <=80%, CPU <=60%, wall-clock deadline.',
    'scene1_reproduced': False,
    'real_episode_count': 0,
    'cleanup': read(run / 'rtx-cleanup-20261018.json'),
    'capture_methods': {'sensor_png': 'PIL saves the actual Camera.get_rgba buffer without image editing',
                        'ui_png': 'omni.kit.renderer.capture captures the actual Isaac window swapchain',
                        'ui_camera_preview': 'An in-app panel displays the same saved sensor PNG; not a claim that the default viewport renders correctly'},
    'visual_review': {'cube-a13/view-0.png': 'Actual red cube on ground, manually inspected',
                      'retro-render-a01/view-0.png': 'Rejected: mostly black first buffer; original weak variance-only test reported passed',
                      'retro-render-a01/view-1.png': 'Actual street/parking area visible; manually inspected',
                      'retro-render-a02/view-0.png': 'Passed visual inspection: street, bus shelter, houses, trees and light poles',
                      'retro-render-a02/view-1.png': 'Passed visual inspection: parking area, vehicles, houses, trees and street',
                      'retro-render-a02/ui-camera-preview-1.png': 'Actual Isaac app capture; preview panel displays the saved RGB buffer and measured frame/time'},
    'sources': [
        'https://learn.microsoft.com/en-us/troubleshoot/windows-client/performance/introduction-to-the-page-file',
        'https://learn.microsoft.com/en-us/troubleshoot/windows-client/performance/slow-page-file-growth-memory-allocation-errors',
        'https://docs.omniverse.nvidia.com/kit/docs/omni.kit.renderer.capture/106.0.0/omni.kit.renderer.capture/omni.kit.renderer.capture.IRendererCapture.html'
    ],
}
for folder in sorted(run.iterdir()):
    if folder.is_dir() and (folder / 'execution.json').exists() and (folder / 'resources.jsonl').exists():
        name = folder.name
        frames = run / (name + '-frames')
        samples_path = folder / 'resources.jsonl'
        samples = [json.loads(line) for line in samples_path.read_text().splitlines() if line.strip()]
        data['runs'].append({
            'id': name, 'execution': read(folder / 'execution.json'),
            'report': read(frames / 'report.json'), 'last_progress': read(frames / 'progress.json'),
            'minimum_available_gib': min(s['available_gib'] for s in samples) if samples else None,
            'minimum_commit_headroom_gib': min(s['available_commit_gib'] for s in samples) if samples else None,
            'maximum_gpu_memory_fraction': max(s['gpu_memory_fraction'] for s in samples) if samples else None,
            'compiler_out_of_memory': 'LLVM ERROR: out of memory' in (folder / 'stdout.log').read_text(errors='replace')
        })
data['screenshots'] = [
    {'file': str(p.relative_to(run)).replace('\\', '/'),
     'sha256': hashlib.sha256(p.read_bytes()).hexdigest(), 'bytes': p.stat().st_size}
    for p in sorted((run / 'screenshots').glob('*.png'))
]
data['teacher_screenshots'] = [
    {'file': str(p.relative_to(run)).replace('\\', '/'), 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}
    for p in sorted((run / 'teacher-screenshots').glob('*.png'))
]
data['cube_rgb_passed'] = any(x['id'].startswith('cube-') and (x['report'] or {}).get('status') == 'passed' and (x['report'] or {}).get('frames') for x in data['runs'])
data['retro_rgb_passed'] = any(x['id'] == 'retro-render-a02' and x['execution'].get('exit_code') == 0
                             and (x['report'] or {}).get('status') == 'passed'
                             and len((x['report'] or {}).get('frames', [])) == 2
                             and all(f.get('nonblack_fraction', 0) >= .05 for f in x['report']['frames'])
                             for x in data['runs'])
for path in (run / 'evidence.json', root / 'docs/development/ugv-ogn/rtx-first-frame-20261018.json'):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'runs': len(data['runs']), 'cube_rgb_passed': data['cube_rgb_passed'], 'retro_rgb_passed': data['retro_rgb_passed'], 'screenshots': len(data['screenshots'])}))
