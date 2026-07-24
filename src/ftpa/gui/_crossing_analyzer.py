"""
穿越分析器 — 穿越线绘制 + 缩放 + 统计更新。

从 PlotCanvasWidget 中提取的职责：
- 穿越参数设置和应用
- 穿越线绘制/清除
- 缩放和重置
- 统计信息计算和文本更新

参照 MATLAB plotCoreInteractive.m 的 applyThresholdCb / resetViewCb 实现。
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import numpy as np
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QMessageBox

from ..statistics import find_crossing_points
from ..time_utils import format_time_seconds

if TYPE_CHECKING:
    from .panel_plot import PlotCanvasWidget

logger = logging.getLogger(__name__)


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

        # 初始时间范围缓存（数据加载时记录，供 reset_zoom 恢复）
        self._initial_time_range: tuple[float, float] | None = None

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
        """应用穿越 — 在当前视图范围内检测穿越点并缩放。

        逻辑参照 MATLAB plotCoreInteractive.m applyThresholdCb：
        1. 获取当前视图 xlim 作为搜索窗口
        2. 在窗口内搜索穿越点（排除 NaN）
        3. 左/右穿越点未找到时回退到窗口边界
        4. 缩放所有子图 X 轴至 [left_x, right_x]
        5. 自动调整每个子图 Y 轴适配可见数据
        """
        w = self.w
        self.left_val = left_val
        self.left_mode = left_mode
        self.right_val = right_val
        self.right_mode = right_mode
        self.master_field = master_field

        ctx = w.ctx
        if ctx is None or ctx.time_sec is None:
            return

        if not master_field:
            return

        master_data = ctx.data.get(master_field)
        if master_data is None:
            return

        # ── 步骤 1: 获取当前视图范围作为搜索窗口 ──
        if not w.axes:
            return
        try:
            cur_xlim = w.axes[0].get_xlim()
            t_start_sec = float(cur_xlim[0])
            t_end_sec = float(cur_xlim[1])
        except Exception:
            t_start_sec, t_end_sec = ctx.get_time_range_sec()

        # ── 步骤 2: 在窗口内搜索穿越点（排除 NaN） ──
        time_sec = ctx.time_sec
        master_arr = np.asarray(master_data, dtype=float)

        # 选取窗口内的数据索引
        search_mask = (time_sec >= t_start_sec) & (time_sec <= t_end_sec)
        sub_time = time_sec[search_mask]
        sub_sig = master_arr[search_mask]

        # 移除 NaN 以避免穿越检测失败
        valid = ~np.isnan(sub_sig)
        sub_time = sub_time[valid]
        sub_sig = sub_sig[valid]

        if len(sub_sig) < 2:
            w.log_message.emit("当前视图内有效数据点不足，无法检测穿越")
            return

        # 检测穿越点
        left_x: float | None = None
        right_x: float | None = None

        for side, (val, mode) in [("left", (left_val, left_mode)),
                                   ("right", (right_val, right_mode))]:
            pos = find_crossing_points(sub_sig, val, mode)
            if pos is not None:
                t_point = float(sub_time[pos - 1])
                if side == "left":
                    left_x = t_point
                else:
                    right_x = t_point

        # ── 步骤 3: 穿越点未找到时回退到窗口边界 ──
        if left_x is None:
            left_x = t_start_sec
            w.log_message.emit("未找到左边界穿越点，使用当前视图起点")
        if right_x is None:
            right_x = t_end_sec
            w.log_message.emit("未找到右边界穿越点，使用当前视图终点")

        # ── 步骤 4: 验证并缩放 ──
        if left_x >= right_x:
            w.log_message.emit(
                f"左边界 ({format_time_seconds(left_x)}) 不早于右边界 ({format_time_seconds(right_x)})，请检查阈值或方向"
            )
            return

        # 绘制穿越线（基于窗口内的穿越点）
        self._crossing_x = {"left": left_x, "right": right_x}
        self._redraw_crossing_lines()

        # 缩放所有子图 X 轴
        for ax in w.axes:
            ax.set_xlim(left_x, right_x)

        # ── 步骤 5: 自动调整每个子图 Y 轴 ──
        self._adjust_y_limits()

        w.canvas.draw_idle()
        self.update_stats()

    def reset_zoom(self) -> None:
        """重置时间范围到初始状态（保留穿越线）。

        逻辑参照 MATLAB plotCoreInteractive.m resetViewCb：
        1. 恢复到数据加载时的初始时间范围
        2. 自动调整每个子图 Y 轴适配可见数据
        3. 更新统计信息
        """
        w = self.w
        if w.ctx is None or w.ctx.time_sec is None or len(w.ctx.time_sec) < 2:
            return

        # 优先使用初始时间范围缓存，否则用数据起止
        if self._initial_time_range is not None:
            t_start, t_end = self._initial_time_range
        else:
            t_start = float(w.ctx.time_sec[0])
            t_end = float(w.ctx.time_sec[-1])

        for ax in w.axes:
            ax.set_xlim(t_start, t_end)

        # 自动调整每个子图 Y 轴
        self._adjust_y_limits()

        w.canvas.draw_idle()
        self.update_stats()
        w.log_message.emit("缩放已重置")

    def save_initial_time_range(self) -> None:
        """记录当前数据的时间范围作为初始范围（数据加载时调用）。"""
        w = self.w
        if w.ctx is not None and w.ctx.time_sec is not None and len(w.ctx.time_sec) > 1:
            self._initial_time_range = (float(w.ctx.time_sec[0]), float(w.ctx.time_sec[-1]))
        else:
            self._initial_time_range = None

    # ── 穿越线绘制 ──

    def _clear_crossing_lines(self) -> None:
        """清除所有穿越线。"""
        for line in self.crossing_lines:
            try:
                line.remove()
            except Exception:
                pass
        self.crossing_lines.clear()

    def _redraw_crossing_lines(self) -> None:
        """根据 _crossing_x 缓存重新绘制穿越线（不重新计算穿越点）。"""
        w = self.w
        self._clear_crossing_lines()

        if not self._crossing_x.get("left") and not self._crossing_x.get("right"):
            return

        colors = {"left": "red", "right": "firebrick"}
        linestyles = {"left": "solid", "right": "dashed"}

        for side in ("left", "right"):
            x_pos = self._crossing_x.get(side)
            if x_pos is not None:
                for ax in w.axes:
                    if ax.get_visible():
                        line = ax.axvline(x_pos, color=colors[side], linewidth=1.0,
                                          alpha=0.7, linestyle=linestyles[side])
                        self.crossing_lines.append(line)

    def _redraw_crossing(self) -> None:
        """重新绘制穿越线（全量数据搜索，保留向后兼容）。

        注意：apply_crossing 已改为窗口内搜索，此方法仅供外部兼容调用。
        """
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

    # ── Y 轴自动调整 ──

    def _adjust_y_limits(self) -> None:
        """自动调整每个子图 Y 轴以适配当前可见时间窗口内的数据。

        参照 MATLAB plotCoreInteractive.m adjustYLimits：
        对每个子图，取可见时间范围内的数据，计算 min/max 并添加 5% 边距。
        """
        w = self.w
        if w.ctx is None or not w.axes or w.ctx.time_sec is None:
            return

        for i, ax in enumerate(w.axes):
            try:
                xlim = ax.get_xlim()
                t_start, t_end = float(xlim[0]), float(xlim[1])
            except Exception:
                continue

            fields = w.subplot_fields.get(i, [])
            if not fields:
                continue

            y_min_all = np.inf
            y_max_all = -np.inf
            has_data = False

            for f in fields:
                arr = w.ctx.data.get(f)
                if arr is None:
                    continue
                idx = (w.ctx.time_sec >= t_start) & (w.ctx.time_sec <= t_end)
                seg = arr[idx]
                # 排除 NaN
                seg = seg[~np.isnan(seg)]
                if len(seg) > 0:
                    y_min_all = min(y_min_all, float(np.min(seg)))
                    y_max_all = max(y_max_all, float(np.max(seg)))
                    has_data = True

            if has_data:
                if y_min_all == y_max_all:
                    y_min_all -= 1.0
                    y_max_all += 1.0
                else:
                    margin = 0.05 * (y_max_all - y_min_all)
                    y_min_all -= margin
                    y_max_all += margin
                ax.set_ylim(y_min_all, y_max_all)

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
