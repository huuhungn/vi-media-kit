# netmode.py - explicit offline mode: when enabled, no operation goes to the network on its own
"""Enable it via a setting in the UI or the environment variable VIMEDIA_OFFLINE=1.
When enabled: no downloading of models/voices/GPU packages and no online services; the app uses the resources already on the machine.
Every place that downloads files calls `require_online("...")` before opening a connection."""
from __future__ import annotations

import os

_state: dict[str, bool | None] = {"offline": None}  # None = follow the environment variable


class OfflineError(RuntimeError):
    """The operation needs the network but offline mode is on."""


def is_offline() -> bool:
    if _state["offline"] is not None:
        return bool(_state["offline"])
    return os.environ.get("VIMEDIA_OFFLINE", "").strip().lower() in ("1", "true", "yes", "on")


def set_offline(value: bool | None) -> None:
    """True/False forces the value; None goes back to following the environment variable."""
    _state["offline"] = value


def require_online(what: str = "thao tác này") -> None:
    if is_offline():
        raise OfflineError(f"Đang bật chế độ offline nên không thể {what}. Tắt chế độ offline để dùng mạng.")
