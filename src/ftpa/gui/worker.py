"""
后台工作线程（QThread）及信号定义。

每个长时间操作使用 QThread 子类模式，生命周期更简单可控。
"""

from __future__ import annotations

import logging

from PySide6.QtCore import QThread, Signal

from ...errors import (
    FtpaError,
    FileNotFoundLoadError,
    FormatLoadError,
    ResourceLoadError,
)

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
            ctx.load(self.data_path, self.excel_path)
            self._ctx = ctx
            self.progress.emit(100, "加载完成")
            self.load_finished.emit(ctx, "")
        except FileNotFoundLoadError as e:
            self.load_finished.emit(None, f"文件不存在: {e}")
        except FormatLoadError as e:
            self.load_finished.emit(None, f"文件格式错误，请检查文件内容: {e}")
        except ResourceLoadError as e:
            msg = str(e)
            if "内存不足" in msg:
                self.load_finished.emit(None, "内存不足，文件过大，请关闭其他程序后重试")
            else:
                self.load_finished.emit(None, f"文件读取失败: {e}")
        except FtpaError as e:
            self.load_finished.emit(None, f"加载失败: {e}")
        except Exception as e:
            logger.exception("数据加载未知错误")
            self.load_finished.emit(None, f"加载失败: {e}")


class AnalysisWorker(QThread):
    """系统级分析专用工作者（P1-PERF-1）。

    在后台线程执行 SystemAnalyzer.analyze() + generate_reports()，
    避免大数据集分析时冻结 GUI 主线程。

    信号:
        progress: 进度回调 (value: 0-100, message: str)
        analysis_finished: 分析完成 (results: dict | None, reports: dict | None, error_msg: str)
    """

    progress = Signal(int, str)
    analysis_finished = Signal(object, object, str)  # (results, reports, error_msg)

    def __init__(self, data, source_type: str = "", parent=None):
        """
        Args:
            data: 输入数据（dict[str, np.ndarray] 或 DataFrame）。
            source_type: 数据源类型 ("txt" | "csv")。
            parent: 父 QObject。
        """
        super().__init__(parent)
        self._data = data
        self._source_type = source_type

    def run(self):
        try:
            from ..analysis import SystemAnalyzer

            self.progress.emit(10, "正在初始化分析器...")
            analyzer = SystemAnalyzer()

            self.progress.emit(30, "正在运行系统分析...")
            results = analyzer.analyze(
                self._data,
                self._source_type,
                progress_callback=lambda v, m: self.progress.emit(30 + v // 2, m),
            )

            self.progress.emit(80, "正在生成报告...")
            reports = analyzer.generate_reports(results)

            self.progress.emit(100, "分析完成")
            self.analysis_finished.emit(results, reports, "")
        except Exception as e:
            logger.exception("系统分析未知错误")
            self.analysis_finished.emit(None, None, f"系统分析出错：{e}")
