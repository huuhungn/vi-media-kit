# procutil.py - chạy tiến trình con không nháy cửa sổ console (bản exe windowed trên Windows)
"""Dùng thay `subprocess.run/Popen` cho ffmpeg, nvidia-smi...: thêm CREATE_NO_WINDOW trên Windows."""
from __future__ import annotations

import subprocess
import sys

_FLAGS = getattr(subprocess, "CREATE_NO_WINDOW", 0) if sys.platform == "win32" else 0


def run(cmd, **kw):
    if _FLAGS:
        kw.setdefault("creationflags", _FLAGS)
    return subprocess.run(cmd, **kw)


def popen(cmd, **kw):
    if _FLAGS:
        kw.setdefault("creationflags", _FLAGS)
    return subprocess.Popen(cmd, **kw)
