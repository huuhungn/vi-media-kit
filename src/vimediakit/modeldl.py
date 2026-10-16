# modeldl.py - download Whisper models (faster-whisper format) from Hugging Face, with real progress reporting
"""Download a speech-recognition model into data/whisper_models using the HuggingFace cache layout
(models--<org>--<repo>/snapshots/<sha>/…), so faster-whisper can use it right away.

Why faster-whisper's snapshot_download is not used: it reports no progress (the bar stalls at 5%), has no explicit
timeout when the network is flaky (Xet CDN), and runs several threads that are hard to control. Here:
- ask the API for the commit sha + size + sha256 of each file; download sequentially with urllib, reads have a timeout
  (READ_TIMEOUT), retry up to RETRIES times and resume (Range) from the .part file;
- continuously report "downloaded/total MB · speed"; cancellable; verify the sha256 of large files;
- the endpoint is read from the HF_ENDPOINT environment variable (default https://huggingface.co) so users can pick a mirror.
"""
from __future__ import annotations

import hashlib
import http.client
import json
import os
import re
import shutil
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Callable

UA = "vi-media-kit (+modeldl)"
ENDPOINT = "https://huggingface.co"
READ_TIMEOUT = 30      # max seconds to wait per read; past that the download counts as hung and is retried
RETRIES = 6
_NAMES = ("config.json", "preprocessor_config.json", "tokenizer.json", "model.bin")
_CHUNK = 262144


class TaiModelError(RuntimeError):
    """Model download error (the message is already in Vietnamese)."""


class KhongTruyCap(TaiModelError):
    """The API cannot be reached (network blocked / DNS): the caller may fall back to the old download method."""


_SHA_RE = re.compile(r"[0-9a-f]{40}")
_locks: dict[str, threading.Lock] = {}
_locks_guard = threading.Lock()


def _want(fn: str) -> bool:
    """Accept only flat file names (no '/', '\\', '..') — this value comes from the server (possibly a mirror)."""
    if "/" in fn or "\\" in fn or ".." in fn or not fn:
        return False
    return fn in _NAMES or fn.startswith("vocabulary.")


def _check_endpoint(ep: str) -> None:
    low = ep.lower()
    if not (low.startswith("https://") or low.startswith("http://127.0.0.1") or low.startswith("http://localhost")):
        raise TaiModelError(f"HF_ENDPOINT phải là https:// (đang là {ep}).")


def _endpoint() -> str:
    return (os.environ.get("HF_ENDPOINT") or ENDPOINT).rstrip("/")


def _open(url: str, headers: dict | None = None, timeout: float | None = None):
    from .netmode import OfflineError, require_online
    try:
        require_online("tải model")
    except OfflineError as e:
        raise TaiModelError(str(e)) from e
    return urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA, **(headers or {})}),
                                  timeout=timeout or READ_TIMEOUT)


def thong_tin(repo: str, endpoint: str | None = None) -> tuple[str, list[dict]]:
    """(commit sha, [{name, size, sha256}]) of the files faster-whisper needs."""
    ep = (endpoint or _endpoint()).rstrip("/")
    _check_endpoint(ep)
    try:
        with _open(f"{ep}/api/models/{repo}?blobs=true", timeout=30) as r:
            d = json.load(r)
    except urllib.error.HTTPError as e:
        raise TaiModelError(f"Hugging Face trả lỗi {e.code} khi hỏi model {repo}.") from e
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise KhongTruyCap(f"Không kết nối được tới {ep} ({e}).") from e
    files = []
    for s in d.get("siblings") or []:
        fn = s.get("rfilename") or ""
        if _want(fn):
            files.append({"name": fn, "size": int(s.get("size") or 0), "sha256": ((s.get("lfs") or {}).get("sha256") or "")})
    if not any(f["name"] == "model.bin" for f in files):
        raise TaiModelError(f"Kho {repo} không có model.bin (không phải model faster-whisper?).")
    sha = str(d.get("sha") or "")
    if not _SHA_RE.fullmatch(sha):
        raise TaiModelError(f"Phản hồi của máy chủ không hợp lệ (sha commit: {sha[:20]!r}).")
    return (sha, files)


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            b = f.read(1048576)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def _tai_file(url: str, dst: str, size: int, sha256: str, step: Callable[[int], None], cancel: Callable[[], bool],
              on_log: Callable[[str], None]) -> None:
    part = dst + ".part"
    last: Exception | None = None
    for attempt in range(RETRIES + 1):
        have = os.path.getsize(part) if os.path.exists(part) else 0
        if size and have > size:
            os.remove(part)
            have = 0
        if size and have == size:
            break
        try:
            hdr = {"Range": f"bytes={have}-"} if have else {}
            with _open(url, hdr) as r:
                mode = "ab" if have and getattr(r, "status", 200) == 206 else "wb"
                if mode == "wb":
                    have = 0
                step(have)
                with open(part, mode) as f:
                    while True:
                        if cancel():
                            raise TaiModelError("Đã huỷ tải model.")
                        b = r.read(_CHUNK)
                        if not b:
                            break
                        f.write(b)
                        have += len(b)
                        step(have)
        except TaiModelError:
            raise
        except urllib.error.HTTPError as e:
            if e.code == 416 and size and have == size:  # the .part file is already complete, the server has nothing left to send
                break
            if e.code in (401, 403, 404):
                raise TaiModelError(f"Hugging Face từ chối tải {os.path.basename(dst)} (mã {e.code}).") from e
            last = e
        except (urllib.error.URLError, TimeoutError, ConnectionError, http.client.HTTPException, OSError) as e:
            last = e
        else:
            if not size or os.path.getsize(part) == size:
                break
            last = RuntimeError("tải thiếu dung lượng")
        if attempt < RETRIES:
            on_log(f"   ⚠ Mạng chập chờn ({str(last)[:80]}) → thử lại lần {attempt + 1}/{RETRIES}, nối tiếp từ chỗ dở")
            time.sleep(min(2 ** attempt, 10))
    else:
        raise TaiModelError(f"Tải {os.path.basename(dst)} thất bại sau {RETRIES} lần thử: {last}")
    if sha256 and _sha256(part) != sha256:
        os.remove(part)
        raise TaiModelError(f"{os.path.basename(dst)} tải về bị sai (sha256 không khớp); đã xoá, hãy tải lại.")
    os.replace(part, dst)


