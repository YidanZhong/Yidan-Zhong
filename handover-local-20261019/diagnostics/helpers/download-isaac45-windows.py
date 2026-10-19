import concurrent.futures
import hashlib
import json
import pathlib
import time
import urllib.request

URL = 'https://download.isaacsim.omniverse.nvidia.com/isaac-sim-standalone-4.5.0-windows-x86_64.zip'
TOTAL = 7013544567
CHUNK = 64 * 1024 * 1024
ROOT = pathlib.Path(r'D:\RAVEN-4060\setup')
PARTS = ROOT / 'isaac45-parts'
OUTPUT = ROOT / 'isaac-sim-4.5.0-windows.zip'
PARTS.mkdir(exist_ok=True)
started = time.monotonic()

def download(index):
    start = index * CHUNK
    end = min(TOTAL, start + CHUNK) - 1
    path = PARTS / f'{index:04d}.part'
    if path.exists() and path.stat().st_size == end - start + 1:
        return path
    for attempt in range(3):
        try:
            request = urllib.request.Request(URL, headers={'Range': f'bytes={start}-{end}'})
            with urllib.request.urlopen(request, timeout=45) as response:
                if response.status != 206 or response.headers.get('Content-Range') != f'bytes {start}-{end}/{TOTAL}':
                    raise RuntimeError('Unexpected range response')
                with path.open('wb') as stream:
                    while data := response.read(1024 * 1024):
                        stream.write(data)
            if path.stat().st_size != end - start + 1:
                raise RuntimeError('Incomplete range download')
            return path
        except Exception:
            if attempt == 2:
                raise
            time.sleep(2)

count = (TOTAL + CHUNK - 1) // CHUNK
completed = 0
with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
    for future in concurrent.futures.as_completed([pool.submit(download, i) for i in range(count)]):
        part = future.result()
        completed += part.stat().st_size
        status = {'phase': 'download', 'completed_bytes': completed, 'total_bytes': TOTAL,
                  'percent': round(completed / TOTAL * 100, 1), 'elapsed_s': round(time.monotonic() - started, 1)}
        (ROOT / 'isaac45-download-status.json').write_text(json.dumps(status))
        print(json.dumps(status), flush=True)

digest = hashlib.sha256()
with OUTPUT.open('wb') as stream:
    for index in range(count):
        with (PARTS / f'{index:04d}.part').open('rb') as source:
            while data := source.read(4 * 1024 * 1024):
                stream.write(data)
                digest.update(data)
status = {'phase': 'complete', 'bytes': OUTPUT.stat().st_size, 'sha256': digest.hexdigest(),
          'url': URL, 'elapsed_s': round(time.monotonic() - started, 1)}
(ROOT / 'isaac45-download-status.json').write_text(json.dumps(status, indent=2))
print(json.dumps(status), flush=True)
