# applog.py - write logs to a file + capture unhandled errors (windowed exe builds have no console)
"""Rotating log at <data>/logs/app.log (3 x 1 MB). Uncaught errors (main thread and worker threads) land here too,
so users can attach this file when reporting a bug."""
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
    """Call once, as early as possible. Returns the log file path ('' if it cannot be written)."""
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
    try:  # native crash (ctranslate2/onnxruntime/Qt): write the Python traceback of every thread to crash.log
        import faulthandler
        _crash_fh = open(os.path.join(os.path.dirname(p), "crash.log"), "a", encoding="utf-8")  # noqa: SIM115 - kept open for the whole session
        _crash_fh.write("--- phiên " + time.strftime("%Y-%m-%d %H:%M:%S") + " ---\n")
        _crash_fh.flush()
        faulthandler.enable(file=_crash_fh, all_threads=True)
    except Exception:
        pass
    return p


def path() -> str:
    return _path
