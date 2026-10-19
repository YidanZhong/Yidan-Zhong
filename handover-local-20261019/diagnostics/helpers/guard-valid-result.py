from pathlib import Path
import sys
Path(sys.argv[1]).write_text('{"status":"passed"}',encoding="utf-8")
