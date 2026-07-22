"""
Phase 4: 批量处理面板 — 多文件批量处理、分析、导出摘要。
"""

from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QProgressBar,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..batch_processor import (
    batch_analyze_statistics,
    batch_export_summaries,
    batch_process_files,
)
from .services import DataContext
from .widgets import TimeWindowCtrl


class BatchPanel(QWidget):
    """批量处理面板。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.ctx: DataContext | None = None
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        # 配置区
        form = QGroupBox("批量配置")
        fl = QFormLayout(form)
        self.pattern_input = QLineEdit()
        self.pattern_input.setPlaceholderText("例如: data/*.txt")
        row = QHBoxLayout()
        row.addWidget(self.pattern_input)
        btn = QPushButton("浏览")
        btn.clicked.connect(self._browse_pattern)
        row.addWidget(btn)
        fl.addRow("文件模式:", row)

        self.output_input = QLineEdit()
        self.output_input.setPlaceholderText("输出目录 (默认: ./output)")
        row2 = QHBoxLayout()
        row2.addWidget(self.output_input)
        btn2 = QPushButton("浏览")
        btn2.clicked.connect(self._browse_output)
        row2.addWidget(btn2)
        fl.addRow("输出目录:", row2)

        self.format_combo = QComboBox()
        self.format_combo.addItems(["csv", "parquet", "hdf5", "excel"])
        fl.addRow("导出格式:", self.format_combo)
        layout.addWidget(form)

        # 按钮行
        btn_row = QHBoxLayout()
        btn_process = QPushButton("批量处理数据")
        btn_process.clicked.connect(self._run_batch_process)
        btn_row.addWidget(btn_process)
        btn_analyze = QPushButton("批量分析统计")
        btn_analyze.clicked.connect(self._run_batch_analyze)
        btn_row.addWidget(btn_analyze)
        btn_export = QPushButton("批量导出摘要")
        btn_export.clicked.connect(self._run_batch_export)
        btn_row.addWidget(btn_export)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # 结果表格
        self.result_table = QTableWidget()
        self.result_table.setColumnCount(5)
        self.result_table.setHorizontalHeaderLabels(["文件", "记录数", "通道数", "状态", "说明"])
        self.result_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.result_table.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(self.result_table, 1)

    def set_data_context(self, ctx: DataContext):
        self.ctx = ctx

    def _browse_pattern(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择文件", "", "文本文件 (*.txt);;所有文件 (*)")
        if path:
            self.pattern_input.setText(path)

    def _browse_output(self):
        path = QFileDialog.getExistingDirectory(self, "选择输出目录")
        if path:
            self.output_input.setText(path)

    def _run_batch_process(self):
        pattern = self.pattern_input.text().strip()
        output = self.output_input.text().strip() or "./output"
        fmt = self.format_combo.currentText()
        excel_path = self.ctx.excel_path if self.ctx else ""
        self._run_batch("process", pattern, output, fmt, excel_path)

    def _run_batch_analyze(self):
        pattern = self.pattern_input.text().strip()
        output = self.output_input.text().strip() or "./output"
        excel_path = self.ctx.excel_path if self.ctx else ""
        self._run_batch("analyze", pattern, output, "csv", excel_path)

    def _run_batch_export(self):
        pattern = self.pattern_input.text().strip()
        output = self.output_input.text().strip() or "./output"
        excel_path = self.ctx.excel_path if self.ctx else ""
        self._run_batch("export", pattern, output, "csv", excel_path)

    def _run_batch(self, mode: str, pattern: str, output: str, fmt: str, excel_path: str):
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.result_table.setRowCount(0)

        # 后台线程运行批量操作
        self._batch_thread = QThread()
        self._batch_worker = _BatchWorker(mode, pattern, output, fmt, excel_path)
        self._batch_worker.moveToThread(self._batch_thread)
        self._batch_worker.progress.connect(self.progress_bar.setValue)
        self._batch_worker.finished.connect(self._on_batch_finished)
        self._batch_thread.started.connect(self._batch_worker.run)
        self._batch_worker.finished.connect(self._batch_thread.quit)
        self._batch_worker.finished.connect(self._batch_worker.deleteLater)
        self._batch_thread.finished.connect(self._batch_thread.deleteLater)
        self._batch_thread.start()

    def _on_batch_finished(self, results: list[tuple[str, str, int, int, str, str]]):
        self.progress_bar.setVisible(False)
        self.result_table.setRowCount(len(results))
        for row, (mode, file_name, records, channels, status, note) in enumerate(results):
            self.result_table.setItem(row, 0, QTableWidgetItem(file_name))
            self.result_table.setItem(row, 1, QTableWidgetItem(str(records)))
            self.result_table.setItem(row, 2, QTableWidgetItem(str(channels)))
            self.result_table.setItem(row, 3, QTableWidgetItem(status))
            self.result_table.setItem(row, 4, QTableWidgetItem(note))


class _BatchWorker(QThread):
    """批量操作后台工作者。"""
    progress = Signal(int)
    finished = Signal(list)

    def __init__(self, mode, pattern, output, fmt, excel_path):
        super().__init__()
        self.mode = mode
        self.pattern = pattern
        self.output = output
        self.fmt = fmt
        self.excel_path = excel_path

    def run(self):
        results: list[tuple] = []
        try:
            self.progress.emit(10)
            if self.mode == "process":
                res = batch_process_files(self.pattern, self.output, self.excel_path, export_format=self.fmt)
                for f, info in (res.get("results", {}) if isinstance(res, dict) else {}).items():
                    results.append((
                        self.mode,
                        str(f),
                        info.get("records", 0),
                        info.get("channels", 0),
                        "成功",
                        ""
                    ))
            elif self.mode == "analyze":
                df = batch_analyze_statistics(self.pattern, self.excel_path)
                results.append(("analyze", self.pattern, len(df), len(df.columns) if not df.empty else 0, "成功", ""))
            elif self.mode == "export":
                batch_export_summaries(self.pattern, self.excel_path, self.output)
                results.append(("export", self.pattern, 0, 0, "成功", f"已导出到 {self.output}"))
            self.progress.emit(100)
        except Exception as e:
            results.append((self.mode, self.pattern, 0, 0, "失败", str(e)))
        self.finished.emit(results)
