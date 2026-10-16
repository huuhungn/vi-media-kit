"""Tải model Whisper (vimediakit/modeldl.py): chạy offline bằng máy chủ HTTP giả lập API + resolve của Hugging Face."""
import hashlib
import http.server
import json
import os
import threading

import pytest

from vimediakit import modeldl as tai_model

REPO = "test/faster-whisper-x"
SHA = "c0ffee" * 6 + "abcd"
MODEL = os.urandom(3 * 1048576 + 123)
FILES = {
    "config.json": b'{"a": 1}',
    "tokenizer.json": b'{"b": 2}',
    "vocabulary.txt": b"x\ny\n",
    "model.bin": MODEL,
    "README.md": b"khong can",
}


class _Handler(http.server.BaseHTTPRequestHandler):
    cut_once = False       # lần đầu tải model.bin: gửi nửa chừng rồi đóng kết nối
    stall_once = False     # lần đầu tải model.bin: im lặng (mô phỏng treo) rồi mới trả lời
    bad_sha = False        # công bố sha256 sai cho model.bin
    hits: list = []

    def log_message(self, *a):
        pass

    def do_GET(self):
        cls = type(self)
        cls.hits.append(self.path)
        if self.path.startswith(f"/api/models/{REPO}"):
            sib = []
            for n, b in FILES.items():
                s = {"rfilename": n, "size": len(b)}
                if n == "model.bin":
                    s["lfs"] = {"sha256": ("0" * 64) if cls.bad_sha else hashlib.sha256(b).hexdigest()}
                sib.append(s)
            body = json.dumps({"sha": SHA, "siblings": sib}).encode()
            self.send_response(200); self.send_header("Content-Length", str(len(body))); self.end_headers()
            self.wfile.write(body)
            return
        prefix = f"/{REPO}/resolve/{SHA}/"
        if self.path.startswith(prefix) and self.path[len(prefix):] in FILES:
            data = FILES[self.path[len(prefix):]]
            start = 0
            rng = self.headers.get("Range")
            if rng and rng.startswith("bytes="):
                start = int(rng[6:].split("-")[0])
            if self.path.endswith("model.bin") and cls.stall_once:
                cls.stall_once = False
                threading.Event().wait(2.5)  # không dùng time.sleep: fixture đã vá time.sleep
            self.send_response(206 if start else 200)
            self.send_header("Content-Length", str(len(data) - start))
            if start:
                self.send_header("Content-Range", f"bytes {start}-{len(data) - 1}/{len(data)}")
            self.end_headers()
            if self.path.endswith("model.bin") and cls.cut_once and not start:
                cls.cut_once = False
                self.wfile.write(data[: len(data) // 2])
                self.wfile.flush()
                self.close_connection = True
                return
            self.wfile.write(data[start:])
            return
        self.send_response(404); self.end_headers()


@pytest.fixture()
def server(monkeypatch):
    _Handler.cut_once = False
    _Handler.stall_once = False
    _Handler.bad_sha = False
    _Handler.hits = []
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    monkeypatch.setenv("HF_ENDPOINT", f"http://127.0.0.1:{srv.server_port}")
    monkeypatch.setattr(tai_model.time, "sleep", lambda s: None)
    yield srv
    srv.shutdown()


def _snap(tmp_path):
    return tmp_path / "models--test--faster-whisper-x" / "snapshots" / SHA


def test_tai_du_file_va_bo_cuc_cache(server, tmp_path):
    pcts = []
    snap = tai_model.tai("x", REPO, str(tmp_path), on_progress=lambda p, s: pcts.append((p, s)))
    s = _snap(tmp_path)
    assert str(s) == snap
    assert (s / "model.bin").read_bytes() == MODEL
    assert (s / "config.json").exists() and (s / "tokenizer.json").exists() and (s / "vocabulary.txt").exists()
    assert not (s / "README.md").exists()
    assert (tmp_path / "models--test--faster-whisper-x" / "refs" / "main").read_text() == SHA
    assert not list(s.glob("*.part"))
    assert pcts[0][0] == 5 and pcts[-1][0] == 96
    assert any("MB" in t for _, t in pcts)
    assert [p for p, _ in pcts] == sorted(p for p, _ in pcts)


def test_dut_giua_chung_thi_noi_tiep_bang_range(server, tmp_path):
    _Handler.cut_once = True
    logs = []
    tai_model.tai("x", REPO, str(tmp_path), on_log=logs.append)
    assert (_snap(tmp_path) / "model.bin").read_bytes() == MODEL
    assert any("thử lại" in m for m in logs)


def test_khong_tai_lai_khi_da_du(server, tmp_path):
    tai_model.tai("x", REPO, str(tmp_path))
    _Handler.hits.clear()
    tai_model.tai("x", REPO, str(tmp_path))
    assert [h for h in _Handler.hits if "/resolve/" in h] == []


def test_sha256_sai_thi_bao_loi_va_xoa_file(server, tmp_path):
    _Handler.bad_sha = True
    with pytest.raises(tai_model.TaiModelError, match="sha256"):
        tai_model.tai("x", REPO, str(tmp_path))
    assert not (_snap(tmp_path) / "model.bin").exists()
    assert not (_snap(tmp_path) / "model.bin.part").exists()


def test_huy_giua_chung(server, tmp_path):
    n = {"i": 0}

    def cancel():
        n["i"] += 1
        return n["i"] > 3

    with pytest.raises(tai_model.TaiModelError, match="huỷ"):
        tai_model.tai("x", REPO, str(tmp_path), should_cancel=cancel)


def test_khong_ket_noi_duoc_thi_bao_khong_truy_cap(tmp_path, monkeypatch):
    monkeypatch.setenv("HF_ENDPOINT", "http://127.0.0.1:1")
    with pytest.raises(tai_model.KhongTruyCap):
        tai_model.tai("x", REPO, str(tmp_path))


def test_treo_thi_het_han_doc_va_thu_lai(server, tmp_path, monkeypatch):
    monkeypatch.setattr(tai_model, "READ_TIMEOUT", 0.7)
    _Handler.stall_once = True
    logs = []
    tai_model.tai("x", REPO, str(tmp_path), on_log=logs.append)
    assert (_snap(tmp_path) / "model.bin").read_bytes() == MODEL
    assert any("thử lại" in m for m in logs)
