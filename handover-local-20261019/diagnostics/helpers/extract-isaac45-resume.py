import concurrent.futures, json, pathlib, shutil, time, zipfile, os, zlib
root=pathlib.Path(r'D:\RAVEN-4060')
target=root/'isaac45'
target.mkdir(exist_ok=True)
started=time.monotonic()
def status(data):
    data['elapsed_s']=round(time.monotonic()-started,1)
    (root/'setup'/'isaac45-extract-status.json').write_text(json.dumps(data))
    print(json.dumps(data),flush=True)
with zipfile.ZipFile(root/'setup'/'isaac-sim-4.5.0-windows.zip') as archive:
    entries=archive.infolist()
    for item in entries:
        p=pathlib.PureWindowsPath(item.filename)
        if p.is_absolute() or p.drive or p.root or '..' in p.parts or ':' in item.filename:
            raise RuntimeError('Unsafe archive member: '+item.filename)
    status({'phase':'validated','total_files':len(entries)})
    def extract(item):
        destination=pathlib.Path('\\\\?\\'+str(target/item.filename))
        if item.is_dir():
            destination.mkdir(parents=True,exist_ok=True)
            return 0
        destination.parent.mkdir(parents=True,exist_ok=True)
        if destination.exists() and destination.stat().st_size==item.file_size:
            crc=0
            with destination.open('rb') as stream:
                for block in iter(lambda:stream.read(1024*1024),b''):
                    crc=zlib.crc32(block,crc)
            if crc==item.CRC: return item.file_size
        with archive.open(item) as source, destination.open('wb') as output:
            shutil.copyfileobj(source,output,1024*1024)
        return item.file_size
    count=size=0
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        for value in pool.map(extract,entries):
            count+=1; size+=value
            if count%2000==0:
                status({'phase':'extract','files':count,'total_files':len(entries),'extracted_bytes':size})
status({'phase':'complete','files':count,'extracted_bytes':size,'crc':'all extracted or resumed members passed'})
