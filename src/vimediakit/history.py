# history.py - speech-to-text (STT) history: atomic writes, capped entry count, diacritic-insensitive search
"""File: <data>/stt_history.json (newest first). The full text is not stored, only an excerpt of the first 200 characters."""
from __future__ import annotations

import json
import os
import time

MAX_ITEMS = 300
_EXCERPT = 200


def _path(data_dir: str) -> str:
    return os.path.join(data_dir, "stt_history.json")


def load(data_dir: str) -> list[dict]:
    try:
        with open(_path(data_dir), encoding="utf-8") as f:
            d = json.load(f)
        return [x for x in d if isinstance(x, dict)] if isinstance(d, list) else []
    except (OSError, ValueError):
        return []


def add(data_dir: str, file: str, text: str, lang: str = "", so_cau: int = 0, phu_de: str = "",
        max_items: int = MAX_ITEMS) -> dict:
    entry = {
        "ten": os.path.basename(file),
        "file": file,
        "ngay": time.strftime("%Y-%m-%d %H:%M:%S"),
        "ngon_ngu": lang,
        "so_cau": int(so_cau),
        "phu_de": phu_de,
        "text": " ".join((text or "").split())[:_EXCERPT],
    }
    items = [x for x in load(data_dir) if x.get("file") != file]
    items.insert(0, entry)
    items = items[:max_items]
    os.makedirs(data_dir, exist_ok=True)
    tmp = _path(data_dir) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=1)
    os.replace(tmp, _path(data_dir))
    return entry


def clear(data_dir: str) -> None:
    try:
        os.remove(_path(data_dir))
    except OSError:
        pass
