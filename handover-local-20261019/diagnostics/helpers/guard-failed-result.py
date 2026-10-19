from pathlib import Path
import sys,time
Path(sys.argv[1]).write_text('{"status":"failed","error":"test_failure"}',encoding="utf-8")
time.sleep(30)