def tai(name: str, repo: str, models_dir: str, on_progress: Callable[[int, str], None] | None = None,
        on_log: Callable[[str], None] | None = None, should_cancel: Callable[[], bool] | None = None) -> str:
    """Download all model files into models_dir and return the snapshot directory. Files that are already complete are not downloaded again."""
    with _locks_guard:
        lock = _locks.setdefault(repo, threading.Lock())
    if not lock.acquire(blocking=False):
        # another thread is already downloading the same model: wait, then reuse the result (the download function will see the files are complete)
        (on_log or (lambda s: None))(f"   Đang có một lần tải '{name}' khác, chờ…")
        lock.acquire()
    try:
        return _tai_locked(name, repo, models_dir, on_progress, on_log, should_cancel)
    finally:
        lock.release()


def _tai_locked(name: str, repo: str, models_dir: str, on_progress, on_log, should_cancel) -> str:
    prog = on_progress or (lambda p, s: None)
    log = on_log or (lambda s: None)
    cancel = should_cancel or (lambda: False)
    ep = _endpoint()
    prog(5, f"Hỏi Hugging Face về model {name}…")
    sha, files = thong_tin(repo, ep)
    total = sum(f["size"] for f in files)
    base = os.path.join(models_dir, "models--" + repo.replace("/", "--"))
    snap = os.path.join(base, "snapshots", sha)
    os.makedirs(snap, exist_ok=True)
    need = [f for f in files if not (os.path.exists(os.path.join(snap, f["name"]))
                                     and (not f["size"] or os.path.getsize(os.path.join(snap, f["name"])) == f["size"]))]
    todo = sum(f["size"] for f in need)
    if need:
        free = shutil.disk_usage(models_dir).free
        if free < todo + 200 * 1048576:
            raise TaiModelError(f"Không đủ chỗ trống: cần ≈ {todo // 1048576 + 200} MB, ổ đĩa còn {free // 1048576} MB.")
        log(f"Tải model '{name}' ({total // 1048576} MB) từ {ep.split('//')[-1]}…")
    done_before = start_done = total - todo
    t0 = time.time()
    t_last = [0.0]

    for f in need:
        dst = os.path.join(snap, f["name"])
        url = f"{ep}/{repo}/resolve/{sha}/{f['name']}"

        def step(have: int, _f=f, _base=done_before) -> None:
            now = time.time()
            if now - t_last[0] < 0.4 and have < _f["size"]:
                return
            t_last[0] = now
            got = _base + have
            mb = got / 1048576
            speed = (got - start_done) / max(now - t0, 0.001) / 1048576
            pct = 5 + int(90 * got / total) if total else 50
            prog(min(pct, 95), f"Tải model {name} · {mb:.0f}/{total / 1048576:.0f} MB · {speed:.1f} MB/s")

        _tai_file(url, dst, f["size"], f["sha256"], step, cancel, log)
        done_before += f["size"]
    snaps = os.path.join(base, "snapshots")
    for old in os.listdir(snaps):  # old snapshots (a newer, complete one exists) just waste disk space
        p = os.path.join(snaps, old)
        if old != sha and os.path.isdir(p):
            shutil.rmtree(p, ignore_errors=True)
    os.makedirs(os.path.join(base, "refs"), exist_ok=True)
    with open(os.path.join(base, "refs", "main"), "w", encoding="utf-8") as fh:
        fh.write(sha)
    prog(96, "Đã tải xong, đang kiểm tra…")
    return snap
