"""
平移控制器 — 鼠标拖拽水平平移画布。

从 PlotCanvasWidget 中提取的职责：
- 左键拖拽水平平移（所有子图 X 轴同步）
- 点击/拖拽区分（5 像素阈值）
- 平移后触发 Y 轴自适应 + 统计更新（防抖）

设计原则：
  - 水平平移计算完全独立于 Y 轴状态
  - 使用纯像素差 × X 轴缩放比计算 dx_data，不依赖 transData
  - 无边界约束：允许自由平移到数据范围之外（用户可通过缩放回到数据区）

防抖策略：
  拖拽过程中仅修改 X 轴，Y 轴自适应推迟到 on_release 后
  由 on_canvas_zoom 防抖回调统一处理。这避免了 X 轴平移与
  Y 轴自适应在同一渲染帧内的循环冲突，消除绘图区域跳动。

参照 MATLAB plotCoreInteractive.m 的交互行为。
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt

if TYPE_CHECKING:
    from .panel_plot import PlotCanvasWidget

logger = logging.getLogger(__name__)


class PanController:
    """画布拖拽水平平移控制器。

    事件协调策略：
      - PanController 先于 LayoutController 处理 button_press/button_release
      - 通过 was_panning 标记告知 LayoutController 是否跳过子图选择
      - 拖拽阈值 5 像素：未超过阈值 → 点击（选择子图），超过 → 拖拽（平移）

    坐标变换策略（Y 轴无关）：
      - dx_data = dx_pixel × x_scale
      - x_scale = (xlim[1] - xlim[0]) / axes_pixel_width
      - 仅依赖 X 轴参数（xlim）和 axes 像素宽度，与 Y 轴状态完全无关
      - 比 transData.inverted() 更快（无需 2D 仿射矩阵求逆）
    """

    DRAG_THRESHOLD: int = 5  # 像素，区分点击与拖拽

    def __init__(self, widget: PlotCanvasWidget) -> None:
        self._widget = widget

        # 按下时的 matplotlib 事件对象
        self._press_event = None
        # 是否已进入平移模式（超过阈值后置 True）
        self._is_panning: bool = False
        # 按下时各子图的 xlim 缓存
        self._press_xlim: list[tuple[float, float]] | None = None
        # 上一次 release 时是否为平移（供外部查询后清除）
        self._was_panning: bool = False
        # 按下时缓存的 X 轴缩放比（data_units / pixel），Y 轴无关
        self._x_scale: float | None = None

    # ── 事件处理 ──

    def on_press(self, event) -> None:
        """鼠标按下：记录起始位置、当前 xlim 和 X 轴缩放比。

        仅当左键在 axes 区域内且有数据时记录，否则忽略。
        缓存 x_scale 确保整个拖拽过程中使用一致的坐标变换，
        不受后续 Y 轴自适应（_adjust_y_limits）影响。
        """
        if event.button != 1 or event.inaxes is None:
            self._press_event = None
            return
        # 无数据时禁止平移
        time_sec = self._widget.ctx.query.get_time_sec() if self._widget.ctx else None
        if time_sec is None or len(time_sec) == 0:
            self._press_event = None
            return

        # 缓存 X 轴缩放比（Y 轴无关）
        self._x_scale = self._compute_x_scale(event.inaxes)

        self._press_event = event
        self._is_panning = False
        self._was_panning = False
        self._press_xlim = [ax.get_xlim() for ax in self._widget.axes]

    def on_motion(self, event) -> None:
        """鼠标移动：若超出阈值则开始水平平移。

        算法（Y 轴无关）：
          1. 像素距离 < DRAG_THRESHOLD → 仍在"可能点击"状态，不做任何操作
          2. 像素距离 ≥ DRAG_THRESHOLD → 进入平移模式
          3. dx_data = dx_pixel × x_scale（仅依赖 X 轴参数，与 Y 轴状态无关）
          4. 所有子图 X 轴同步偏移
          5. 仅触发 draw_idle，不修改 Y 轴（Y 轴自适应推迟到 release 防抖）
        """
        if self._press_event is None:
            return
        # event.x/event.y 可能为 None（鼠标移出 canvas）
        if event.x is None and event.y is None:
            return

        # 判断是否超过拖拽阈值
        if not self._is_panning:
            dx_px = abs(event.x - self._press_event.x) if event.x is not None else 0
            dy_px = abs(event.y - self._press_event.y) if event.y is not None else 0
            if dx_px < self.DRAG_THRESHOLD and dy_px < self.DRAG_THRESHOLD:
                return
            self._is_panning = True

            # 拖拽开始：光标变为 ClosedHandCursor（握拳）
            self._widget.canvas.setCursor(Qt.CursorShape.ClosedHandCursor)

        # 计算数据坐标偏移量：纯像素差 × X 轴缩放比（Y 轴无关）
        if event.x is None or self._press_event.x is None:
            return
        if self._x_scale is None:
            return

        dx_pixel = self._press_event.x - event.x  # 正值=向右拖=视图左移
        dx_data = dx_pixel * self._x_scale

        # 同步平移所有子图（仅修改 X 轴）
        self._apply_pan(dx_data)

        # 仅触发重绘，不修改 Y 轴
        # Y 轴自适应推迟到 on_release → on_canvas_zoom 防抖回调统一处理
        # 避免同一渲染帧内 X 轴平移与 Y 轴自适应的循环冲突导致绘图区域跳动
        self._widget.canvas.draw_idle()

    def on_release(self, event) -> None:
        """鼠标释放：若为平移则触发 Y 轴自适应 + 统计更新。

        调用后通过 was_panning() 可查询本次 release 是否为平移操作，
        以便 LayoutController 决定是否跳过子图选择。

        注意：平移后的 Y 轴自适应和统计更新由 on_canvas_zoom 的
        防抖回调统一处理，此处不再重复调用。
        """
        self._was_panning = self._is_panning

        # 释放后恢复光标为 OpenHandCursor（仍在子图区域内）
        if self._is_panning:
            self._widget.canvas.setCursor(Qt.CursorShape.OpenHandCursor)

        # 重置状态
        self._press_event = None
        self._is_panning = False
        self._press_xlim = None
        self._x_scale = None

    # ── 状态查询 ──

    def was_panning(self) -> bool:
        """查询上一次 release 是否为平移操作。

        返回 True 表示刚完成一次平移，LayoutController 应跳过子图选择。
        采用"读取即清除"模式，避免多次调用返回过期值。
        """
        result = self._was_panning
        self._was_panning = False
        return result

    def is_panning(self) -> bool:
        """查询当前是否处于平移拖拽中。"""
        return self._is_panning

    def reset(self) -> None:
        """强制重置平移状态。

        在布局切换、数据重载、右键中断等场景下调用，
        避免对已销毁 axes 的悬空引用。
        """
        self._press_event = None
        self._is_panning = False
        self._was_panning = False
        self._press_xlim = None
        self._x_scale = None

    # ── 内部方法 ──

    @staticmethod
    def _compute_x_scale(ax) -> float | None:
        """计算 X 轴缩放比（数据单位/像素），Y 轴无关。

        公式：x_scale = (xlim[1] - xlim[0]) / axes_pixel_width

        此公式仅依赖：
          - xlim: X 轴数据范围（X 轴参数）
          - axes_pixel_width: axes 在画布中的像素宽度（布局参数）
        不依赖 Y 轴任何参数（ylim、Y 轴 tick 标签宽度等），
        彻底隔离 Y 轴缩放操作对水平平移计算的影响。

        Args:
            ax: matplotlib Axes 对象

        Returns:
            X 轴缩放比（data_units/pixel），或 None（计算失败）
        """
        try:
            xlim = ax.get_xlim()
            span = xlim[1] - xlim[0]
            if span <= 0:
                return None
            # 获取 axes 在显示坐标系中的像素宽度
            bbox = ax.get_window_extent()
            width = bbox.width
            if width <= 0:
                return None
            return span / width
        except Exception:
            logger.debug("X 轴缩放比计算失败", exc_info=True)
            return None

    def _apply_pan(self, dx_data: float) -> None:
        """将所有子图 X 轴平移 dx_data 数据单位。

        无边界约束：允许自由平移到数据范围之外。
        用户可通过滚轮缩放或重置缩放回到数据区域。
        这确保水平移动完全不受 Y 轴缩放状态影响。
        """
        if self._press_xlim is None:
            return

        for i, ax in enumerate(self._widget.axes):
            if i >= len(self._press_xlim):
                continue
            old_start, old_end = self._press_xlim[i]
            new_start = old_start + dx_data
            new_end = old_end + dx_data
            ax.set_xlim(new_start, new_end)
