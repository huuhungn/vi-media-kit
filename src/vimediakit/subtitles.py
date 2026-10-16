# subtitles.py - xuất/đọc/sửa phụ đề: srt, vtt, txt; gộp/tách câu; đọc file văn bản đúng mã hoá
"""Phần thuần Python (không Qt) để GUI và kiểm thử dùng chung. Cue/parse/ghi SRT nằm ở srt.py."""
from __future__ import annotations

import os
import re

from .srt import Cue, fmt_time, parse_srt, to_srt

FORMATS = ("srt", "vtt", "txt")


def doc_van_ban(path: str) -> str:
    """Đọc file văn bản thử lần lượt utf-8-sig, utf-16 (nếu có BOM), cp1258 (tiếng Việt Windows), cp1252, latin-1."""
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
    """Rút phần chữ từ nội dung .srt (bỏ số thứ tự + mốc thời gian); không phải srt thì trả nguyên."""
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
    """Ghi nguyên tử (tmp → replace). fmt mặc định theo đuôi file. Trả về path."""
    fmt = fmt or os.path.splitext(path)[1]
    data = render(cues, fmt)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(data)
    os.replace(tmp, path)
    return path


def doc(path: str) -> list[Cue]:
    """Đọc .srt/.vtt thành cue."""
    raw = doc_van_ban(path)
    if raw.lstrip().upper().startswith("WEBVTT"):
        raw = re.sub(r"^WEBVTT[^\n]*\n", "", raw.lstrip(), flags=re.I)
    return parse_srt(raw)


def danh_so(cues: list[Cue]) -> list[Cue]:
    for i, c in enumerate(cues, 1):
        c.idx = i
    return cues


def gop_cau(cues: list[Cue], i: int) -> list[Cue]:
    """Gộp câu i với câu i+1 (giữ thời gian từ đầu i đến cuối i+1)."""
    if not 0 <= i < len(cues) - 1:
        raise IndexError("Không có câu kế tiếp để gộp")
    a, b = cues[i], cues[i + 1]
    m = Cue(idx=a.idx, start=a.start, end=max(a.end, b.end), text=f"{(a.text or '').strip()} {(b.text or '').strip()}".strip(),
            meta=dict(a.meta))
    return danh_so(cues[:i] + [m] + cues[i + 2:])


def tach_cau(cues: list[Cue], i: int, vi_tri: int) -> list[Cue]:
    """Tách câu i tại vị trí ký tự `vi_tri`; chia thời gian theo tỉ lệ số ký tự."""
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
    """Áp phần chữ người dùng đã sửa (mỗi dòng một câu) lên các cue. Chỉ áp khi số dòng khớp số cue có chữ;
    trả (cues, da_ap)."""
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
    """Tìm không phân biệt hoa/thường và dấu trong danh sách mục lịch sử (dict)."""
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
