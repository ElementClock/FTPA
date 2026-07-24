"""
交互绘图面板 — 单屏核心组件。

布局（嵌在 MainWindow Row 1 Col 0）：
┌──────────────────────────────────────────────┐
│  [1×1] [4×1] [2×2]   (布局切换按钮)          │
├──────────────────────────────────────────────┤
│                                              │
│  FigureCanvasQTAgg（动态子图布局）             │
│                                              │
│  1×1: 1个子图         4×1: 4个垂直子图        │
│  2×2: 2行2列子图                              │
│                                              │
│  点击子图 → 蓝色边框高亮                       │
└──────────────────────────────────────────────┘

架构：
  PlotCanvasWidget (QWidget)  ← 外观容器，保持外部 API
    ├── LayoutController      ← 布局模式 + 子图选择
    ├── PlotRenderer          ← 数据绘制 + 信号管理
    └── CrossingAnalyzer     ← 穿越分析 + 统计更新
"""

from __future__ import annotations

from typing import Any

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from ..plotting import _configure_display_font
from .services import DataContext
from ._layout_ctrl import LayoutController
from ._plot_renderer import PlotRenderer
from ._crossing_analyzer import CrossingAnalyzer

# 确保使用 Qt 后端（仅在 matplotlib 尚未初始化后端时设置）
if matplotlib.get_backend() == "_agg":
    matplotlib.use("QtAgg")


class PlotCanvasWidget(QWidget):
    """交互绘图画布面板 — 动态子图布局。

    外部 API 保持不变，内部委托给三个控制器：
    - _layout: LayoutController — 布局模式 + 子图选择
    - _renderer: PlotRenderer — 数据绘制 + 信号管理
    - _crossing: CrossingAnalyzer — 穿越分析 + 统计更新
    """

    # 子图选中信号（发送子图索引，0-based）
    subplot_selected = Signal(object)  # int | None
    # 日志消息
    log_message = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.ctx: DataContext | None = None

        # 动态子图管理（共享状态）
        self._layout_mode: str = "4x1"  # "1x1" | "4x1" | "2x2"
        self.figure = Figure(figsize=(10, 6))
        self.canvas = FigureCanvas(self.figure)
        self.axes: list[plt.Axes] = []

        # 子图信号分配: 子图索引 -> field_name 列表
        self.subplot_fields: dict[int, list[str]] = {i: [] for i in range(4)}

        # 子图选择
        self._selected_subplot_idx: int | None = None

        # 右键菜单追踪
        self._right_clicked_axes_idx: int | None = None

        # 首次调用时扫描字体（_configure_display_font 是惰性的）
        _configure_display_font()

        # 创建内部控制器
        self._layout = LayoutController(self)
        self._renderer = PlotRenderer(self)
        self._crossing = CrossingAnalyzer(self)

        # 构建 UI
        self._build_ui()
        self._layout.rebuild_axes_for_mode()
        self._connect_events()

    # ── UI 构建 ──

    def _build_ui(self):
        """构建画布布局：仅含 FigureCanvas。"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # 画布
        self.canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout.addWidget(self.canvas, 1)

    def _connect_events(self):
        """连接画布事件。"""
        self.canvas.mpl_connect("button_press_event", self._layout.on_canvas_click)
        self.canvas.mpl_connect("button_release_event", self._crossing.on_canvas_zoom)
        self.canvas.mpl_connect("scroll_event", self._crossing.on_canvas_zoom)

    # ── 外部 API（委托到控制器）──

    def get_selected_subplot(self) -> int | None:
        """获取当前选中的子图索引。"""
        return self._layout.get_selected_subplot()

    def get_layout_mode(self) -> str:
        """获取当前布局模式。"""
        return self._layout.get_layout_mode()

    def set_layout_mode(self, mode: str):
        """供菜单/外部调用切换布局。"""
        self._layout.switch_layout(mode)

    def add_to_subplot(self, field_name: str):
        """添加信号到当前选中的子图。"""
        self._renderer.add_to_subplot(field_name)

    def remove_from_subplot(self, field_name: str):
        """从当前选中的子图移除信号。"""
        self._renderer.remove_from_subplot(field_name)

    def clear_selected_subplot(self):
        """清空当前选中子图的所有信号（供外部按钮调用）。"""
        self._renderer.clear_selected_subplot()

    def set_crossing_context(self, left_val: float, left_mode: str,
                             right_val: float, right_mode: str, master_field: str):
        """从外部设置穿越参数。"""
        self._crossing.set_crossing_context(left_val, left_mode, right_val, right_mode, master_field)

    def apply_crossing(self, left_val: float, left_mode: str,
                       right_val: float, right_mode: str, master_field: str):
        """应用穿越 — 缩放到左右穿越点之间的时间区间。"""
        self._crossing.apply_crossing(left_val, left_mode, right_val, right_mode, master_field)

    def reset_zoom(self):
        """重置时间范围到数据起止（保留穿越线）。"""
        self._crossing.reset_zoom()

    def get_stats_text(self) -> str:
        """获取当前统计文本（供外部信息显示框使用）。"""
        return self._crossing.get_stats_text()

    def set_data_context(self, ctx: DataContext):
        """设置数据上下文。"""
        self._renderer.set_data_context(ctx)

    # ── 保存截图 ──

    def save_screenshot(self, filepath: str | None = None):
        """保存画布为图片。"""
        if filepath is None:
            path, _ = QFileDialog.getSaveFileName(
                self, "保存截图", "plot.png", "PNG (*.png);;PDF (*.pdf);;SVG (*.svg)")
            if path:
                self.figure.savefig(path, dpi=150, bbox_inches="tight")
                self.log_message.emit(f"截图已保存: {path}")
                return path
            return None
        else:
            self.figure.savefig(filepath, dpi=150, bbox_inches="tight")
            self.log_message.emit(f"截图已保存: {filepath}")
            return filepath
