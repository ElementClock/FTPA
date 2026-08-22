"""
主窗口 — 3 行网格布局单屏界面。

布局结构：
┌──────────────────────────────────────────────────────────┐
│ Row 0: 菜单栏 + 工具栏（文件 | 视图 | 帮助）              │
├─────────────────────────────────┬────────────────────────┤
│ Row 1 Col 0: PlotCanvasWidget   │ Row 1 Col 1:           │
│   [1×1] [4×1] [2×2]            │   ParameterTreeWidget  │
│   ┌──────────────────┐         │   [搜索框]             │
│   │  FigureCanvas     │         │   [参数列表]           │
│   │  (动态子图)        │         │   [加入] [删除]        │
│   └──────────────────┘         │                        │
├─────────────────────────────────┴────────────────────────┤
│ Row 2: 控制面板（左: 穿越控件 | 右: 信息显示）            │
│  左阈值:[_] [FirstUp▼]  ┌─────────────────────────────┐  │
│  右阈值:[_] [LastDown▼] │  统计/穿越/日志信息          │  │
│  主穿越信号:[θ ▼]        │                              │  │
│  [应用] [重置] [复制信息] │                              │  │
└──────────────────────────────────────────────────────────┘
"""

from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import Qt, QSettings
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from .panel_plot import PlotCanvasWidget
from .panel_preview import PreviewPanel
from .services import DataContext
from .widgets import ParameterTreeWidget
from .. import __version__
from ..analysis.interval_analysis import INTERVAL_OPERATIONS, run_interval_analysis
from ..config import CONFIG
from ..utils.time_utils import format_time_seconds

import numpy as np

import logging
logger = logging.getLogger(__name__)


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_TXT = PROJECT_ROOT / "FTPD-AG600-007-QD-260509-G-1-飞机性能操稳-32.txt"


