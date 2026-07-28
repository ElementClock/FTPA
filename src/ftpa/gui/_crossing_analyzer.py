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
from ..config import CONFIG

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
        # 防抖快照：触发时的 axes 数量，用于检测回调时 axes 是否已变化
        self._zoom_snapshot_axes_count: int = -1

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

        委托给 _do_crossing_search() 执行核心逻辑。
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

        # 获取当前视图范围作为搜索窗口
        if not w.axes:
            return
        try:
            cur_xlim = w.axes[0].get_xlim()
            t_start_sec = float(cur_xlim[0])
            t_end_sec = float(cur_xlim[1])
        except Exception:
            t_start_sec, t_end_sec = ctx.get_time_range_sec()

        self._do_crossing_search(t_start_sec, t_end_sec)

    def apply_crossing_in_region(self, t_start: float, t_end: float) -> bool:
        """在指定时间区间内执行穿越检测并缩放。

        与 apply_crossing() 的区别：
        - 搜索窗口由参数指定（而非当前视图 xlim）
        - 返回 bool 表示是否成功找到穿越点
        - 穿越点未找到时直接返回 False（不回退到窗口边界）

        Args:
            t_start: 搜索窗口起始时间（秒）
            t_end: 搜索窗口结束时间（秒）

        Returns:
            True — 找到穿越点并成功缩放
            False — 未找到有效穿越点
        """
        w = self.w
        ctx = w.ctx
        if ctx is None or ctx.time_sec is None:
            return False

        return self._do_crossing_search(t_start, t_end, allow_fallback=False)

    def _do_crossing_search(self, t_start_sec: float, t_end_sec: float,
                            *, allow_fallback: bool = True) -> bool:
        """核心穿越检测逻辑 — 在指定时间窗口内搜索穿越点并缩放。

        提取自 apply_crossing()，供 apply_crossing() 和 apply_crossing_in_region() 复用。

        Args:
            t_start_sec: 搜索窗口起始时间（秒）
            t_end_sec: 搜索窗口结束时间（秒）
            allow_fallback: 穿越点未找到时是否回退到窗口边界。
                           apply_crossing() 使用 True（原有行为），
                           apply_crossing_in_region() 使用 False（失败即返回）。

        Returns:
            True — 找到穿越点并成功缩放
            False — 未找到有效穿越点或参数不足
        """
        w = self.w
        ctx = w.ctx
        if ctx is None or ctx.time_sec is None:
            return False

        if not self.master_field:
            return False

        master_data = ctx.data.get(self.master_field)
        if master_data is None:
            return False

        if not w.axes:
            return False

        # 任何缩放操作都应清除框选覆盖层（缩放后时间范围已变化）
        w.cancel_region_selection()

        # ── 在窗口内搜索穿越点（排除 NaN） ──
        time_sec = ctx.time_sec
        master_arr = np.asarray(master_data, dtype=float)

        # 选取窗口内的数据索引
        i_start = np.searchsorted(time_sec, t_start_sec, side="left")
        i_end = np.searchsorted(time_sec, t_end_sec, side="right")
        sub_time = time_sec[i_start:i_end]
        sub_sig = master_arr[i_start:i_end]

        # 移除 NaN 以避免穿越检测失败
        valid = ~np.isnan(sub_sig)
        sub_time = sub_time[valid]
        sub_sig = sub_sig[valid]

        if len(sub_sig) < 2:
            w.log_message.emit("框选区域内有效数据点不足，无法检测穿越")
            return False

        # 检测穿越点
        left_x: float | None = None
        right_x: float | None = None

        for side, (val, mode) in [("left", (self.left_val, self.left_mode)),
                                   ("right", (self.right_val, self.right_mode))]:
            pos = find_crossing_points(sub_sig, val, mode)
            if pos is not None:
                t_point = float(sub_time[pos - 1])
                if side == "left":
                    left_x = t_point
                else:
                    right_x = t_point

        # 穿越点未找到时的处理
        if left_x is None or right_x is None:
            if allow_fallback:
                # 原有行为：回退到窗口边界
                if left_x is None:
                    left_x = t_start_sec
                    w.log_message.emit("未找到左边界穿越点，使用窗口起点")
                if right_x is None:
                    right_x = t_end_sec
                    w.log_message.emit("未找到右边界穿越点，使用窗口终点")
            else:
                # 区域筛选模式：穿越点未找到即失败，不缩放
                missing = []
                if left_x is None:
                    missing.append("左边界")
                if right_x is None:
                    missing.append("右边界")
                w.log_message.emit(
                    f"框选区域内未找到{'、'.join(missing)}穿越点，请调整阈值或方向"
                )
                return False

        # 验证并缩放
        if left_x >= right_x:
            w.log_message.emit(
                f"左边界 ({format_time_seconds(left_x)}) 不早于右边界 ({format_time_seconds(right_x)})，请检查阈值或方向"
            )
            return False

        # 绘制穿越线（基于窗口内的穿越点）
        self._crossing_x = {"left": left_x, "right": right_x}
        self._redraw_crossing_lines()

        # 缩放所有子图 X 轴
        for ax in w.axes:
            ax.set_xlim(left_x, right_x)

        # 自动调整每个子图 Y 轴
        self._adjust_y_limits()

        w.canvas.draw_idle()
        self.update_stats()
        return True

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

        # 取消待处理的防抖回调，避免过期回调在 reset 后触发
        if self._zoom_timer is not None and self._zoom_timer.isActive():
            self._zoom_timer.stop()

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
        # 刷新 Line2D 数据：降采样状态下 Line2D 仅持有可见区间子集，
        # reset 后 xlim 回到全量范围，必须重新评估降采样
        w._renderer.refresh_viewport_data()

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
                logger.debug("穿越线移除失败", exc_info=True)
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

        性能优化：使用 np.searchsorted 替代布尔索引，
        对已排序的 time_sec 数组复杂度从 O(N) 降到 O(log N)，
        且无需创建临时 bool 数组。
        """
        w = self.w
        if w.ctx is None or not w.axes or w.ctx.time_sec is None:
            return

        time_sec = w.ctx.time_sec

        for i, ax in enumerate(w.axes):
            try:
                xlim = ax.get_xlim()
                t_start, t_end = float(xlim[0]), float(xlim[1])
            except Exception:
                logger.warning("子图 %d xlim 获取失败，跳过 Y 轴调整", i, exc_info=True)
                continue

            fields = w.subplot_fields.get(i, [])
            if not fields:
                continue

            y_min_all = np.inf
            y_max_all = -np.inf
            has_data = False

            # 使用 searchsorted 快速定位可见窗口索引
            i_start = np.searchsorted(time_sec, t_start, side="left")
            i_end = np.searchsorted(time_sec, t_end, side="right")

            for f in fields:
                arr = w.ctx.data.get(f)
                if arr is None:
                    continue
                seg = arr[i_start:i_end]
                # 排除 NaN
                valid_mask = ~np.isnan(seg)
                valid_seg = seg[valid_mask]
                if len(valid_seg) > 0:
                    y_min_all = min(y_min_all, float(np.min(valid_seg)))
                    y_max_all = max(y_max_all, float(np.max(valid_seg)))
                    has_data = True

            if has_data:
                if y_min_all == y_max_all:
                    y_min_all -= 1.0
                    y_max_all += 1.0
                else:
                    margin = CONFIG.plot.y_margin_ratio * (y_max_all - y_min_all)
                    y_min_all -= margin
                    y_max_all += margin
                ax.set_ylim(y_min_all, y_max_all)

    # ── 缩放防抖 ──

    def on_scroll_zoom(self, event) -> None:
        """鼠标滚轮缩放时间轴。

        以鼠标位置为缩放中心，所有子图X轴同步缩放。
        缩放后通过 on_canvas_zoom 触发防抖的Y轴自适应+统计更新。

        Args:
            event: matplotlib scroll_event 事件对象。
                   必须包含 button ("up"/"down")、xdata、inaxes 属性。

        行为:
          - event.inaxes 为 None → 直接返回（鼠标在子图外）
          - ctx 为 None 或 time_sec 为空 → 直接返回
          - axes 为空 → 直接返回
          - 上滚 (button="up") → 放大 (span × 0.92, 8%步长)
          - 下滚 (button="down") → 缩小 (span × 1.087, 8.7%步长)
          - span 最小值 = MIN_ZOOM_SPAN (1.0秒)
          - span 最大值 = data_span × 2
          - 缩放后调用 on_canvas_zoom(event) 触发防抖
        """
        try:
            w = self.w
            # 前置检查：鼠标必须在子图内
            if getattr(event, "inaxes", None) is None:
                return
            # 前置检查：必须有数据上下文
            ctx = w.ctx
            if ctx is None or ctx.time_sec is None or len(ctx.time_sec) < 2:
                return
            # 前置检查：必须有子图
            if not w.axes:
                return

            # 缩放方向：上滚放大，下滚缩小
            button = getattr(event, "button", None)
            if button == "up":
                factor = CONFIG.zoom.factor_in
            elif button == "down":
                factor = CONFIG.zoom.factor_out
            else:
                return

            # 取第一个子图xlim作为基准（所有子图xlim通常相同）
            try:
                cur_xlim = w.axes[0].get_xlim()
                cur_start = float(cur_xlim[0])
                cur_end = float(cur_xlim[1])
            except Exception:
                return

            span = cur_end - cur_start
            # 数据时间范围
            t_min = float(ctx.time_sec[0])
            t_max = float(ctx.time_sec[-1])
            data_span = t_max - t_min

            # span 异常时回退到 data_span
            if span <= 0:
                span = data_span if data_span > 0 else 1.0

            # 缩放中心：优先使用鼠标位置，否则回退到当前视图中心
            center = getattr(event, "xdata", None)
            if center is None:
                center = (cur_start + cur_end) / 2.0
            center = float(center)

            # 计算鼠标在视图中的相对位置 [0, 1]
            ratio = (center - cur_start) / span if span > 0 else 0.5

            # 新的 span
            new_span = span * factor
            # 限制 span 范围：[MIN_ZOOM_SPAN, data_span × 2]
            max_span = data_span * 2.0 if data_span > 0 else new_span
            if new_span < CONFIG.zoom.min_span:
                new_span = CONFIG.zoom.min_span
            elif new_span > max_span:
                new_span = max_span

            # 保持鼠标位置不变，重新计算 new_start / new_end
            new_start = center - ratio * new_span
            new_end = new_start + new_span

            # 同步所有子图
            for ax in w.axes:
                ax.set_xlim(new_start, new_end)

            # 触发防抖的Y轴自适应 + 统计更新
            self.on_canvas_zoom(event)
        except Exception:
            logger.exception("on_scroll_zoom 执行失败")

    def on_canvas_zoom(self, event=None) -> None:
        """画布缩放/滚动/平移后更新统计 + Y轴自适应（防抖 200ms）。

        防抖回调 _zoom_timeout_cb 中执行：
          1. _adjust_y_limits() — Y轴自适应（5%边距）
          2. canvas.draw_idle() — 重绘
          3. update_stats() — 统计更新
        """
        w = self.w
        if self._zoom_timer is None:
            self._zoom_timer = QTimer()
            self._zoom_timer.setSingleShot(True)
            self._zoom_timer.timeout.connect(self._zoom_timeout_cb)
        self._zoom_snapshot_axes_count = len(w.axes)
        self._zoom_timer.start(200)

    def _zoom_timeout_cb(self) -> None:
        """缩放防抖回调：Y轴自适应 + 数据刷新 + 统计更新。

        如果 axes 数量在防抖期间发生了变化（如布局切换），
        则跳过过期回调，避免对已销毁的 axes 操作。
        """
        if len(self.w.axes) != self._zoom_snapshot_axes_count:
            return
        self._adjust_y_limits()
        # 根据当前视图刷新 Line2D 数据（缩放后数据可能需降采样/取消降采样）
        self.w._renderer.refresh_viewport_data()
        self.w.canvas.draw_idle()
        self.update_stats()

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
        time_sec = w.ctx.time_sec
        i_start = np.searchsorted(time_sec, t_start, side="left")
        i_end = np.searchsorted(time_sec, t_end, side="right")

        for i in sorted(w.subplot_fields.keys()):
            fields = w.subplot_fields[i]
            if not fields:
                continue
            for f in fields:
                arr = w.ctx.data.get(f)
                if arr is None:
                    continue
                seg = arr[i_start:i_end]
                if len(seg) > 0:
                    label = w.ctx.get_label(f)
                    lines.append(f"  {label}: min={np.nanmin(seg):.4g}, max={np.nanmax(seg):.4g}, mean={np.nanmean(seg):.4g}")

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
