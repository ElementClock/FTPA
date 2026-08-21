"""曲线预览面板。

位于右侧参数树下方，点选参数时刷新显示对应数据的曲线。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from PySide6.QtWidgets import QSizePolicy, QVBoxLayout, QWidget

from ._font_config import configure_display_font

if TYPE_CHECKING:
    from .services import DataContext


class PreviewPanel(QWidget):
    """参数曲线预览区。"""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._ctx: DataContext | None = None

        configure_display_font()

        self.figure = Figure(figsize=(4, 2))
        self.canvas = FigureCanvas(self.figure)
        self.canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.canvas)

        self.setMinimumHeight(140)
        self.show_placeholder("点击右侧参数预览曲线")

    def set_data_context(self, ctx: DataContext | None) -> None:
        """绑定数据上下文。"""
        self._ctx = ctx
        self.clear_preview()

    def preview_field(self, field_name: str) -> None:
        """绘制指定字段的曲线。"""
        if self._ctx is None or not self._ctx.is_loaded:
            self.show_placeholder("数据未加载")
            return

        time_sec = self._ctx.query.get_time_sec()
        data = self._ctx.query.get_signal_data(field_name)

        if time_sec is None or data is None or len(time_sec) == 0:
            self.show_placeholder(f"无数据: {field_name}")
            return

        try:
            values = np.asarray(data, dtype=float)
        except (TypeError, ValueError):
            self.show_placeholder(f"非数值参数: {field_name}")
            return

        self.figure.clear()
        ax = self.figure.add_subplot(111)
        ax.plot(time_sec, values, linewidth=0.8, color="#1976D2")
        # 预览区只展示曲线本身，隐藏参数名/时间/刻度等已知信息以最大化曲线区域
        ax.set_xticks([])
        ax.set_yticks([])
        ax.set_xlabel("")
        ax.set_ylabel("")
        ax.set_title("")
        ax.grid(False)
        self.figure.subplots_adjust(left=0.01, right=0.99, top=0.99, bottom=0.01)
        self.canvas.draw_idle()

    def clear_preview(self) -> None:
        """清空预览区。"""
        self.show_placeholder("点击右侧参数预览曲线")

    def show_placeholder(self, text: str) -> None:
        """显示占位文字。"""
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        ax.text(
            0.5, 0.5, text,
            ha="center", va="center", transform=ax.transAxes,
            fontsize=10, color="#888888",
        )
        ax.set_axis_off()
        self.canvas.draw_idle()
