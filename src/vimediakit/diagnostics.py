# diagnostics.py - gói chẩn đoán một file zip để gửi hỗ trợ (không chứa khoá API, văn bản hay âm thanh của người dùng)
"""`xuat(data_dir, out_zip)`: log ứng dụng, thông tin máy/phiên bản, danh sách model/cache (tên + dung lượng), thiết lập đã
che các giá trị nhạy cảm."""
from __future__ import annotations

import json
import os
import platform
import re
import sys
import time
import zipfile

_SECRET = re.compile(r"key|token|secret|cookie|password|passwd|auth|credential", re.I)


def che_bi_mat(obj):
    """Đệ quy: mọi giá trị có tên khoá nhạy cảm thành '***'."""
    if isinstance(obj, dict):
        return {k: ("***" if _SECRET.search(str(k)) and v not in (None, "", False) else che_bi_mat(v)) for k, v in obj.items()}
    if isinstance(obj, list):
        return [che_bi_mat(v) for v in obj]
    return obj


def _tree(root: str, max_depth: int = 3) -> list[str]:
    out = []
    base = root.rstrip("\\/").count(os.sep)
    for d, dirs, files in os.walk(root):
        depth = d.count(os.sep) - base
        if depth >= max_depth:
            dirs[:] = []
        rel = os.path.relpath(d, root)
        for f in files:
            p = os.path.join(d, f)
            try:
                sz = os.path.getsize(p)
            except OSError:
                sz = -1
            out.append(f"{os.path.join(rel, f) if rel != '.' else f}\t{sz}")
        if len(out) > 2000:
            out.append("... (cắt bớt)")
            break
    return out


def thong_tin_may(app_version: str = "") -> dict:
    info = {
        "thoi_diem": time.strftime("%Y-%m-%d %H:%M:%S"),
        "python": sys.version.split()[0],
        "frozen": bool(getattr(sys, "frozen", False)),
        "he_dieu_hanh": platform.platform(),
    }
    if app_version:
        info["phien_ban_app"] = app_version
    try:
        from . import hwprofile
        hw = hwprofile.detect()
        info["phan_cung"] = {"cpu_cores": hw.cpu_cores, "cpu_threads": hw.cpu_threads, "ram_gb": hw.ram_gb,
                             "gpu": hw.gpu_name, "vram_mb": hw.vram_mb, "cuda_ready": hw.cuda_ready}
        info["goi_y"] = hwprofile.recommend(hw).ghi_chu
    except Exception as e:
        info["phan_cung"] = f"lỗi: {e}"
    for mod in ("faster_whisper", "ctranslate2", "edge_tts", "piper", "PySide6", "onnxruntime", "av"):
        try:
            m = __import__(mod)
            info.setdefault("thu_vien", {})[mod] = getattr(m, "__version__", "?")
        except Exception:
            info.setdefault("thu_vien", {})[mod] = "không có"
    return info


def xuat(data_dir: str, out_zip: str, settings: dict | None = None, app_version: str = "") -> str:
    """Tạo out_zip; trả về đường dẫn. Không bao giờ ném lỗi vì một mục lẻ."""
    os.makedirs(os.path.dirname(os.path.abspath(out_zip)), exist_ok=True)
    tmp = out_zip + ".tmp"
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("may.json", json.dumps(thong_tin_may(app_version), ensure_ascii=False, indent=2))
        if settings is None:
            try:
                with open(os.path.join(data_dir, "settings.json"), encoding="utf-8") as f:
                    settings = json.load(f)
            except (OSError, ValueError):
                settings = {}
        z.writestr("thiet_lap.json", json.dumps(che_bi_mat(settings), ensure_ascii=False, indent=2))
        logs = os.path.join(data_dir, "logs")
        if os.path.isdir(logs):
            for f in sorted(os.listdir(logs)):
                p = os.path.join(logs, f)
                if os.path.isfile(p) and os.path.getsize(p) < 5_000_000:
                    try:
                        z.write(p, f"logs/{f}")
                    except OSError:
                        pass
        for sub in ("whisper_models", "piper_models", "cuda", "tts_cache", "tts_out"):
            d = os.path.join(data_dir, sub)
            if os.path.isdir(d):
                z.writestr(f"danh_sach/{sub}.txt", "\n".join(_tree(d)))
    os.replace(tmp, out_zip)
    return out_zip
