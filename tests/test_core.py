"""The small modules: srt, errors, netmode, history, diagnostics, hwprofile, mediainfo."""
import json
import urllib.error
import zipfile

import pytest

from vimediakit import diagnostics, errors, history, hwprofile, mediainfo, netmode
from vimediakit.srt import Cue, fmt_time, parse_srt, parse_time, to_srt


def test_srt_khu_hoi_doc_ghi():
    cues = [Cue(1, 0.0, 1.5, "Xin chào"), Cue(2, 3661.007, 3662.0, "dòng 1\ndòng 2")]
    assert fmt_time(3661.007) == "01:01:01,007"
    back = parse_srt(to_srt(cues))
    assert [(c.start, c.end, c.text) for c in back] == [(0.0, 1.5, "Xin chào"), (3661.007, 3662.0, "dòng 1\ndòng 2")]


def test_srt_chiu_loi_dinh_dang():
    raw = "﻿1\r\n00:00:01.5 --> 00:00:02.25\r\nA\r\n\r\nrác không có mốc\r\n\r\n00:00:03,000 --> 00:00:04,000\r\nB\r\n"
    cues = parse_srt(raw.lstrip("﻿"))
    assert [(c.start, c.end, c.text) for c in cues] == [(1.5, 2.25, "A"), (3.0, 4.0, "B")]
    assert parse_time("0:0:5") == 5.0
    with pytest.raises(ValueError):
        parse_time("abc")


def test_errors_thong_bao_tieng_viet():
    assert "mạng" in errors.thong_bao(urllib.error.URLError("x"))
    assert "quyền" in errors.thong_bao(PermissionError())
    assert "RAM" in errors.thong_bao(MemoryError())
    assert errors.thong_bao(netmode.OfflineError("đang offline")) == "đang offline"
    assert "RuntimeError" in errors.thong_bao(RuntimeError("lạ"))


def test_netmode_env_va_ghi_de(monkeypatch):
    monkeypatch.setenv("VIMEDIA_OFFLINE", "1")
    netmode.set_offline(None)
    assert netmode.is_offline()
    with pytest.raises(netmode.OfflineError):
        netmode.require_online("tải model")
    netmode.set_offline(False)
    try:
        netmode.require_online()
    finally:
        netmode.set_offline(None)


def test_history_nguyen_tu_va_gioi_han(tmp_path):
    d = str(tmp_path)
    for i in range(5):
        history.add(d, f"f{i}.wav", "chữ " * 100, max_items=3)
    items = history.load(d)
    assert [x["ten"] for x in items] == ["f4.wav", "f3.wav", "f2.wav"]
    assert len(items[0]["text"]) <= 200
    history.add(d, "f3.wav", "mới", max_items=3)
    assert history.load(d)[0]["ten"] == "f3.wav" and len(history.load(d)) == 3
    history.clear(d)
    assert history.load(d) == []


def test_diagnostics_che_bi_mat_va_zip(tmp_path):
    assert diagnostics.che_bi_mat({"api_key": "abc", "ten": "x", "n": {"Token": "t", "ok": 1}, "rong": {"key": ""}}) == {
        "api_key": "***", "ten": "x", "n": {"Token": "***", "ok": 1}, "rong": {"key": ""}}
    data = tmp_path / "data"
    (data / "logs").mkdir(parents=True)
    (data / "logs" / "app.log").write_text("dòng log", encoding="utf-8")
    (data / "settings.json").write_text(json.dumps({"password": "hunter2", "theme": "dark"}), encoding="utf-8")
    out = diagnostics.xuat(str(data), str(tmp_path / "chan_doan.zip"), app_version="9.9")
    with zipfile.ZipFile(out) as z:
        names = z.namelist()
        assert {"may.json", "thiet_lap.json", "logs/app.log"} <= set(names)
        assert "hunter2" not in z.read("thiet_lap.json").decode()
        assert json.loads(z.read("may.json"))["phien_ban_app"] == "9.9"


def test_hwprofile_goi_y():
    gpu = hwprofile.Hardware(gpu_name="X", vram_mb=8000, cuda_devices=1, cuda_libs=True, cpu_cores=8, ram_gb=32)
    p = hwprofile.recommend(gpu)
    assert p.device == "cuda" and p.model == "large-v3-turbo"
    yeu = hwprofile.Hardware(cpu_cores=2, cpu_threads=4, ram_gb=4)
    p = hwprofile.recommend(yeu)
    assert p.device == "cpu" and p.model == "base"
    cpu = hwprofile.Hardware(cpu_cores=8, cpu_threads=16, ram_gb=16)
    p = hwprofile.recommend(cpu)
    assert p.device == "cpu" and p.model == "small" and 1 <= p.cpu_threads <= 8
    assert hwprofile.tom_tat(cpu, p)


def test_mediainfo_phan_tich_stderr_ffmpeg():
    err = ("  Duration: 00:01:02.50, start: 0.0, bitrate: 900 kb/s\n"
           "  Stream #0:0: Video: h264 (High), yuv420p, 1280x720 [SAR 1:1], 30 fps\n")
    assert mediainfo.parse_ffmpeg_i(err) == (1280, 720, 62.5)
    with pytest.raises(ValueError):
        mediainfo.parse_ffmpeg_i("không có gì")
