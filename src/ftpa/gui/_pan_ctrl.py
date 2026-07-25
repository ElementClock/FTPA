"""
平移控制器 — 鼠标拖拽水平平移画布。

从 PlotCanvasWidget 中提取的职责：
- 左键拖拽水平平移（所有子图 X 轴同步）
- 点击/拖拽区分（5 像素阈值）
- 平移后触发 Y 轴自适应 + 统计更新（防抖）
- 条件性边界约束（仅当视图已放大时启用，全视图时允许溢出）

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
    """

    DRAG_THRESHOLD: int = 5  # 像素，区分点击与拖拽

    def __init__(self, widget: PlotCanvasWidget, white_margin_ratio: float = 0.05) -> None:
        self.w = widget
        self._white_margin_ratio = white_margin_ratio

        # 按下时的 matplotlib 事件对象
        self._press_event = None
        # 是否已进入平移模式（超过阈值后置 True）
        self._is_panning: bool = False
        # 按下时各子图的 xlim 缓存
        self._press_xlim: list[tuple[float, float]] | None = None
        # 上一次 release 时是否为平移（供外部查询后清除）
        self._was_panning: bool = False

    # ── 事件处理 ──

    def on_press(self, event) -> None:
        """鼠标按下：记录起始位置和当前 xlim。

        仅当左键在 axes 区域内且有数据时记录，否则忽略。
        """
        if event.button != 1 or event.inaxes is None:
            self._press_event = None
            return
        # 无数据时禁止平移
        if self.w.ctx is None or self.w.ctx.time_sec is None or len(self.w.ctx.time_sec) == 0:
            self._press_event = None
            return
        self._press_event = event
        self._is_panning = False
        self._was_panning = False
        self._press_xlim = [ax.get_xlim() for ax in self.w.axes]

    def on_motion(self, event) -> None:
        """鼠标移动：若超出阈值则开始水平平移。

        算法：
          1. 像素距离 < DRAG_THRESHOLD → 仍在"可能点击"状态，不做任何操作
          2. 像素距离 ≥ DRAG_THRESHOLD → 进入平移模式
          3. 用像素差 × 按下时的坐标变换计算数据坐标偏移量
             （避免依赖 event.xdata，消除 axes 位置变化导致的 xdata 抖动）
          4. 所有子图 X 轴同步偏移，并应用边界约束
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
            self.w.canvas.setCursor(Qt.CursorShape.ClosedHandCursor)

        # 计算数据坐标偏移量：使用像素差 + 按下时的 transData 变换
        # 不依赖 event.xdata，因为 xdata 受 axes 位置影响（Y轴变化→axes微移→xdata偏移）
        press_ax = self._press_event.inaxes
        if press_ax is None:
            return

        try:
            # 使用按下时缓存的坐标变换（不受后续 Y 轴变化影响）
            inv = press_ax.transData.inverted()
            press_data_x = inv.transform((self._press_event.x, self._press_event.y))[0]
            curr_data_x = inv.transform((event.x, event.y))[0]
            dx_data = press_data_x - curr_data_x
        except Exception:
            logger.debug("坐标变换失败，跳过本次平移")
            return

        # 同步平移所有子图（仅修改 X 轴）
        self._apply_pan(dx_data)

        # 仅触发重绘，不修改 Y 轴
        # Y 轴自适应推迟到 on_release → on_canvas_zoom 防抖回调统一处理
        # 避免同一渲染帧内 X 轴平移与 Y 轴自适应的循环冲突导致绘图区域跳动
        self.w.canvas.draw_idle()

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
            self.w.canvas.setCursor(Qt.CursorShape.OpenHandCursor)

        # 重置状态
        self._press_event = None
        self._is_panning = False
        self._press_xlim = None

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

    # ── 内部方法 ──

    def _apply_pan(self, dx_data: float) -> None:
        """将所有子图 X 轴平移 dx_data 数据单位，并应用条件性边界约束。

        边界约束策略（条件性启用）：
          - 当 span ≥ data_span × 0.95（全视图）→ 禁用约束，允许自由溢出
          - 当 span < data_span × 0.95（已放大）→ 启用约束，含可配置白边

        约束算法（仅当启用时执行）：
          1. 计算新范围 [new_start, new_end] = [old_start + dx, old_end + dx]
          2. 计算白边边界：left_bound = t_min - margin, right_bound = t_max + margin
             其中 margin = white_margin_ratio × (t_max - t_min)
          3. 如果 new_start < left_bound → 整体右移至 left_bound
          4. 如果 new_end > right_bound → 整体左移至 right_bound
          5. 确保 span = new_end - new_start 不变（不改变缩放级别）
        """
        if self._press_xlim is None:
            return

        # 获取数据时间边界
        t_min: float | None = None
        t_max: float | None = None
        if self.w.ctx is not None and self.w.ctx.time_sec is not None and len(self.w.ctx.time_sec) > 0:
            t_min = float(self.w.ctx.time_sec[0])
            t_max = float(self.w.ctx.time_sec[-1])

        for i, ax in enumerate(self.w.axes):
            if i >= len(self._press_xlim):
                continue
            old_start, old_end = self._press_xlim[i]
            new_start = old_start + dx_data
            new_end = old_end + dx_data
            span = new_end - new_start

            # 条件性边界约束：仅当已放大时启用（span < data_span × 0.95）
            if t_min is not None and t_max is not None:
                data_span = t_max - t_min
                if data_span > 0 and span < data_span * 0.95:
                    margin = self._white_margin_ratio * data_span
                    left_bound = t_min - margin
                    right_bound = t_max + margin
                    if new_start < left_bound:
                        new_start = left_bound
                        new_end = left_bound + span
                    if new_end > right_bound:
                        new_end = right_bound
                        new_start = right_bound - span

            ax.set_xlim(new_start, new_end)
