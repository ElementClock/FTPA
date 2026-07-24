"""
后台工作线程（QThread）及信号定义。

每个长时间操作使用 QObject + moveToThread 模式。
"""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal


class DataLoaderWorker(QObject):
    """数据加载专用工作者。"""

    progress = Signal(int, str)
    finished = Signal(object, str)  # (DataContext | None, error_msg)

    def __init__(self, data_path: str, excel_path: str):
        super().__init__()
        self.data_path = data_path
        self.excel_path = excel_path

    def run(self):
        try:
            from .services import DataContext

            ctx = DataContext()
            self.progress.emit(30, "正在加载数据...")
            ok, msg = ctx.load(self.data_path, self.excel_path)
            if ok:
                self.progress.emit(100, "加载完成")
                self.finished.emit(ctx, "")
            else:
                self.finished.emit(None, msg or f"加载失败: {self.data_path}")
        except Exception as e:
            self.finished.emit(None, str(e))
