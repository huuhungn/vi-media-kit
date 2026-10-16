"""Export/read/edit subtitles: golden files for srt/vtt/txt, merge/split, encoding detection, history search, theme, JobManager."""
import pytest

from vimediakit import subtitles as SUB
from vimediakit import theme
from vimediakit.srt import Cue


def _cues():
    return [Cue(idx=1, start=0.0, end=1.5, text="Xin chào"),
            Cue(idx=2, start=2.0, end=3.25, text="các bạn"),
            Cue(idx=3, start=61.5, end=3600.5, text="Tạm biệt.")]


SRT = """1
00:00:00,000 --> 00:00:01,500
Xin chào

2
00:00:02,000 --> 00:00:03,250
các bạn

3
00:01:01,500 --> 01:00:00,500
Tạm biệt.
"""

VTT = """WEBVTT

00:00:00.000 --> 00:00:01.500
Xin chào

00:00:02.000 --> 00:00:03.250
các bạn

00:01:01.500 --> 01:00:00.500
Tạm biệt.
"""


def test_golden_srt_vtt_txt():
    assert SUB.render(_cues(), "srt") == SRT
    assert SUB.render(_cues(), "vtt") == VTT
    assert SUB.render(_cues(), ".txt") == "Xin chào\ncác bạn\nTạm biệt.\n"
    with pytest.raises(ValueError):
        SUB.render(_cues(), "ass")


def test_ghi_va_doc_lai(tmp_path):
    for fmt in ("srt", "vtt"):
        p = SUB.ghi(_cues(), str(tmp_path / f"a.{fmt}"))
        back = SUB.doc(p)
        assert [c.text for c in back] == ["Xin chào", "các bạn", "Tạm biệt."]
        assert abs(back[2].end - 3600.5) < 0.01
    assert not list(tmp_path.glob("*.tmp"))


def test_doc_van_ban_nhieu_ma_hoa(tmp_path):
    s = "Việt Nam đẹp lắm"
    for enc in ("utf-8", "utf-8-sig", "utf-16"):
        p = tmp_path / f"{enc}.txt"
        p.write_bytes(s.encode(enc))
        assert SUB.doc_van_ban(str(p)) == s, enc
    # cp1258 (older Vietnamese Windows): can only encode characters that exist in the code page
    s2 = "Xin chào các bác, đây là tôi"
    p = tmp_path / "cp1258.txt"
    p.write_bytes(s2.encode("cp1258"))
    assert SUB.doc_van_ban(str(p)) == s2


def test_srt_thanh_van_ban():
    assert SUB.srt_thanh_van_ban(SRT) == "Xin chào\ncác bạn\nTạm biệt."
    assert SUB.srt_thanh_van_ban("chỉ là văn bản", is_srt=False) == "chỉ là văn bản"


def test_gop_va_tach_cau():
    cs = SUB.gop_cau(_cues(), 0)
    assert len(cs) == 2 and cs[0].text == "Xin chào các bạn" and cs[0].end == 3.25 and [c.idx for c in cs] == [1, 2]
    t = SUB.tach_cau(cs, 0, len("Xin chào"))
    assert [c.text for c in t] == ["Xin chào", "các bạn", "Tạm biệt."]
    assert t[0].start == 0.0 and t[0].end == pytest.approx(t[1].start) and t[1].end == 3.25
    with pytest.raises(ValueError):
        SUB.tach_cau(cs, 0, 0)
    with pytest.raises(IndexError):
        SUB.gop_cau(cs, 1)


def test_ap_van_ban_da_sua():
    cs = _cues()
    out, ok = SUB.ap_van_ban_da_sua(cs, "Chào\nbạn\nTạm biệt nhé.")
    assert ok and [c.text for c in out] == ["Chào", "bạn", "Tạm biệt nhé."] and cs[0].text == "Xin chào"
    out2, ok2 = SUB.ap_van_ban_da_sua(cs, "chỉ một dòng")
    assert not ok2 and out2 is cs


def test_tim_lich_su_khong_dau():
    muc = [{"ten": "Bài giảng Toán", "file": "a.mp4"}, {"ten": "Phim hoạt hình", "file": "b.mp4"}]
    assert SUB.tim_trong_lich_su(muc, "giang toan") == [muc[0]]
    assert SUB.tim_trong_lich_su(muc, "HOAT hinh") == [muc[1]]
    assert SUB.tim_trong_lich_su(muc, "") == muc


def test_theme_token_va_resolve():
    assert theme.resolve("auto", True) == "dark" and theme.resolve("auto", False) == "light"
    assert theme.resolve("light", True) == "light" and theme.resolve("???", False) == "light"
    for name in ("dark", "light"):
        q = theme.build_qss(name)
        assert theme.TOKENS[name]["bg"] in q and theme.ACCENT in q
    assert theme.TOKENS["dark"]["bg"] != theme.TOKENS["light"]["bg"]


def test_job_manager_mot_viec_va_huy(qapp_core):
    import time

    from vimediakit import jobs

    mgr = jobs.JobManager()
    seen = []

    def long(prog, log, cancel):
        while not cancel():
            time.sleep(0.01)
        return "x"
    t1 = jobs.Task(long)
    t1.err.connect(lambda m: seen.append(("err", m)))
    assert mgr.start(t1)
    t2 = jobs.Task(lambda p, l, c: 1)
    assert not mgr.start(t2)             # busy → rejected
    assert mgr.shutdown(3000)
    assert not mgr.busy()
    assert t1.exc is not None and isinstance(t1.exc, jobs.Cancelled)


def test_task_phat_err_ca_voi_baseexception(qapp_core):
    from vimediakit import jobs
    got = []

    def boom(prog, log, cancel):
        raise KeyboardInterrupt("x")
    t = jobs.Task(boom)
    t.err.connect(got.append)
    t.start()
    t.wait(3000)
    qapp_core.processEvents()
    assert got and "KeyboardInterrupt" in got[0]
