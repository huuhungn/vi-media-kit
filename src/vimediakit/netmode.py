# netmode.py - chế độ offline rõ ràng: bật thì không có thao tác nào tự động đi ra mạng
"""Bật bằng cài đặt trong giao diện hoặc biến môi trường VIMEDIA_OFFLINE=1.
Khi bật: không tải model/giọng/gói GPU, không dùng dịch vụ trực tuyến; ứng dụng gọi dùng tài nguyên có sẵn trên máy.
Các nơi tải file gọi `require_online("...")` trước khi mở kết nối."""
from __future__ import annotations

import os

_state: dict[str, bool | None] = {"offline": None}  # None = theo biến môi trường


class OfflineError(RuntimeError):
    """Thao tác cần mạng nhưng đang ở chế độ offline."""


def is_offline() -> bool:
    if _state["offline"] is not None:
        return bool(_state["offline"])
    return os.environ.get("VIMEDIA_OFFLINE", "").strip().lower() in ("1", "true", "yes", "on")


def set_offline(value: bool | None) -> None:
    """True/False đặt cứng; None quay về theo biến môi trường."""
    _state["offline"] = value


def require_online(what: str = "thao tác này") -> None:
    if is_offline():
        raise OfflineError(f"Đang bật chế độ offline nên không thể {what}. Tắt chế độ offline để dùng mạng.")
