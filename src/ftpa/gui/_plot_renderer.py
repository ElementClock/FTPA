"""
绘图渲染器 — 数据绘制 + 信号管理。

从 PlotCanvasWidget 中提取的职责：
- 子图信号绘制和重绘
- 信号添加/移除/清空
- 右键上下文菜单
- 数据上下文设置

性能优化策略：
- Line2D 复用：信号增删时增量更新（set_xdata/set_ydata），
  仅布局变更时才执行 ax.clear() 全量重建。
- tight_layout 条件化：仅在布局变更时调用（~22ms），
  数据变更时跳过。
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import numpy as np
from matplotlib.ticker import FuncFormatter

from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMenu, QMessageBox

from ..utils.time_utils import format_time_seconds
from ._layout_ctrl import LayoutController
from ._downsampler import min_max_downsample
from .parameter_picker import ParameterPickerDialog
from ..config import CONFIG

if TYPE_CHECKING:
    from .panel_plot import PlotCanvasWidget

logger = logging.getLogger(__name__)


class PlotRenderer:
    """数据绘制 + 信号管理。"""

    def __init__(self, widget: PlotCanvasWidget) -> None:
        self._widget = widget
        # Line2D 缓存: (subplot_idx, field_name) -> Line2D
        self._line_cache: dict[tuple[int, str], Any] = {}
        # 空子图文本标注缓存: subplot_idx -> Text
        self._empty_text_cache: dict[int, Any] = {}
        # 右键菜单追踪：当前右键点击的子图索引
        self._right_clicked_idx: int | None = None

    # ── 公共属性 ──

    @property
    def right_clicked_subplot(self) -> int | None:
        """当前右键点击的子图索引（公开访问接口）。"""
        return self._right_clicked_idx

    @right_clicked_subplot.setter
    def right_clicked_subplot(self, value: int | None) -> None:
        self._right_clicked_idx = value

    def invalidate_cache(self) -> None:
        """清除 Line2D 缓存（布局切换/axes 重建时调用）。"""
        self._line_cache.clear()
        self._empty_text_cache.clear()

    # ── 数据绘制 ──

    def _get_render_data(self, f: str) -> tuple[np.ndarray, np.ndarray] | None:
        """获取信号 f 的渲染数据（大数据集自动降采样）。

        Returns:
            (time, data) 渲染用的时间/数据数组，或 None（数据不可用）。
        """
        w = self._widget
        query = w.ctx.query
        data_arr = query.get_signal_data(f)
        time_sec = query.get_time_sec()
        if data_arr is None or time_sec is None:
            return None

        # 检测是否需要降采样：根据当前视图范围
        try:
            xlim = w.axes[0].get_xlim() if w.axes else None
        except Exception:
            logger.debug("xlim 获取失败，跳过降采样", exc_info=True)
            xlim = None

        if xlim is not None:
            t_start, t_end = float(xlim[0]), float(xlim[1])
            n_total = len(time_sec)
            # 粗略估计可见点数
            i_start = np.searchsorted(time_sec, t_start, side="left")
            i_end = np.searchsorted(time_sec, t_end, side="right")
            n_visible = i_end - i_start

            if n_visible > CONFIG.plot.downsample_threshold:
                ds_time, ds_data = min_max_downsample(
                    time_sec, data_arr, t_start, t_end
                )
                return ds_time, ds_data

        return time_sec, data_arr

    def refresh_viewport_data(self) -> None:
        """根据当前视图范围重新评估降采样，刷新所有 Line2D 数据。

        缩放/平移后调用，保证 Line2D 数据始终与当前视图匹配：
        - 视图范围大（> 阈值）：使用降采样数据
        - 视图范围小（< 阈值）：使用原始全分辨率数据

        性能：仅更新 Line2D 数据，不触发 axes 重建或 tight_layout。
        """
        for (idx, f), line in list(self._line_cache.items()):
            render_data = self._get_render_data(f)
            if render_data is not None:
                t, d = render_data
                line.set_xdata(t)
                line.set_ydata(d)

    def plot_subplot(self, ax, idx: int, crossing_fields: set[str]) -> None:
        """在子图 ax 上绘制第 idx 组信号，并将出现的信号名加入 crossing_fields。

        仅用于 switch_layout 中的全量绘制（布局切换时 axes 被重建）。
        """
        self._render_subplot_from_scratch(ax, idx, crossing_fields)

    def rebuild_plot(self, layout_changed: bool = False) -> None:
        """重新绘制所有子图的信号内容。

        Args:
            layout_changed: 是否因布局切换调用。
                True → ax.clear() 全量重建 + tight_layout（安全但较慢）
                False → Line2D 增量更新，跳过 tight_layout（快速路径）

        增量更新策略（layout_changed=False）：
          - 对比 _line_cache 与当前 subplot_fields
          - 移除已删除信号的 Line2D
          - 复用已有 Line2D（set_xdata/set_ydata）
          - 新建新增信号的 Line2D
          - 避免不必要的 ax.clear() + 对象重建
        """
        w = self._widget
        if w.ctx is None:
            return

        if layout_changed:
            self._full_rebuild()
            return

        # ── 增量更新路径 ──
        crossing_fields: set[str] = set()

        for i, ax in enumerate(w.axes):
            fields = w.subplot_fields.get(i, [])
            field_set = set(fields)

            # 1. 获取该子图已缓存的 field 集合
            cached_fields = {k[1] for k in self._line_cache if k[0] == i}

            # 2. 移除不再需要的 Line2D
            removed_fields = cached_fields - field_set
            for f in removed_fields:
                line = self._line_cache.pop((i, f), None)
                if line is not None:
                    try:
                        line.remove()
                    except ValueError:
                        pass

            # 3. 更新/新增 Line2D
            for f in fields:
                render_data = self._get_render_data(f)
                if render_data is None:
                    continue
                t, d = render_data
                crossing_fields.add(f)

                key = (i, f)
                if key in self._line_cache:
                    # 复用已有 Line2D：仅更新数据
                    line = self._line_cache[key]
                    line.set_xdata(t)
                    line.set_ydata(d)
                else:
                    # 新建 Line2D
                    self._create_line_for_field(ax, i, f, crossing_fields)

            # 4. 处理空子图文本标注
            if not fields:
                if i not in self._empty_text_cache:
                    self._create_empty_text(ax, i)
            else:
                txt = self._empty_text_cache.pop(i, None)
                if txt is not None:
                    try:
                        txt.remove()
                    except ValueError:
                        pass

            # 5. Legend + ylabel
            self._apply_legend(ax, fields, incremental=True)
            ax.set_ylabel(self._compute_ylabel(fields, i))

        # 7. 通用装饰
        self._apply_axis_decorations()

        # 8. 同步所有子图 X 轴范围：以 axes[0] 为基准
        #    防止增量更新中新建 Line2D（ax.plot()）触发自动缩放导致 xlim 解耦
        if w.axes:
            ref_xlim = w.axes[0].get_xlim()
            for ax in w.axes[1:]:
                ax.set_xlim(ref_xlim)

        w._layout.apply_spine_color()
        w.canvas.draw_idle()

    def _full_rebuild(self) -> None:
        """全量重建：ax.clear() + 重绘所有 Line2D + tight_layout。

        仅在布局变更（switch_layout）时调用，确保 axes 完全干净。
        """
        w = self._widget
        self.invalidate_cache()

        crossing_fields: set[str] = set()

        for i, ax in enumerate(w.axes):
            ax.clear()
            ax.grid(True, alpha=0.3)
            self._render_subplot_from_scratch(ax, i, crossing_fields)

        self._apply_axis_decorations()
        w._layout.apply_spine_color()

        # 全量重建后同步所有子图 X 轴范围
        if w.axes:
            ref_xlim = w.axes[0].get_xlim()
            for ax in w.axes[1:]:
                ax.set_xlim(ref_xlim)

        w.figure.tight_layout()
        w.canvas.draw_idle()

    def _render_subplot_from_scratch(
        self, ax, idx: int, crossing_fields: set[str],
    ) -> None:
        """在干净子图上全量绘制所有信号。

        前提：ax 已通过 ax.clear() 清空或为新创建的 Axes。
        由 plot_subplot 和 _full_rebuild 共用。

        Args:
            ax: 已清空的子图 Axes
            idx: 子图索引（0-based）
            crossing_fields: 穿越字段收集集合（就地修改）
        """
        w = self._widget
        fields = w.subplot_fields.get(idx, [])
        if fields:
            for f in fields:
                self._create_line_for_field(ax, idx, f, crossing_fields)
            self._apply_legend(ax, fields)
            ax.set_ylabel(self._compute_ylabel(fields, idx))
        else:
            self._create_empty_text(ax, idx)

    def _apply_legend(self, ax, fields: list[str], *, incremental: bool = False) -> None:
        """根据字段数量条件性地管理子图 legend。

        Args:
            ax: 目标子图 Axes
            fields: 子图字段列表
            incremental: 是否增量模式。
                False（全量模式）：仅在 len(fields)>1 时创建 legend
                True（增量模式）：先移除旧 legend，再条件性重建
        """
        need_legend = len(fields) > 1
        if incremental:
            old_legend = ax.get_legend()
            if old_legend is not None:
                old_legend.remove()
            if need_legend:
                ax.legend(fontsize=CONFIG.plot.legend_fontsize)
        else:
            if need_legend:
                ax.legend(fontsize=CONFIG.plot.legend_fontsize)

    def _create_line_for_field(
        self, ax, idx: int, field: str, crossing_fields: set[str] | None = None,
    ) -> Any | None:
        """在 ax 上创建信号 field 的 Line2D 并缓存。

        Args:
            ax: 目标子图 Axes
            idx: 子图索引
            field: 字段名
            crossing_fields: 穿越字段收集集合（可选，不传则不收集）

        Returns:
            创建的 Line2D 对象，或 None（数据不可用）。
        """
        render_data = self._get_render_data(field)
        if render_data is None:
            return None
        t, d = render_data
        w = self._widget
        line = ax.plot(
            t, d, linewidth=CONFIG.plot.line_width, label=w.ctx.get_label(field),
        )[0]
        self._line_cache[(idx, field)] = line
        if crossing_fields is not None:
            crossing_fields.add(field)
        return line

    def _create_empty_text(self, ax, idx: int) -> Any:
        """在空子图中央显示提示文本并缓存。

        Returns:
            创建的 Text 对象。
        """
        txt = ax.text(
            0.5, 0.5, f"子图 {idx + 1}（空）\n点击选中后添加参数",
            ha="center", va="center", transform=ax.transAxes,
            fontsize=CONFIG.plot.empty_text_fontsize, alpha=CONFIG.plot.empty_text_alpha,
        )
        self._empty_text_cache[idx] = txt
        return txt

    def _compute_ylabel(self, fields: list[str], idx: int) -> str:
        """计算子图的 Y 轴标签。

        单信号显示信号标签，多信号显示"子图N"，空子图返回空字符串。
        """
        if not fields:
            return ""
        if len(fields) == 1:
            return self._widget.ctx.get_label(fields[0])
        return f"子图{idx + 1}"

    def _apply_axis_decorations(self) -> None:
        """应用 X 轴标签和时间格式化器（不触发重绘）。"""
        w = self._widget
        mode = w._layout_mode

        # 确定底部子图索引（仅底部显示 X 轴标签）
        bottom_indices: list[int] = []
        if mode == "2x2":
            bottom_indices = [2, 3]
        elif mode == "1x1":
            bottom_indices = [0]
        else:
            # Nx1 模式（2x1, 3x1, 4x1）：仅最底部一个子图
            bottom_indices = [len(w.axes) - 1]

        for i in bottom_indices:
            w.axes[i].set_xlabel("时间 (s)")

        # 为所有子图设置时间格式化器，确保各子图 X 轴刻度显示一致
        for ax in w.axes:
            ax.xaxis.set_major_formatter(FuncFormatter(
                lambda s, _: format_time_seconds(float(s))))

    # ── 信号管理 ──

    def add_to_subplot(self, field_name: str) -> None:
        """添加信号到当前选中的子图。"""
        w = self._widget
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
        max_per_plot = LayoutController.LAYOUT_CONFIG.get(w._layout_mode, (0, 5))[1]
        if max_per_plot > 0 and len(w.subplot_fields.get(idx, [])) >= max_per_plot:
            w.log_message.emit(f"子图 {idx + 1} 已达到最大信号数 ({max_per_plot})")
            return

        if idx not in w.subplot_fields:
            w.subplot_fields[idx] = []
        w.subplot_fields[idx].append(field_name)
        w.log_message.emit(f"添加信号 [{w.ctx.get_label(field_name)}] 到子图 {idx + 1}")
        w.subplot_fields_changed.emit()
        self.rebuild_plot()

    def remove_from_subplot(self, field_name: str) -> None:
        """从当前选中的子图移除信号。"""
        w = self._widget
        idx = w._selected_subplot_idx
        if idx is None:
            w.log_message.emit("请先点击选中一个子图")
            return
        if w.ctx is None:
            return

        if idx in w.subplot_fields and field_name in w.subplot_fields[idx]:
            w.subplot_fields[idx].remove(field_name)
            w.log_message.emit(f"从子图 {idx + 1} 移除信号 [{w.ctx.get_label(field_name)}]")
            w.subplot_fields_changed.emit()
            self.rebuild_plot()
        else:
            w.log_message.emit(f"子图 {idx + 1} 中不存在该信号")

    # ── 右键菜单 ──

    def show_context_menu(self, event) -> None:
        """显示子图右键菜单：布局切换 + 删除信号、清空子图 + 区域筛选。

        布局子菜单始终显示；信号管理选项在右键点击子图时显示。
        区域筛选选项在有框选区域时显示。
        - "删除信号"：仅子图有信号时显示
        - "清空该子图"：始终显示，无信号时灰显
        """
        w = self._widget
        ctx = w.ctx
        menu = QMenu(w)

        # ── 区域筛选（框选区域存在时显示）──
        if w.has_region_selection():
            region = w.get_region_time_range()
            if region is not None:
                t_start, t_end = region
                region_label = (f"应用区域筛选 ({format_time_seconds(t_start)} → "
                                f"{format_time_seconds(t_end)})")
                act_apply_region = QAction(region_label, w)
                act_apply_region.triggered.connect(lambda: w.apply_region_selection())
                menu.addAction(act_apply_region)

            act_cancel_region = QAction("取消区域筛选", w)
            act_cancel_region.triggered.connect(lambda: w.cancel_region_selection())
            menu.addAction(act_cancel_region)
            menu.addSeparator()

        # ── 布局子菜单（始终显示）──
        layout_menu = menu.addMenu("布局")
        for mode, text in [("1x1", "1×1"), ("2x1", "2×1"), ("3x1", "3×1"),
                           ("4x1", "4×1"), ("2x2", "2×2")]:
            act = QAction(text, w)
            act.setCheckable(True)
            act.setChecked(mode == w._layout_mode)
            act.triggered.connect(lambda _, m=mode: self._switch_layout_from_menu(m))
            layout_menu.addAction(act)

        # ── 信号管理（右键点击子图时显示）──
        idx = self._right_clicked_idx
        current_fields = w.subplot_fields.get(idx, []) if idx is not None else []

        if ctx is not None and idx is not None:
            menu.addSeparator()

            # 删除信号子菜单（仅子图有信号时显示）
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
            act_clear.setEnabled(bool(current_fields))
            act_clear.triggered.connect(lambda: self._clear_subplot(idx))
            menu.addAction(act_clear)

            act_add = QAction("添加参数...", w)
            act_add.triggered.connect(lambda: self._open_parameter_picker(idx))
            menu.addAction(act_add)

        widget_pos = w.canvas.mapFromGlobal(w.cursor().pos())
        menu.exec(w.canvas.mapToGlobal(widget_pos))

    def _open_parameter_picker(self, idx: int) -> None:
        """右键“添加参数...”：打开搜索式参数选择对话框。"""
        w = self._widget
        if w.ctx is None:
            return
        field_labels, available_fields = w.ctx.get_all_field_labels_with_units()
        dialog = ParameterPickerDialog(w, field_labels, available_fields)
        if dialog.exec() and dialog.selected_field():
            self._add_to_subplot(idx, dialog.selected_field())

    def _switch_layout_from_menu(self, mode: str) -> None:
        """右键菜单：切换布局模式。"""
        self._widget.set_layout_mode(mode)

    def _add_to_subplot(self, idx: int, field: str) -> None:
        """向指定子图 idx 添加信号 field（供拖放和内部调用）。"""
        w = self._widget
        max_per_plot = LayoutController.LAYOUT_CONFIG.get(w._layout_mode, (0, 5))[1]
        if max_per_plot > 0 and len(w.subplot_fields.get(idx, [])) >= max_per_plot:
            QMessageBox.information(w, "提示", f"子图 {idx + 1} 已达到最大信号数 ({max_per_plot})。")
            return
        if idx not in w.subplot_fields:
            w.subplot_fields[idx] = []
        if field not in w.subplot_fields[idx]:
            w.subplot_fields[idx].append(field)
            label = w.ctx.get_label(field) if w.ctx else field
            w.log_message.emit(f"添加信号 [{label}] 到子图 {idx + 1}")
            w.subplot_fields_changed.emit()
            self.rebuild_plot()

    def _remove_from_subplot(self, idx: int, field: str) -> None:
        """右键菜单：从指定子图 idx 移除信号 field。"""
        w = self._widget
        if idx in w.subplot_fields and field in w.subplot_fields[idx]:
            w.subplot_fields[idx].remove(field)
            label = w.ctx.get_label(field) if w.ctx else field
            w.log_message.emit(f"从子图 {idx + 1} 移除信号 [{label}]")
            w.subplot_fields_changed.emit()
            self.rebuild_plot()

    def _clear_subplot(self, idx: int) -> None:
        """清空指定子图 idx 的所有信号。"""
        w = self._widget
        if idx in w.subplot_fields and w.subplot_fields[idx]:
            w.subplot_fields[idx] = []
            w.log_message.emit(f"已清空子图 {idx + 1}")
            w.subplot_fields_changed.emit()
            self.rebuild_plot()

    def clear_selected_subplot(self) -> None:
        """清空当前选中子图的所有信号（供外部按钮调用）。"""
        w = self._widget
        idx = w._selected_subplot_idx
        if idx is None:
            w.log_message.emit("请先点击选中一个子图")
            return
        self._clear_subplot(idx)

    # ── 数据设置 ──

    def set_data_context(self, ctx) -> None:
        """设置数据上下文并重绘。"""
        w = self._widget
        w.ctx = ctx
        self.rebuild_plot()
        # 记录初始时间范围（供 reset_zoom 恢复）
        w._crossing.save_initial_time_range()
        w._crossing.update_stats()
        # 重置平移状态，避免悬空引用
        w._pan.reset()
