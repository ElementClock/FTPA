"""
Phase 4: 航线轨迹面板 — 经纬度轨迹图 + 拟合圆半径。
"""

from __future__ import annotations

import matplotlib
matplotlib.use("QtAgg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ..computing import compute_fitted_circle_radius
from .services import DataContext
from .widgets import TimeWindowCtrl


class TrackPanel(QWidget):
    """航线轨迹面板。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.ctx: DataContext | None = None
        self.figure = Figure(figsize=(8, 6))
        self.canvas = FigureCanvas(self.figure)
        self._build_ui()

    def _build_ui(self):
        layout = QHBoxLayout(self)

        # 左侧控件
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)

        form = QGroupBox("轨迹设置")
        fl = QFormLayout(form)
        self.lat_combo = QComboBox()
        self.lon_combo = QComboBox()
        fl.addRow("纬度字段:", self.lat_combo)
        fl.addRow("经度字段:", self.lon_combo)
        left_layout.addWidget(form)

        self.track_time = TimeWindowCtrl()
        left_layout.addWidget(self.track_time)

        btn_draw = QPushButton("绘制轨迹")
        btn_draw.clicked.connect(self._draw_track)
        left_layout.addWidget(btn_draw)

        self.fit_btn = QPushButton("拟合圆半径")
        self.fit_btn.clicked.connect(self._compute_circle)
        self.fit_btn.setEnabled(False)
        left_layout.addWidget(self.fit_btn)

        self.result_text = QTextEdit()
        self.result_text.setReadOnly(True)
        self.result_text.setMaximumHeight(80)
        left_layout.addWidget(self.result_text)

        left_layout.addStretch()

        # 右侧画布
        self.canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        layout.addWidget(left, 1)
        layout.addWidget(self.canvas, 3)

    def set_data_context(self, ctx: DataContext):
        self.ctx = ctx
        fields = ctx.get_field_names()
        # 自动匹配可能的经纬度字段
        lat_candidates = [f for f in fields if "lat" in f.lower() or "纬度" in ctx.get_label(f)]
        lon_candidates = [f for f in fields if "lon" in f.lower() or "经度" in ctx.get_label(f)]
        self.lat_combo.addItems(lat_candidates or fields)
        self.lon_combo.addItems(lon_candidates or fields)

    def _draw_track(self):
        if self.ctx is None:
            return
        lat_field = self.lat_combo.currentText()
        lon_field = self.lon_combo.currentText()
        lat = self.ctx.data.get(lat_field)
        lon = self.ctx.data.get(lon_field)
        if lat is None or lon is None or len(lat) < 2:
            self.result_text.setPlainText("经纬度数据不足")
            return

        t_start, t_end = self.track_time.get_time_range()
        if t_start is not None and t_end is not None and self.ctx.time_sec is not None:
            from ..time_utils import select_time_window
            idx, _, _ = select_time_window(self.ctx.time_sec, t_start, t_end)
            lat_arr = np.asarray(lat, dtype=float)[idx]
            lon_arr = np.asarray(lon, dtype=float)[idx]
        else:
            lat_arr = np.asarray(lat, dtype=float)
            lon_arr = np.asarray(lon, dtype=float)

        if len(lat_arr) < 2:
            self.result_text.setPlainText("窗口内数据不足")
            return

        self.figure.clear()
        ax = self.figure.add_subplot(111)
        ax.plot(lon_arr, lat_arr, linewidth=1, color="blue")
        ax.plot(lon_arr[0], lat_arr[0], "go", markersize=8, label="起点")
        ax.plot(lon_arr[-1], lat_arr[-1], "ro", markersize=8, label="终点")
        ax.set_xlabel("经度 (°)")
        ax.set_ylabel("纬度 (°)")
        ax.set_title("航线轨迹")
        ax.grid(True)
        ax.set_aspect("equal")
        ax.legend()
        self.figure.tight_layout()
        self.canvas.draw_idle()
        self.fit_btn.setEnabled(True)
        self.result_text.setPlainText(f"轨迹已绘制: {len(lat_arr)} 点")

    def _compute_circle(self):
        if self.ctx is None:
            return
        lat_field = self.lat_combo.currentText()
        lon_field = self.lon_combo.currentText()
        t_start, t_end = self.track_time.get_time_range()
        try:
            R = compute_fitted_circle_radius(
                self.ctx.time_vec, t_start or "", t_end or "",
                self.ctx.data[lat_field], self.ctx.data[lon_field]
            )
            if np.isnan(R):
                self.result_text.setPlainText("拟合圆半径: 数据不足（需要至少3个点）")
            else:
                self.result_text.setPlainText(f"拟合圆半径: {R:.4f} 米")
        except Exception as e:
            self.result_text.setPlainText(f"拟合错误: {e}")
