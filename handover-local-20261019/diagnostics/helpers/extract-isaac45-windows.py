import concurrent.futures
import json
import pathlib
import shutil
import time
import zipfile

root = pathlib.Path(r'D:\RAVEN-4060')
target = root / 'isaac45'
target.mkdir(exist_ok=False)
started = time.monotonic()
with zipfile.ZipFile(root / 'setup' / 'isaac-sim-4.5.0-windows.zip') as archive:
    files = archive.infolist()
    for item in files:
        if not (target / item.filename).resolve().is_relative_to(target.resolve()):
            raise RuntimeError('Unsafe archive path: ' + item.filename)
    def extract(item):
        destination = pathlib.Path('\\\\?\\' + str(target / item.filename))
        if item.is_dir():
            destination.mkdir(parents=True, exist_ok=True)
            return 0
        destination.parent.mkdir(parents=True, exist_ok=True)
        # ZipFile reads validate each member CRC while extracting.
        with archive.open(item) as source, destination.open('wb') as output:
            shutil.copyfileobj(source, output, length=1024*1024)
        return item.file_size
    completed = 0
    size = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        for value in pool.map(extract, files):
            completed += 1
            size += value
            if completed % 2000 == 0:
                status = {'phase': 'extract', 'files': completed, 'total_files': len(files),
                          'extracted_bytes': size, 'elapsed_s': round(time.monotonic()-started,1)}
                (root/'setup'/'isaac45-extract-status.json').write_text(json.dumps(status))
                print(json.dumps(status), flush=True)
status = {'phase': 'complete', 'files': completed, 'extracted_bytes': size,
          'elapsed_s': round(time.monotonic()-started,1), 'crc': 'all extracted members passed'}
(root/'setup'/'isaac45-extract-status.json').write_text(json.dumps(status,indent=2))
print(json.dumps(status),flush=True)
