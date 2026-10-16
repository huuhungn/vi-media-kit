# render_min.py - minimal video export: burn subtitles into the picture (hard-sub) and/or replace the audio track
"""EXPERIMENTAL.

ffmpeg runs with its cwd set to a temporary directory holding an ASCII-named subtitle file, to avoid escaping problems with `\\`, `:`
and Vietnamese diacritics in the `subtitles=` filter. Progress comes from `-progress pipe:1`; cancellable (terminates ffmpeg).
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from collections.abc import Callable

from . import procutil

STYLE = "FontName=Arial,FontSize=22,PrimaryColour=&H00FFFFFF&,OutlineColour=&H00000000&,BorderStyle=1,Outline=2,Shadow=0,MarginV=28"


class RenderError(RuntimeError):
    """Video export error (the message is already in Vietnamese)."""


def duration_of(ffmpeg: str, media: str) -> float:
    r = procutil.run([ffmpeg, "-hide_banner", "-i", media], capture_output=True, timeout=60)
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", (r.stderr or b"").decode("utf-8", "replace"))
    if not m:
        return 0.0
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))


def build_cmd(ffmpeg: str, video: str, sub_name: str | None, audio: str | None, out: str, crf: int = 20) -> list[str]:
    cmd = [ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-progress", "pipe:1", "-nostats", "-i", video]
    if audio:
        cmd += ["-i", audio]
    if sub_name:
        cmd += ["-vf", f"subtitles={sub_name}:force_style='{STYLE}'", "-c:v", "libx264", "-preset", "veryfast", "-crf", str(crf),
                "-pix_fmt", "yuv420p"]
    else:
        cmd += ["-c:v", "copy"]
    if audio:
        cmd += ["-map", "0:v:0", "-map", "1:a:0", "-c:a", "aac", "-b:a", "160k", "-shortest"]
    else:
        cmd += ["-map", "0:v:0", "-map", "0:a?", "-c:a", "copy"]
    return cmd + ["-movflags", "+faststart", out]


def render(ffmpeg: str, video: str, out_path: str, srt: str | None = None, audio: str | None = None,
           on_progress: Callable[[int, str], None] | None = None,
           should_cancel: Callable[[], bool] | None = None) -> str:
    """Burn subtitles into the video (srt) and/or replace the audio (audio). Writes to a temporary file, then renames it."""
    prog = on_progress or (lambda p, s: None)
    cancel = should_cancel or (lambda: False)
    if not (srt or audio):
        raise RenderError("Chưa chọn phụ đề hoặc âm thanh để ghép.")
    if not ffmpeg or not os.path.exists(ffmpeg):
        raise RenderError("Không tìm thấy ffmpeg.")
    for p, ten in ((video, "video"), (srt, "phụ đề"), (audio, "âm thanh")):
        if p and not os.path.isfile(p):
            raise RenderError(f"Không tìm thấy file {ten}: {os.path.basename(p)}")
    if os.path.abspath(out_path) == os.path.abspath(video):
        raise RenderError("File đích trùng file video gốc.")
    total = duration_of(ffmpeg, video)
    work = tempfile.mkdtemp(prefix="render_")
    tmp_out = os.path.join(work, "out.mp4")
    try:
        sub_name = None
        if srt:
            sub_name = "sub.srt"
            shutil.copyfile(srt, os.path.join(work, sub_name))
        cmd = build_cmd(ffmpeg, os.path.abspath(video), sub_name, os.path.abspath(audio) if audio else None, tmp_out)
        proc = procutil.popen(cmd, cwd=work, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                              encoding="utf-8", errors="replace")
        prog(1, "Đang xuất video")
        assert proc.stdout is not None
        for line in proc.stdout:
            if cancel():
                proc.terminate()
                proc.wait(10)
                raise RenderError("Đã huỷ xuất video.")
            m = re.match(r"out_time_(?:ms|us)=(\d+)", line)
            if m and total > 0:
                sec = int(m.group(1)) / 1_000_000
                prog(min(98, 1 + int(97 * sec / total)), f"Đang xuất video {int(sec)}/{int(total)} s")
        err = proc.stderr.read() if proc.stderr else ""
        rc = proc.wait()
        if rc != 0 or not os.path.isfile(tmp_out) or os.path.getsize(tmp_out) == 0:
            last = [x for x in err.strip().splitlines() if x.strip()][-1:] or ["không rõ"]
            raise RenderError(f"ffmpeg không xuất được video: {last[0][:200]}")
        os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
        part = out_path + ".part"
        shutil.move(tmp_out, part)
        os.replace(part, out_path)
        prog(100, "Xong")
        return out_path
    finally:
        shutil.rmtree(work, ignore_errors=True)