class MainWindow(QMainWindow):
    """FTPA 主窗口 — 3 行网格单屏布局。"""

    def __init__(self, dry_run: bool = False):
        super().__init__()
        self.dry_run = dry_run
        self.data_context: DataContext | None = None
        self._load_thread = None
        self._analysis_thread = None
        self._build_ui()

    def _build_ui(self):
        self.setWindowTitle("FTPA - 飞机性能操稳数据分析系统")
        self.setMinimumSize(1024, 680)
        self.resize(CONFIG.gui.window_width, CONFIG.gui.window_height)

        # 菜单栏
        self._build_menu()

        # 中央组件
        central = QWidget()
        grid = QGridLayout(central)
        grid.setSpacing(6)
        grid.setContentsMargins(8, 4, 8, 4)

        # === Row 1: 绘图区 + 参数树 ===
        self.plot_widget = PlotCanvasWidget()
        self.plot_widget.log_message.connect(self._append_log)
        self.plot_widget.subplot_selected.connect(self._on_subplot_selected)
        self.plot_widget.param_dropped.connect(self._on_subplot_fields_changed)
        self.plot_widget.subplot_fields_changed.connect(self._on_subplot_fields_changed)

        self.param_tree = ParameterTreeWidget()
        self.preview_panel = PreviewPanel()
        self.param_tree.param_selected.connect(self._on_param_selected_for_preview)

        # 右侧容器：参数树 + 曲线预览区（右下角）
        self._right_panel = QWidget()
        self._right_layout = QVBoxLayout(self._right_panel)
        self._right_layout.setContentsMargins(0, 0, 0, 0)
        self._right_layout.setSpacing(0)

        self._right_splitter = QSplitter(Qt.Vertical)
        self._right_splitter.addWidget(self.param_tree)
        self._right_splitter.addWidget(self.preview_panel)
        self._right_splitter.setStretchFactor(0, 3)
        self._right_splitter.setStretchFactor(1, 2)
        self._right_splitter.setCollapsible(0, False)
        self._right_splitter.setCollapsible(1, True)
        self._right_splitter.setSizes([400, 180])
        self._right_layout.addWidget(self._right_splitter)

        self._splitter = QSplitter(Qt.Horizontal)
        self._splitter.addWidget(self.plot_widget)
        self._splitter.addWidget(self._right_panel)
        self._splitter.setStretchFactor(0, 5)
        self._splitter.setStretchFactor(1, 1)
        self._splitter.setCollapsible(0, False)   # 绘图区不可折叠
        self._splitter.setCollapsible(1, True)    # 右侧面板可折叠

        # 参数面板最小宽度：控制面板在小于此宽度时自动隐藏
        # 默认阈值 50px（约为 QSplitter 默认折叠阈值 ~150px 的 1/3）
        self._PANEL_COLLAPSE_THRESHOLD = 50
        self.param_tree.setMinimumWidth(30)  # 允许拖拽到很窄但仍可见
        self._splitter.splitterMoved.connect(self._on_splitter_moved)

        # 从 QSettings 恢复用户上次的分隔条尺寸，首次使用默认值
        settings = QSettings("FTPA", "FTPA")
        saved_sizes = settings.value("splitter_sizes")
        if saved_sizes is not None:
            try:
                self._splitter.setSizes([int(s) for s in saved_sizes])
            except (ValueError, TypeError):
                self._splitter.setSizes([960, 160])
        else:
            self._splitter.setSizes([960, 160])

        grid.addWidget(self._splitter, 1, 0, 1, 2)
        grid.setRowStretch(1, 1)  # Row 1 占据所有剩余空间

        # === Row 2: 控制面板 ===
        control_widget = QWidget()
        control_grid = QGridLayout(control_widget)
        control_grid.setContentsMargins(0, 4, 0, 0)
        control_grid.setHorizontalSpacing(8)
        control_grid.setVerticalSpacing(4)

        # 各列宽度：标签固定 70px，阈值输入固定 90px，模式下拉 120px，按钮区
        col_label = 0
        col_input = 1
        col_mode  = 2
        col_btn   = 3

        # 第 0 行：左阈值
        control_grid.addWidget(QLabel("左阈值:"), 0, col_label, Qt.AlignRight | Qt.AlignVCenter)
        self.left_threshold = QLineEdit()
        self.left_threshold.setPlaceholderText("阈值")
        self.left_threshold.setFixedWidth(90)
        control_grid.addWidget(self.left_threshold, 0, col_input)
        self.left_mode = QComboBox()
        self.left_mode.addItems(["FirstUp", "LastUp", "FirstDown", "LastDown"])
        self.left_mode.setCurrentText("FirstUp")
        self.left_mode.setFixedWidth(120)
        control_grid.addWidget(self.left_mode, 0, col_mode)

        # 第 1 行：右阈值
        control_grid.addWidget(QLabel("右阈值:"), 1, col_label, Qt.AlignRight | Qt.AlignVCenter)
        self.right_threshold = QLineEdit()
        self.right_threshold.setPlaceholderText("阈值")
        self.right_threshold.setFixedWidth(90)
        control_grid.addWidget(self.right_threshold, 1, col_input)
        self.right_mode = QComboBox()
        self.right_mode.addItems(["FirstUp", "LastUp", "FirstDown", "LastDown"])
        self.right_mode.setCurrentText("LastDown")
        self.right_mode.setFixedWidth(120)
        control_grid.addWidget(self.right_mode, 1, col_mode)

        # 第 2 行：主穿越信号
        control_grid.addWidget(QLabel("主穿越信号:"), 2, col_label, Qt.AlignRight | Qt.AlignVCenter)
        self.master_combo = QComboBox()
        self.master_combo.setMinimumWidth(160)
        self.master_combo.setEnabled(False)
        control_grid.addWidget(self.master_combo, 2, col_input, 1, 2)  # 占 input+mode 两列

        # 第 3 行：应用 + 重置 + 复制信息
        self.apply_btn = QPushButton("应用")
        self.apply_btn.clicked.connect(self._on_apply_crossing)
        self.apply_btn.setEnabled(False)
        control_grid.addWidget(self.apply_btn, 3, col_label)

        self.reset_btn = QPushButton("重置")
        self.reset_btn.clicked.connect(self._on_reset_zoom)
        self.reset_btn.setEnabled(False)
        control_grid.addWidget(self.reset_btn, 3, col_input)

        self.copy_btn = QPushButton("复制信息")
        self.copy_btn.clicked.connect(self._on_copy_info)
        self.copy_btn.setEnabled(False)
        control_grid.addWidget(self.copy_btn, 3, col_mode)

        # 第 4 列 stretch（按钮区）
        control_grid.setColumnStretch(col_btn, 1)

        # ── 区间分析模块（阈值选取区域右侧）──
        self.analysis_group = QGroupBox("区间分析")
        analysis_layout = QVBoxLayout(self.analysis_group)
        analysis_layout.setContentsMargins(6, 4, 6, 4)
        analysis_layout.setSpacing(4)

        row1 = QHBoxLayout()
        row1.addWidget(QLabel("目标信号:"))
        self.target_signal_combo = QComboBox()
        self.target_signal_combo.setMinimumWidth(120)
        self.target_signal_combo.setEnabled(False)
        row1.addWidget(self.target_signal_combo, 1)
        analysis_layout.addLayout(row1)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("功能:"))
        self.analysis_op_combo = QComboBox()
        self.analysis_op_combo.addItems(list(INTERVAL_OPERATIONS.keys()))
        self.analysis_op_combo.setEnabled(False)
        row2.addWidget(self.analysis_op_combo, 1)
        self.analysis_run_btn = QPushButton("执行分析")
        self.analysis_run_btn.setEnabled(False)
        self.analysis_run_btn.clicked.connect(self._on_run_interval_analysis)
        row2.addWidget(self.analysis_run_btn)
        analysis_layout.addLayout(row2)

        self.analysis_interval_label = QLabel("区间: 当前视图")
        analysis_layout.addWidget(self.analysis_interval_label)

        control_grid.addWidget(self.analysis_group, 0, 4, 4, 1)

        # 右列：信息显示框（跨 4 行）
        self.info_display = QPlainTextEdit()
        self.info_display.setReadOnly(True)
        self.info_display.setMaximumHeight(140)
        self.info_display.setPlaceholderText("统计/穿越/日志信息")
        self.info_display.setStyleSheet("background-color: #fafafa;")
        control_grid.addWidget(self.info_display, 0, 5, 4, 1)

        # 列比例：左固定，分析模块固定，右侧信息框弹性
        control_grid.setColumnStretch(0, 0)  # 固定列不 stretch
        control_grid.setColumnStretch(1, 0)
        control_grid.setColumnStretch(2, 0)
        control_grid.setColumnStretch(3, 0)
        control_grid.setColumnStretch(4, 0)
        control_grid.setColumnStretch(5, 2)

        grid.addWidget(control_widget, 2, 0, 1, 2)
        grid.setRowStretch(2, 0)

        self.setCentralWidget(central)

        # 状态栏
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("就绪")

    # ── 菜单栏 ──

    def _build_menu(self):
        menubar = self.menuBar()

        # 文件
        menu_file = menubar.addMenu("文件")
        act_load = QAction("加载数据...", self)
        act_load.setShortcut("Ctrl+O")
        act_load.triggered.connect(self._load_data)
        menu_file.addAction(act_load)

        act_export = QAction("导出截图...", self)
        act_export.setShortcut("Ctrl+E")
        act_export.triggered.connect(self._save_screenshot)
        menu_file.addAction(act_export)

        menu_file.addSeparator()

        act_unload = QAction("卸载数据", self)
        act_unload.triggered.connect(self._unload_data)
        menu_file.addAction(act_unload)

        act_sys_analysis = QAction("系统分析...", self)
        act_sys_analysis.triggered.connect(self._run_system_analysis)
        menu_file.addAction(act_sys_analysis)

        menu_file.addSeparator()

        act_quit = QAction("退出", self)
        act_quit.setShortcut("Ctrl+Q")
        act_quit.triggered.connect(self.close)
        menu_file.addAction(act_quit)

        # 视图
        menu_view = menubar.addMenu("视图")

        act_panel = QAction("参数面板", self)
        act_panel.setCheckable(True)
        act_panel.setChecked(True)
        act_panel.triggered.connect(self._toggle_param_panel)
        menu_view.addAction(act_panel)

        act_status = QAction("状态栏", self)
        act_status.setCheckable(True)
        act_status.setChecked(True)
        act_status.triggered.connect(lambda checked: self.status_bar.setVisible(checked))
        menu_view.addAction(act_status)

        # 帮助
        menu_help = menubar.addMenu("帮助")
        act_about = QAction("关于", self)
        act_about.triggered.connect(self._show_about)
        menu_help.addAction(act_about)

    def _show_about(self):
        QMessageBox.about(
            self,
            "关于 FTPA",
            "FTPA - 飞机性能操稳数据分析系统\n\n"
            "AG600 试飞数据处理工具\n"
            "版本 " + __version__
        )

    # ── 分隔条面板折叠 ──

    def _on_splitter_moved(self, pos: int, index: int):
        """分隔条移动时检测右侧面板是否需要自动隐藏/显示。"""
        sizes = self._splitter.sizes()
        if len(sizes) < 2:
            return
        panel_width = sizes[1]
        if panel_width < self._PANEL_COLLAPSE_THRESHOLD and self._right_panel.isVisible():
            self._right_panel.hide()
            self.status_bar.showMessage("参数面板已隐藏，点击菜单「视图 → 参数面板」恢复", 3000)
        elif panel_width >= self._PANEL_COLLAPSE_THRESHOLD and not self._right_panel.isVisible():
            self._right_panel.show()

    def _toggle_param_panel(self, visible: bool):
        """切换参数面板的显示/隐藏。"""
        if visible and not self._right_panel.isVisible():
            self._right_panel.show()
            # 恢复到合理宽度
            sizes = self._splitter.sizes()
            total = sum(sizes) if sizes else 1120
            self._splitter.setSizes([int(total * 0.85), int(total * 0.15)])
        elif not visible and self._right_panel.isVisible():
            self._right_panel.hide()

    # ── 子图选择 ──

    def _on_subplot_selected(self, idx: int | None):
        """子图选中回调。"""
        self.param_tree.set_selected_subplot(idx)
        if idx is not None:
            self.status_bar.showMessage(f"已选中子图 {idx + 1}")

    def _on_param_selected_for_preview(self, field_name: str):
        """点选右侧参数时，在右下角预览区刷新曲线。"""
        if self.data_context is not None and self.data_context.is_loaded:
            self.preview_panel.preview_field(field_name)
        else:
            self.preview_panel.clear_preview()

    # ── 区间分析 ──

    def _update_target_signal_combo(self, ctx: DataContext) -> None:
        """填充区间分析目标信号下拉框。"""
        current_text = self.target_signal_combo.currentText()
        self.target_signal_combo.clear()
        self._target_combo_label_to_field: dict[str, str] = {}

        for field in ctx.get_field_names():
            label = ctx.get_label(field)
            self._target_combo_label_to_field[label] = field
            self.target_signal_combo.addItem(label)

        has_fields = self.target_signal_combo.count() > 0
        self.target_signal_combo.setEnabled(has_fields)
        self.analysis_op_combo.setEnabled(has_fields)
        self.analysis_run_btn.setEnabled(has_fields)

        if current_text in self._target_combo_label_to_field:
            self.target_signal_combo.setCurrentText(current_text)
        self.analysis_interval_label.setText("区间: 当前视图")

    def _reset_interval_analysis_controls(self) -> None:
        """清空并禁用区间分析控件。"""
        self.target_signal_combo.clear()
        self.target_signal_combo.setEnabled(False)
        self.analysis_op_combo.setEnabled(False)
        self.analysis_run_btn.setEnabled(False)
        self.analysis_interval_label.setText("区间: 当前视图")

    def _get_analysis_interval(self) -> tuple[float, float] | None:
        """自动确定分析区间：优先框选区域，否则当前视图。"""
        if self.plot_widget.has_region_selection():
            region = self.plot_widget.get_region_time_range()
            if region is not None:
                return region
        if self.plot_widget.axes:
            xlim = self.plot_widget.axes[0].get_xlim()
            return float(xlim[0]), float(xlim[1])
        return None

    def _on_run_interval_analysis(self) -> None:
        """执行区间分析并将结果追加到信息框（统一异常兜底）。"""
        self.status_bar.showMessage("区间分析执行中...")
        try:
            self._do_interval_analysis()
            self.status_bar.showMessage("区间分析完成", 3000)
        except Exception as e:
            self._append_log(f"[区间分析] 执行失败: {e}")
            logger.exception("区间分析执行失败")
            self.status_bar.showMessage("区间分析失败", 3000)

    def _do_interval_analysis(self) -> None:
        """区间分析内部实现。"""
        if self.data_context is None or not self.data_context.is_loaded:
            self._append_log("[区间分析] 数据未加载")
            return

        label = self.target_signal_combo.currentText()
        if not label:
            self._append_log("[区间分析] 请先选择目标信号")
            return
        field = self._target_combo_label_to_field.get(label, label)
        time_sec = self.data_context.query.get_time_sec()
        values = self.data_context.query.get_signal_data(field)

        if time_sec is None or values is None:
            self._append_log(f"[区间分析] 信号 {label} 无数据")
            return

        interval = self._get_analysis_interval()
        if interval is None:
            self._append_log("[区间分析] 无法获取分析区间")
            return

        t_start, t_end = interval
        i_start = int(np.searchsorted(time_sec, t_start, side="left"))
        i_end = int(np.searchsorted(time_sec, t_end, side="right"))

        if i_end <= i_start:
            self._append_log(
                f"[区间分析] 区间内无数据: "
                f"{format_time_seconds(t_start)} - {format_time_seconds(t_end)}"
            )
            return

        operation = self.analysis_op_combo.currentText()
        result = run_interval_analysis(
            time_sec[i_start:i_end],
            values[i_start:i_end],
            operation,
        )

        self.analysis_interval_label.setText(
            f"区间: {format_time_seconds(t_start)} - {format_time_seconds(t_end)}"
        )
        self._append_log(f"[区间分析] {label} {operation}: {result}")

    # ── 参数树操作 ──

    def _on_subplot_fields_changed(self, field_name: str = ""):
        """子图信号列表变化 / 拖放参数回调 — 更新参数树指示器和穿越信号下拉框。"""
        self._update_param_tree_indicators()
        self._update_master_combo()

    def _update_param_tree_indicators(self):
        """更新参数树中的使用指示器。"""
        self.param_tree.update_indicators(self.plot_widget.subplot_fields)

    def _update_master_combo(self):
        """更新主穿越信号下拉框（显示中文标签）。"""
        current_text = self.master_combo.currentText()
        self.master_combo.clear()
        self._combo_label_to_field: dict[str, str] = {}

        fields_set: set[str] = set()
        for flist in self.plot_widget.subplot_fields.values():
            fields_set.update(flist)

        if not fields_set:
            self.master_combo.setEnabled(False)
            return

        # 按 display_label 排序，建立反向映射
        ctx = self.data_context
        label_field_pairs: list[tuple[str, str]] = []
        for f in fields_set:
            label = ctx.get_label(f) if ctx else f
            label_field_pairs.append((label, f))
        label_field_pairs.sort(key=lambda x: x[0])

        for label, field in label_field_pairs:
            self._combo_label_to_field[label] = field
            self.master_combo.addItem(label)

        self.master_combo.setEnabled(True)

        # 恢复之前的选中项
        if current_text in self._combo_label_to_field:
            self.master_combo.setCurrentText(current_text)

    # ── 穿越控制 ──

    def _safe_float(self, text: str, default: float = 0.0) -> float:
        """安全转换文本为浮点数，失败时返回默认值并提示。"""
        try:
            return float(text) if text else default
        except ValueError:
            self._append_log(f"无效数值输入: '{text}'，使用默认值 {default}")
            return default

    def _on_apply_crossing(self):
        """应用穿越分析。

        当有框选区域时，在框选区间内执行穿越检测；
        否则使用当前视图范围（原有行为）。
        """
        left_val = self._safe_float(self.left_threshold.text(), 0.0)
        left_mode = self.left_mode.currentText()
        right_val = self._safe_float(self.right_threshold.text(), 0.0)
        right_mode = self.right_mode.currentText()
        # 从中文标签反查 field_name
        master_label = self.master_combo.currentText()
        master = self._combo_label_to_field.get(master_label, master_label)
        if not master:
            self._append_log("请先选择主穿越信号")
            return

        # 检测是否有框选区域
        region = self.plot_widget.get_region_time_range() if self.plot_widget.has_region_selection() else None

        if region is not None:
            # 有框选区域 → 设置穿越参数后在框选区间内执行穿越检测
            self.plot_widget.set_crossing_context(left_val, left_mode, right_val, right_mode, master)
            success = self.plot_widget.apply_region_selection()
            if success:
                # 更新信息显示框
                stats = self.plot_widget.get_stats_text()
                if stats:
                    self.info_display.setPlainText(stats)
                self._append_log(f"区域穿越分析: 主信号={master}")
            # 失败时 apply_selection 已发送日志
        else:
            # 无框选区域 → 使用当前视图范围（原有行为）
            self.plot_widget.apply_crossing(left_val, left_mode, right_val, right_mode, master)
            # 更新信息显示框
            stats = self.plot_widget.get_stats_text()
            if stats:
                self.info_display.setPlainText(stats)
            self._append_log(f"穿越分析: 主信号={master}")

    def _on_reset_zoom(self):
        """重置缩放。"""
        self.plot_widget.reset_zoom()
        stats = self.plot_widget.get_stats_text()
        if stats:
            self.info_display.setPlainText(stats)
        self._append_log("缩放已重置")

    def _on_copy_info(self):
        """复制信息到剪贴板。"""
        text = self.info_display.toPlainText()
        if text:
            QApplication.clipboard().setText(text)
            self.status_bar.showMessage("已复制到剪贴板", 2000)

    # ── 日志 / 信息显示 ──

    def _append_log(self, message: str):
        """在信息显示框中追加日志消息。"""
        import datetime
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        self.info_display.appendPlainText(f"[{ts}] {message}")

    # ── 截图 ──

    def _save_screenshot(self):
        """保存截图。"""
        self.plot_widget.save_screenshot()

    # ── 数据加载 ──

    def _load_data(self):
        """加载数据——自动发现标签文件，不再手动选择。"""
        from ..utils import resolve_excel_path

        settings = QSettings("FTPA", "FTPA")
        last_dir = settings.value("last_data_dir", str(DEFAULT_TXT))
        dp, _ = QFileDialog.getOpenFileName(
            self, "选择数据文件", last_dir, "数据文件 (*.txt *.csv);;文本文件 (*.txt);;CSV文件 (*.csv);;所有文件 (*)")
        if not dp:
            return

        ep = resolve_excel_path()
        if not os.path.exists(ep):
            logger.warning("标签文件自动发现失败: %s", ep)

        self._do_load(dp, ep)

    def _do_load(self, data_path: str, excel_path: str):
        """后台线程加载数据。使用 QThread 子类模式，避免 moveToThread 生命周期问题。"""
        from .worker import DataLoaderWorker

        logger.info("开始加载: data_path=%s", data_path)
        logger.info("  os.path.exists(data_path)=%s", os.path.exists(data_path))
        logger.info("  excel_path=%s, os.path.exists(excel_path)=%s", excel_path, os.path.exists(excel_path))

        if not os.path.exists(data_path):
            QMessageBox.warning(self, "文件错误", f"数据文件不存在:\n{data_path}")
            return

        # 清理上一次加载的线程
        old_thread = getattr(self, '_load_thread', None)
        self._load_thread = None
        if old_thread is not None:
            try:
                if old_thread.isRunning():
                    old_thread.quit()
                    old_thread.wait(3000)
            except RuntimeError:
                logger.warning("旧加载线程清理失败", exc_info=True)
            old_thread = None

        self.status_bar.showMessage("加载中...")
        self.apply_btn.setEnabled(False)

        self._load_thread = DataLoaderWorker(data_path, excel_path, self)
        self._load_thread.progress.connect(lambda p, m: self.status_bar.showMessage(m))
        self._load_thread.load_finished.connect(self._on_load_finished)
        self._load_thread.start()

    def _reset_to_unloaded_state(self) -> None:
        """安全重置 GUI 到未加载状态（数据加载失败后调用）。"""
        try:
            if self.data_context is not None:
                self.data_context.unload()
        except Exception:
            logger.warning("卸载数据失败", exc_info=True)
        self.data_context = None
        self.plot_widget.clear_data_context()
        self.param_tree.clear_params()
        self.preview_panel.clear_preview()
        self._reset_interval_analysis_controls()
        self.apply_btn.setEnabled(False)
        self.reset_btn.setEnabled(False)
        self.copy_btn.setEnabled(False)
        self.master_combo.clear()
        self.master_combo.setEnabled(False)
        self.info_display.clear()
        self.status_bar.showMessage("就绪")

    def _on_load_finished(self, ctx, msg: str):
        """数据加载完成回调。ctx 为 DataContext 对象或 None。"""
        if ctx is None:
            self.status_bar.showMessage("加载失败")
            QMessageBox.critical(self, "加载失败", msg)
            self._reset_to_unloaded_state()
            self._load_thread = None
            return

        try:
            self._on_data_ready(ctx)
        except Exception as e:
            logger.exception("数据加载完成后的界面刷新失败")
            self._reset_to_unloaded_state()
            QMessageBox.critical(self, "加载失败", f"数据加载后界面刷新失败：\n{e}")
        finally:
            self._load_thread = None

    def _on_data_ready(self, ctx: DataContext):
        """数据就绪，刷新界面。"""
        self.data_context = ctx

        # 验证加载状态
        if not ctx.is_loaded or not ctx.query.has_data():
            QMessageBox.critical(self, "数据无效", "数据加载后为空，请检查文件格式。")
            return

        # 记住上次成功加载的数据文件目录
        settings = QSettings("FTPA", "FTPA")
        settings.setValue("last_data_dir", os.path.dirname(ctx.query.get_data_path()))

        # 重置子图（不自动填充默认信号）
        self.plot_widget.subplot_fields = {i: [] for i in range(len(self.plot_widget.axes))}

        # 填充参数树（完整参数库 + 当前数据可用标记）
        field_labels, available_fields = ctx.get_all_field_labels_with_units()
        self.param_tree.set_params(field_labels, available_fields=available_fields)
        self.param_tree.update_indicators(self.plot_widget.subplot_fields)

        # 填充绘图区
        self.plot_widget.set_data_context(ctx)

        # 绑定预览区并清空初始状态
        self.preview_panel.set_data_context(ctx)

        # 填充区间分析目标信号
        self._update_target_signal_combo(ctx)

        # 启用控件
        self.apply_btn.setEnabled(True)
        self.reset_btn.setEnabled(True)
        self.copy_btn.setEnabled(True)

        # 状态栏和信息
        self.status_bar.showMessage(
            f"已加载: {ctx.get_row_count()} 行, {ctx.get_column_count()} 列")
        self._append_log(f"数据加载完成: {ctx.query.get_data_path()}")
        self._append_log(f"行数: {ctx.get_row_count()}, 信号数: {len(ctx.get_field_names())}")

        # 更新信息显示
        info_lines = [
            f"数据文件: {ctx.query.get_data_path()}",
            f"行数: {ctx.get_row_count()}, 列数: {ctx.get_column_count()}",
            f"时间范围: {ctx.get_time_range_sec()[0]:.1f}s - {ctx.get_time_range_sec()[1]:.1f}s",
            f"信号数量: {len(ctx.get_field_names())}",
        ]
        self.info_display.setPlainText("\n".join(info_lines))

    def _unload_data(self):
        """卸载当前数据，清空界面所有关联状态。"""
        if self.data_context is None or not self.data_context.is_loaded:
            self.status_bar.showMessage("当前无数据可卸载")
            return

        # 确认对话框
        reply = QMessageBox.question(
            self, "确认卸载",
            "确定要卸载当前数据吗？\n所有图表和统计结果将被清空。",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        # DataContext 卸载
        self.data_context.unload()

        # 清空绘图区
        self.plot_widget.clear_data_context()

        # 清空参数树
        self.param_tree.clear_params()

        # 清空预览区
        self.preview_panel.clear_preview()

        # 清空区间分析控件
        self._reset_interval_analysis_controls()

        # 禁用控件
        self.apply_btn.setEnabled(False)
        self.reset_btn.setEnabled(False)
        self.copy_btn.setEnabled(False)

        # 清空信息显示
        self.info_display.clear()
        self.master_combo.clear()
        self.master_combo.setEnabled(False)

        # 清空穿越控件
        self.left_threshold.clear()
        self.right_threshold.clear()

        self.status_bar.showMessage("数据已卸载")
        self._append_log("数据已卸载")

    # ── 系统分析 ──

    def _run_system_analysis(self):
        """运行系统级分析（发动机/燃油/电源/CAS）——后台线程执行，避免冻结 GUI。"""
        if self.data_context is None or not self.data_context.is_loaded:
            QMessageBox.information(self, "系统分析", "请先加载数据后再运行系统分析。")
            return

        from .worker import AnalysisWorker

        # 清理上一次分析线程
        old_thread = getattr(self, '_analysis_thread', None)
        self._analysis_thread = None
        if old_thread is not None:
            try:
                if old_thread.isRunning():
                    old_thread.quit()
                    old_thread.wait(3000)
            except RuntimeError:
                logger.warning("旧分析线程清理失败", exc_info=True)
            old_thread = None

        self.status_bar.showMessage("正在运行系统分析...")
        self.apply_btn.setEnabled(False)

        worker = AnalysisWorker(
            self.data_context.query.get_raw_data(),
            self.data_context.query.get_source_type(),
            self,
        )
        worker.progress.connect(lambda p, m: self.status_bar.showMessage(m))
        worker.analysis_finished.connect(self._on_analysis_finished)
        self._analysis_thread = worker
        worker.start()

    def _on_analysis_finished(self, results, reports, error_msg: str):
        """系统分析完成回调（主线程执行）。"""
        if error_msg:
            logger.error("系统分析失败: %s", error_msg)
            QMessageBox.critical(self, "分析失败", error_msg)
            self.status_bar.showMessage("系统分析失败")
            self.apply_btn.setEnabled(True)
            self._analysis_thread = None
            return

        try:
            # 保存结果到 DataContext
            if self.data_context is not None:
                self.data_context.analysis_result = results

            # 显示报告
            report_lines = []
            if reports:
                for name, text in reports.items():
                    if text:
                        report_lines.append(text)
                        report_lines.append("")

            if report_lines:
                self.info_display.setPlainText("\n".join(report_lines))
            else:
                self.info_display.setPlainText("系统分析完成，未生成报告（可能缺少相关数据列）。")

            self.status_bar.showMessage("系统分析完成")
            self._append_log("系统分析完成")
            self.apply_btn.setEnabled(True)
        except Exception as e:
            logger.exception("系统分析完成后界面刷新失败")
            QMessageBox.critical(self, "分析失败", f"系统分析结果展示出错：\n{e}")
            self.status_bar.showMessage("系统分析失败")
            self.apply_btn.setEnabled(True)
        finally:
            self._analysis_thread = None

    # ── 窗口关闭清理 ──

    def closeEvent(self, event):
        """窗口关闭时清理后台线程与绘图资源，避免 C++ 对象退出时崩溃。"""
        # 保存分隔条尺寸到 QSettings（用户下次启动恢复）
        try:
            settings = QSettings("FTPA", "FTPA")
            settings.setValue("splitter_sizes", self._splitter.sizes())
        except Exception:
            logger.warning("QSettings 保存失败", exc_info=True)

        # 停止数据加载线程
        thread = getattr(self, '_load_thread', None)
        if thread is not None:
            try:
                if thread.isRunning():
                    thread.quit()
                    thread.wait(3000)
            except RuntimeError:
                logger.warning("加载线程清理失败", exc_info=True)
            self._load_thread = None

        # 停止系统分析线程
        analysis_thread = getattr(self, '_analysis_thread', None)
        if analysis_thread is not None:
            try:
                if analysis_thread.isRunning():
                    analysis_thread.quit()
                    analysis_thread.wait(3000)
            except RuntimeError:
                logger.warning("分析线程清理失败", exc_info=True)
            self._analysis_thread = None

        # 清空数据上下文，释放 numpy 数组内存
        if self.data_context is not None:
            try:
                self.data_context.unload()
            except Exception:
                logger.warning("数据卸载失败", exc_info=True)
            self.data_context = None

        # 显式清理 matplotlib canvas，避免 Qt 退出时释放顺序冲突
        try:
            self.plot_widget.clear_data_context()
            if hasattr(self.plot_widget, 'canvas'):
                self.plot_widget.canvas.close()
            self.preview_panel.clear_preview()
            if hasattr(self.preview_panel, 'canvas'):
                self.preview_panel.canvas.close()
        except Exception:
            logger.warning("Canvas 清理失败", exc_info=True)

        event.accept()

