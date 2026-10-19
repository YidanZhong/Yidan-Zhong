import pathlib
import zipfile
import email
import shutil

cache = pathlib.Path('/home/raven/.cache/pip')
dest = pathlib.Path('/mnt/d/xprogram/.raven-setup-cache/raven4060-wheels')
dest.mkdir(exist_ok=True)
count = 0
for path in cache.rglob('*'):
    if not path.is_file() or not zipfile.is_zipfile(path):
        continue
    try:
        with zipfile.ZipFile(path) as archive:
            wheel_path = next(n for n in archive.namelist() if n.endswith('.dist-info/WHEEL'))
            metadata_path = wheel_path.removesuffix('WHEEL') + 'METADATA'
            metadata = email.message_from_bytes(archive.read(metadata_path))
            wheel = email.message_from_bytes(archive.read(wheel_path))
            tag = wheel.get_all('Tag')[0]
            name = metadata['Name'].replace('-', '_')
            filename = f"{name}-{metadata['Version']}-{tag}.whl"
            data = path.read_bytes()
            offset = min(item.header_offset for item in archive.infolist())
            if data[offset:offset+4] != b'PK\x03\x04':
                continue
            (dest / filename).write_bytes(data[offset:])
            with zipfile.ZipFile(dest / filename) as check:
                if check.testzip() is not None:
                    raise ValueError('CRC failure')
            print(filename)
            count += 1
    except (StopIteration, ValueError, zipfile.BadZipFile, KeyError):
        continue
print('WHEELS', count)
