"""
绘图渲染器 — 数据绘制 + 信号管理。

从 PlotCanvasWidget 中提取的职责：
- 子图信号绘制和重绘
- 信号添加/移除/清空
- 右键上下文菜单
- 数据上下文设置
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from matplotlib.ticker import FuncFormatter

from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMenu, QMessageBox

from ..time_utils import format_time_seconds

if TYPE_CHECKING:
    from .panel_plot import PlotCanvasWidget


class PlotRenderer:
    """数据绘制 + 信号管理。"""

    def __init__(self, widget: PlotCanvasWidget) -> None:
        self.w = widget

    # ── 数据绘制 ──

    def plot_subplot(self, ax, idx: int, crossing_fields: set[str]) -> None:
        """在子图 ax 上绘制第 idx 组信号，并将出现的信号名加入 crossing_fields。"""
        w = self.w
        fields = w.subplot_fields.get(idx, [])
        if fields:
            for f in fields:
                data_arr = w.ctx.data.get(f)
                if data_arr is not None and w.ctx.time_sec is not None:
                    ax.plot(w.ctx.time_sec, data_arr, linewidth=0.8, label=w.ctx.get_label(f))
                    crossing_fields.add(f)
            if len(fields) > 1:
                ax.legend(fontsize=8)
            ax.set_ylabel(w.ctx.get_label(fields[0]) if len(fields) == 1 else f"子图{idx + 1}")
        else:
            ax.text(0.5, 0.5, f"子图 {idx + 1}（空）\n点击选中后添加参数",
                    ha="center", va="center", transform=ax.transAxes, fontsize=9, alpha=0.4)

    def rebuild_plot(self) -> None:
        """重新绘制所有子图的信号内容（不重建 axes，仅清除+重绘数据）。"""
        w = self.w
        if w.ctx is None:
            return

        crossing_fields: set[str] = set()

        for i, ax in enumerate(w.axes):
            ax.clear()
            ax.grid(True, alpha=0.3)

            fields = w.subplot_fields.get(i, [])
            if fields:
                for f in fields:
                    data_arr = w.ctx.data.get(f)
                    if data_arr is not None and w.ctx.time_sec is not None:
                        ax.plot(w.ctx.time_sec, data_arr, linewidth=0.8, label=w.ctx.get_label(f))
                        crossing_fields.add(f)
                if len(fields) > 1:
                    ax.legend(fontsize=8)
                ax.set_ylabel(w.ctx.get_label(fields[0]) if len(fields) == 1 else f"子图{i + 1}")
            else:
                ax.text(0.5, 0.5, f"子图 {i + 1}（空）\n点击选中后添加参数",
                        ha="center", va="center", transform=ax.transAxes, fontsize=9, alpha=0.4)

        if w._layout_mode == "4x1":
            w.axes[-1].set_xlabel("时间 (s)")
        elif w._layout_mode == "1x1":
            w.axes[0].set_xlabel("时间 (s)")
        elif w._layout_mode == "2x2":
            for i in [2, 3]:
                w.axes[i].set_xlabel("时间 (s)")

        bottom_axes = []
        if w._layout_mode == "4x1":
            bottom_axes = [w.axes[-1]]
        elif w._layout_mode == "1x1":
            bottom_axes = [w.axes[0]]
        elif w._layout_mode == "2x2":
            bottom_axes = [w.axes[i] for i in [2, 3]]
        for ax in bottom_axes:
            ax.xaxis.set_major_formatter(FuncFormatter(
                lambda s, _: format_time_seconds(float(s))))

        w._layout.apply_spine_color()

        w.figure.tight_layout()
        w.canvas.draw_idle()

    # ── 信号管理 ──

    def add_to_subplot(self, field_name: str) -> None:
        """添加信号到当前选中的子图。"""
        w = self.w
        idx = w._selected_subplot_idx
        if idx is None:
            w.log_message.emit("请先点击选中一个子图")
            return
        if w.ctx is None:
            return

        # 检查信号是否已存在
        if field_name in w.subplot_fields.get(idx, []):
            w.log_message.emit(f"信号 [{w.ctx.get_label(field_name)}] 已在子图 {idx + 1} 中")
            return

        # 检查子图容量
        max_per_plot = {"1x1": 0, "4x1": 5, "2x2": 4}.get(w._layout_mode, 5)
        if max_per_plot > 0 and len(w.subplot_fields.get(idx, [])) >= max_per_plot:
            w.log_message.emit(f"子图 {idx + 1} 已达到最大信号数 ({max_per_plot})")
            return

        if idx not in w.subplot_fields:
            w.subplot_fields[idx] = []
        w.subplot_fields[idx].append(field_name)
        w.log_message.emit(f"添加信号 [{w.ctx.get_label(field_name)}] 到子图 {idx + 1}")
        self.rebuild_plot()

    def remove_from_subplot(self, field_name: str) -> None:
        """从当前选中的子图移除信号。"""
        w = self.w
        idx = w._selected_subplot_idx
        if idx is None:
            w.log_message.emit("请先点击选中一个子图")
            return
        if w.ctx is None:
            return

        if idx in w.subplot_fields and field_name in w.subplot_fields[idx]:
            w.subplot_fields[idx].remove(field_name)
            w.log_message.emit(f"从子图 {idx + 1} 移除信号 [{w.ctx.get_label(field_name)}]")
            self.rebuild_plot()
        else:
            w.log_message.emit(f"子图 {idx + 1} 中不存在该信号")

    # ── 右键菜单 ──

    def show_context_menu(self, event) -> None:
        """显示子图右键菜单：添加/删除信号、清空子图。"""
        w = self.w
        ctx = w.ctx
        if ctx is None or w._right_clicked_axes_idx is None:
            return

        idx = w._right_clicked_axes_idx
        current_fields = w.subplot_fields.get(idx, [])

        menu = QMenu(w)

        # 添加信号子菜单
        add_menu = menu.addMenu("添加信号")
        all_fields = ctx.get_field_names()
        for f in all_fields:
            label = ctx.get_label(f)
            if f not in current_fields:
                act = QAction(f"  {label}", w)
                act.setData(f)
                act.triggered.connect(lambda _, ff=f: self._add_to_subplot(idx, ff))
                add_menu.addAction(act)
            else:
                act = QAction(f"✓ {label}", w)
                act.setEnabled(False)
                add_menu.addAction(act)

        # 删除信号子菜单
        if current_fields:
            del_menu = menu.addMenu("删除信号")
            for f in current_fields:
                label = ctx.get_label(f)
                act = QAction(f"{label}", w)
                act.setData(f)
                act.triggered.connect(lambda _, ff=f: self._remove_from_subplot(idx, ff))
                del_menu.addAction(act)

        menu.addSeparator()
        act_clear = QAction("清空该子图", w)
        act_clear.triggered.connect(lambda: self._clear_subplot(idx))
        menu.addAction(act_clear)

        widget_pos = w.canvas.mapFromGlobal(w.cursor().pos())
        menu.exec(w.canvas.mapToGlobal(widget_pos))

    def _add_to_subplot(self, idx: int, field: str) -> None:
        """右键菜单：添加信号 field 到指定子图 idx。"""
        w = self.w
        max_per_plot = {"1x1": 0, "4x1": 5, "2x2": 4}.get(w._layout_mode, 5)
        if max_per_plot > 0 and len(w.subplot_fields.get(idx, [])) >= max_per_plot:
            QMessageBox.information(w, "提示", f"子图 {idx + 1} 已达到最大信号数 ({max_per_plot})。")
            return
        if idx not in w.subplot_fields:
            w.subplot_fields[idx] = []
        if field not in w.subplot_fields[idx]:
            w.subplot_fields[idx].append(field)
            label = w.ctx.get_label(field) if w.ctx else field
            w.log_message.emit(f"添加信号 [{label}] 到子图 {idx + 1}")
            self.rebuild_plot()

    def _remove_from_subplot(self, idx: int, field: str) -> None:
        """右键菜单：从指定子图 idx 移除信号 field。"""
        w = self.w
        if idx in w.subplot_fields and field in w.subplot_fields[idx]:
            w.subplot_fields[idx].remove(field)
            self.rebuild_plot()

    def _clear_subplot(self, idx: int) -> None:
        """清空指定子图 idx 的所有信号。"""
        w = self.w
        if idx in w.subplot_fields:
            w.subplot_fields[idx] = []
            self.rebuild_plot()

    def clear_selected_subplot(self) -> None:
        """清空当前选中子图的所有信号（供外部按钮调用）。"""
        w = self.w
        idx = w._selected_subplot_idx
        if idx is None:
            w.log_message.emit("请先点击选中一个子图")
            return
        self._clear_subplot(idx)
        w.log_message.emit(f"已清空子图 {idx + 1}")

    # ── 数据设置 ──

    def set_data_context(self, ctx) -> None:
        """设置数据上下文并重绘。"""
        w = self.w
        w.ctx = ctx
        self.rebuild_plot()
        w._crossing.update_stats()
