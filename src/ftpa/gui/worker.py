"""
后台工作线程（QThread）及信号定义。

每个长时间操作使用 QThread 子类模式，生命周期更简单可控。
"""

from __future__ import annotations

import logging

import pandas as pd
from PySide6.QtCore import QThread, Signal

logger = logging.getLogger(__name__)


class DataLoaderWorker(QThread):
    """数据加载专用工作者。"""

    progress = Signal(int, str)
    load_finished = Signal(object, str)  # (DataContext | None, error_msg)

    def __init__(self, data_path: str, excel_path: str, parent=None):
        super().__init__(parent)
        self.data_path = data_path
        self.excel_path = excel_path
        self._ctx = None

    def run(self):
        try:
            from .services import DataContext

            ctx = DataContext()
            self.progress.emit(30, "正在加载数据...")
            ok, msg = ctx.load(self.data_path, self.excel_path)
            self._ctx = ctx if ok else None
            if ok:
                self.progress.emit(100, "加载完成")
                self.load_finished.emit(ctx, "")
            else:
                self.load_finished.emit(None, msg or f"加载失败: {self.data_path}")
        except FileNotFoundError as e:
            self.load_finished.emit(None, f"文件不存在: {e}")
        except (pd.errors.ParserError, ValueError) as e:
            self.load_finished.emit(None, f"文件格式错误，请检查文件内容: {e}")
        except MemoryError:
            self.load_finished.emit(None, "内存不足，文件过大，请关闭其他程序后重试")
        except OSError as e:
            self.load_finished.emit(None, f"文件读取失败: {e}")
        except Exception as e:
            logger.exception("数据加载未知错误")
            self.load_finished.emit(None, f"加载失败: {e}")
