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

        label = self._ctx.get_label(field_name)
        unit = self._ctx.query.get_label_map().get_unit(field_name) if self._ctx.query.get_label_map() else None
        ylabel = f"{label} ({unit})" if unit else label

        self.figure.clear()
        ax = self.figure.add_subplot(111)
        ax.plot(time_sec, values, linewidth=0.8, color="#1976D2")
        ax.set_xlabel("时间 (s)")
        ax.set_ylabel(ylabel)
        ax.set_title(label, fontsize=9)
        ax.grid(True, alpha=0.3)
        self.figure.tight_layout()
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
