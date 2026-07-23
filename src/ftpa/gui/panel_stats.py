"""
Phase 3: 统计分析面板 — 参数统计表 + 穿越分析 + 起降统计。
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from .services import DataContext
from .widgets import StatsTableWidget, TimeWindowCtrl


class StatisticsPanel(QWidget):
    """统计分析 Tab：三个子功能。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.ctx: DataContext | None = None
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        tabs = QTabWidget()
        layout.addWidget(tabs)

        # 子 Tab 1: 参数统计
        tabs.addTab(self._build_param_stats(), "参数统计")
        # 子 Tab 2: 穿越分析
        tabs.addTab(self._build_crossing(), "穿越分析")
        # 子 Tab 3: 起降统计
        tabs.addTab(self._build_takeoff(), "起降统计")

    def set_data_context(self, ctx: DataContext):
        self.ctx = ctx
        signals = list(ctx.get_field_labels().values())
        # 更新所有信号选择器（由各子面板自行处理）

    # ---------- 参数统计 ----------

    def _build_param_stats(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)

        # 时间窗口
        self.param_time = TimeWindowCtrl()

        # 信号选择
        self.param_signal_input = QLineEdit()
        self.param_signal_input.setPlaceholderText("输入信号名(用逗号分隔)，留空表示所有信号")

        btn = QPushButton("计算统计")
        btn.clicked.connect(self._run_param_stats)
        btn_row = QHBoxLayout()
        btn_row.addWidget(self.param_time)
        btn_row.addWidget(self.param_signal_input)
        btn_row.addWidget(btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        # 结果表格
        self.param_table = StatsTableWidget()
        layout.addWidget(self.param_table, 1)

        return panel

    def _run_param_stats(self):
        if self.ctx is None:
            return
        t_start, t_end = self.param_time.get_time_range()
        text = self.param_signal_input.text().strip()
        signal_ids = [s.strip() for s in text.split(",") if s.strip()] if text else None
        try:
            results = self.ctx.compute_parameter_stats(t_start or "", t_end or "", signal_ids)
            self.param_table.populate(results)
        except Exception as e:
            self.param_table.setRowCount(1)
            self.param_table.setItem(0, 0, QTableWidgetItem(f"错误: {e}"))

    # ---------- 穿越分析 ----------

    def _build_crossing(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)

        form = QFormLayout()

        self.cross_signal = QComboBox()
        self.cross_signal.setEditable(True)
        self.cross_signal.setPlaceholderText("输入或选择主信号...")
        form.addRow("主信号:", self.cross_signal)

        self.cross_associated = QLineEdit()
        self.cross_associated.setPlaceholderText("关联信号名(逗号分隔)，留空=自动")
        form.addRow("关联信号:", self.cross_associated)

        self.cross_threshold = QLineEdit()
        self.cross_threshold.setPlaceholderText("0.0")
        form.addRow("阈值:", self.cross_threshold)

        self.cross_mode = QComboBox()
        self.cross_mode.addItems(["FirstDown", "LastDown", "FirstUp", "LastUp"])
        form.addRow("模式:", self.cross_mode)

        self.cross_time = TimeWindowCtrl()
        form.addRow("", self.cross_time)

        layout.addLayout(form)

        btn = QPushButton("分析穿越")
        btn.clicked.connect(self._run_crossing)
        layout.addWidget(btn)

        self.cross_result = QTextEdit()
        self.cross_result.setReadOnly(True)
        layout.addWidget(self.cross_result, 1)

        return panel

    def _run_crossing(self):
        if self.ctx is None:
            return
        t_start, t_end = self.cross_time.get_time_range()
        mode = self.cross_mode.currentText()
        try:
            threshold = float(self.cross_threshold.text())
        except (ValueError, TypeError):
            threshold = 0.0

        main_signal = self.cross_signal.currentText().strip()
        assoc_text = self.cross_associated.text().strip()
        signal_ids = [s.strip() for s in assoc_text.split(",") if s.strip()]
        if main_signal:
            signal_ids = [main_signal] + signal_ids

        try:
            results = self.ctx.compute_crossing_analysis(
                signal_ids, mode, threshold, t_start or "", t_end or ""
            )
            self.cross_result.setPlainText("\n".join(results) if results else "无穿越结果")
        except Exception as e:
            self.cross_result.setPlainText(f"错误: {e}")

    # ---------- 起降统计 ----------

    def _build_takeoff(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)

        self.to_time = TimeWindowCtrl()

        btn = QPushButton("计算起降统计")
        btn.clicked.connect(self._run_takeoff)
        layout.addWidget(btn)

        self.to_result = QTextEdit()
        self.to_result.setReadOnly(True)
        layout.addWidget(self.to_result, 1)

        return panel

    def _run_takeoff(self):
        if self.ctx is None:
            return
        t_start, t_end = self.to_time.get_time_range()
        try:
            result = self.ctx.compute_takeoff_landing_stats(t_start or "", t_end or "")
            self.to_result.setPlainText(result)
        except Exception as e:
            self.to_result.setPlainText(f"错误: {e}")
