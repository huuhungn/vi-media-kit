# srt.py - read/write SRT subtitles (newly written, standalone)
"""Cue = one subtitle cue. `parse_srt` tolerates CRLF, missing sequence numbers, and '.' instead of ',' in timestamps."""
from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class Cue:
    idx: int
    start: float
    end: float
    text: str = ""
    dich: str = ""
    meta: dict = field(default_factory=dict)


_TS = re.compile(r"(\d+):(\d{1,2}):(\d{1,2})(?:[.,](\d{1,3}))?")
_ARROW = re.compile(r"(\S+)\s*-->\s*(\S+)")


def fmt_time(sec: float) -> str:
    """Seconds → 'HH:MM:SS,mmm' (rounded to the millisecond, never negative)."""
    ms = max(0, round(float(sec) * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def parse_time(text: str) -> float:
    m = _TS.fullmatch(text.strip())
    if not m:
        raise ValueError(f"Mốc thời gian không hợp lệ: {text!r}")
    h, mi, s, frac = m.groups()
    return int(h) * 3600 + int(mi) * 60 + int(s) + (int((frac or "0").ljust(3, "0")) / 1000)


def parse_srt(raw: str) -> list[Cue]:
    cues: list[Cue] = []
    for block in re.split(r"\n\s*\n", raw.replace("\r\n", "\n").replace("\r", "\n").strip()):
        lines = [x for x in block.split("\n") if x.strip()]
        k = next((i for i, x in enumerate(lines) if "-->" in x), None)
        if k is None:
            continue
        m = _ARROW.search(lines[k])
        if not m:
            continue
        try:
            start, end = parse_time(m.group(1)), parse_time(m.group(2))
        except ValueError:
            continue
        text = "\n".join(x.strip() for x in lines[k + 1:])
        cues.append(Cue(len(cues) + 1, start, max(start, end), text))
    return cues


def to_srt(cues: list[Cue]) -> str:
    out = []
    for i, c in enumerate(cues, 1):
        out.append(f"{i}\n{fmt_time(c.start)} --> {fmt_time(c.end)}\n{(c.text or '').strip()}\n")
    return "\n".join(out)
