"""
区域框选控制器 — 右键拖动框选时间区间。

从 PlotCanvasWidget 中提取的职责：
- 管理右键拖动框选的交互状态机
- 绘制/更新/清除半透明蓝色覆盖层 (axvspan)
- 计算框选区域的精确时间范围
- 在画布上显示起止时间标注

交互流程：
  右键按下 → 记录起点
    ├─ 右键拖动（>5px）→ 进入框选模式 → 实时绘制选区 → 松开 → 保持选区
    └─ 右键单击（<5px）→ 不处理（由外部触发上下文菜单）

  控制面板"应用"按钮 → 检测到框选区域时，在框选区间内执行穿越检测
    ├─ 找到穿越点 → 缩放视图到穿越点区间 → 自动清除选区
    └─ 未找到穿越点 → 日志提示 → 选区保持

  右键菜单"取消区域筛选" / 新框选 → 清除选区，回到 IDLE
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt

from ..utils.time_utils import format_time_seconds
from ..config import CONFIG

if TYPE_CHECKING:
    from .panel_plot import PlotCanvasWidget

logger = logging.getLogger(__name__)


class RegionController:
    """区域框选控制器 — 右键拖动框选时间区间。

    状态机：
      IDLE → (右键press) → PRESSED → (拖动>阈值) → SELECTING → (release) → SELECTED
        ↑                              │                              │            │
        │                              └─(单击<阈值) → 回到 IDLE)     │            │
        └────────────(取消 / 新框选)────────────────────────────────┘  └─(应用成功→自动清除)─┘

    应用操作由外部控制面板的"应用"按钮触发，不在画布上创建浮动按钮。
    """

    # 状态常量
    IDLE = "idle"
    PRESSED = "pressed"
    SELECTING = "selecting"
    SELECTED = "selected"

    # 像素阈值，区分单击与拖动（与 PanController 一致）
    DRAG_THRESHOLD: int = 5

    def __init__(self, widget: PlotCanvasWidget) -> None:
        self._widget = widget

        # 状态
        self._state: str = self.IDLE

        # 按下时的 matplotlib 事件对象
        self._press_event = None

        # 框选时间范围（数据坐标，秒）
        self._region_start: float | None = None
        self._region_end: float | None = None

        # matplotlib artist 缓存
        self._span_artists: list = []      # axvspan 覆盖层
        self._line_artists: list = []      # axvline 边界线
        self._label_artists: list = []     # 时间标注文本

    # ── 事件处理 ──

    def on_press(self, event) -> None:
        """鼠标右键按下：记录起始位置。

        仅当右键在 axes 区域内且有数据时记录。
        菜单触发推迟到 release，由拖动距离判断。
        """
        if event.button != 3:
            return

        # 无数据时禁止框选
        w = self._widget
        if w.ctx is None or w.ctx.query.get_time_sec() is None or len(w.ctx.query.get_time_sec()) == 0:
            self._press_event = None
            return

        # 必须在 axes 内
        if event.inaxes is None:
            self._press_event = None
            return

        self._press_event = event
        self._state = self.PRESSED

    def on_motion(self, event) -> None:
        """鼠标移动：若超出阈值则进入框选模式，实时绘制选区。

        算法：
          1. 像素距离 < DRAG_THRESHOLD → 仍在"可能单击"状态
          2. 像素距离 ≥ DRAG_THRESHOLD → 进入 SELECTING
          3. 根据鼠标 xdata 计算框选时间范围
          4. 实时更新覆盖层和时间标注
          5. 仅触发 draw_idle
        """
        if self._press_event is None:
            return
        if self._state not in (self.PRESSED, self.SELECTING):
            return

        w = self._widget

        # 判断是否超过拖拽阈值
        if self._state == self.PRESSED:
            if event.x is None or self._press_event.x is None:
                return
            dx_px = abs(event.x - self._press_event.x)
            dy_px = abs(event.y - self._press_event.y) if event.y is not None and self._press_event.y is not None else 0
            if dx_px < self.DRAG_THRESHOLD and dy_px < self.DRAG_THRESHOLD:
                return

            # 超过阈值 → 进入 SELECTING
            self._state = self.SELECTING

            # 记录起始时间
            self._region_start = self._press_event.xdata
            self._region_end = event.xdata

            # 框选开始：光标变为 CrossCursor
            w.canvas.setCursor(Qt.CursorShape.CrossCursor)

        # SELECTING 状态：更新框选终点
        if self._state == self.SELECTING:
            if event.xdata is not None:
                self._region_end = event.xdata

            if self._region_start is not None and self._region_end is not None:
                self._draw_region(self._region_start, self._region_end)

            w.canvas.draw_idle()

    def on_release(self, event) -> bool:
        """鼠标右键释放：完成框选或判定为单击。

        Returns:
            True  — 右键拖动完成（框选区域已建立）
            False — 右键单击（应由外部触发上下文菜单）
        """
        if self._press_event is None:
            return False

        was_selecting = self._state == self.SELECTING

        if was_selecting:
            # 拖动完成 → 进入 SELECTED
            self._state = self.SELECTED

            # 确保 region_end 使用最终位置
            if event.xdata is not None:
                self._region_end = event.xdata

            # 规范化：确保 start < end
            if self._region_start is not None and self._region_end is not None:
                if self._region_start > self._region_end:
                    self._region_start, self._region_end = self._region_end, self._region_start

            # 最终绘制
            self._draw_region(self._region_start, self._region_end)
            self._widget.canvas.draw_idle()

            # 日志
            if self._region_start is not None and self._region_end is not None:
                self._widget.log_message.emit(
                    f"已框选区域: {format_time_seconds(self._region_start)} → "
                    f"{format_time_seconds(self._region_end)}  "
                    f"（点击「应用」按钮执行穿越检测）"
                )
                # 通知外部框选区域已生效（区间分析等以此优先于视图范围）
                self._widget.view_range_changed.emit(
                    float(self._region_start), float(self._region_end)
                )

            # 重置按下事件
            self._press_event = None
            return True
        else:
            # 单击 → 回到 IDLE（外部应触发上下文菜单）
            self._state = self.IDLE
            self._press_event = None
            return False

    # ── 状态查询 ──

    def is_selecting(self) -> bool:
        """查询当前是否处于框选拖动中。"""
        return self._state == self.SELECTING

    def is_selected(self) -> bool:
        """查询当前是否有已完成的框选区域。"""
        return self._state == self.SELECTED

    def get_state(self) -> str:
        """返回当前状态。"""
        return self._state

    def get_region(self) -> tuple[float, float] | None:
        """返回当前框选的时间范围 (t_start, t_end)，或 None。"""
        if self._region_start is not None and self._region_end is not None:
            return (self._region_start, self._region_end)
        return None

    # ── 应用/取消 ──

    def apply_selection(self) -> bool:
        """应用框选区域 — 在框选区间内执行穿越检测。

        由外部控制面板的"应用"按钮调用。

        任何缩放操作（包括穿越检测成功后的缩放）都会统一清除覆盖层，
        因此此方法只需执行穿越检测逻辑，覆盖层的清除由缩放触发。

        Returns:
            True  — 穿越检测成功，已缩放并自动清除框选
            False — 穿越检测失败，选区保持
        """
        w = self._widget
        region = self.get_region()
        if region is None:
            w.log_message.emit("无有效框选区域")
            return False

        t_start, t_end = region

        # 调用 CrossingAnalyzer 在框选区间内执行穿越检测
        # 成功时 CrossingAnalyzer 会缩放视图 → 缩放触发 cancel_selection 清除覆盖层
        success = w._crossing.apply_crossing_in_region(t_start, t_end)

        if success:
            # 成功 → 缩放已完成，覆盖层已由缩放清除
            # 但状态数据仍需手动清除
            self._state = self.IDLE
            self._region_start = None
            self._region_end = None
            self._press_event = None
            w.log_message.emit("区域筛选应用成功，视图已缩放至穿越点区间")
            # 附加更新后的统计信息
            stats = w._crossing.get_stats_text()
            if stats:
                w.log_message.emit(stats)
            return True
        else:
            # 失败 → 选区保持（未缩放，覆盖层不变）
            w.log_message.emit("框选区域内未找到有效穿越点，选区保持")
            return False

    def cancel_selection(self) -> None:
        """清除框选区域，回到 IDLE。"""
        self._clear_region()
        self._state = self.IDLE
        self._region_start = None
        self._region_end = None
        self._press_event = None

        # 恢复光标
        w = self._widget
        has_data = w.ctx is not None and w.ctx.query.get_time_sec() is not None and len(w.ctx.query.get_time_sec()) > 0
        # 光标恢复将在 panel_plot._on_motion 中自动处理
        w.canvas.draw_idle()

    def reset(self) -> None:
        """强制重置框选状态。

        在布局切换、数据重载等场景下调用。
        """
        self._clear_region()
        self._state = self.IDLE
        self._region_start = None
        self._region_end = None
        self._press_event = None

    # ── 绘制 ──

    def _draw_region(self, t_start: float, t_end: float) -> None:
        """在所有子图上绘制/更新框选覆盖层和时间标注。

        视觉反馈：
          - 半透明蓝色覆盖层 (axvspan)
          - 蓝色虚线边界 (axvline)
          - 顶部时间标注文本
        """
        self._clear_region()
        w = self._widget

        if not w.axes:
            return

        # 确保 start < end
        t_min, t_max = (t_start, t_end) if t_start <= t_end else (t_end, t_start)

        for i, ax in enumerate(w.axes):
            if not ax.get_visible():
                continue

            # 半透明蓝色覆盖层
            span = ax.axvspan(t_min, t_max, alpha=0.15, color=CONFIG.plot.selected_color, zorder=0)
            self._span_artists.append(span)

            # 蓝色虚线边界
            line_left = ax.axvline(t_min, color=CONFIG.plot.selected_color, linestyle='--',
                                   linewidth=1.0, alpha=0.8, zorder=5)
            line_right = ax.axvline(t_max, color=CONFIG.plot.selected_color, linestyle='--',
                                    linewidth=1.0, alpha=0.8, zorder=5)
            self._line_artists.extend([line_left, line_right])

            # 仅在第一个子图顶部显示时间标注
            if i == 0:
                t_mid = (t_min + t_max) / 2.0
                label_text = f"{format_time_seconds(t_min)} → {format_time_seconds(t_max)}"
                txt = ax.text(
                    t_mid, 0.98, label_text,
                    transform=ax.get_xaxis_transform(),
                    ha='center', va='top', fontsize=9,
                    color='#1565C0', fontweight='bold',
                    bbox=dict(boxstyle='round,pad=0.3', facecolor='white',
                              edgecolor=CONFIG.plot.selected_color, alpha=0.9),
                    zorder=10
                )
                self._label_artists.append(txt)

    def _clear_region(self) -> None:
        """清除所有框选相关的 matplotlib artist。

        使用双重保障：先设不可见确保视觉消失，再从 axes 中移除。
        """
        all_artists = self._span_artists + self._line_artists + self._label_artists

        # 第一重：设不可见，确保即使 remove 失败也不会渲染
        for artist in all_artists:
            try:
                artist.set_visible(False)
            except Exception:
                logger.debug("框选 artist 设不可见失败", exc_info=True)

        # 第二重：从 axes 中移除
        for artist in all_artists:
            try:
                artist.remove()
            except (ValueError, AttributeError):
                pass
            except Exception:
                logger.debug("框选 artist 移除失败: %s", artist, exc_info=True)

        self._span_artists.clear()
        self._line_artists.clear()
        self._label_artists.clear()
