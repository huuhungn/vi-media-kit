# applog.py - ghi log ra file + bắt lỗi chưa xử lý (bản exe windowed không có console)
"""Log xoay vòng ở <data>/logs/app.log (3 x 1 MB). Lỗi không bắt được (luồng chính và luồng phụ) cũng vào đây,
để người dùng gửi file này khi báo lỗi."""
from __future__ import annotations

import logging
import logging.handlers
import os
import sys
import threading
import time

_path = ""
_crash_fh = None


def init(data_dir: str) -> str:
    """Gọi một lần, sớm nhất có thể. Trả về đường dẫn file log ('' nếu không ghi được)."""
    global _path, _crash_fh
    if _path:
        return _path
    try:
        d = os.path.join(data_dir, "logs")
        os.makedirs(d, exist_ok=True)
        p = os.path.join(d, "app.log")
        h = logging.handlers.RotatingFileHandler(p, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
        h.setFormatter(logging.Formatter("%(asctime)s %(levelname)-7s %(name)s: %(message)s"))
        root = logging.getLogger()
        root.setLevel(logging.INFO)
        root.addHandler(h)
        _path = p
    except Exception:
        return ""
    log = logging.getLogger("app")
    log.info("=== khởi động · Python %s · frozen=%s", sys.version.split()[0], bool(getattr(sys, "frozen", False)))

    def _hook(et, ev, tb):
        log.critical("Lỗi chưa xử lý", exc_info=(et, ev, tb))

    def _thread_hook(args):
        log.critical("Lỗi chưa xử lý trong luồng %s", getattr(args.thread, "name", "?"),
                     exc_info=(args.exc_type, args.exc_value, args.exc_traceback))

    sys.excepthook = _hook
    threading.excepthook = _thread_hook
    try:  # sập native (ctranslate2/onnxruntime/Qt): ghi traceback Python của mọi luồng vào crash.log
        import faulthandler
        _crash_fh = open(os.path.join(os.path.dirname(p), "crash.log"), "a", encoding="utf-8")  # noqa: SIM115 - giữ mở suốt phiên
        _crash_fh.write("--- phiên " + time.strftime("%Y-%m-%d %H:%M:%S") + " ---\n")
        _crash_fh.flush()
        faulthandler.enable(file=_crash_fh, all_threads=True)
    except Exception:
        pass
    return p


def path() -> str:
    return _path
