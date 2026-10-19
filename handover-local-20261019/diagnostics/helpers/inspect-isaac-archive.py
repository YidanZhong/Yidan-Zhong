import zipfile
from pathlib import Path
with zipfile.ZipFile(r'D:\RAVEN-4060\setup\isaac-sim-4.5.0-windows.zip') as z:
    print('FILES',len(z.infolist()))
    print('UNCOMPRESSED_BYTES',sum(i.file_size for i in z.infolist()))
    for name in ['post_install.bat','python.bat','setup_python_env.bat','VERSION']:
        if name in z.namelist():
            print('\nFILE:',name)
            print(z.read(name).decode('utf-8',errors='replace')[:12000])
