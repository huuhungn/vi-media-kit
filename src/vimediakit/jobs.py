# jobs.py - run background tasks for a GUI: one job at a time, cancellable, closing the window does not crash the thread
"""Task: a QThread that runs fn(prog, log, cancel). Always emits exactly one of done/err (even for BaseException).
JobManager: keeps a reference to the Task (so it is not garbage-collected while running), refuses to start a new job while busy,
`shutdown()` cancels and waits when the window is closed."""
from __future__ import annotations

import traceback

from PySide6.QtCore import QThread, Signal


class Cancelled(Exception):
    """fn can raise this to signal "cancelled" (shown as a soft notice, not as an error)."""


class Task(QThread):
    prog = Signal(int, str)
    log = Signal(str)
    done = Signal(object)
    err = Signal(str)      # full traceback (for the log); get the friendly message via errors.thong_bao(self.exc)

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
        except BaseException as e:  # noqa: BLE001 - err must be emitted in every case so the button does not get stuck
            # once cancellation was requested, any exception raised afterwards counts as "cancelled", not as an error
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
        """False if another job is running (the caller shows a notice)."""
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
        """Cancel and wait up to wait_ms. True if every thread has stopped. Never terminates (it could corrupt a file being written)."""
        self.cancel_all()
        ok = True
        for t in list(self._running):
            if t.isRunning() and not t.wait(wait_ms):
                ok = False
        return ok
