from pathlib import Path
import re
import zipfile

base=Path(r'D:\RAVEN-4060')
target=base/'logs/target-integration-20261018.zip'
with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED) as archive:
    for path in sorted((base/'logs').glob('jackal-target-a*')):
        files=sorted(path.rglob('*')) if path.is_dir() else [path]
        for item in files:
            if item.is_file(): archive.write(item,item.relative_to(base/'logs'))
        stdout=path/'stdout.log'
        if stdout.is_file():
            for match in re.findall(r'Logging to file: ([^\r\n]+)',stdout.read_text(errors='replace')):
                native=Path(match.strip())
                if native.is_file() and native.resolve().is_relative_to((base/'isaac45').resolve()):
                    archive.write(native,'native-logs/'+native.name)
    for name in ['probe_windows_scene_render.py','probe_jackal_motion.py','probe_jackal_nav2.py',
                 'probe_nav2_wsl_peer.py','probe_target_confirmation.py','target-input.json','target-benchmark.zip','run-target-wsl-peer.sh','run_windows_probe.py',
                 'launch-raven-probe.py','fastdds-windows.xml','fastdds-wsl.xml']:
        path=base/'setup'/name
        if path.is_file(): archive.write(path,'source/'+name)
    for pattern in ['jackal-target-a*.json','probe-jackal-target-a*.py','probe_nav2_wsl_peer-route-*.py']:
        for path in sorted((base/'setup').glob(pattern)):
            archive.write(path,'source/'+path.name)
    for name in ['ros-bridge-network-20261018.json','target-integration-cleanup-20261018.json']:
        path=base/'logs'/name
        if path.is_file(): archive.write(path,name)
print(str(target),target.stat().st_size)
