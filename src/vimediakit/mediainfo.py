# mediainfo.py - đọc kích thước / thời lượng video mà KHÔNG cần ffprobe.exe (chỉ cần ffmpeg)
"""probe(ffmpeg, path) -> (width, height, duration_giây). Ưu tiên ffprobe nếu nằm cạnh ffmpeg; không có thì phân tích
stderr của `ffmpeg -i`. Ném ValueError nếu không đọc được."""
from __future__ import annotations

import os
import re

from . import procutil

_RE_DUR = re.compile(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)")
_RE_VID = re.compile(r"Stream #\S+.*?Video:.*?,\s*(\d{2,5})x(\d{2,5})")


def parse_ffmpeg_i(stderr: str) -> tuple[int, int, float]:
    m = _RE_VID.search(stderr or "")
    if not m:
        raise ValueError("không thấy luồng video")
    w, h = int(m.group(1)), int(m.group(2))
    d = _RE_DUR.search(stderr)
    dur = int(d.group(1)) * 3600 + int(d.group(2)) * 60 + float(d.group(3)) if d else 0.0
    return w, h, dur


def probe(ffmpeg: str, path: str) -> tuple[int, int, float]:
    probe_exe = os.path.join(os.path.dirname(ffmpeg), "ffprobe.exe") if ffmpeg.lower().endswith(".exe") else "ffprobe"
    if os.path.isfile(probe_exe) or not ffmpeg.lower().endswith(".exe"):
        try:
            r = procutil.run([probe_exe, "-v", "error", "-select_streams", "v:0", "-show_entries",
                                "stream=width,height:format=duration", "-of", "csv=p=0", path],
                               capture_output=True, text=True, timeout=30)
            parts = [x for x in r.stdout.replace("\n", ",").split(",") if x.strip()]
            return int(parts[0]), int(parts[1]), float(parts[-1])
        except Exception:
            pass
    r = procutil.run([ffmpeg, "-hide_banner", "-i", path], capture_output=True, text=True, errors="replace", timeout=30)
    return parse_ffmpeg_i(r.stderr)
