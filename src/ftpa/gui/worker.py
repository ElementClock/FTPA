"""
后台工作线程（QThread）及信号定义。

每个长时间操作作为 QThread 的子类或使用 Worker + moveToThread 模式。
使用 Signal/Slot 机制避免 wx.CallAfter 模式。
"""

from __future__ import annotations

from typing import Any, Callable

from PySide6.QtCore import QObject, Signal, QThread


class WorkerSignals(QObject):
    """工作线程的信号集合。"""

    progress = Signal(int, str)  # (percent, message)
    result = Signal(object)  # 执行结果
    error = Signal(str)  # 错误消息
    finished = Signal()


class Worker(QObject):
    """通用工作对象，通过 moveToThread 在后台执行。"""

    def __init__(self, fn: Callable, *args, **kwargs):
        super().__init__()
        self._fn = fn
        self._args = args
        self._kwargs = kwargs
        self.signals = WorkerSignals()
        self._canceled = False

    def cancel(self):
        self._canceled = True

    @property
    def is_canceled(self) -> bool:
        return self._canceled

    def run(self):
        """在线程中执行函数。"""
        try:
            result = self._fn(
                *self._args,
                **self._kwargs,
                progress_callback=self.signals.progress,
                cancel_check=lambda: self._canceled,
            )
            if not self._canceled:
                self.signals.result.emit(result)
        except Exception as e:
            if not self._canceled:
                self.signals.error.emit(str(e))
        finally:
            self.signals.finished.emit()


def run_in_thread(fn: Callable, parent: QObject | None = None) -> tuple[QThread, Worker]:
    """在后台线程中执行 fn，返回 (thread, worker)。"""
    thread = QThread(parent)
    worker = Worker(fn)
    worker.moveToThread(thread)
    thread.started.connect(worker.run)
    worker.signals.finished.connect(thread.quit)
    worker.signals.finished.connect(worker.deleteLater)
    thread.finished.connect(thread.deleteLater)
    thread.start()
    return thread, worker


class DataLoaderWorker(QObject):
    """数据加载专用工作者。"""

    progress = Signal(int, str)
    finished = Signal(bool, str)

    def __init__(self, data_path: str, excel_path: str):
        super().__init__()
        self.data_path = data_path
        self.excel_path = excel_path

    def run(self):
        try:
            from .services import DataContext

            ctx = DataContext()
            self.progress.emit(30, "正在加载数据...")
            ok = ctx.load(self.data_path, self.excel_path)
            if ok:
                self.progress.emit(100, "加载完成")
                self.finished.emit(True, "")
            else:
                self.finished.emit(False, f"文件不存在: {self.data_path}")
        except Exception as e:
            self.finished.emit(False, str(e))
