"""
布局控制器 — 子图布局模式管理 + 选择控制。

从 PlotCanvasWidget 中提取的职责：
- 布局模式切换 (1×1, 4×1, 2×2)
- 子图轴创建和重建
- 子图选择/取消选择
- 子图边框样式
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from matplotlib.ticker import FuncFormatter

from ..time_utils import format_time_seconds

if TYPE_CHECKING:
    from .panel_plot import PlotCanvasWidget


class LayoutController:
    """子图布局管理 + 选择控制。"""

    def __init__(self, widget: PlotCanvasWidget) -> None:
        self.w = widget

    # ── 布局切换 ──

    def switch_layout(self, mode: str) -> None:
        """切换子图布局模式（原子操作）。"""
        w = self.w
        if mode == w._layout_mode:
            return
        # 重置平移状态，避免对已销毁 axes 的悬空引用
        w._pan.reset()
        w._layout_mode = mode

        # 1. 重分配信号到新布局
        old_fields = dict(w.subplot_fields)
        if mode == "1x1":
            new_count = 1
            max_per_plot = 0
        elif mode == "4x1":
            new_count = 4
            max_per_plot = 5
        elif mode == "2x2":
            new_count = 4
            max_per_plot = 4
        else:
            return

        new_fields: dict[int, list[str]] = {i: [] for i in range(new_count)}
        ordered_signals: list[str] = []
        for idx in sorted(old_fields.keys()):
            ordered_signals.extend(old_fields[idx])

        if mode in ("4x1", "2x2"):
            plot_idx = 0
            for f in ordered_signals:
                if max_per_plot > 0 and len(new_fields[plot_idx]) >= max_per_plot:
                    plot_idx += 1
                if plot_idx < new_count:
                    new_fields[plot_idx].append(f)
                else:
                    new_fields[new_count - 1].append(f)
        elif mode == "1x1":
            new_fields[0] = list(ordered_signals)

        for idx in list(new_fields.keys()):
            if max_per_plot > 0 and len(new_fields[idx]) > max_per_plot:
                overflow = new_fields[idx][max_per_plot:]
                new_fields[idx] = new_fields[idx][:max_per_plot]
                for f in overflow:
                    placed = False
                    for j in range(new_count):
                        if len(new_fields[j]) < max_per_plot:
                            new_fields[j].append(f)
                            placed = True
                            break
                    if not placed:
                        w.log_message.emit(f"子图已满，信号 [{f}] 被丢弃")

        w.subplot_fields = new_fields
        w._selected_subplot_idx = None

        # 2. 原子化重建：一次 clear + 一次性创建所有轴并绘制
        w.figure.clear()
        w.axes = []
        # 布局变更导致 axes 重建，Line2D 缓存失效
        w._renderer.invalidate_cache()

        crossing_fields: set[str] = set()

        if mode == "1x1":
            ax = w.figure.add_subplot(111)
            ax.grid(True, alpha=0.3)
            w.axes.append(ax)
            if w.ctx is not None:
                w._renderer.plot_subplot(ax, 0, crossing_fields)
            w.axes[0].set_xlabel("时间 (s)")
            w.axes[0].xaxis.set_major_formatter(
                FuncFormatter(lambda s, _: format_time_seconds(float(s))))

        elif mode == "4x1":
            for i in range(4):
                ax = w.figure.add_subplot(4, 1, i + 1)
                ax.grid(True, alpha=0.3)
                w.axes.append(ax)
                if w.ctx is not None:
                    w._renderer.plot_subplot(ax, i, crossing_fields)
            w.axes[-1].set_xlabel("时间 (s)")
            w.axes[-1].xaxis.set_major_formatter(
                FuncFormatter(lambda s, _: format_time_seconds(float(s))))

        elif mode == "2x2":
            for i in range(4):
                ax = w.figure.add_subplot(2, 2, i + 1)
                ax.grid(True, alpha=0.3)
                w.axes.append(ax)
                if w.ctx is not None:
                    w._renderer.plot_subplot(ax, i, crossing_fields)
            for i in [2, 3]:
                w.axes[i].set_xlabel("时间 (s)")
                w.axes[i].xaxis.set_major_formatter(
                    FuncFormatter(lambda s, _: format_time_seconds(float(s))))

        # 3. 后处理
        self.apply_spine_color()

        w.figure.tight_layout()
        w.canvas.draw_idle()
        w.log_message.emit(f"切换到 {mode} 布局")

    def rebuild_axes_for_mode(self) -> None:
        """根据当前布局模式创建空子图轴（仅在初始化时调用）。"""
        w = self.w
        w.figure.clear()
        w.axes = []
        w._renderer.invalidate_cache()
        for i in range(4):
            ax = w.figure.add_subplot(4, 1, i + 1)
            ax.grid(True, alpha=0.3)
            w.axes.append(ax)
        w.axes[-1].set_xlabel("时间 (s)")
        w.axes[-1].xaxis.set_major_formatter(
            FuncFormatter(lambda s, _: format_time_seconds(float(s))))
        w.figure.tight_layout()

    # ── 子图边框样式 ──

    def apply_spine_color(self) -> None:
        """应用子图边框颜色（选中=蓝色，未选中=浅灰）。"""
        w = self.w
        for i, ax in enumerate(w.axes):
            for spine in ax.spines.values():
                if w._selected_subplot_idx == i:
                    spine.set_color("#1976D2")
                    spine.set_linewidth(2.5)
                    spine.set_linestyle("solid")
                else:
                    spine.set_color("#cccccc")
                    spine.set_linewidth(0.8)
                    spine.set_linestyle("solid")

    def apply_drag_highlight(self, hover_idx: int | None) -> None:
        """应用拖拽悬停高亮（绿色虚线边框）。

        拖拽悬停子图显示绿色虚线，选中子图保持蓝色实线，其余浅灰。
        """
        w = self.w
        for i, ax in enumerate(w.axes):
            for spine in ax.spines.values():
                if i == hover_idx:
                    # 拖拽悬停：绿色虚线
                    spine.set_color("#4CAF50")
                    spine.set_linestyle("dashed")
                    spine.set_linewidth(2.5)
                elif w._selected_subplot_idx == i:
                    # 选中子图：保持蓝色实线
                    spine.set_color("#1976D2")
                    spine.set_linestyle("solid")
                    spine.set_linewidth(2.5)
                else:
                    # 普通子图：浅灰实线
                    spine.set_color("#cccccc")
                    spine.set_linestyle("solid")
                    spine.set_linewidth(0.8)
        w.canvas.draw_idle()

    def clear_drag_highlight(self) -> None:
        """清除拖拽悬停高亮，恢复原始边框样式。"""
        self.apply_spine_color()
        self.w.canvas.draw_idle()

    # ── 子图选择 ──

    def on_canvas_click(self, event) -> None:
        """画布点击事件（在 button_release 时调用）。

        仅处理左键子图选择。右键菜单已移至 panel_plot._on_button_press。
        注意：此方法仅在非平移（was_panning=False）时被调用，
        因此无需区分点击/拖拽。
        """
        w = self.w
        if event.button == 1:  # 左键
            if event.inaxes is not None:
                for i, ax in enumerate(w.axes):
                    if ax == event.inaxes:
                        self.select_subplot(i)
                        return
            else:
                self.deselect_subplot()

    def select_subplot(self, idx: int) -> None:
        """选中子图并通知外部。"""
        w = self.w
        if idx == w._selected_subplot_idx:
            return
        w._selected_subplot_idx = idx
        self.apply_spine_color()
        w.canvas.draw_idle()
        w.subplot_selected.emit(idx)

    def deselect_subplot(self) -> None:
        """取消选中子图。"""
        w = self.w
        if w._selected_subplot_idx is None:
            return
        w._selected_subplot_idx = None
        self.apply_spine_color()
        w.canvas.draw_idle()
        w.subplot_selected.emit(None)

    def get_selected_subplot(self) -> int | None:
        """获取当前选中的子图索引。"""
        return self.w._selected_subplot_idx

    def get_layout_mode(self) -> str:
        """获取当前布局模式。"""
        return self.w._layout_mode
