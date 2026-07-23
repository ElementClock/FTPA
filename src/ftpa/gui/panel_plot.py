"""
交互绘图面板 — 单屏核心组件。

布局（嵌在 MainWindow Row 1 Col 0）：
┌──────────────────────────────────────────────┐
│  [1×1] [4×1] [2×2]   (布局切换按钮)          │
├──────────────────────────────────────────────┤
│                                              │
│  FigureCanvasQTAgg（动态子图布局）             │
│                                              │
│  1×1: 1个子图         4×1: 4个垂直子图        │
│  2×2: 2行2列子图                              │
│                                              │
│  点击子图 → 蓝色边框高亮                       │
└──────────────────────────────────────────────┘
"""

from __future__ import annotations

from typing import Any

import matplotlib
matplotlib.use("QtAgg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QAction, QFont
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMenu,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from matplotlib.ticker import FuncFormatter

from ..statistics import find_crossing_points
from ..time_utils import format_time_seconds
from ..plotting import _configure_display_font
from .services import DataContext


class PlotCanvasWidget(QWidget):
    """交互绘图画布面板 — 动态子图布局。"""

    # 子图选中信号（发送子图索引，0-based）
    subplot_selected = Signal(object)  # int | None
    # 日志消息
    log_message = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.ctx: DataContext | None = None

        # 动态子图管理
        self._layout_mode: str = "4x1"  # "1x1" | "4x1" | "2x2"
        self.figure = Figure(figsize=(10, 6))
        self.canvas = FigureCanvas(self.figure)
        self.axes: list[plt.Axes] = []

        # 子图信号分配: 子图索引 -> field_name 列表
        self.subplot_fields: dict[int, list[str]] = {i: [] for i in range(4)}

        # 子图选择
        self._selected_subplot_idx: int | None = None

        # 穿越状态
        self.crossing_lines: list[Any] = []
        self.left_val: float = 0.0
        self.left_mode: str = "FirstUp"
        self.right_val: float = 0.0
        self.right_mode: str = "LastDown"
        self.master_field: str = ""

        # 子图右键菜单追踪
        self._right_clicked_axes_idx: int | None = None

        # 穿越点 x 坐标缓存（供 apply_crossing 缩放使用）
        self._crossing_x: dict[str, float | None] = {"left": None, "right": None}

        # 缩放防抖定时器
        self._zoom_timer: QTimer | None = None

        # 首次调用时扫描字体（_configure_display_font 是惰性的）
        _configure_display_font()

        self._build_ui()
        self._rebuild_axes_for_mode()
        self._connect_events()

    # ── 布局构建 ──

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # 画布
        self.canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout.addWidget(self.canvas, 1)

    def _connect_events(self):
        """连接画布事件。"""
        self.canvas.mpl_connect("button_press_event", self._on_canvas_click)
        self.canvas.mpl_connect("button_release_event", self._on_canvas_zoom)
        self.canvas.mpl_connect("scroll_event", self._on_canvas_zoom)

    # ── 子图布局管理 ──

    def _switch_layout(self, mode: str):
        """切换子图布局模式（原子操作）。"""
        if mode == self._layout_mode:
            return
        self._layout_mode = mode

        # 1. 重分配信号到新布局
        old_fields = dict(self.subplot_fields)
        if mode == "1x1":
            new_count = 1
            max_per_plot = 0
        elif mode == "4x1":
            new_count = 4
            max_per_plot = 5
        elif mode == "2x2":
            new_count = 4
            max_per_plot = 4

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
                        self.log_message.emit(f"子图已满，信号 [{f}] 被丢弃")

        self.subplot_fields = new_fields
        self._selected_subplot_idx = None

        # 2. 原子化重建：一次 clear + 一次性创建所有轴并绘制
        self.figure.clear()
        self.axes = []

        crossing_fields: set[str] = set()

        if mode == "1x1":
            ax = self.figure.add_subplot(111)
            ax.grid(True, alpha=0.3)
            self.axes.append(ax)
            if self.ctx is not None:
                self._plot_subplot(ax, 0, crossing_fields)
            self.axes[0].set_xlabel("时间 (s)")
            self.axes[0].xaxis.set_major_formatter(
                FuncFormatter(lambda s, _: format_time_seconds(float(s))))

        elif mode == "4x1":
            for i in range(4):
                ax = self.figure.add_subplot(4, 1, i + 1)
                ax.grid(True, alpha=0.3)
                self.axes.append(ax)
                if self.ctx is not None:
                    self._plot_subplot(ax, i, crossing_fields)
            self.axes[-1].set_xlabel("时间 (s)")
            self.axes[-1].xaxis.set_major_formatter(
                FuncFormatter(lambda s, _: format_time_seconds(float(s))))

        elif mode == "2x2":
            for i in range(4):
                ax = self.figure.add_subplot(2, 2, i + 1)
                ax.grid(True, alpha=0.3)
                self.axes.append(ax)
                if self.ctx is not None:
                    self._plot_subplot(ax, i, crossing_fields)
            for i in [2, 3]:
                self.axes[i].set_xlabel("时间 (s)")
                self.axes[i].xaxis.set_major_formatter(
                    FuncFormatter(lambda s, _: format_time_seconds(float(s))))

        # 3. 后处理
        self._apply_spine_color()
        self._update_master_combo(sorted(crossing_fields))

        self.figure.tight_layout()
        self.canvas.draw_idle()
        self.log_message.emit(f"切换到 {mode} 布局")

    def _rebuild_axes_for_mode(self):
        """初始化时创建默认布局的空轴。"""
        self.figure.clear()
        self.axes = []
        for i in range(4):
            ax = self.figure.add_subplot(4, 1, i + 1)
            ax.grid(True, alpha=0.3)
            self.axes.append(ax)
        self.axes[-1].set_xlabel("时间 (s)")
        self.axes[-1].xaxis.set_major_formatter(
            FuncFormatter(lambda s, _: format_time_seconds(float(s))))
        self.figure.tight_layout()

    def _plot_subplot(self, ax, idx: int, crossing_fields: set[str]):
        """在子图 ax 上绘制 idx 对应的信号（不调 ax.clear）。"""
        fields = self.subplot_fields.get(idx, [])
        if fields:
            for f in fields:
                data_arr = self.ctx.data.get(f)
                if data_arr is not None and self.ctx.time_sec is not None:
                    ax.plot(self.ctx.time_sec, data_arr, linewidth=0.8, label=self.ctx.get_label(f))
                    crossing_fields.add(f)
            if len(fields) > 1:
                ax.legend(fontsize=8)
            ax.set_ylabel(self.ctx.get_label(fields[0]) if len(fields) == 1 else f"子图{idx + 1}")
        else:
            ax.text(0.5, 0.5, f"子图 {idx + 1}（空）\n点击选中后添加参数",
                    ha="center", va="center", transform=ax.transAxes, fontsize=9, alpha=0.4)

    def _rebuild_plot(self):
        """重新绘制所有子图（仅信号内容变化时调用，不重建 axes）。"""
        if self.ctx is None:
            return

        crossing_fields: set[str] = set()

        for i, ax in enumerate(self.axes):
            ax.clear()
            ax.grid(True, alpha=0.3)

            fields = self.subplot_fields.get(i, [])
            if fields:
                for f in fields:
                    data_arr = self.ctx.data.get(f)
                    if data_arr is not None and self.ctx.time_sec is not None:
                        ax.plot(self.ctx.time_sec, data_arr, linewidth=0.8, label=self.ctx.get_label(f))
                        crossing_fields.add(f)
                if len(fields) > 1:
                    ax.legend(fontsize=8)
                ax.set_ylabel(self.ctx.get_label(fields[0]) if len(fields) == 1 else f"子图{i + 1}")
            else:
                ax.text(0.5, 0.5, f"子图 {i + 1}（空）\n点击选中后添加参数",
                        ha="center", va="center", transform=ax.transAxes, fontsize=9, alpha=0.4)

        if self._layout_mode == "4x1":
            self.axes[-1].set_xlabel("时间 (s)")
        elif self._layout_mode == "1x1":
            self.axes[0].set_xlabel("时间 (s)")
        elif self._layout_mode == "2x2":
            for i in [2, 3]:
                self.axes[i].set_xlabel("时间 (s)")

        bottom_axes = []
        if self._layout_mode == "4x1":
            bottom_axes = [self.axes[-1]]
        elif self._layout_mode == "1x1":
            bottom_axes = [self.axes[0]]
        elif self._layout_mode == "2x2":
            bottom_axes = [self.axes[i] for i in [2, 3]]
        for ax in bottom_axes:
            ax.xaxis.set_major_formatter(FuncFormatter(
                lambda s, _: format_time_seconds(float(s))))

        self._apply_spine_color()
        self._update_master_combo(sorted(crossing_fields))

        self.figure.tight_layout()
        self.canvas.draw_idle()

    def _apply_spine_color(self):
        """应用子图边框颜色（选中=蓝色，未选中=浅灰）。"""
        for i, ax in enumerate(self.axes):
            for spine in ax.spines.values():
                if self._selected_subplot_idx == i:
                    spine.set_color("#1976D2")
                    spine.set_linewidth(2.5)
                else:
                    spine.set_color("#cccccc")
                    spine.set_linewidth(0.8)

    # ── 子图选择 ──

    def _on_canvas_click(self, event):
        """画布点击事件。左键=选择子图，右键=上下文菜单。"""
        if event.button == 1:  # 左键
            if event.inaxes is not None:
                for i, ax in enumerate(self.axes):
                    if ax == event.inaxes:
                        self._select_subplot(i)
                        return
            else:
                self._deselect_subplot()
        elif event.button == 3:  # 右键
            if event.inaxes is not None:
                for i, ax in enumerate(self.axes):
                    if ax == event.inaxes and self.subplot_fields.get(i, []):
                        self._right_clicked_axes_idx = i
                        self._show_context_menu(event)
                        return

    def _select_subplot(self, idx: int):
        """选中子图并通知外部。"""
        if idx == self._selected_subplot_idx:
            return
        self._selected_subplot_idx = idx
        self._apply_spine_color()
        self.canvas.draw_idle()
        self.subplot_selected.emit(idx)

    def _deselect_subplot(self):
        """取消选中子图。"""
        if self._selected_subplot_idx is None:
            return
        self._selected_subplot_idx = None
        self._apply_spine_color()
        self.canvas.draw_idle()
        self.subplot_selected.emit(None)

    def get_selected_subplot(self) -> int | None:
        return self._selected_subplot_idx

    def get_layout_mode(self) -> str:
        return self._layout_mode

    def set_layout_mode(self, mode: str):
        """供菜单/外部调用切换布局。"""
        self._switch_layout(mode)

    # ── 信号管理（供 ParameterTreeWidget 调用）──

    def add_to_subplot(self, field_name: str):
        """添加信号到当前选中的子图。"""
        idx = self._selected_subplot_idx
        if idx is None:
            self.log_message.emit("请先点击选中一个子图")
            return
        if self.ctx is None:
            return

        # 检查信号是否已存在
        if field_name in self.subplot_fields.get(idx, []):
            self.log_message.emit(f"信号 [{self.ctx.get_label(field_name)}] 已在子图 {idx + 1} 中")
            return

        # 检查子图容量
        max_per_plot = {"1x1": 0, "4x1": 5, "2x2": 4}.get(self._layout_mode, 5)
        if max_per_plot > 0 and len(self.subplot_fields.get(idx, [])) >= max_per_plot:
            self.log_message.emit(f"子图 {idx + 1} 已达到最大信号数 ({max_per_plot})")
            return

        if idx not in self.subplot_fields:
            self.subplot_fields[idx] = []
        self.subplot_fields[idx].append(field_name)
        self.log_message.emit(f"添加信号 [{self.ctx.get_label(field_name)}] 到子图 {idx + 1}")
        self._rebuild_plot()

    def remove_from_subplot(self, field_name: str):
        """从当前选中的子图移除信号。"""
        idx = self._selected_subplot_idx
        if idx is None:
            self.log_message.emit("请先点击选中一个子图")
            return
        if self.ctx is None:
            return

        if idx in self.subplot_fields and field_name in self.subplot_fields[idx]:
            self.subplot_fields[idx].remove(field_name)
            self.log_message.emit(f"从子图 {idx + 1} 移除信号 [{self.ctx.get_label(field_name)}]")
            self._rebuild_plot()
        else:
            self.log_message.emit(f"子图 {idx + 1} 中不存在该信号")

    # ── 右键菜单 ──

    def _show_context_menu(self, event):
        """显示子图右键菜单。"""
        ctx = self.ctx
        if ctx is None or self._right_clicked_axes_idx is None:
            return

        idx = self._right_clicked_axes_idx
        current_fields = self.subplot_fields.get(idx, [])

        menu = QMenu(self)

        # 添加信号子菜单
        add_menu = menu.addMenu("添加信号")
        all_fields = ctx.get_field_names()
        for f in all_fields:
            label = ctx.get_label(f)
            if f not in current_fields:
                act = QAction(f"  {label}", self)
                act.setData(f)
                act.triggered.connect(lambda _, ff=f: self._add_to_subplot(idx, ff))
                add_menu.addAction(act)
            else:
                act = QAction(f"✓ {label}", self)
                act.setEnabled(False)
                add_menu.addAction(act)

        # 删除信号子菜单
        if current_fields:
            del_menu = menu.addMenu("删除信号")
            for f in current_fields:
                label = ctx.get_label(f)
                act = QAction(f"{label}", self)
                act.setData(f)
                act.triggered.connect(lambda _, ff=f: self._remove_from_subplot(idx, ff))
                del_menu.addAction(act)

        menu.addSeparator()
        act_clear = QAction("清空该子图", self)
        act_clear.triggered.connect(lambda: self._clear_subplot(idx))
        menu.addAction(act_clear)

        widget_pos = self.canvas.mapFromGlobal(self.cursor().pos())
        menu.exec(self.canvas.mapToGlobal(widget_pos))

    def _add_to_subplot(self, idx: int, field: str):
        """右键添加信号到指定子图。"""
        max_per_plot = {"1x1": 0, "4x1": 5, "2x2": 4}.get(self._layout_mode, 5)
        if max_per_plot > 0 and len(self.subplot_fields.get(idx, [])) >= max_per_plot:
            QMessageBox.information(self, "提示", f"子图 {idx + 1} 已达到最大信号数 ({max_per_plot})。")
            return
        if idx not in self.subplot_fields:
            self.subplot_fields[idx] = []
        if field not in self.subplot_fields[idx]:
            self.subplot_fields[idx].append(field)
            label = self.ctx.get_label(field) if self.ctx else field
            self.log_message.emit(f"添加信号 [{label}] 到子图 {idx + 1}")
            self._rebuild_plot()

    def _remove_from_subplot(self, idx: int, field: str):
        """右键从指定子图移除信号。"""
        if idx in self.subplot_fields and field in self.subplot_fields[idx]:
            self.subplot_fields[idx].remove(field)
            self._rebuild_plot()

    def _clear_subplot(self, idx: int):
        """清空指定子图。"""
        if idx in self.subplot_fields:
            self.subplot_fields[idx] = []
            self._rebuild_plot()

    def clear_selected_subplot(self):
        """清空当前选中子图的所有信号（供外部按钮调用）。"""
        idx = self._selected_subplot_idx
        if idx is None:
            self.log_message.emit("请先点击选中一个子图")
            return
        self._clear_subplot(idx)
        self.log_message.emit(f"已清空子图 {idx + 1}")

    # ── 穿越分析 ──

    def set_crossing_context(self, left_val: float, left_mode: str,
                             right_val: float, right_mode: str, master_field: str):
        """从外部设置穿越参数。"""
        self.left_val = left_val
        self.left_mode = left_mode
        self.right_val = right_val
        self.right_mode = right_mode
        self.master_field = master_field

    def _update_master_combo(self, crossing_fields: list[str]):
        """更新主穿越信号选择（外部控件持有的引用，此处仅用于内部逻辑）。"""
        # 这是在外部控件中维护的，这里不做重复处理
        pass

    def apply_crossing(self, left_val: float, left_mode: str,
                       right_val: float, right_mode: str, master_field: str):
        """应用穿越 — 缩放到左右穿越点之间的时间区间。"""
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
            for ax in self.axes:
                ax.set_xlim(left_x - pad, right_x + pad)
            self.canvas.draw_idle()

    def reset_zoom(self):
        """重置时间范围到数据起止（保留穿越线）。"""
        if self.ctx and self.ctx.time_sec is not None and len(self.ctx.time_sec) > 1:
            for ax in self.axes:
                ax.set_xlim(float(self.ctx.time_sec[0]), float(self.ctx.time_sec[-1]))
        self.canvas.draw_idle()
        self._update_stats()

    def _clear_crossing_lines(self):
        for line in self.crossing_lines:
            try:
                line.remove()
            except Exception:
                pass
        self.crossing_lines.clear()

    def _redraw_crossing(self):
        """重新绘制穿越线，并保存穿越点 x 坐标。"""
        self._clear_crossing_lines()
        ctx = self.ctx
        if ctx is None or ctx.time_sec is None:
            return

        if not self.master_field:
            self.canvas.draw_idle()
            return

        master_data = ctx.data.get(self.master_field)
        if master_data is None:
            self.canvas.draw_idle()
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
                for ax in self.axes:
                    if ax.get_visible():
                        line = ax.axvline(x_pos, color=colors[side], linewidth=1.0,
                                          alpha=0.7, linestyle=linestyles[side])
                        self.crossing_lines.append(line)

        self.canvas.draw_idle()
        self._update_stats()

    # ── 统计更新 ──

    def _on_canvas_zoom(self, event=None):
        """画布缩放/滚动后更新统计（防抖 200ms）。"""
        if self._zoom_timer is None:
            self._zoom_timer = QTimer()
            self._zoom_timer.setSingleShot(True)
            self._zoom_timer.timeout.connect(self._update_stats)
        self._zoom_timer.start(200)

    def _update_stats(self):
        """更新统计信息。"""
        if self.ctx is None or not self.axes or self.ctx.time_sec is None:
            return

        try:
            xlim = self.axes[0].get_xlim()
            t_start, t_end = xlim[0], xlim[1]
        except Exception:
            return

        lines: list[str] = []
        lines.append(f"时间窗口: {format_time_seconds(t_start)} - {format_time_seconds(t_end)}")

        # 各子图的信号统计
        for i in sorted(self.subplot_fields.keys()):
            fields = self.subplot_fields[i]
            if not fields:
                continue
            for f in fields:
                arr = self.ctx.data.get(f)
                if arr is None:
                    continue
                idx = (self.ctx.time_sec >= t_start) & (self.ctx.time_sec <= t_end)
                seg = arr[idx]
                if len(seg) > 0:
                    label = self.ctx.get_label(f)
                    lines.append(f"  {label}: min={np.min(seg):.4g}, max={np.max(seg):.4g}, mean={np.mean(seg):.4g}")

        # 穿越信息
        for side, (val, mode) in [("左", (self.left_val, self.left_mode)),
                                   ("右", (self.right_val, self.right_mode))]:
            if self.master_field and self.ctx:
                master_arr = np.asarray(self.ctx.data.get(self.master_field, []), dtype=float)
                pos = find_crossing_points(master_arr, val, mode)
                if pos is not None and self.ctx.time_sec is not None:
                    x = self.ctx.time_sec[pos - 1]
                    lines.append(f"穿越({side}): {mode} → {format_time_seconds(float(x))} ({self.master_field}={master_arr[pos - 1]:.4g})")
                else:
                    lines.append(f"穿越({side}): {mode} → 无")

        self.last_stats_text = "\n".join(lines)

    def get_stats_text(self) -> str:
        """获取当前统计文本（供外部信息显示框使用）。"""
        return getattr(self, 'last_stats_text', '')

    # ── 数据设置 ──

    def set_data_context(self, ctx: DataContext):
        """设置数据上下文。"""
        self.ctx = ctx
        self._rebuild_plot()
        self._update_stats()

    # ── 保存截图 ──

    def save_screenshot(self, filepath: str | None = None):
        """保存画布为图片。"""
        if filepath is None:
            path, _ = QFileDialog.getSaveFileName(
                self, "保存截图", "plot.png", "PNG (*.png);;PDF (*.pdf);;SVG (*.svg)")
            if path:
                self.figure.savefig(path, dpi=150, bbox_inches="tight")
                self.log_message.emit(f"截图已保存: {path}")
                return path
            return None
        else:
            self.figure.savefig(filepath, dpi=150, bbox_inches="tight")
            self.log_message.emit(f"截图已保存: {filepath}")
            return filepath
