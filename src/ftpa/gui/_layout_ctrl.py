"""
布局控制器 — 子图布局模式管理 + 选择控制。

从 PlotCanvasWidget 中提取的职责：
- 布局模式切换 (1×1, 2×1, 3×1, 4×1, 2×2)
- 子图轴创建和重建
- 子图选择/取消选择
- 子图边框样式
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from matplotlib.ticker import FuncFormatter

from ..utils.time_utils import format_time_seconds
from ..config import CONFIG

if TYPE_CHECKING:
    from .panel_plot import PlotCanvasWidget


class LayoutController:
    """子图布局管理 + 选择控制。"""

    # 布局模式配置：mode -> (子图数量, 每子图最大信号数)
    LAYOUT_CONFIG: dict[str, tuple[int, int]] = {
        "1x1": (1, 0),   # 0 表示无限制
        "2x1": (2, 5),
        "3x1": (3, 5),
        "4x1": (4, 5),
        "2x2": (4, 4),
    }

    def __init__(self, widget: PlotCanvasWidget) -> None:
        self._widget = widget

    # ── 布局切换 ──

    def switch_layout(self, mode: str) -> None:
        """切换子图布局模式（原子操作）。"""
        w = self._widget
        if mode == w._layout_mode:
            return
        if mode not in self.LAYOUT_CONFIG:
            return

        # 重置平移状态，避免对已销毁 axes 的悬空引用
        w._pan.reset()
        w._layout_mode = mode

        new_count, max_per_plot = self.LAYOUT_CONFIG[mode]

        # 1. 重分配信号到新布局
        old_fields = dict(w.subplot_fields)
        new_fields: dict[int, list[str]] = {i: [] for i in range(new_count)}
        ordered_signals: list[str] = []
        for idx in sorted(old_fields.keys()):
            ordered_signals.extend(old_fields[idx])

        if mode == "1x1":
            new_fields[0] = list(ordered_signals)
        else:
            plot_idx = 0
            for f in ordered_signals:
                if max_per_plot > 0 and len(new_fields[plot_idx]) >= max_per_plot:
                    plot_idx += 1
                if plot_idx < new_count:
                    new_fields[plot_idx].append(f)
                else:
                    new_fields[new_count - 1].append(f)

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
        self._create_axes_for_mode(mode)

        # 3. 后处理
        self.apply_spine_color()

        w.figure.tight_layout()
        w.canvas.draw_idle()
        w.log_message.emit(f"切换到 {mode} 布局")

    def _create_axes_for_mode(self, mode: str) -> None:
        """根据布局模式创建子图轴并绘制信号（供 switch_layout 和 rebuild_axes_for_mode 复用）。"""
        w = self._widget
        w.figure.clear()
        w.axes = []
        w._renderer.invalidate_cache()

        new_count = self.LAYOUT_CONFIG[mode][0]
        crossing_fields: set[str] = set()

        if mode == "1x1":
            ax = w.figure.add_subplot(111)
            ax.grid(True, alpha=0.3)
            w.axes.append(ax)
            if w.ctx is not None:
                w._renderer.plot_subplot(ax, 0, crossing_fields)

        elif mode == "2x2":
            for i in range(new_count):
                ax = w.figure.add_subplot(2, 2, i + 1)
                ax.grid(True, alpha=0.3)
                w.axes.append(ax)
                if w.ctx is not None:
                    w._renderer.plot_subplot(ax, i, crossing_fields)

        else:
            # Nx1 模式（2x1, 3x1, 4x1）
            n_rows = new_count
            for i in range(new_count):
                ax = w.figure.add_subplot(n_rows, 1, i + 1)
                ax.grid(True, alpha=0.3)
                w.axes.append(ax)
                if w.ctx is not None:
                    w._renderer.plot_subplot(ax, i, crossing_fields)

        # 设置底部子图的 X 轴标签，并为所有子图设置时间格式化
        self.apply_axis_decorations(mode)

        # 同步所有子图 X 轴范围：优先以有数据的子图为基准
        # 防止各子图因 ax.plot() 自动缩放而产生不一致的 xlim
        ref_xlim = w._renderer.get_reference_xlim()
        if ref_xlim is not None:
            for ax in w.axes:
                ax.set_xlim(ref_xlim)

    def apply_axis_decorations(self, mode: str | None = None) -> None:
        """为布局模式应用 X 轴装饰：底部子图 X 轴标签 + 全部子图时间格式化器。

        唯一实现（D1）：PlotRenderer 等外部调用统一走这里；
        mode 缺省时取当前布局模式；不触发重绘。
        """
        w = self._widget
        if mode is None:
            mode = w._layout_mode
        bottom_indices: list[int] = []

        if mode == "1x1":
            bottom_indices = [0]
        elif mode == "2x2":
            bottom_indices = [2, 3]
        else:
            # Nx1 模式（2x1, 3x1, 4x1）：仅最底部一个子图
            bottom_indices = [len(w.axes) - 1]

        # 仅为底部子图设置 X 轴标签（避免冗余）
        for i in bottom_indices:
            w.axes[i].set_xlabel("时间 (s)")

        # 为所有子图设置时间格式化器，确保各子图 X 轴刻度显示一致
        for ax in w.axes:
            ax.xaxis.set_major_formatter(
                FuncFormatter(lambda s, _: format_time_seconds(float(s))))

    def rebuild_axes_for_mode(self) -> None:
        """根据当前布局模式创建空子图轴（仅在初始化时调用）。"""
        w = self._widget
        w.figure.clear()
        w.axes = []
        w._renderer.invalidate_cache()

        mode = w._layout_mode
        new_count = self.LAYOUT_CONFIG[mode][0]

        if mode == "2x2":
            for i in range(new_count):
                ax = w.figure.add_subplot(2, 2, i + 1)
                ax.grid(True, alpha=0.3)
                w.axes.append(ax)
        else:
            # 1x1 和 Nx1 模式
            n_rows = new_count
            for i in range(new_count):
                ax = w.figure.add_subplot(n_rows, 1, i + 1)
                ax.grid(True, alpha=0.3)
                w.axes.append(ax)

        self.apply_axis_decorations(mode)
        w.figure.tight_layout()

    # ── 子图边框样式 ──

    def apply_spine_color(self) -> None:
        """应用子图边框颜色（选中=蓝色，未选中=浅灰）。"""
        w = self._widget
        for i, ax in enumerate(w.axes):
            for spine in ax.spines.values():
                if w._selected_subplot_idx == i:
                    spine.set_color(CONFIG.plot.selected_color)
                    spine.set_linewidth(2.5)
                    spine.set_linestyle("solid")
                else:
                    spine.set_color(CONFIG.plot.unselected_color)
                    spine.set_linewidth(0.8)
                    spine.set_linestyle("solid")

    def apply_drag_highlight(self, hover_idx: int | None) -> None:
        """应用拖拽悬停高亮（绿色虚线边框）。

        拖拽悬停子图显示绿色虚线，选中子图保持蓝色实线，其余浅灰。
        """
        w = self._widget
        for i, ax in enumerate(w.axes):
            for spine in ax.spines.values():
                if i == hover_idx:
                    # 拖拽悬停：绿色虚线
                    spine.set_color("#4CAF50")
                    spine.set_linestyle("dashed")
                    spine.set_linewidth(2.5)
                elif w._selected_subplot_idx == i:
                    # 选中子图：保持蓝色实线
                    spine.set_color(CONFIG.plot.selected_color)
                    spine.set_linestyle("solid")
                    spine.set_linewidth(2.5)
                else:
                    # 普通子图：浅灰实线
                    spine.set_color(CONFIG.plot.unselected_color)
                    spine.set_linestyle("solid")
                    spine.set_linewidth(0.8)
        w.canvas.draw_idle()

    def clear_drag_highlight(self) -> None:
        """清除拖拽悬停高亮，恢复原始边框样式。"""
        self.apply_spine_color()
        self._widget.canvas.draw_idle()

    # ── 子图选择 ──

    def on_canvas_click(self, event) -> None:
        """画布点击事件（在 button_release 时调用）。

        仅处理左键子图选择。右键菜单已移至 panel_plot._on_button_press。
        注意：此方法仅在非平移（was_panning=False）时被调用，
        因此无需区分点击/拖拽。
        """
        w = self._widget
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
        w = self._widget
        if idx == w._selected_subplot_idx:
            return
        w._selected_subplot_idx = idx
        self.apply_spine_color()
        w.canvas.draw_idle()
        w.subplot_selected.emit(idx)

    def deselect_subplot(self) -> None:
        """取消选中子图。"""
        w = self._widget
        if w._selected_subplot_idx is None:
            return
        w._selected_subplot_idx = None
        self.apply_spine_color()
        w.canvas.draw_idle()
        w.subplot_selected.emit(None)

    def get_selected_subplot(self) -> int | None:
        """获取当前选中的子图索引。"""
        return self._widget._selected_subplot_idx

    def get_layout_mode(self) -> str:
        """获取当前布局模式。"""
        return self._widget._layout_mode
