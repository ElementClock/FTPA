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

from PySide6.QtCore import Qt, QSettings, QThread
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QStatusBar,
    QWidget,
)

from .panel_plot import PlotCanvasWidget
from .services import DataContext
from .widgets import ParameterTreeWidget
from .. import __version__

import logging
logger = logging.getLogger(__name__)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_TXT = PROJECT_ROOT / "FTPD-AG600-007-QD-260509-G-1-飞机性能操稳-32.txt"


class MainWindow(QMainWindow):
    """FTPA 主窗口 — 3 行网格单屏布局。"""

    def __init__(self, dry_run: bool = False):
        super().__init__()
        self.dry_run = dry_run
        self.data_context: DataContext | None = None
        self._load_thread = None
        self._build_ui()

    def _build_ui(self):
        self.setWindowTitle("FTPA - 飞机性能操稳数据分析系统")
        self.setMinimumSize(1024, 680)
        self.resize(1400, 860)

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
        self.plot_widget.param_dropped.connect(self._on_param_dropped)

        self.param_tree = ParameterTreeWidget()
        self.param_tree.add_clicked.connect(self._on_add_param)
        self.param_tree.remove_clicked.connect(self._on_remove_param)
        self.param_tree.clear_clicked.connect(self._on_clear_param)

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self.plot_widget)
        splitter.addWidget(self.param_tree)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([900, 300])

        grid.addWidget(splitter, 1, 0, 1, 2)
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

        # 第 4 列 stretch
        control_grid.setColumnStretch(col_btn, 1)

        # 右列：信息显示框（跨 4 行）
        self.info_display = QPlainTextEdit()
        self.info_display.setReadOnly(True)
        self.info_display.setMaximumHeight(140)
        self.info_display.setPlaceholderText("统计/穿越/日志信息")
        self.info_display.setStyleSheet("background-color: #fafafa;")
        control_grid.addWidget(self.info_display, 0, 4, 4, 1)

        # 列比例：左 3 : 右 2
        control_grid.setColumnStretch(0, 0)  # 固定列不 stretch
        control_grid.setColumnStretch(1, 0)
        control_grid.setColumnStretch(2, 0)
        control_grid.setColumnStretch(3, 0)
        control_grid.setColumnStretch(4, 2)

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
        self._menu_layout_actions = {}
        menu_view = menubar.addMenu("视图")
        for mode, text in [("1x1", "1×1"), ("4x1", "4×1"), ("2x2", "2×2")]:
            act = QAction(text, self)
            act.setCheckable(True)
            act.setChecked(mode == "4x1")
            act.triggered.connect(lambda _, m=mode: self._switch_layout(m))
            self._menu_layout_actions[mode] = act
            menu_view.addAction(act)

        menu_view.addSeparator()

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

    # ── 布局切换 ──

    def _switch_layout(self, mode: str):
        """切换子图布局模式。"""
        self.plot_widget.set_layout_mode(mode)
        # 同步菜单项状态
        for m, act in self._menu_layout_actions.items():
            act.setChecked(m == mode)

    # ── 子图选择 ──

    def _on_subplot_selected(self, idx: int | None):
        """子图选中回调。"""
        self.param_tree.set_selected_subplot(idx)
        if idx is not None:
            self.status_bar.showMessage(f"已选中子图 {idx + 1}")

    # ── 参数树操作 ──

    def _on_add_param(self, field_name: str):
        """参数树「加入」按钮回调。"""
        self.plot_widget.add_to_subplot(field_name)
        self._update_param_tree_indicators()
        self._update_master_combo()

    def _on_remove_param(self, field_name: str):
        """参数树「删除」按钮回调。"""
        self.plot_widget.remove_from_subplot(field_name)
        self._update_param_tree_indicators()
        self._update_master_combo()

    def _on_clear_param(self):
        """参数树「清空」按钮回调。"""
        self.plot_widget.clear_selected_subplot()
        self._update_param_tree_indicators()
        self._update_master_combo()

    def _on_param_dropped(self, field_name: str):
        """拖放参数到子图后的回调 — 更新指示器和下拉框。"""
        self._update_param_tree_indicators()
        self._update_master_combo()

    def _update_param_tree_indicators(self):
        """更新参数树中的使用指示器。"""
        self.param_tree.update_indicators(self.plot_widget.subplot_fields)

    def _update_master_combo(self):
        """更新主穿越信号下拉框。"""
        current = self.master_combo.currentText()
        self.master_combo.clear()
        fields_set: set[str] = set()
        for flist in self.plot_widget.subplot_fields.values():
            fields_set.update(flist)
        sorted_fields = sorted(fields_set)
        if sorted_fields:
            self.master_combo.addItems(sorted_fields)
            self.master_combo.setEnabled(True)
            if current in sorted_fields:
                self.master_combo.setCurrentText(current)
        else:
            self.master_combo.setEnabled(False)

    # ── 穿越控制 ──

    def _on_apply_crossing(self):
        """应用穿越分析。"""
        left_val = float(self.left_threshold.text() or 0)
        left_mode = self.left_mode.currentText()
        right_val = float(self.right_threshold.text() or 0)
        right_mode = self.right_mode.currentText()
        master = self.master_combo.currentText()
        if not master:
            self._append_log("请先选择主穿越信号")
            return
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
                pass
            old_thread = None

        self.status_bar.showMessage("加载中...")
        self.apply_btn.setEnabled(False)

        self._load_thread = DataLoaderWorker(data_path, excel_path, self)
        self._load_thread.progress.connect(lambda p, m: self.status_bar.showMessage(m))
        self._load_thread.load_finished.connect(self._on_load_finished)
        self._load_thread.start()

    def _on_load_finished(self, ctx, msg: str):
        """数据加载完成回调。ctx 为 DataContext 对象或 None。"""
        if ctx is None:
            self.status_bar.showMessage("加载失败")
            QMessageBox.critical(self, "加载失败", msg)
            self._load_thread = None
            return

        try:
            self._on_data_ready(ctx)
        except Exception as e:
            logger.exception("数据加载完成后的界面刷新失败")
            QMessageBox.critical(self, "加载失败", f"数据加载后界面刷新失败：\n{e}")
        finally:
            self._load_thread = None

    def _on_data_ready(self, ctx: DataContext):
        """数据就绪，刷新界面。"""
        self.data_context = ctx

        # 验证加载状态
        if not ctx.is_loaded or not ctx.data:
            QMessageBox.critical(self, "数据无效", "数据加载后为空，请检查文件格式。")
            return

        # 记住上次成功加载的数据文件目录
        settings = QSettings("FTPA", "FTPA")
        settings.setValue("last_data_dir", os.path.dirname(ctx.data_path))

        # 重置子图（不自动填充默认信号）
        self.plot_widget.subplot_fields = {i: [] for i in range(len(self.plot_widget.axes))}

        # 填充参数树
        field_labels = ctx.get_field_labels()
        self.param_tree.set_params(field_labels)
        self.param_tree.update_indicators(self.plot_widget.subplot_fields)

        # 填充绘图区
        self.plot_widget.set_data_context(ctx)

        # 启用控件
        self.apply_btn.setEnabled(True)
        self.reset_btn.setEnabled(True)
        self.copy_btn.setEnabled(True)

        # 状态栏和信息
        self.status_bar.showMessage(
            f"已加载: {ctx.get_row_count()} 行, {ctx.get_column_count()} 列")
        self._append_log(f"数据加载完成: {ctx.data_path}")
        self._append_log(f"行数: {ctx.get_row_count()}, 信号数: {len(ctx.get_field_names())}")

        # 更新信息显示
        info_lines = [
            f"数据文件: {ctx.data_path}",
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
        """运行系统级分析（发动机/燃油/电源/CAS）。"""
        if self.data_context is None or not self.data_context.is_loaded:
            QMessageBox.information(self, "系统分析", "请先加载数据后再运行系统分析。")
            return

        try:
            from ..analysis import SystemAnalyzer

            self.status_bar.showMessage("正在运行系统分析...")
            self.apply_btn.setEnabled(False)

            analyzer = SystemAnalyzer()
            results = analyzer.analyze(self.data_context.data, self.data_context.source_type)
            reports = analyzer.generate_reports(results)

            # 保存结果到 DataContext
            self.data_context.analysis_result = results

            # 显示报告
            report_lines = []
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
            logger.error("系统分析失败: %s", e)
            QMessageBox.critical(self, "分析失败", f"系统分析出错：\n{e}")
            self.status_bar.showMessage("系统分析失败")
            self.apply_btn.setEnabled(True)

    # ── 窗口关闭清理 ──

    def closeEvent(self, event):
        """窗口关闭时清理后台线程与绘图资源，避免 C++ 对象退出时崩溃。"""
        # 停止数据加载线程
        thread = getattr(self, '_load_thread', None)
        if thread is not None:
            try:
                if thread.isRunning():
                    thread.quit()
                    thread.wait(3000)
            except RuntimeError:
                pass
            self._load_thread = None

        # 清空数据上下文，释放 numpy 数组内存
        if self.data_context is not None:
            try:
                self.data_context.unload()
            except Exception:
                pass
            self.data_context = None

        # 显式清理 matplotlib canvas，避免 Qt 退出时释放顺序冲突
        try:
            self.plot_widget.clear_data_context()
            if hasattr(self.plot_widget, 'canvas'):
                self.plot_widget.canvas.close()
        except Exception:
            pass

        event.accept()

