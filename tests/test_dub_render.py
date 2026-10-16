"""Dubbing + minimal video export: exact timestamp placement, speed-up when too long, cancellation, real subtitle burn-in with ffmpeg."""
import os
import shutil
import subprocess

import numpy as np
import pytest
import soundfile as sf

from vimediakit import dubbing, render_min
from vimediakit.srt import Cue

FF = shutil.which("ffmpeg")
needs_ff = pytest.mark.skipif(not FF, reason="ffmpeg is not available on the test machine")


def _tone(path, seconds, freq=440.0, sr=24000):
    t = np.arange(int(seconds * sr)) / sr
    sf.write(path, (0.4 * np.sin(2 * np.pi * freq * t)).astype("float32"), sr)
    return path


def test_lap_thoi_gian_khong_chong_nhau():
    cues = [Cue(1, 0.0, 1.0, "a"), Cue(2, 0.5, 1.5, "b"), Cue(3, 10.0, 11.0, "c")]
    spans = dubbing.lap_thoi_gian(cues, [2.0, 1.0, 1.0])
    assert spans == [(0.0, 2.0), (2.0, 3.0), (10.0, 11.0)]


def test_atempo_chain_chia_buoc_toi_da_2x():
    assert dubbing._atempo_chain(1.5) == "atempo=1.5000"
    assert dubbing._atempo_chain(3.0) == "atempo=2.0,atempo=1.5000"


@needs_ff
def test_dub_ghep_dung_moc_va_tang_toc(tmp_path):
    cues = [Cue(1, 1.0, 2.0, "một"), Cue(2, 4.0, 4.5, "hai dài hơn khe"), Cue(3, 4.6, 5.6, "ba")]
    lens = {"một": 0.8, "hai dài hơn khe": 1.0, "ba": 0.5}

    def synth(text):
        return _tone(str(tmp_path / f"{abs(hash(text))}.wav"), lens[text])
    out = str(tmp_path / "dub.wav")
    st = dubbing.dub_cues(cues, synth, FF, out)
    assert st["doc"] == 3 and st["tang_toc"] == 1 and st["bo_qua"] == 0
    y, sr = sf.read(out)
    assert sr == 24000
    # the 0–1 s stretch is silent; there is sound around 1.0–1.8 s
    assert np.abs(y[: int(0.9 * sr)]).max() < 1e-3
    assert np.abs(y[int(1.1 * sr): int(1.7 * sr)]).max() > 0.2
    # cue 2 starts at 4.0 s and has sound
    assert np.abs(y[int(4.05 * sr): int(4.4 * sr)]).max() > 0.2
    assert not os.path.exists(out + ".tmp.wav")


@needs_ff
def test_dub_cau_loi_duoc_bo_qua_va_huy(tmp_path):
    cues = [Cue(1, 0.0, 1.0, "tốt"), Cue(2, 1.0, 2.0, "hỏng")]

    def synth(text):
        if text == "hỏng":
            raise RuntimeError("TTS lỗi")
        return _tone(str(tmp_path / "ok.wav"), 0.5)
    st = dubbing.dub_cues(cues, synth, FF, str(tmp_path / "o.wav"))
    assert st["doc"] == 1 and st["bo_qua"] == 1
    with pytest.raises(dubbing.DubError, match="huỷ"):
        dubbing.dub_cues(cues, synth, FF, str(tmp_path / "o2.wav"), should_cancel=lambda: True)
    assert not (tmp_path / "o2.wav").exists()


def test_dub_khong_co_chu_hoac_thieu_ffmpeg(tmp_path):
    with pytest.raises(dubbing.DubError, match="Không có câu"):
        dubbing.dub_cues([Cue(1, 0, 1, "  ")], lambda t: "", "x", str(tmp_path / "a.wav"))
    with pytest.raises(dubbing.DubError, match="ffmpeg"):
        dubbing.dub_cues([Cue(1, 0, 1, "a")], lambda t: "", str(tmp_path / "khong_co.exe"), str(tmp_path / "a.wav"))


def test_render_kiem_tra_dau_vao(tmp_path):
    with pytest.raises(render_min.RenderError, match="Chưa chọn"):
        render_min.render("ff", "v", "o")
    ff = tmp_path / "ffmpeg.exe"
    ff.write_bytes(b"x")
    with pytest.raises(render_min.RenderError, match="Không tìm thấy file video"):
        render_min.render(str(ff), str(tmp_path / "khong.mp4"), str(tmp_path / "o.mp4"), srt=str(ff))
    v = tmp_path / "v.mp4"
    v.write_bytes(b"x")
    with pytest.raises(render_min.RenderError, match="trùng"):
        render_min.render(str(ff), str(v), str(v), srt=str(v))


def test_build_cmd_burn_in_va_thay_audio():
    c = render_min.build_cmd("ff", "v.mp4", "sub.srt", None, "o.mp4")
    assert "subtitles=sub.srt" in " ".join(c) and "libx264" in c and c[-1] == "o.mp4"
    c2 = render_min.build_cmd("ff", "v.mp4", None, "a.wav", "o.mp4")
    assert "copy" in c2 and "aac" in c2 and "1:a:0" in c2


@needs_ff
def test_render_burn_in_that_voi_ten_tieng_viet_co_dau(tmp_path):
    src = tmp_path / "Video thử nghiệm ✓.mp4"
    r = subprocess.run([FF, "-y", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc=size=320x180:rate=15:duration=2",
                        "-f", "lavfi", "-i", "sine=frequency=300:duration=2", "-shortest", "-pix_fmt", "yuv420p", str(src)],
                       capture_output=True)
    assert r.returncode == 0, r.stderr
    srt = tmp_path / "phụ đề: thử.srt"
    srt.write_text("1\n00:00:00,200 --> 00:00:01,500\nXin chào các bạn\n", encoding="utf-8")
    out = tmp_path / "kết quả.mp4"
    seen = []
    render_min.render(FF, str(src), str(out), srt=str(srt), on_progress=lambda p, s: seen.append(p))
    assert out.is_file() and out.stat().st_size > 1000
    assert seen and seen[-1] == 100
    assert abs(render_min.duration_of(FF, str(out)) - 2.0) < 0.3
    assert not list(tmp_path.glob("*.part"))


@needs_ff
def test_render_thay_audio(tmp_path):
    src = tmp_path / "v.mp4"
    subprocess.run([FF, "-y", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc=size=160x90:rate=10:duration=2",
                    "-pix_fmt", "yuv420p", str(src)], capture_output=True, check=True)
    aud = _tone(str(tmp_path / "a.wav"), 1.5)
    out = tmp_path / "o.mp4"
    render_min.render(FF, str(src), str(out), audio=aud)
    r = subprocess.run([FF, "-hide_banner", "-i", str(out)], capture_output=True, text=True)
    assert "Audio:" in r.stderr and "Video:" in r.stderr
