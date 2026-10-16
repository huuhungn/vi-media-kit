# errors.py - turn technical exceptions into clear Vietnamese messages for users
"""`thong_bao(exc)` → a short message for the user (with a hint on what to do next). Technical details still go to the log."""
from __future__ import annotations

import errno
import socket
import ssl
import urllib.error


def thong_bao(exc: BaseException) -> str:
    # errors raised by the app itself already carry a Vietnamese message (TaiModelError, OfflineError, DubError, RenderError...)
    name = type(exc).__name__
    if name in {"TaiModelError", "KhongTruyCap", "OfflineError", "DubError", "RenderError"}:
        return str(exc)
    if isinstance(exc, MemoryError):
        return "Hết bộ nhớ (RAM). Hãy đóng bớt ứng dụng, dùng model nhỏ hơn hoặc file ngắn hơn."
    if isinstance(exc, PermissionError):
        return "Không có quyền ghi/đọc file hoặc thư mục này (hoặc file đang được mở ở chương trình khác). Chọn nơi lưu khác."
    if isinstance(exc, FileNotFoundError):
        return "Không tìm thấy file hoặc thư mục (có thể đã bị di chuyển hoặc xoá)."
    if isinstance(exc, OSError) and getattr(exc, "errno", None) == errno.ENOSPC:
        return "Ổ đĩa đã đầy. Giải phóng dung lượng rồi thử lại."
    if isinstance(exc, (urllib.error.URLError, socket.timeout, TimeoutError, ConnectionError, ssl.SSLError)):
        return "Không kết nối được mạng hoặc máy chủ phản hồi quá chậm. Kiểm tra mạng rồi thử lại."
    if isinstance(exc, UnicodeError):
        return "File văn bản có mã hoá lạ, không đọc được. Hãy lưu lại dạng UTF-8."
    if isinstance(exc, OSError) and getattr(exc, "winerror", None) == 206:
        return "Đường dẫn quá dài. Đặt file ở thư mục ngắn hơn (ví dụ D:\\Audio)."
    msg = str(exc).strip().splitlines()[0] if str(exc).strip() else name
    return f"Đã xảy ra lỗi ({name}): {msg[:200]}. Chi tiết nằm trong file log."
