# subtitles.py - export/read/edit subtitles: srt, vtt, txt; merge/split cues; read text files with the right encoding
"""Pure-Python part (no Qt) shared by the GUI and the tests. Cue/parse/write for SRT live in srt.py."""
from __future__ import annotations

import os
import re

from .srt import Cue, fmt_time, parse_srt, to_srt

FORMATS = ("srt", "vtt", "txt")


def doc_van_ban(path: str) -> str:
    """Read a text file, trying in turn utf-8-sig, utf-16 (if there is a BOM), cp1258 (Windows Vietnamese), cp1252, latin-1."""
    with open(path, "rb") as f:
        raw = f.read()
    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        return raw.decode("utf-16")
    for enc in ("utf-8-sig", "cp1258", "cp1252"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("latin-1")


def srt_thanh_van_ban(raw: str, is_srt: bool = True) -> str:
    """Extract the text from .srt content (dropping sequence numbers + timestamps); anything that is not srt is returned unchanged."""
    if not (is_srt or "-->" in raw):
        return raw
    out = []
    for block in re.split(r"\n\s*\n", raw.replace("\r\n", "\n").strip()):
        lines = [x for x in block.split("\n") if x.strip()]
        lines = [x for x in lines if "-->" not in x and not re.fullmatch(r"\d+", x.strip())]
        if lines:
            out.append(" ".join(lines))
    return "\n".join(out)


def _vtt_time(sec: float) -> str:
    return fmt_time(sec).replace(",", ".")


def to_vtt(cues: list[Cue]) -> str:
    out = ["WEBVTT", ""]
    for c in cues:
        out.append(f"{_vtt_time(c.start)} --> {_vtt_time(c.end)}")
        out.append((c.text or "").strip())
        out.append("")
    return "\n".join(out)


def to_txt(cues: list[Cue]) -> str:
    return "\n".join((c.text or "").strip() for c in cues if (c.text or "").strip()) + "\n"


def render(cues: list[Cue], fmt: str) -> str:
    fmt = fmt.lower().lstrip(".")
    if fmt == "srt":
        return to_srt(cues)
    if fmt == "vtt":
        return to_vtt(cues)
    if fmt == "txt":
        return to_txt(cues)
    raise ValueError(f"Định dạng phụ đề không hỗ trợ: {fmt}")


def ghi(cues: list[Cue], path: str, fmt: str | None = None) -> str:
    """Atomic write (tmp → replace). fmt defaults to the file extension. Returns path."""
    fmt = fmt or os.path.splitext(path)[1]
    data = render(cues, fmt)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(data)
    os.replace(tmp, path)
    return path


def doc(path: str) -> list[Cue]:
    """Read .srt/.vtt into cues."""
    raw = doc_van_ban(path)
    if raw.lstrip().upper().startswith("WEBVTT"):
        raw = re.sub(r"^WEBVTT[^\n]*\n", "", raw.lstrip(), flags=re.I)
    return parse_srt(raw)


def danh_so(cues: list[Cue]) -> list[Cue]:
    for i, c in enumerate(cues, 1):
        c.idx = i
    return cues


def gop_cau(cues: list[Cue], i: int) -> list[Cue]:
    """Merge cue i with cue i+1 (keeping the time span from the start of i to the end of i+1)."""
    if not 0 <= i < len(cues) - 1:
        raise IndexError("Không có câu kế tiếp để gộp")
    a, b = cues[i], cues[i + 1]
    m = Cue(idx=a.idx, start=a.start, end=max(a.end, b.end), text=f"{(a.text or '').strip()} {(b.text or '').strip()}".strip(),
            meta=dict(a.meta))
    return danh_so(cues[:i] + [m] + cues[i + 2:])


def tach_cau(cues: list[Cue], i: int, vi_tri: int) -> list[Cue]:
    """Split cue i at character position `vi_tri`; the time is divided in proportion to the number of characters."""
    c = cues[i]
    text = c.text or ""
    left, right = text[:vi_tri].strip(), text[vi_tri:].strip()
    if not left or not right:
        raise ValueError("Vị trí tách phải nằm giữa câu")
    ratio = len(left) / max(1, len(left) + len(right))
    mid = c.start + (c.end - c.start) * ratio
    a = Cue(idx=c.idx, start=c.start, end=mid, text=left, meta=dict(c.meta))
    b = Cue(idx=c.idx + 1, start=mid, end=c.end, text=right, meta=dict(c.meta))
    return danh_so(cues[:i] + [a, b] + cues[i + 1:])


def ap_van_ban_da_sua(cues: list[Cue], van_ban: str) -> tuple[list[Cue], bool]:
    """Apply user-edited text (one cue per line) to the cues. Only applied when the number of lines matches the number of cues
    that have text; returns (cues, da_ap)."""
    lines = [x.strip() for x in van_ban.split("\n")]
    idx = [k for k, c in enumerate(cues) if (c.text or "").strip()]
    lines = [x for x in lines if x]
    if len(lines) != len(idx):
        return cues, False
    out = [Cue(idx=c.idx, start=c.start, end=c.end, text=c.text, dich=c.dich, meta=dict(c.meta)) for c in cues]
    for k, line in zip(idx, lines, strict=True):
        out[k].text = line
    return out, True


def tim_trong_lich_su(muc: list[dict], truy_van: str, truong: tuple[str, ...] = ("ten", "text", "file", "ghi_chu")) -> list[dict]:
    """Case- and diacritic-insensitive search over a list of history entries (dicts)."""
    import unicodedata

    def bo_dau(s: str) -> str:
        s = unicodedata.normalize("NFD", s.replace("đ", "d").replace("Đ", "D"))
        return "".join(ch for ch in s if unicodedata.category(ch) != "Mn").lower()
    q = bo_dau(truy_van).split()
    if not q:
        return list(muc)
    out = []
    for m in muc:
        hay = bo_dau(" ".join(str(m.get(k, "")) for k in truong))
        if all(t in hay for t in q):
            out.append(m)
    return out
