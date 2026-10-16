# dubbing.py - lồng tiếng tối thiểu: phụ đề .srt → từng câu đọc bằng TTS → ghép đúng mốc thời gian → một file âm thanh
"""THỬ NGHIỆM.

Cách làm: mỗi cue được đọc bằng `synth(text) -> đường dẫn file`; clip dài hơn khe thời gian thì tăng tốc (atempo, tối đa
MAX_SPEEDUP) — vẫn dài hơn thì để tràn (câu sau bị đẩy lùi, không chồng lên). Kết quả là WAV mono 24 kHz (hoặc mp3/m4a
theo đuôi file đích, mã hoá bằng ffmpeg).

Thuần Python + ffmpeg qua procutil; `synth` được tiêm vào nên kiểm thử không cần mạng.
"""
from __future__ import annotations

import os
import shutil
import tempfile
from collections.abc import Callable

import numpy as np
import soundfile as sf

from . import procutil
from .srt import Cue

SR = 24000
MAX_SPEEDUP = 1.6
MIN_CLIP_S = 0.05


class DubError(RuntimeError):
    """Lỗi lồng tiếng (đã có thông báo tiếng Việt)."""


def _ff(ffmpeg: str, args: list[str], timeout: int = 600):
    r = procutil.run([ffmpeg, "-hide_banner", "-loglevel", "error", "-y", *args], capture_output=True, timeout=timeout)
    if r.returncode != 0:
        tail = (r.stderr or b"").decode("utf-8", "replace").strip().splitlines()[-1:] or ["không rõ"]
        raise DubError(f"ffmpeg lỗi: {tail[0][:200]}")


def _atempo_chain(factor: float) -> str:
    """atempo chỉ nhận 0.5–2.0 mỗi bước."""
    parts = []
    f = factor
    while f > 2.0:
        parts.append("atempo=2.0")
        f /= 2.0
    parts.append(f"atempo={f:.4f}")
    return ",".join(parts)


def _load_clip(ffmpeg: str, src: str, work: str, tag: str, speed: float = 1.0) -> np.ndarray:
    wav = os.path.join(work, f"{tag}.wav")
    af = ["-af", _atempo_chain(speed)] if speed > 1.001 else []
    _ff(ffmpeg, ["-i", src, *af, "-ac", "1", "-ar", str(SR), "-c:a", "pcm_s16le", wav])
    data, sr = sf.read(wav, dtype="float32", always_2d=False)
    if sr != SR:
        raise DubError("Sai tần số lấy mẫu sau chuyển đổi")
    return data if data.ndim == 1 else data.mean(axis=1)


def lap_thoi_gian(cues: list[Cue], clip_lens: list[float]) -> list[tuple[float, float]]:
    """Từ danh sách độ dài clip (đã gồm tăng tốc) → [(bắt đầu thực, kết thúc thực)]; không cho hai clip chồng nhau."""
    out = []
    cur = 0.0
    for c, ln in zip(cues, clip_lens, strict=True):
        st = max(c.start, cur)
        out.append((st, st + ln))
        cur = st + ln
    return out


def dub_cues(cues: list[Cue], synth: Callable[[str], str], ffmpeg: str, out_path: str,
             on_progress: Callable[[int, str], None] | None = None,
             should_cancel: Callable[[], bool] | None = None,
             on_log: Callable[[str], None] | None = None, total_dur: float | None = None) -> dict:
    """Trả về thống kê: {'cues', 'doc', 'tang_toc', 'tran', 'dai_giay', 'bo_qua'}."""
    prog = on_progress or (lambda p, s: None)
    log = on_log or (lambda m: None)
    cancel = should_cancel or (lambda: False)
    items = [c for c in cues if (c.text or "").strip()]
    if not items:
        raise DubError("Không có câu nào có chữ để đọc.")
    if not ffmpeg or not os.path.exists(ffmpeg):
        raise DubError("Không tìm thấy ffmpeg.")
    work = tempfile.mkdtemp(prefix="dub_")
    try:
        clips: list[np.ndarray] = []
        stats = {"cues": len(items), "doc": 0, "tang_toc": 0, "tran": 0, "bo_qua": 0}
        n = len(items)
        for i, c in enumerate(items):
            if cancel():
                raise DubError("Đã huỷ lồng tiếng.")
            prog(5 + int(80 * i / n), f"Đọc câu {i + 1}/{n}")
            try:
                src = synth(c.text.strip())
                y = _load_clip(ffmpeg, src, work, f"c{i}")
            except DubError:
                raise
            except Exception as e:
                log(f"   ⚠ bỏ qua câu {i + 1}: {e}")
                stats["bo_qua"] += 1
                clips.append(np.zeros(0, dtype="float32"))
                continue
            slot = max(MIN_CLIP_S, c.end - c.start)
            ln = len(y) / SR
            if ln > slot * 1.02:
                need = min(MAX_SPEEDUP, ln / slot)
                if need > 1.02:
                    y = _load_clip(ffmpeg, src, work, f"c{i}s", speed=need)
                    stats["tang_toc"] += 1
            stats["doc"] += 1
            clips.append(y)
        prog(88, "Ghép theo mốc thời gian")
        spans = lap_thoi_gian(items, [len(y) / SR for y in clips])
        stats["tran"] = sum(1 for (st, _e), c in zip(spans, items, strict=True) if st > c.start + 0.25)
        end = max((e for _s, e in spans), default=0.0)
        if total_dur:
            end = max(end, total_dur)
        buf = np.zeros(int(end * SR) + SR // 2, dtype="float32")
        for (st, _e), y in zip(spans, clips, strict=True):
            a = int(st * SR)
            buf[a:a + len(y)] += y[:max(0, len(buf) - a)]
        np.clip(buf, -1.0, 1.0, out=buf)
        stats["dai_giay"] = round(len(buf) / SR, 2)
        ext = os.path.splitext(out_path)[1].lower()
        os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
        tmp = out_path + ".tmp" + ext
        if ext == ".wav":
            sf.write(tmp, buf, SR, subtype="PCM_16")
        else:
            wav = os.path.join(work, "mix.wav")
            sf.write(wav, buf, SR, subtype="PCM_16")
            _ff(ffmpeg, ["-i", wav, "-b:a", "128k", tmp])
        os.replace(tmp, out_path)
        prog(100, "Xong")
        return stats
    finally:
        shutil.rmtree(work, ignore_errors=True)
