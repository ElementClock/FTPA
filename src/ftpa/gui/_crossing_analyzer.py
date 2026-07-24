"""
穿越分析器 — 穿越线绘制 + 缩放 + 统计更新。

从 PlotCanvasWidget 中提取的职责：
- 穿越参数设置和应用
- 穿越线绘制/清除
- 缩放和重置
- 统计信息计算和文本更新
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import numpy as np
from PySide6.QtCore import QTimer

from ..statistics import find_crossing_points
from ..time_utils import format_time_seconds

if TYPE_CHECKING:
    from .panel_plot import PlotCanvasWidget


class CrossingAnalyzer:
    """穿越分析 + 统计更新。"""

    def __init__(self, widget: PlotCanvasWidget) -> None:
        self.w = widget

        # 穿越状态
        self.crossing_lines: list[Any] = []
        self.left_val: float = 0.0
        self.left_mode: str = "FirstUp"
        self.right_val: float = 0.0
        self.right_mode: str = "LastDown"
        self.master_field: str = ""

        # 穿越点 x 坐标缓存（供 apply_crossing 缩放使用）
        self._crossing_x: dict[str, float | None] = {"left": None, "right": None}

        # 缩放防抖定时器
        self._zoom_timer: QTimer | None = None

        # 统计文本缓存
        self.last_stats_text: str = ""

    # ── 穿越参数设置 ──

    def set_crossing_context(self, left_val: float, left_mode: str,
                             right_val: float, right_mode: str, master_field: str) -> None:
        """从外部设置穿越参数。"""
        self.left_val = left_val
        self.left_mode = left_mode
        self.right_val = right_val
        self.right_mode = right_mode
        self.master_field = master_field

    def apply_crossing(self, left_val: float, left_mode: str,
                       right_val: float, right_mode: str, master_field: str) -> None:
        """应用穿越 — 缩放到左右穿越点之间的时间区间。"""
        w = self.w
        self.left_val = left_val
        self.left_mode = left_mode
        self.right_val = right_val
        self.right_mode = right_mode
        self.master_field = master_field
        self._redraw_crossing()
        # 缩放到左右穿越点之间的区间
        left_x = self._crossing_x.get("left")
        right_x = self._crossing_x.get("right")
        if left_x is not None and right_x is not None and left_x < right_x:
            pad = (right_x - left_x) * 0.05
            for ax in w.axes:
                ax.set_xlim(left_x - pad, right_x + pad)
            w.canvas.draw_idle()

    def reset_zoom(self) -> None:
        """重置时间范围到数据起止（保留穿越线）。"""
        w = self.w
        if w.ctx and w.ctx.time_sec is not None and len(w.ctx.time_sec) > 1:
            for ax in w.axes:
                ax.set_xlim(float(w.ctx.time_sec[0]), float(w.ctx.time_sec[-1]))
        w.canvas.draw_idle()
        self.update_stats()

    # ── 穿越线绘制 ──

    def _clear_crossing_lines(self) -> None:
        """清除所有穿越线。"""
        for line in self.crossing_lines:
            try:
                line.remove()
            except Exception:
                pass
        self.crossing_lines.clear()

    def _redraw_crossing(self) -> None:
        """重新绘制穿越线，并保存穿越点 x 坐标。"""
        w = self.w
        self._clear_crossing_lines()
        ctx = w.ctx
        if ctx is None or ctx.time_sec is None:
            return

        if not self.master_field:
            w.canvas.draw_idle()
            return

        master_data = ctx.data.get(self.master_field)
        if master_data is None:
            w.canvas.draw_idle()
            return

        # 清空上次的穿越点缓存
        self._crossing_x = {"left": None, "right": None}

        master_arr = master_data  # 已由 DataContext 预转为 float64
        colors = {"left": "red", "right": "firebrick"}
        linestyles = {"left": "solid", "right": "dashed"}

        for side, (val, mode) in [("left", (self.left_val, self.left_mode)),
                                   ("right", (self.right_val, self.right_mode))]:
            pos = find_crossing_points(master_arr, val, mode)
            if pos is not None:
                x_pos = float(ctx.time_sec[pos - 1])
                self._crossing_x[side] = x_pos  # 保存坐标
                for ax in w.axes:
                    if ax.get_visible():
                        line = ax.axvline(x_pos, color=colors[side], linewidth=1.0,
                                          alpha=0.7, linestyle=linestyles[side])
                        self.crossing_lines.append(line)

        w.canvas.draw_idle()
        self.update_stats()

    # ── 缩放防抖 ──

    def on_canvas_zoom(self, event=None) -> None:
        """画布缩放/滚动后更新统计（防抖 200ms）。"""
        w = self.w
        if self._zoom_timer is None:
            self._zoom_timer = QTimer()
            self._zoom_timer.setSingleShot(True)
            self._zoom_timer.timeout.connect(self.update_stats)
        self._zoom_timer.start(200)

    # ── 统计更新 ──

    def update_stats(self) -> None:
        """根据当前时间窗口和穿越参数更新统计信息文本。"""
        w = self.w
        if w.ctx is None or not w.axes or w.ctx.time_sec is None:
            return

        try:
            xlim = w.axes[0].get_xlim()
            t_start, t_end = xlim[0], xlim[1]
        except Exception:
            return

        lines: list[str] = []
        lines.append(f"时间窗口: {format_time_seconds(t_start)} - {format_time_seconds(t_end)}")

        # 各子图的信号统计
        for i in sorted(w.subplot_fields.keys()):
            fields = w.subplot_fields[i]
            if not fields:
                continue
            for f in fields:
                arr = w.ctx.data.get(f)
                if arr is None:
                    continue
                idx = (w.ctx.time_sec >= t_start) & (w.ctx.time_sec <= t_end)
                seg = arr[idx]
                if len(seg) > 0:
                    label = w.ctx.get_label(f)
                    lines.append(f"  {label}: min={np.min(seg):.4g}, max={np.max(seg):.4g}, mean={np.mean(seg):.4g}")

        # 穿越信息
        for side, (val, mode) in [("左", (self.left_val, self.left_mode)),
                                   ("右", (self.right_val, self.right_mode))]:
            if self.master_field and w.ctx:
                master_arr = np.asarray(w.ctx.data.get(self.master_field, []), dtype=float)
                pos = find_crossing_points(master_arr, val, mode)
                if pos is not None and w.ctx.time_sec is not None:
                    x = w.ctx.time_sec[pos - 1]
                    lines.append(f"穿越({side}): {mode} → {format_time_seconds(float(x))} ({self.master_field}={master_arr[pos - 1]:.4g})")
                else:
                    lines.append(f"穿越({side}): {mode} → 无")

        self.last_stats_text = "\n".join(lines)

    def get_stats_text(self) -> str:
        """获取当前统计文本（供外部信息显示框使用）。"""
        return self.last_stats_text
