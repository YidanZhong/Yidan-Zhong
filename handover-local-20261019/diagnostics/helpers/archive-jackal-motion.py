from pathlib import Path
import re
import zipfile
base=Path(r'D:\RAVEN-4060')
with zipfile.ZipFile(base/'logs/jackal-native-logs-20261018.zip','w',zipfile.ZIP_DEFLATED) as z:
    for job in ['jackal-motion-a01','jackal-motion-a02','jackal-motion-a03']:
        text=(base/f'logs/{job}/stdout.log').read_text(errors='replace')
        for match in re.findall(r'Logging to file: ([^\r\n]+)',text):
            p=Path(match.strip())
            if p.is_file() and p.resolve().is_relative_to((base/'isaac45').resolve()):
                z.write(p,p.name)
        for p in [base/f'logs/{job}-wsl.log',base/f'setup/probe-{job}.py',base/f'setup/{job}.json']:
            if p.exists(): z.write(p,p.name)
    for name in ['probe_jackal_motion.py','probe_jackal_wsl_peer.py','run-jackal-wsl-peer.sh']:
        z.write(base/'setup'/name,name)
print('Native logs and diagnostic sources archived.')
