# procutil.py - run child processes without flashing a console window (windowed exe builds on Windows)
"""Use in place of `subprocess.run/Popen` for ffmpeg, nvidia-smi...: adds CREATE_NO_WINDOW on Windows."""
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
