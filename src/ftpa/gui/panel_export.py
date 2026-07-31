"""
Phase 4: 导出与摘要面板 — 数据导出 + 统计导出 + 数据摘要。
"""

from __future__ import annotations

import os

from PySide6.QtCore import Qt
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
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..data.exporter import export_data, export_statistics
from .services import DataContext


class ExportPanel(QWidget):
    """导出与摘要面板。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.ctx: DataContext | None = None
        self._build_ui()

    def _build_ui(self):
        """构建导出面板 UI：数据导出、统计导出、数据摘要三个分组。"""
        layout = QVBoxLayout(self)

        # --- 数据导出 ---
        gb1 = QGroupBox("数据导出")
        fl1 = QFormLayout(gb1)
        self.export_fmt = QComboBox()
        self.export_fmt.addItems(["csv", "parquet", "hdf5", "excel", "json"])
        fl1.addRow("格式:", self.export_fmt)
        self.export_compression = QComboBox()
        self.export_compression.addItems(["无", "gzip", "snappy"])
        fl1.addRow("压缩:", self.export_compression)
        row = QHBoxLayout()
        self.export_path = QLineEdit()
        self.export_path.setPlaceholderText("输出文件路径 (默认: export.<fmt>)")
        row.addWidget(self.export_path)
        btn = QPushButton("浏览")
        btn.clicked.connect(self._browse_export)
        row.addWidget(btn)
        fl1.addRow("路径:", row)
        btn_export = QPushButton("导出数据")
        btn_export.clicked.connect(self._run_export)
        fl1.addRow("", btn_export)
        layout.addWidget(gb1)

        # --- 统计导出 ---
        gb2 = QGroupBox("统计导出")
        fl2 = QFormLayout(gb2)
        self.stat_fmt = QComboBox()
        self.stat_fmt.addItems(["csv", "json"])
        fl2.addRow("格式:", self.stat_fmt)
        self.stat_path = QLineEdit()
        self.stat_path.setPlaceholderText("输出文件路径")
        row2 = QHBoxLayout()
        row2.addWidget(self.stat_path)
        btn2 = QPushButton("浏览")
        btn2.clicked.connect(self._browse_stat)
        row2.addWidget(btn2)
        fl2.addRow("路径:", row2)
        btn_stat = QPushButton("导出统计")
        btn_stat.clicked.connect(self._run_stat_export)
        fl2.addRow("", btn_stat)
        layout.addWidget(gb2)

        # --- 数据摘要 ---
        gb3 = QGroupBox("数据摘要")
        layout3 = QVBoxLayout(gb3)
        btn_summary = QPushButton("生成摘要")
        btn_summary.clicked.connect(self._run_summary)
        layout3.addWidget(btn_summary)
        self.summary_table = QTableWidget()
        self.summary_table.setColumnCount(6)
        self.summary_table.setHorizontalHeaderLabels(["通道名", "最小值", "最大值", "平均值", "有效数", "无效数"])
        self.summary_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.summary_table.setEditTriggers(QTableWidget.NoEditTriggers)
        layout3.addWidget(self.summary_table, 1)
        layout.addWidget(gb3, 1)

    def set_data_context(self, ctx: DataContext):
        """设置数据上下文。"""
        self.ctx = ctx

    def _browse_export(self):
        """打开文件对话框选择导出路径。"""
        path, _ = QFileDialog.getSaveFileName(self, "保存导出", "", "所有文件 (*)")
        if path:
            self.export_path.setText(path)

    def _browse_stat(self):
        """打开文件对话框选择统计导出路径。"""
        path, _ = QFileDialog.getSaveFileName(self, "保存统计", "", "CSV (*.csv);;JSON (*.json)")
        if path:
            self.stat_path.setText(path)

    def _run_export(self):
        """执行数据导出。"""
        if self.ctx is None:
            return
        fmt = self.export_fmt.currentText()
        compress = self.export_compression.currentText()
        compression = {"无": None, "gzip": "gzip", "snappy": "snappy"}.get(compress, None)
        path = self.export_path.text().strip()
        if not path:
            path = f"export.{fmt}"
        try:
            result = self.ctx.export_data(path, fmt, compression)
            self.export_path.setText(result)
        except Exception as e:
            self.export_path.setText(f"错误: {e}")

    def _run_stat_export(self):
        """执行统计结果导出。"""
        if self.ctx is None:
            return
        fmt = self.stat_fmt.currentText()
        path = self.stat_path.text().strip()
        if not path:
            path = f"statistics.{fmt}"
        try:
            # 通过 DataContext 计算并导出统计
            signals = self.ctx.get_field_names()[:20]
            stats = self.ctx.compute_parameter_stats("", "", signals)
            result = export_statistics(stats, path, fmt)
            self.stat_path.setText(result)
        except Exception as e:
            self.stat_path.setText(f"错误: {e}")

    def _run_summary(self):
        """生成并显示数据摘要表格。"""
        if self.ctx is None:
            return
        try:
            summary = self.ctx.generate_summary()
            channels = summary.get("channels", summary.get("data", {}))
            if isinstance(channels, list):
                self.summary_table.setRowCount(len(channels))
                for row, ch in enumerate(channels):
                    self.summary_table.setItem(row, 0, QTableWidgetItem(ch.get("name", "")))
                    self.summary_table.setItem(row, 1, QTableWidgetItem(str(ch.get("min", ""))))
                    self.summary_table.setItem(row, 2, QTableWidgetItem(str(ch.get("max", ""))))
                    self.summary_table.setItem(row, 3, QTableWidgetItem(str(ch.get("mean", ""))))
                    self.summary_table.setItem(row, 4, QTableWidgetItem(str(ch.get("valid_count", ""))))
                    self.summary_table.setItem(row, 5, QTableWidgetItem(str(ch.get("invalid_count", ""))))
        except Exception as e:
            self.summary_table.setRowCount(1)
            self.summary_table.setItem(0, 0, QTableWidgetItem(f"错误: {e}"))
