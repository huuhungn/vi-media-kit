# jobs.py - chạy tác vụ nền cho GUI: một việc tại một thời điểm, huỷ được, đóng cửa sổ không làm sập luồng
"""Task: QThread chạy fn(prog, log, cancel). Luôn phát đúng một trong done/err (kể cả BaseException).
JobManager: giữ tham chiếu tới Task (không bị thu gom khi đang chạy), từ chối bắt đầu việc mới khi đang bận,
`shutdown()` huỷ và chờ khi đóng cửa sổ."""
from __future__ import annotations

import traceback

from PySide6.QtCore import QThread, Signal


class Cancelled(Exception):
    """fn có thể ném lỗi này để báo "đã huỷ" (hiện thành thông báo nhẹ, không phải lỗi)."""


class Task(QThread):
    prog = Signal(int, str)
    log = Signal(str)
    done = Signal(object)
    err = Signal(str)      # traceback đầy đủ (ghi log); thông báo thân thiện lấy qua errors.thong_bao(self.exc)

    def __init__(self, fn, parent=None):
        super().__init__(parent)
        self.fn = fn
        self._cancel = False
        self.exc: BaseException | None = None

    def cancel(self) -> None:
        self._cancel = True

    @property
    def cancelled(self) -> bool:
        return self._cancel

    def run(self) -> None:
        try:
            r = self.fn(lambda p, s: self.prog.emit(int(p), str(s)),
                        lambda m: self.log.emit(str(m)),
                        lambda: self._cancel)
        except BaseException as e:  # noqa: BLE001 - phải phát err cho mọi trường hợp để nút không kẹt
            # đã yêu cầu huỷ thì mọi ngoại lệ phát sinh sau đó coi là "huỷ", không phải lỗi
            self.exc = Cancelled("Đã huỷ") if self._cancel else e
            self.err.emit(traceback.format_exc())
            return
        if self._cancel:
            self.exc = Cancelled("Đã huỷ")
            self.err.emit("Đã huỷ")
            return
        self.done.emit(r)


class JobManager:
    def __init__(self):
        self._running: list[Task] = []

    def busy(self) -> bool:
        self._running = [t for t in self._running if t.isRunning()]
        return bool(self._running)

    def start(self, task: Task) -> bool:
        """False nếu đang có việc khác chạy (nơi gọi hiện thông báo)."""
        if self.busy():
            return False
        self._running.append(task)
        task.finished.connect(lambda t=task: self._forget(t))
        task.start()
        return True

    def _forget(self, task: Task) -> None:
        if task in self._running and not task.isRunning():
            self._running.remove(task)

    def cancel_all(self) -> None:
        for t in self._running:
            t.cancel()

    def shutdown(self, wait_ms: int = 5000) -> bool:
        """Huỷ và chờ tối đa wait_ms. True nếu mọi luồng đã dừng. Không terminate (có thể làm hỏng file đang ghi)."""
        self.cancel_all()
        ok = True
        for t in list(self._running):
            if t.isRunning() and not t.wait(wait_ms):
                ok = False
        return ok
