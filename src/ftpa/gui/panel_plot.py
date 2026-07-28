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
from ._pan_ctrl import PanController
from ._region_ctrl import RegionController

# 确保使用 Qt 后端（仅在 matplotlib 尚未初始化后端时设置）
if matplotlib.get_backend() == "_agg":
    matplotlib.use("QtAgg")


class PlotCanvasWidget(QWidget):
    """交互绘图画布面板 — 动态子图布局。

    外部 API 保持不变，内部委托给五个控制器：
    - _layout: LayoutController — 布局模式 + 子图选择
    - _renderer: PlotRenderer — 数据绘制 + 信号管理
    - _crossing: CrossingAnalyzer — 穿越分析 + 统计更新
    - _pan: PanController — 拖拽水平平移
    - _region: RegionController — 右键拖动框选时间区间
    """

    # 子图选中信号（发送子图索引，0-based）
    subplot_selected = Signal(object)  # int | None
    # 拖放参数添加信号（通知 MainWindow 更新指示器）
    param_dropped = Signal(str)       # 参数 field_name
    # 子图信号列表变化（添加/删除/清空）
    subplot_fields_changed = Signal()
    # 日志消息
    log_message = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.ctx: DataContext | None = None

        # 动态子图管理（共享状态）
        self._layout_mode: str = "1x1"  # "1x1" | "2x1" | "3x1" | "4x1" | "2x2"
        self.figure = Figure(figsize=(10, 6))
        self.canvas = FigureCanvas(self.figure)
        self.axes: list[plt.Axes] = []

        # 子图信号分配: 子图索引 -> field_name 列表
        self.subplot_fields: dict[int, list[str]] = {0: []}

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
        self._pan = PanController(self)
        self._region = RegionController(self)

        # 构建 UI
        self._build_ui()
        self._layout.rebuild_axes_for_mode()
        self._connect_events()

        # 拖放过滤器：安装在 canvas 上，处理参数拖入子图
        from ._drop_ctrl import CanvasDropFilter
        self._drop_filter = CanvasDropFilter(self)
        self.canvas.installEventFilter(self._drop_filter)
        self.canvas.setAcceptDrops(True)

    # ── UI 构建 ──

    def _build_ui(self):
        """构建画布布局：仅含 FigureCanvas。"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # 画布
        self.canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout.addWidget(self.canvas, 1)

    def _connect_events(self):
        """连接画布事件。

        事件分发策略：
          - button_press: PanController 先记录，LayoutController 在 release 时按需调用
          - motion_notify: PanController 处理拖拽平移 + 光标样式更新
          - button_release: PanController 处理释放 → 非平移则交由 LayoutController
          - scroll: CrossingAnalyzer 处理缩放 + Y轴自适应
        """
        self.canvas.mpl_connect("button_press_event", self._on_button_press)
        self.canvas.mpl_connect("motion_notify_event", self._on_motion)
        self.canvas.mpl_connect("button_release_event", self._on_button_release)
        self.canvas.mpl_connect("scroll_event", self._on_scroll)

    # ── 事件分发 ──

    def _on_button_press(self, event) -> None:
        """鼠标按下：PanController 记录起始位置 + RegionController 记录右键起点。

        右键行为：
          - press 时交给 RegionController 记录起点（不立即触发菜单）
          - 菜单触发推迟到 release，由 RegionController 判断是单击还是拖动
        """
        if event.button == 3:
            # 右键中断左键平移
            if self._pan.is_panning():
                self._pan.reset()
            # 交给 RegionController 记录起点
            self._region.on_press(event)
        # 左键交给 PanController
        self._pan.on_press(event)

    def _on_motion(self, event) -> None:
        """鼠标移动：RegionController 处理框选拖动 / PanController 处理平移 + 光标样式更新。"""
        # 右键框选优先：PRESSED（判断阈值）或 SELECTING（实时绘制）状态都交给 RegionController
        if self._region.get_state() in (RegionController.PRESSED, RegionController.SELECTING):
            self._region.on_motion(event)
            return

        # 然后处理拖拽平移
        self._pan.on_motion(event)

        # 光标样式：仅在非拖拽状态下且样式实际变化时更新
        if not self._pan.is_panning():
            has_data = self.ctx is not None and self.ctx.time_sec is not None and len(self.ctx.time_sec) > 0
            want_cursor = (Qt.CursorShape.OpenHandCursor
                           if event.inaxes is not None and has_data
                           else Qt.CursorShape.ArrowCursor)
            if self.canvas.cursor().shape() != want_cursor:
                self.canvas.setCursor(want_cursor)

    def _on_button_release(self, event) -> None:
        """鼠标释放：右键由 RegionController 判断拖动/单击；左键由 PanController 处理。"""
        if event.button == 3:
            # 右键释放 → RegionController 判断是拖动（框选）还是单击（菜单）
            was_region_drag = self._region.on_release(event)
            if was_region_drag:
                # 右键拖动完成 → 框选区域已建立，不触发菜单
                return
            # 右键单击 → 触发上下文菜单（与原有行为一致）
            self._right_clicked_axes_idx = None
            if event.inaxes is not None:
                for i, ax in enumerate(self.axes):
                    if ax == event.inaxes:
                        self._right_clicked_axes_idx = i
                        break
            self._renderer.show_context_menu(event)
            return

        # 左键释放：PanController 处理平移完成
        self._pan.on_release(event)
        if self._pan.was_panning():
            # 平移完成后刷新 Line2D 数据 + Y轴自适应 + 统计更新
            self._renderer.refresh_viewport_data()
            self._crossing.on_canvas_zoom(event)
        else:
            # 非平移 → 交给 LayoutController 处理子图选择
            self._layout.on_canvas_click(event)

    def _on_scroll(self, event) -> None:
        """滚轮事件：缩放时清除框选覆盖层，然后执行时间轴缩放。

        路由:
          1. 平移中 → 忽略（避免事件冲突）
          2. 清除框选覆盖层（缩放后时间范围已变化，框选不再有意义）
          3. 调用 _crossing.on_scroll_zoom 执行缩放
        """
        if self._pan.is_panning():
            return
        # 缩放操作清除框选覆盖层
        self._region.cancel_selection()
        self._crossing.on_scroll_zoom(event)

    # ── 外部 API（委托到控制器）──

    def has_region_selection(self) -> bool:
        """查询当前是否有已完成的框选区域。"""
        if self._region is None:
            return False
        return self._region.is_selected()

    def get_region_time_range(self) -> tuple[float, float] | None:
        """获取框选区域的时间范围 (t_start, t_end)，无框选时返回 None。"""
        if self._region is None:
            return None
        return self._region.get_region()

    def apply_region_selection(self) -> bool:
        """应用框选区域穿越检测。

        Returns:
            True  — 穿越检测成功，已缩放并自动清除框选
            False — 穿越检测失败或无框选区域
        """
        if self._region is None:
            return False
        return self._region.apply_selection()

    def add_signal_to_subplot(self, idx: int, field: str) -> None:
        """向指定子图添加信号（供拖放等外部调用）。"""
        self._renderer._add_to_subplot(idx, field)

    def get_selected_subplot(self) -> int | None:
        """获取当前选中的子图索引。"""
        return self._layout.get_selected_subplot()

    def get_layout_mode(self) -> str:
        """获取当前布局模式。"""
        return self._layout.get_layout_mode()

    def set_layout_mode(self, mode: str):
        """供菜单/外部调用切换布局。"""
        self._pan.reset()
        self._region.reset()
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
        """应用穿越 — 缩放到左右穿越点之间的时间区间 — 同时清除框选覆盖层。"""
        self._region.cancel_selection()
        self._crossing.apply_crossing(left_val, left_mode, right_val, right_mode, master_field)

    def reset_zoom(self):
        """重置时间范围到数据起止（保留穿越线）— 同时清除框选覆盖层。"""
        self._region.cancel_selection()
        self._crossing.reset_zoom()

    def get_stats_text(self) -> str:
        """获取当前统计文本（供外部信息显示框使用）。"""
        return self._crossing.get_stats_text()

    def set_data_context(self, ctx: DataContext):
        """设置数据上下文。"""
        self._pan.reset()
        self._region.reset()
        self._renderer.set_data_context(ctx)

    def clear_data_context(self) -> None:
        """清除数据上下文，清空所有子图和统计。"""
        self._pan.reset()
        self._region.reset()
        self._renderer.set_data_context(None)
        self.subplot_fields = {i: [] for i in range(len(self.axes))}

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
