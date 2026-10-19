from pathlib import Path
import zipfile

base = Path(r'D:\RAVEN-4060')
out = base / 'logs/rtx-first-frame-native-logs-20261018.zip'
with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
    for p in (base / 'isaac45/kit/logs/Kit/Isaac-Sim Python/4.5').glob('*.log'):
        if p.name >= 'kit_20261018_183600.log':
            z.write(p, 'kit/' + p.name)
    for pattern in ('cube-a09.json', 'cube-a10.json', 'cube-a11.json', 'cube-a12.json', 'cube-a13.json',
                    'retro-render-a01.json', 'retro-render-a02.json', 'run_windows_probe.py',
                    'probe-cube-a11.py', 'probe-cube-a12.py', 'probe-cube-a13.py',
                    'probe-retro-render-a01.py', 'probe-retro-render-a02.py', 'launch-raven-probe.py'):
        p = base / 'setup' / pattern
        if p.is_file():
            z.write(p, 'setup/' + p.name)
print(out)
