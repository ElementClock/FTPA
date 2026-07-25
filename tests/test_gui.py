"""
测试 GUI 服务层 —— DataContext 及其方法。
"""

import os
import tempfile
from unittest.mock import MagicMock, patch, PropertyMock

import numpy as np
import pytest

from ftpa.gui.services import DataContext
from ftpa.gui._pan_ctrl import PanController


class TestDataContext:
    """测试 DataContext 核心数据模型。"""

    def test_resolve_path_absolute_existing(self, tmp_path):
        """绝对路径且存在时直接返回。"""
        f = tmp_path / "test.txt"
        f.write_text("hello")
        result = DataContext.resolve_path(str(f))
        assert os.path.samefile(result, str(f))

    def test_resolve_path_empty_returns_default(self):
        """空路径返回默认值。"""
        result = DataContext.resolve_path("", default="fallback")
        assert result == "fallback"

    def test_resolve_path_none_returns_default(self):
        """None 路径返回默认值。"""
        result = DataContext.resolve_path(None, default="fallback")
        assert result == "fallback"

    def test_data_context_initial_state(self):
        """DataContext 初始状态应为未加载。"""
        ctx = DataContext()
        assert not ctx.is_loaded
        assert ctx.data == {}
        assert ctx.get_row_count() == 0
        assert ctx.get_column_count() == 0
        assert ctx.get_field_names() == []

    def test_data_context_load_missing_file(self):
        """加载不存在的文件应返回失败。"""
        ctx = DataContext()
        ok, msg = ctx.load("/nonexistent/path.txt", "/nonexistent/labels.xlsx")
        assert not ok
        assert "不存在" in msg

    def test_get_field_labels_without_labelmap(self):
        """无 LabelMap 时字段标签应等于字段名本身。"""
        ctx = DataContext()
        ctx.data = {"TIME": np.array([]), "signal1": np.array([1.0, 2.0])}
        ctx._loaded = True
        labels = ctx.get_field_labels()
        assert "signal1" in labels
        assert labels["signal1"] == "signal1"

    def test_resolve_field_direct_match(self):
        """字段名直接匹配时 resolve_field 应返回原字段名。"""
        ctx = DataContext()
        ctx.data = {"TIME": np.array([]), "signal1": np.array([1.0])}
        result = ctx.resolve_field("signal1")
        assert result == "signal1"

    def test_resolve_field_not_found(self):
        """找不到字段时 resolve_field 应返回 None。"""
        ctx = DataContext()
        ctx.data = {"TIME": np.array([]), "signal1": np.array([1.0])}
        result = ctx.resolve_field("nonexistent")
        assert result is None

    def test_get_time_range_sec_unloaded(self):
        """未加载时时间范围应为 (0, 0)。"""
        ctx = DataContext()
        assert ctx.get_time_range_sec() == (0.0, 0.0)

    def test_generate_summary_unloaded(self):
        """未加载时 generate_summary 应返回空字典。"""
        ctx = DataContext()
        assert ctx.generate_summary() == {}

    def test_unload_clears_all_state(self):
        """unload() 应清除所有数据状态。"""
        ctx = DataContext()
        # 模拟加载状态
        ctx.data = {"TIME": np.array([0.0]), "sig": np.array([1.0])}
        ctx.time_vec = np.array([0.0])
        ctx.time_sec = np.array([0.0])
        ctx._loaded = True
        ctx.data_path = "/some/file.txt"
        ctx.excel_path = "/some/labels.xlsx"
        ctx._label_cache = {"sig": "信号"}

        # 卸载
        ctx.unload()

        assert not ctx.is_loaded
        assert ctx.data == {}
        assert ctx.time_vec is None
        assert ctx.time_sec is None
        assert ctx.data_path == ""
        assert ctx.excel_path == ""
        assert ctx._label_cache is None
        assert ctx.get_row_count() == 0
        assert ctx.get_column_count() == 0
        assert ctx.get_field_names() == []

    def test_unload_idempotent(self):
        """多次调用 unload() 不应出错。"""
        ctx = DataContext()
        ctx.unload()
        ctx.unload()
        assert not ctx.is_loaded

    def test_unload_then_load_cycle(self):
        """卸载后重新加载应正常工作。"""
        ctx = DataContext()
        # 模拟加载
        ctx.data = {"TIME": np.array([0.0]), "sig": np.array([1.0])}
        ctx._loaded = True
        # 卸载
        ctx.unload()
        assert not ctx.is_loaded
        # 尝试加载不存在的文件（验证状态可正常切换）
        ok, msg = ctx.load("/nonexistent/path.txt", "")
        assert not ok


class TestDataContextWithFile:
    """使用临时数据文件测试 DataContext 加载流程。"""

    @pytest.fixture
    def sample_data_file(self, tmp_path):
        """创建最简 TSV 数据文件。"""
        f = tmp_path / "test_data.txt"
        lines = ["TIME\tCol1\tCol2"]
        for i in range(120):
            lines.append(f"00:00:{i:02d}:000\t{i}.0\t{i * 2}.0")
        f.write_text("\n".join(lines), encoding="utf-8")
        return str(f)

    def test_load_valid_file(self, sample_data_file):
        """加载有效文件应成功。"""
        ctx = DataContext()
        ok, msg = ctx.load(sample_data_file, "/nonexistent/labels.xlsx")
        assert ok, f"加载失败: {msg}"
        assert ctx.is_loaded
        assert ctx.get_row_count() > 0
        assert ctx.get_column_count() > 1

    def test_get_field_names_after_load(self, sample_data_file):
        """加载后应能列出字段名（不含 TIME）。"""
        ctx = DataContext()
        ctx.load(sample_data_file, "/nonexistent/labels.xlsx")
        fields = ctx.get_field_names()
        assert "Col1" in fields or any("Col1" in f for f in fields)
        assert "TIME" not in fields

    def test_get_time_range_after_load(self, sample_data_file):
        """加载后时间范围应合理。"""
        ctx = DataContext()
        ctx.load(sample_data_file, "/nonexistent/labels.xlsx")
        t0, t1 = ctx.get_time_range_sec()
        assert t0 >= 0
        assert t1 > t0


# ============================================================================
# PanController 单元测试
# ============================================================================

def _make_widget_mock(n_axes=2, time_sec=None, xlim_list=None):
    """创建模拟 PlotCanvasWidget 的 mock 对象。

    Args:
        n_axes: 子图数量
        time_sec: DataContext 中的 time_sec 数组（None 表示无数据）
        xlim_list: 每个子图的初始 xlim，默认 (0, 100)
    """
    widget = MagicMock()
    axes = []
    for i in range(n_axes):
        ax = MagicMock()
        xlim = xlim_list[i] if xlim_list and i < len(xlim_list) else (0.0, 100.0)
        ax.get_xlim.return_value = xlim
        # 提供 transData 变换支持：像素→数据坐标的线性映射
        # 默认假设 xlim=(0,100) 映射到像素 x=[0,1000]
        x_left, x_right = xlim
        px_width = 1000.0  # 假设像素宽度
        scale = (x_right - x_left) / px_width if px_width > 0 else 1.0

        inv_transform = MagicMock()
        inv_transform.transform = lambda pt, _xl=x_left, _s=scale: (
            np.array([_xl + pt[0] * _s, _xl + pt[1] * _s])
        )
        trans_data = MagicMock()
        trans_data.inverted.return_value = inv_transform
        ax.transData = trans_data

        # 提供 get_window_extent 支持：返回 axes 像素边界框
        # PanController._compute_x_scale 使用此方法计算 Y 轴无关的缩放比
        bbox = MagicMock()
        bbox.width = px_width
        ax.get_window_extent.return_value = bbox

        axes.append(ax)
    widget.axes = axes

    # DataContext mock（默认提供 time_sec，除非显式传 None）
    if time_sec is not None:
        ctx = MagicMock()
        ctx.time_sec = time_sec
    else:
        ctx = MagicMock()
        ctx.time_sec = np.array([0.0, 100.0])
    widget.ctx = ctx

    # canvas mock
    canvas = MagicMock()
    widget.canvas = canvas

    return widget


def _make_event(button=1, x=100, y=200, xdata=50.0, ydata=25.0, inaxes=None):
    """创建模拟 matplotlib 事件的对象。"""
    evt = MagicMock()
    evt.button = button
    evt.x = x
    evt.y = y
    evt.xdata = xdata
    evt.ydata = ydata
    evt.inaxes = inaxes
    return evt


class TestPanControllerOnPress:
    """测试 PanController.on_press 方法。"""

    def test_left_button_in_axes_records_state(self):
        """左键在 axes 区域内按下应记录事件和 xlim。"""
        widget = _make_widget_mock(n_axes=2, xlim_list=[(0.0, 100.0), (0.0, 100.0)])
        ax0 = widget.axes[0]
        pan = PanController(widget)

        event = _make_event(button=1, x=100, y=200, xdata=50.0, inaxes=ax0)
        pan.on_press(event)

        assert pan._press_event is event
        assert pan._is_panning is False
        assert pan._was_panning is False
        assert pan._press_xlim is not None
        assert len(pan._press_xlim) == 2
        assert pan._press_xlim[0] == (0.0, 100.0)
        assert pan._press_xlim[1] == (0.0, 100.0)

    def test_right_button_ignored(self):
        """右键按下应被忽略（不记录状态）。"""
        widget = _make_widget_mock()
        pan = PanController(widget)

        event = _make_event(button=3, x=100, y=200, xdata=50.0, inaxes=widget.axes[0])
        pan.on_press(event)

        assert pan._press_event is None

    def test_outside_axes_ignored(self):
        """鼠标在 axes 区域外按下应被忽略。"""
        widget = _make_widget_mock()
        pan = PanController(widget)

        event = _make_event(button=1, x=100, y=200, xdata=None, inaxes=None)
        pan.on_press(event)

        assert pan._press_event is None

    def test_press_clears_was_panning(self):
        """按下时应清除上次的 was_panning 标记。"""
        widget = _make_widget_mock()
        pan = PanController(widget)
        pan._was_panning = True

        event = _make_event(button=1, inaxes=widget.axes[0])
        pan.on_press(event)

        assert pan._was_panning is False

    def test_press_resets_is_panning(self):
        """按下时应重置 is_panning 为 False。"""
        widget = _make_widget_mock()
        pan = PanController(widget)
        pan._is_panning = True

        event = _make_event(button=1, inaxes=widget.axes[0])
        pan.on_press(event)

        assert pan._is_panning is False


class TestPanControllerOnMotion:
    """测试 PanController.on_motion 方法。"""

    def test_no_press_event_returns_early(self):
        """未按下时移动不应触发任何操作。"""
        widget = _make_widget_mock()
        pan = PanController(widget)
        assert pan._press_event is None

        event = _make_event(x=200, y=200, xdata=100.0)
        pan.on_motion(event)
        assert pan._is_panning is False

    def test_below_threshold_no_panning(self):
        """拖拽距离小于阈值（5px）不应进入平移模式。"""
        widget = _make_widget_mock()
        pan = PanController(widget)

        press_event = _make_event(button=1, x=100, y=200, xdata=50.0, inaxes=widget.axes[0])
        pan.on_press(press_event)

        motion_event = _make_event(x=103, y=202, xdata=51.0, inaxes=widget.axes[0])
        pan.on_motion(motion_event)

        assert pan._is_panning is False

    def test_above_threshold_enters_panning(self):
        """拖拽距离超过阈值应进入平移模式。"""
        widget = _make_widget_mock(n_axes=2, time_sec=np.array([0.0, 50.0, 100.0]))
        pan = PanController(widget)

        press_event = _make_event(button=1, x=100, y=200, xdata=50.0, inaxes=widget.axes[0])
        pan.on_press(press_event)

        motion_event = _make_event(x=120, y=200, xdata=60.0, inaxes=widget.axes[0])
        pan.on_motion(motion_event)

        assert pan._is_panning is True

    def test_threshold_exact_5px_y_direction(self):
        """Y 方向恰好 5px 应进入平移（>= 阈值）。"""
        widget = _make_widget_mock(n_axes=2, time_sec=np.array([0.0, 50.0, 100.0]))
        pan = PanController(widget)

        press_event = _make_event(button=1, x=100, y=200, xdata=50.0, inaxes=widget.axes[0])
        pan.on_press(press_event)

        # Y 方向移动恰好 5px
        motion_event = _make_event(x=100, y=205, xdata=50.0, inaxes=widget.axes[0])
        pan.on_motion(motion_event)

        assert pan._is_panning is True

    def test_threshold_4px_no_panning(self):
        """X 方向 4px 不应进入平移（< 阈值）。"""
        widget = _make_widget_mock()
        pan = PanController(widget)

        press_event = _make_event(button=1, x=100, y=200, xdata=50.0, inaxes=widget.axes[0])
        pan.on_press(press_event)

        motion_event = _make_event(x=104, y=200, xdata=51.0, inaxes=widget.axes[0])
        pan.on_motion(motion_event)

        assert pan._is_panning is False

    def test_motion_x_none_y_none_returns(self):
        """event.x 和 event.y 都为 None 时应直接返回。"""
        widget = _make_widget_mock()
        pan = PanController(widget)

        press_event = _make_event(button=1, x=100, y=200, xdata=50.0, inaxes=widget.axes[0])
        pan.on_press(press_event)

        motion_event = _make_event(x=None, y=None, xdata=None, ydata=None)
        pan.on_motion(motion_event)

        assert pan._is_panning is False

    def test_panning_applies_horizontal_offset(self):
        """平移应水平偏移所有子图的 xlim（Y 轴无关公式）。

        新公式：dx_data = dx_pixel × x_scale
        其中 dx_pixel = press_x - curr_x, x_scale = (xlim[1] - xlim[0]) / axes_pixel_width
        默认 xlim=(0,100), px_width=1000 → x_scale = 0.1
        向右拖 20px (press=100, curr=120) → dx_pixel = -20 → dx_data = -2.0
        新 xlim = (0-2, 100-2) = (-2, 98)（无边界约束，自由平移）
        """
        widget = _make_widget_mock(n_axes=2, time_sec=np.array([0.0, 50.0, 200.0]))
        pan = PanController(widget)

        press_event = _make_event(button=1, x=100, y=200, xdata=50.0, inaxes=widget.axes[0])
        pan.on_press(press_event)

        # 向右拖拽 20px（视图向左移动）
        motion_event = _make_event(x=120, y=200, xdata=60.0, inaxes=widget.axes[0])
        pan.on_motion(motion_event)

        # dx_pixel = 100 - 120 = -20, dx_data = -20 × 0.1 = -2.0
        # 新 xlim = (-2.0, 98.0)（自由平移，无约束）
        for ax in widget.axes:
            ax.set_xlim.assert_called()
            call_args = ax.set_xlim.call_args[0]
            assert call_args[0] == pytest.approx(-2.0)
            assert call_args[1] == pytest.approx(98.0)

    def test_motion_after_press_inaxes_none_uses_pixel_estimate(self):
        """press_event.inaxes 为 None 时 on_motion 应直接返回。"""
        widget = _make_widget_mock()
        pan = PanController(widget)

        # 手动设置 _press_event 但 inaxes 为 None
        press_event = _make_event(button=1, x=100, y=200, xdata=50.0, inaxes=None)
        pan._press_event = press_event
        pan._is_panning = True

        motion_event = _make_event(x=120, y=200, xdata=60.0, inaxes=widget.axes[0])
        pan.on_motion(motion_event)

        # inaxes 为 None 应直接返回，不调用 set_xlim
        for ax in widget.axes:
            ax.set_xlim.assert_not_called()


class TestPanControllerOnRelease:
    """测试 PanController.on_release 方法。"""

    def test_release_after_panning_sets_was_panning(self):
        """平移后释放应设置 was_panning=True。"""
        widget = _make_widget_mock(n_axes=2, time_sec=np.array([0.0, 50.0, 100.0]))
        pan = PanController(widget)

        press_event = _make_event(button=1, x=100, y=200, xdata=50.0, inaxes=widget.axes[0])
        pan.on_press(press_event)

        # 超过阈值，进入平移
        motion_event = _make_event(x=120, y=200, xdata=60.0, inaxes=widget.axes[0])
        pan.on_motion(motion_event)
        assert pan._is_panning is True

        # 释放
        release_event = _make_event(button=1, x=120, y=200, xdata=60.0)
        pan.on_release(release_event)

        assert pan._was_panning is True
        assert pan._is_panning is False
        assert pan._press_event is None
        assert pan._press_xlim is None

    def test_release_without_panning_not_was_panning(self):
        """未平移即释放时 was_panning 应为 False。"""
        widget = _make_widget_mock()
        pan = PanController(widget)

        press_event = _make_event(button=1, x=100, y=200, xdata=50.0, inaxes=widget.axes[0])
        pan.on_press(press_event)

        # 未超过阈值，未进入平移
        release_event = _make_event(button=1, x=101, y=201, xdata=50.5)
        pan.on_release(release_event)

        assert pan._was_panning is False
        assert pan._is_panning is False

    def test_release_resets_all_state(self):
        """释放后所有内部状态应重置。"""
        widget = _make_widget_mock(n_axes=2, time_sec=np.array([0.0, 50.0, 100.0]))
        pan = PanController(widget)

        press_event = _make_event(button=1, x=100, y=200, xdata=50.0, inaxes=widget.axes[0])
        pan.on_press(press_event)

        motion_event = _make_event(x=120, y=200, xdata=60.0, inaxes=widget.axes[0])
        pan.on_motion(motion_event)

        release_event = _make_event(button=1, x=120, y=200)
        pan.on_release(release_event)

        assert pan._press_event is None
        assert pan._is_panning is False
        assert pan._press_xlim is None


class TestPanControllerWasPanning:
    """测试 PanController.was_panning 查询方法。"""

    def test_initially_false(self):
        """初始状态 was_panning 应为 False。"""
        widget = _make_widget_mock()
        pan = PanController(widget)
        assert pan.was_panning() is False

    def test_after_panning_release_true(self):
        """平移释放后 was_panning 应为 True。"""
        widget = _make_widget_mock(n_axes=2, time_sec=np.array([0.0, 50.0, 100.0]))
        pan = PanController(widget)

        press_event = _make_event(button=1, x=100, y=200, xdata=50.0, inaxes=widget.axes[0])
        pan.on_press(press_event)

        motion_event = _make_event(x=120, y=200, xdata=60.0, inaxes=widget.axes[0])
        pan.on_motion(motion_event)

        release_event = _make_event(button=1)
        pan.on_release(release_event)

        assert pan.was_panning() is True

    def test_cleared_by_next_press(self):
        """下次 on_press 应清除 was_panning 标记。"""
        widget = _make_widget_mock(n_axes=2, time_sec=np.array([0.0, 50.0, 100.0]))
        pan = PanController(widget)

        # 先完成一次平移
        press_event = _make_event(button=1, x=100, y=200, xdata=50.0, inaxes=widget.axes[0])
        pan.on_press(press_event)
        motion_event = _make_event(x=120, y=200, xdata=60.0, inaxes=widget.axes[0])
        pan.on_motion(motion_event)
        release_event = _make_event(button=1)
        pan.on_release(release_event)
        assert pan.was_panning() is True

        # 下次按下清除标记
        press_event2 = _make_event(button=1, x=100, y=200, xdata=50.0, inaxes=widget.axes[0])
        pan.on_press(press_event2)
        assert pan.was_panning() is False


class TestPanControllerIsPanning:
    """测试 PanController.is_panning 查询方法。"""

    def test_initially_false(self):
        """初始状态 is_panning 应为 False。"""
        widget = _make_widget_mock()
        pan = PanController(widget)
        assert pan.is_panning() is False

    def test_true_during_panning(self):
        """平移拖拽中 is_panning 应为 True。"""
        widget = _make_widget_mock(n_axes=2, time_sec=np.array([0.0, 50.0, 100.0]))
        pan = PanController(widget)

        press_event = _make_event(button=1, x=100, y=200, xdata=50.0, inaxes=widget.axes[0])
        pan.on_press(press_event)

        motion_event = _make_event(x=120, y=200, xdata=60.0, inaxes=widget.axes[0])
        pan.on_motion(motion_event)

        assert pan.is_panning() is True

    def test_false_after_release(self):
        """释放后 is_panning 应为 False。"""
        widget = _make_widget_mock(n_axes=2, time_sec=np.array([0.0, 50.0, 100.0]))
        pan = PanController(widget)

        press_event = _make_event(button=1, x=100, y=200, xdata=50.0, inaxes=widget.axes[0])
        pan.on_press(press_event)
        motion_event = _make_event(x=120, y=200, xdata=60.0, inaxes=widget.axes[0])
        pan.on_motion(motion_event)

        release_event = _make_event(button=1)
        pan.on_release(release_event)

        assert pan.is_panning() is False


class TestPanControllerApplyPan:
    """测试 PanController._apply_pan 方法。"""

    def test_shifts_xlim_correctly(self):
        """平移应正确偏移 xlim。"""
        widget = _make_widget_mock(
            n_axes=2,
            time_sec=np.array([0.0, 50.0, 200.0]),
            xlim_list=[(10.0, 60.0), (10.0, 60.0)],
        )
        pan = PanController(widget)
        pan._press_xlim = [(10.0, 60.0), (10.0, 60.0)]

        # 向右平移 5 个数据单位（dx_data = 5）
        pan._apply_pan(5.0)

        # 每个子图应调用 set_xlim(15.0, 65.0)
        for ax in widget.axes:
            ax.set_xlim.assert_called_once_with(15.0, 65.0)

    def test_boundary_constraint_left(self):
        """自由平移模式：向左平移不受约束。"""
        widget = _make_widget_mock(
            n_axes=1,
            time_sec=np.array([0.0, 50.0, 100.0]),
            xlim_list=[(5.0, 55.0)],
        )
        pan = PanController(widget)
        pan._press_xlim = [(5.0, 55.0)]

        # 自由平移：向左平移 10（无约束）
        pan._apply_pan(-10.0)
        widget.axes[0].set_xlim.assert_called_once_with(-5.0, 45.0)

    def test_boundary_constraint_left_hard_stop(self):
        """自由平移模式：向左平移不受约束。"""
        widget = _make_widget_mock(
            n_axes=1,
            time_sec=np.array([0.0, 50.0, 100.0]),
            xlim_list=[(5.0, 55.0)],
        )
        pan = PanController(widget)
        pan._press_xlim = [(5.0, 55.0)]

        # 自由平移：向左平移 10，new_start = -5（无约束）
        pan._apply_pan(-10.0)
        widget.axes[0].set_xlim.assert_called_once_with(-5.0, 45.0)

    def test_boundary_constraint_right(self):
        """自由平移模式：向右平移不受约束。"""
        widget = _make_widget_mock(
            n_axes=1,
            time_sec=np.array([0.0, 50.0, 100.0]),
            xlim_list=[(45.0, 95.0)],
        )
        pan = PanController(widget)
        pan._press_xlim = [(45.0, 95.0)]

        # 自由平移：向右平移 10，new_end = 105（无约束）
        pan._apply_pan(10.0)
        widget.axes[0].set_xlim.assert_called_once_with(55.0, 105.0)

    def test_boundary_constraint_right_hard_stop(self):
        """自由平移模式：右边界无硬停。"""
        widget = _make_widget_mock(
            n_axes=1,
            time_sec=np.array([0.0, 50.0, 100.0]),
            xlim_list=[(45.0, 95.0)],
        )
        pan = PanController(widget)
        pan._press_xlim = [(45.0, 95.0)]

        # 自由平移：向右平移 10（无约束）
        pan._apply_pan(10.0)
        widget.axes[0].set_xlim.assert_called_once_with(55.0, 105.0)

    def test_no_ctx_no_boundary_constraint(self):
        """无 DataContext 时不应用边界约束，允许自由平移。"""
        widget = _make_widget_mock(n_axes=1, xlim_list=[(0.0, 100.0)])
        # 显式设置 ctx = None
        widget.ctx = None
        pan = PanController(widget)
        pan._press_xlim = [(0.0, 100.0)]

        # 向左平移 50 个数据单位（无边界约束）
        pan._apply_pan(-50.0)

        widget.axes[0].set_xlim.assert_called_once_with(-50.0, 50.0)

    def test_no_time_sec_no_boundary_constraint(self):
        """DataContext 存在但 time_sec 为 None 时不应用边界约束。"""
        widget = _make_widget_mock(n_axes=1, xlim_list=[(0.0, 100.0)])
        # 有 ctx 但 time_sec 为 None
        ctx = MagicMock()
        ctx.time_sec = None
        widget.ctx = ctx
        pan = PanController(widget)
        pan._press_xlim = [(0.0, 100.0)]

        pan._apply_pan(-50.0)
        widget.axes[0].set_xlim.assert_called_once_with(-50.0, 50.0)

    def test_empty_time_sec_no_boundary_constraint(self):
        """time_sec 为空数组时不应用边界约束。"""
        widget = _make_widget_mock(n_axes=1, time_sec=np.array([]), xlim_list=[(0.0, 100.0)])
        pan = PanController(widget)
        pan._press_xlim = [(0.0, 100.0)]

        pan._apply_pan(-50.0)
        widget.axes[0].set_xlim.assert_called_once_with(-50.0, 50.0)

    def test_press_xlim_none_returns_early(self):
        """_press_xlim 为 None 时 _apply_pan 不应执行任何操作。"""
        widget = _make_widget_mock()
        pan = PanController(widget)
        pan._press_xlim = None

        pan._apply_pan(10.0)

        for ax in widget.axes:
            ax.set_xlim.assert_not_called()

    def test_no_draw_idle_in_apply_pan(self):
        """_apply_pan 不再直接调用 draw_idle（由 on_motion 统一调用）。"""
        widget = _make_widget_mock(
            n_axes=1,
            time_sec=np.array([0.0, 100.0]),
            xlim_list=[(10.0, 60.0)],
        )
        pan = PanController(widget)
        pan._press_xlim = [(10.0, 60.0)]

        pan._apply_pan(5.0)

        # _apply_pan 不调用 draw_idle（由 on_motion 中的 _adjust_y_limits + draw_idle 统一处理）
        widget.canvas.draw_idle.assert_not_called()

    def test_mismatched_axes_count_only_applies_available(self):
        """axes 数量多于 _press_xlim 条目时只处理有缓存的子图。"""
        widget = _make_widget_mock(
            n_axes=3,
            time_sec=np.array([0.0, 50.0, 200.0]),
            xlim_list=[(10.0, 60.0), (20.0, 70.0), (30.0, 80.0)],
        )
        pan = PanController(widget)
        # 只有前两个子图有缓存
        pan._press_xlim = [(10.0, 60.0), (20.0, 70.0)]

        pan._apply_pan(5.0)

        widget.axes[0].set_xlim.assert_called_once_with(15.0, 65.0)
        widget.axes[1].set_xlim.assert_called_once_with(25.0, 75.0)
        # 第三个子图没有 xlim 缓存，不应设置
        widget.axes[2].set_xlim.assert_not_called()

    def test_span_preserved_during_boundary_constraint(self):
        """自由平移模式：平移保持视口宽度（span）不变。"""
        widget = _make_widget_mock(
            n_axes=1,
            time_sec=np.array([0.0, 50.0, 100.0]),
            xlim_list=[(40.0, 80.0)],  # span = 40
        )
        pan = PanController(widget)
        pan._press_xlim = [(40.0, 80.0)]

        # 自由平移：向右平移 30 → new_start=70, new_end=110（无约束）
        pan._apply_pan(30.0)
        widget.axes[0].set_xlim.assert_called_once_with(70.0, 110.0)

    def test_span_preserved_hard_stop(self):
        """自由平移模式：无硬停，保持 span 不变。"""
        widget = _make_widget_mock(
            n_axes=1,
            time_sec=np.array([0.0, 50.0, 100.0]),
            xlim_list=[(40.0, 80.0)],  # span = 40
        )
        pan = PanController(widget)
        pan._press_xlim = [(40.0, 80.0)]

        # 自由平移：向右平移 30（无约束）
        pan._apply_pan(30.0)
        widget.axes[0].set_xlim.assert_called_once_with(70.0, 110.0)

    def test_nan_data_time_sec_no_boundary_constraint(self):
        """自由平移模式：time_sec 包含 NaN 时仍可自由平移。"""
        widget = _make_widget_mock(
            n_axes=1,
            time_sec=np.array([0.0, np.nan, 100.0]),
            xlim_list=[(10.0, 60.0)],
        )
        pan = PanController(widget)
        pan._press_xlim = [(10.0, 60.0)]

        # 自由平移：向左平移 20（无约束）
        pan._apply_pan(-20.0)
        widget.axes[0].set_xlim.assert_called_once_with(-10.0, 40.0)


class TestPanControllerEdgeCases:
    """测试 PanController 边界情况。"""

    def test_full_press_motion_release_cycle(self):
        """完整的按下→平移→释放周期。"""
        widget = _make_widget_mock(
            n_axes=2,
            time_sec=np.array([0.0, 50.0, 200.0]),
            xlim_list=[(0.0, 100.0), (0.0, 100.0)],
        )
        pan = PanController(widget)

        # 按下
        press = _make_event(button=1, x=100, y=200, xdata=50.0, inaxes=widget.axes[0])
        pan.on_press(press)
        assert pan._press_event is press
        assert pan._is_panning is False

        # 移动（超过阈值）
        motion = _make_event(x=130, y=200, xdata=65.0, inaxes=widget.axes[0])
        pan.on_motion(motion)
        assert pan._is_panning is True

        # 继续移动
        motion2 = _make_event(x=140, y=200, xdata=70.0, inaxes=widget.axes[0])
        pan.on_motion(motion2)
        assert pan._is_panning is True

        # 释放
        release = _make_event(button=1, x=140, y=200, xdata=70.0)
        pan.on_release(release)
        assert pan._was_panning is True
        assert pan._is_panning is False
        assert pan._press_event is None

    def test_short_click_then_release(self):
        """短点击（未超过阈值）→ 释放 → was_panning=False。"""
        widget = _make_widget_mock(n_axes=1, xlim_list=[(0.0, 100.0)])
        pan = PanController(widget)

        press = _make_event(button=1, x=100, y=200, xdata=50.0, inaxes=widget.axes[0])
        pan.on_press(press)

        # 微小移动（2px，不超过阈值）
        motion = _make_event(x=102, y=201, xdata=50.5, inaxes=widget.axes[0])
        pan.on_motion(motion)
        assert pan._is_panning is False

        release = _make_event(button=1, x=102, y=201)
        pan.on_release(release)
        assert pan._was_panning is False

    def test_multiple_press_cycles(self):
        """多次按下→平移→释放周期状态正确切换。"""
        widget = _make_widget_mock(
            n_axes=1,
            time_sec=np.array([0.0, 50.0, 200.0]),
            xlim_list=[(0.0, 100.0)],
        )
        pan = PanController(widget)

        # 第一次：平移
        press1 = _make_event(button=1, x=100, y=200, xdata=50.0, inaxes=widget.axes[0])
        pan.on_press(press1)
        motion1 = _make_event(x=120, y=200, xdata=60.0, inaxes=widget.axes[0])
        pan.on_motion(motion1)
        release1 = _make_event(button=1)
        pan.on_release(release1)
        assert pan.was_panning() is True

        # 第二次：点击（不平移）
        press2 = _make_event(button=1, x=100, y=200, xdata=50.0, inaxes=widget.axes[0])
        pan.on_press(press2)
        assert pan.was_panning() is False  # 被清除
        release2 = _make_event(button=1)
        pan.on_release(release2)
        assert pan.was_panning() is False

    def test_xdata_none_with_pixel_available(self):
        """xdata 为 None 但 x 可用时，仍应进入平移模式（像素差估算路径）。"""
        widget = _make_widget_mock(n_axes=1, time_sec=np.array([0.0, 50.0, 200.0]))
        pan = PanController(widget)

        press = _make_event(button=1, x=100, y=200, xdata=50.0, inaxes=widget.axes[0])
        pan.on_press(press)

        # 鼠标移出 axes 区域，xdata=None 但 x 有值
        motion = _make_event(x=130, y=200, xdata=None, inaxes=None)
        # 需要设置 press_ax 的 transData 逆变换
        widget.axes[0].transData.inverted.return_value.transform.return_value = [0.5, 0]
        pan.on_motion(motion)

        # 因为 xdata=None 但 x 有值，应进入 panning 并尝试像素估算
        assert pan._is_panning is True


# ============================================================================
# Y 轴自适应测试
# ============================================================================

class TestCrossingAnalyzerAdjustYLimits:
    """测试 CrossingAnalyzer._adjust_y_limits 方法。"""

    def _make_crossing_analyzer(self, n_axes=2, fields_per_subplot=None):
        """创建 CrossingAnalyzer 实例（mock widget）。"""
        from ftpa.gui._crossing_analyzer import CrossingAnalyzer

        widget = MagicMock()
        axes = []
        fields = {}
        for i in range(n_axes):
            ax = MagicMock()
            ax.get_xlim.return_value = (0.0, 100.0)
            axes.append(ax)
            fields[i] = fields_per_subplot.get(i, []) if fields_per_subplot else []

        widget.axes = axes
        widget.subplot_fields = fields

        # 创建 DataContext
        ctx = MagicMock()
        ctx.time_sec = np.linspace(0, 100, 101)
        widget.ctx = ctx

        # 为每个字段的 data 创建模拟数据
        all_fields = []
        for flist in fields.values():
            all_fields.extend(flist)
        data_map = {}
        for f in all_fields:
            data_map[f] = np.sin(np.linspace(0, 2 * np.pi, 101)) * 10 + 50
        ctx.data = data_map

        canvas = MagicMock()
        widget.canvas = canvas

        analyzer = CrossingAnalyzer(widget)
        return analyzer, widget

    def test_adjust_with_data(self):
        """有数据时应根据可见范围计算 Y 轴边界（含 5% 边距）。"""
        fields = {0: ["sig1"], 1: ["sig2"]}
        analyzer, widget = self._make_crossing_analyzer(n_axes=2, fields_per_subplot=fields)

        analyzer._adjust_y_limits()

        # 每个 ax 都应调用 set_ylim
        for ax in widget.axes:
            ax.set_ylim.assert_called_once()

    def test_five_percent_margin(self):
        """Y 轴边距应为数据范围的 5%。"""
        # sig1 在 0~100 范围内: sin * 10 + 50 → 范围约 [40, 60]
        fields = {0: ["sig1"]}
        analyzer, widget = self._make_crossing_analyzer(n_axes=1, fields_per_subplot=fields)

        # 手动设置数据确保精确范围
        sig_data = np.array([0.0, 10.0, 20.0])  # min=0, max=20
        widget.ctx.data = {"sig1": sig_data}
        # time_sec: [0, 50, 100]，xlim=(0, 100) 涵盖全部
        widget.ctx.time_sec = np.array([0.0, 50.0, 100.0])
        widget.axes[0].get_xlim.return_value = (0.0, 100.0)

        analyzer._adjust_y_limits()

        # margin = 0.05 * (20 - 0) = 1.0
        # y_min = 0 - 1.0 = -1.0, y_max = 20 + 1.0 = 21.0
        widget.axes[0].set_ylim.assert_called_once_with(-1.0, 21.0)

    def test_constant_data_expands_by_one(self):
        """Y 值恒定时（min == max）应各扩展 1.0。"""
        fields = {0: ["sig1"]}
        analyzer, widget = self._make_crossing_analyzer(n_axes=1, fields_per_subplot=fields)

        sig_data = np.array([5.0, 5.0, 5.0])  # min=max=5
        widget.ctx.data = {"sig1": sig_data}
        widget.ctx.time_sec = np.array([0.0, 50.0, 100.0])
        widget.axes[0].get_xlim.return_value = (0.0, 100.0)

        analyzer._adjust_y_limits()

        widget.axes[0].set_ylim.assert_called_once_with(4.0, 6.0)

    def test_empty_subplot_skipped(self):
        """无信号的子图不应调整 Y 轴。"""
        fields = {0: [], 1: ["sig2"]}
        analyzer, widget = self._make_crossing_analyzer(n_axes=2, fields_per_subplot=fields)

        analyzer._adjust_y_limits()

        # 第一个子图无信号，不应调用 set_ylim
        widget.axes[0].set_ylim.assert_not_called()
        # 第二个子图有信号，应调用
        widget.axes[1].set_ylim.assert_called_once()

    def test_nan_data_excluded(self):
        """NaN 数据应被排除在 Y 轴计算之外。"""
        fields = {0: ["sig1"]}
        analyzer, widget = self._make_crossing_analyzer(n_axes=1, fields_per_subplot=fields)

        sig_data = np.array([np.nan, 10.0, 20.0, np.nan])
        widget.ctx.data = {"sig1": sig_data}
        widget.ctx.time_sec = np.array([0.0, 33.0, 66.0, 100.0])
        widget.axes[0].get_xlim.return_value = (0.0, 100.0)

        analyzer._adjust_y_limits()

        # 排除 NaN 后 min=10, max=20, margin=0.5
        widget.axes[0].set_ylim.assert_called_once_with(9.5, 20.5)

    def test_no_ctx_returns_early(self):
        """无 DataContext 时不应执行任何操作。"""
        from ftpa.gui._crossing_analyzer import CrossingAnalyzer

        widget = MagicMock()
        widget.ctx = None
        widget.axes = [MagicMock()]
        analyzer = CrossingAnalyzer(widget)

        analyzer._adjust_y_limits()

        widget.axes[0].set_ylim.assert_not_called()

    def test_no_axes_returns_early(self):
        """无子图时不应执行任何操作。"""
        from ftpa.gui._crossing_analyzer import CrossingAnalyzer

        widget = MagicMock()
        widget.axes = []
        ctx = MagicMock()
        ctx.time_sec = np.array([0.0, 100.0])
        widget.ctx = ctx
        analyzer = CrossingAnalyzer(widget)

        analyzer._adjust_y_limits()  # 不应抛出异常

    def test_data_field_missing_skipped(self):
        """数据字段在 ctx.data 中不存在时应跳过。"""
        fields = {0: ["nonexistent"]}
        analyzer, widget = self._make_crossing_analyzer(n_axes=1, fields_per_subplot=fields)

        # nonexistent 不在 data 中
        widget.ctx.data = {}

        analyzer._adjust_y_limits()

        widget.axes[0].set_ylim.assert_not_called()

    def test_multiple_fields_in_subplot(self):
        """同一子图有多个信号时，Y 轴应涵盖所有信号的极值。"""
        fields = {0: ["sig1", "sig2"]}
        analyzer, widget = self._make_crossing_analyzer(n_axes=1, fields_per_subplot=fields)

        widget.ctx.data = {
            "sig1": np.array([0.0, 10.0, 20.0]),  # min=0, max=20
            "sig2": np.array([-5.0, 5.0, 30.0]),   # min=-5, max=30
        }
        widget.ctx.time_sec = np.array([0.0, 50.0, 100.0])
        widget.axes[0].get_xlim.return_value = (0.0, 100.0)

        analyzer._adjust_y_limits()

        # 合并 min=-5, max=30, margin=0.05*35=1.75
        widget.axes[0].set_ylim.assert_called_once_with(-6.75, 31.75)


# ============================================================================
# Y 轴自适应 — 缩放防抖回调测试
# ============================================================================

class TestCrossingAnalyzerZoomTimeout:
    """测试 CrossingAnalyzer._zoom_timeout_cb 回调。"""

    def test_zoom_timeout_calls_adjust_and_draw(self):
        """_zoom_timeout_cb 应依次调用 _adjust_y_limits、draw_idle、update_stats。"""
        from ftpa.gui._crossing_analyzer import CrossingAnalyzer

        widget = MagicMock()
        widget.axes = []
        widget.ctx = None
        widget.canvas = MagicMock()

        analyzer = CrossingAnalyzer(widget)

        # 设置快照以通过防抖校验（axes 数量匹配）
        analyzer._zoom_snapshot_axes_count = 0

        # 模拟方法
        analyzer._adjust_y_limits = MagicMock()
        analyzer.update_stats = MagicMock()

        analyzer._zoom_timeout_cb()

        analyzer._adjust_y_limits.assert_called_once()
        widget.canvas.draw_idle.assert_called_once()
        analyzer.update_stats.assert_called_once()


class TestCrossingAnalyzerOnCanvasZoom:
    """测试 CrossingAnalyzer.on_canvas_zoom 防抖机制。"""

    def test_on_canvas_zoom_starts_timer(self):
        """on_canvas_zoom 应启动防抖定时器。"""
        from ftpa.gui._crossing_analyzer import CrossingAnalyzer
        from PySide6.QtCore import QTimer

        widget = MagicMock()
        widget.axes = []
        widget.ctx = None
        widget.canvas = MagicMock()

        analyzer = CrossingAnalyzer(widget)

        # 模拟 QTimer
        mock_timer = MagicMock(spec=QTimer)
        analyzer._zoom_timer = mock_timer

        analyzer.on_canvas_zoom()

        mock_timer.start.assert_called_once_with(200)

    def test_on_canvas_zoom_creates_timer_if_none(self):
        """首次调用时应创建 QTimer 实例。"""
        from ftpa.gui._crossing_analyzer import CrossingAnalyzer

        widget = MagicMock()
        widget.axes = []
        widget.ctx = None
        widget.canvas = MagicMock()

        analyzer = CrossingAnalyzer(widget)
        assert analyzer._zoom_timer is None

        # 需要 mock QTimer 以避免 Qt 依赖
        with patch("ftpa.gui._crossing_analyzer.QTimer") as MockQTimer:
            mock_timer_instance = MagicMock()
            MockQTimer.return_value = mock_timer_instance

            analyzer.on_canvas_zoom()

            MockQTimer.assert_called_once()
            mock_timer_instance.setSingleShot.assert_called_once_with(True)
            mock_timer_instance.timeout.connect.assert_called_once()
            mock_timer_instance.start.assert_called_once_with(200)


# ============================================================================
# 集成：点击 vs 拖拽区分
# ============================================================================

class TestClickVsDragDistinction:
    """测试点击与拖拽的区分逻辑（PanController + LayoutController 协作）。"""

    def test_short_click_triggers_subplot_selection(self):
        """短点击（未超过阈值）→ was_panning=False → 应触发子图选择。"""
        widget = _make_widget_mock(n_axes=1, xlim_list=[(0.0, 100.0)])

        # 创建 PanController
        pan = PanController(widget)

        # 创建 LayoutController mock
        layout_mock = MagicMock()

        # 模拟短点击
        press = _make_event(button=1, x=100, y=200, xdata=50.0, inaxes=widget.axes[0])
        pan.on_press(press)

        release = _make_event(button=1, x=102, y=202, xdata=50.5, inaxes=widget.axes[0])
        pan.on_release(release)

        # was_panning 应为 False
        assert pan.was_panning() is False

        # 模拟 panel_plot 的逻辑：非平移 → 调用 LayoutController
        if not pan.was_panning():
            layout_mock.on_canvas_click(release)

        layout_mock.on_canvas_click.assert_called_once_with(release)

    def test_long_drag_skips_subplot_selection(self):
        """长拖拽（超过阈值）→ was_panning=True → 不应触发子图选择。"""
        widget = _make_widget_mock(
            n_axes=1,
            time_sec=np.array([0.0, 50.0, 200.0]),
            xlim_list=[(0.0, 100.0)],
        )

        pan = PanController(widget)
        layout_mock = MagicMock()

        # 模拟长拖拽
        press = _make_event(button=1, x=100, y=200, xdata=50.0, inaxes=widget.axes[0])
        pan.on_press(press)

        motion = _make_event(x=130, y=200, xdata=65.0, inaxes=widget.axes[0])
        pan.on_motion(motion)

        release = _make_event(button=1, x=130, y=200, xdata=65.0)
        pan.on_release(release)

        # was_panning 采用"读取即清除"模式，只调用一次
        # 模拟 panel_plot 的逻辑：was_panning=True → 不调用 LayoutController
        was_pan = pan.was_panning()
        assert was_pan is True
        if not was_pan:
            layout_mock.on_canvas_click(release)

        layout_mock.on_canvas_click.assert_not_called()

    def test_right_click_ignored_by_pan(self):
        """右键不应触发 PanController 的平移逻辑。"""
        widget = _make_widget_mock()
        pan = PanController(widget)

        press = _make_event(button=3, x=100, y=200, xdata=50.0, inaxes=widget.axes[0])
        pan.on_press(press)

        # 右键按下应被忽略
        assert pan._press_event is None
        assert pan.is_panning() is False

    def test_click_then_drag_then_click(self):
        """先点击 → 再拖拽 → 再点击，状态切换正确。"""
        widget = _make_widget_mock(
            n_axes=1,
            time_sec=np.array([0.0, 50.0, 200.0]),
            xlim_list=[(0.0, 100.0)],
        )
        pan = PanController(widget)

        # 第一次：点击
        press1 = _make_event(button=1, x=100, y=200, xdata=50.0, inaxes=widget.axes[0])
        pan.on_press(press1)
        release1 = _make_event(button=1, x=101, y=201, xdata=50.2)
        pan.on_release(release1)
        assert pan.was_panning() is False

        # 第二次：拖拽
        press2 = _make_event(button=1, x=100, y=200, xdata=50.0, inaxes=widget.axes[0])
        pan.on_press(press2)
        motion2 = _make_event(x=120, y=200, xdata=60.0, inaxes=widget.axes[0])
        pan.on_motion(motion2)
        release2 = _make_event(button=1)
        pan.on_release(release2)
        assert pan.was_panning() is True

        # 第三次：点击
        press3 = _make_event(button=1, x=100, y=200, xdata=50.0, inaxes=widget.axes[0])
        pan.on_press(press3)
        assert pan.was_panning() is False  # 被清除
        release3 = _make_event(button=1, x=101, y=201, xdata=50.2)
        pan.on_release(release3)
        assert pan.was_panning() is False


# ============================================================================
# LayoutController on_canvas_click 简化后测试
# ============================================================================

class TestLayoutControllerOnCanvasClick:
    """测试 LayoutController.on_canvas_click（简化后仅处理左键子图选择）。"""

    def _make_layout_controller(self, n_axes=2):
        """创建 LayoutController 实例。"""
        from ftpa.gui._layout_ctrl import LayoutController

        widget = MagicMock()
        axes = []
        for i in range(n_axes):
            ax = MagicMock()
            axes.append(ax)
        widget.axes = axes
        widget._selected_subplot_idx = None
        widget.subplot_fields = {i: [] for i in range(n_axes)}
        widget.canvas = MagicMock()

        # Signal mock
        subplot_selected = MagicMock()
        widget.subplot_selected = subplot_selected

        ctrl = LayoutController(widget)
        return ctrl, widget

    def test_left_click_in_axes_selects_subplot(self):
        """左键点击子图区域应选中对应子图。"""
        ctrl, widget = self._make_layout_controller(n_axes=2)

        event = _make_event(button=1, inaxes=widget.axes[1])
        ctrl.on_canvas_click(event)

        assert widget._selected_subplot_idx == 1

    def test_left_click_outside_axes_deselects(self):
        """左键点击子图区域外应取消选中。"""
        ctrl, widget = self._make_layout_controller(n_axes=2)
        widget._selected_subplot_idx = 0

        event = _make_event(button=1, inaxes=None)
        ctrl.on_canvas_click(event)

        assert widget._selected_subplot_idx is None

    def test_right_click_ignored(self):
        """右键点击不应触发子图选择。"""
        ctrl, widget = self._make_layout_controller(n_axes=2)

        event = _make_event(button=3, inaxes=widget.axes[0])
        ctrl.on_canvas_click(event)

        # 右键不做任何操作
        assert widget._selected_subplot_idx is None


# ============================================================================
# 降采样模块测试
# ============================================================================

class TestMinMaxDownsample:
    """测试 min-max 降采样算法。"""

    def test_small_data_no_downsample(self):
        """小数据集（≤阈值）不应降采样，直接返回原始数据。"""
        from ftpa.gui._downsampler import min_max_downsample, DOWNSAMPLE_THRESHOLD

        time = np.arange(100, dtype=float)
        data = np.sin(time * 0.1)

        ds_time, ds_data = min_max_downsample(time, data, 0.0, 99.0, max_points=200)

        assert len(ds_time) == 100
        assert len(ds_data) == 100
        np.testing.assert_array_equal(ds_time, time)
        np.testing.assert_array_equal(ds_data, data)

    def test_large_data_downsamples(self):
        """大数据集应降采样到目标点数。"""
        from ftpa.gui._downsampler import min_max_downsample

        n = 50000
        time = np.linspace(0, 100, n)
        data = np.sin(time * 0.5)

        ds_time, ds_data = min_max_downsample(time, data, 0.0, 100.0, max_points=2000)

        assert len(ds_time) <= 4000  # 每桶2点 × 1000桶
        assert len(ds_time) > 0
        # 时间应单调递增
        assert np.all(np.diff(ds_time) >= 0)

    def test_peak_valley_preserved(self):
        """降采样应保留峰值和谷值。"""
        from ftpa.gui._downsampler import min_max_downsample

        n = 50000
        time = np.linspace(0, 100, n)
        # 创建明显的峰和谷
        data = np.zeros(n)
        data[n // 4] = 10.0     # 明显的峰
        data[3 * n // 4] = -10.0  # 明显的谷

        ds_time, ds_data = min_max_downsample(time, data, 0.0, 100.0, max_points=2000)

        # 峰值和谷值应在降采样结果中
        assert np.max(ds_data) == pytest.approx(10.0)
        assert np.min(ds_data) == pytest.approx(-10.0)

    def test_nan_handling(self):
        """含 NaN 的数据应正确处理。"""
        from ftpa.gui._downsampler import min_max_downsample

        n = 50000
        time = np.linspace(0, 100, n)
        data = np.sin(time * 0.5)
        data[1000:2000] = np.nan  # 插入一段 NaN

        ds_time, ds_data = min_max_downsample(time, data, 0.0, 100.0, max_points=2000)

        # 结果中不应有 NaN
        assert not np.any(np.isnan(ds_data))
        assert len(ds_time) > 0

    def test_all_nan_bucket_skipped(self):
        """全为 NaN 的桶应被跳过。"""
        from ftpa.gui._downsampler import min_max_downsample

        n = 50000
        time = np.linspace(0, 100, n)
        data = np.full(n, np.nan)
        data[:100] = 1.0  # 仅前 100 个有值

        ds_time, ds_data = min_max_downsample(time, data, 0.0, 100.0, max_points=2000)

        # 应有少量结果（仅来自前 100 点的桶）
        assert len(ds_time) > 0
        assert not np.any(np.isnan(ds_data))


# ============================================================================
# PanController 新增功能测试
# ============================================================================

class TestPanControllerReset:
    """测试 PanController.reset() 方法。"""

    def test_reset_clears_all_state(self):
        """reset() 应清除所有平移状态。"""
        widget = _make_widget_mock(
            n_axes=1,
            time_sec=np.array([0.0, 100.0]),
            xlim_list=[(10.0, 60.0)],
        )
        pan = PanController(widget)

        # 模拟平移中状态
        pan._press_event = MagicMock()
        pan._is_panning = True
        pan._was_panning = True
        pan._press_xlim = [(10.0, 60.0)]

        pan.reset()

        assert pan._press_event is None
        assert pan._is_panning is False
        assert pan._was_panning is False
        assert pan._press_xlim is None

    def test_reset_idempotent(self):
        """多次调用 reset() 不应报错。"""
        widget = _make_widget_mock()
        pan = PanController(widget)

        pan.reset()
        pan.reset()
        pan.reset()

        assert pan._is_panning is False


class TestPanControllerNoData:
    """测试无数据时平移被禁止。"""

    def test_no_ctx_on_press_rejected(self):
        """ctx 为 None 时 on_press 不记录事件。"""
        widget = _make_widget_mock(n_axes=1, xlim_list=[(0.0, 100.0)])
        widget.ctx = None  # 显式设无数据
        pan = PanController(widget)

        event = _make_event(button=1, x=100, y=200, xdata=50.0, inaxes=widget.axes[0])
        pan.on_press(event)

        assert pan._press_event is None

    def test_empty_time_sec_on_press_rejected(self):
        """time_sec 为空数组时 on_press 不记录事件。"""
        widget = _make_widget_mock(n_axes=1, time_sec=np.array([]), xlim_list=[(0.0, 100.0)])
        pan = PanController(widget)

        event = _make_event(button=1, x=100, y=200, xdata=50.0, inaxes=widget.axes[0])
        pan.on_press(event)

        assert pan._press_event is None


class TestWhiteMarginConfig:
    """测试白边比例可配置。"""

    def test_default_margin(self):
        """默认无边界约束（自由平移模式）。"""
        widget = _make_widget_mock(
            n_axes=1,
            time_sec=np.array([0.0, 100.0]),
            xlim_list=[(0.0, 100.0)],
        )
        pan = PanController(widget)
        # 自由平移：无 _white_margin_ratio 属性
        assert not hasattr(pan, '_white_margin_ratio')

    def test_custom_margin(self):
        """自由平移模式：自定义白边比例不再适用。"""
        widget = _make_widget_mock(
            n_axes=1,
            time_sec=np.array([0.0, 100.0]),
            xlim_list=[(0.0, 100.0)],
        )
        pan = PanController(widget)
        # 自由平移：无边界约束
        assert not hasattr(pan, '_white_margin_ratio')

    def test_zero_margin_hard_stop(self):
        """自由平移模式：零白边不再适用，无硬停。"""
        widget = _make_widget_mock(
            n_axes=1,
            time_sec=np.array([0.0, 100.0]),
            xlim_list=[(5.0, 55.0)],
        )
        pan = PanController(widget)
        pan._press_xlim = [(5.0, 55.0)]

        # 自由平移：向左平移 10（无约束）
        pan._apply_pan(-10.0)
        widget.axes[0].set_xlim.assert_called_once_with(-5.0, 45.0)


# ============================================================================
# 滚轮缩放 + 条件性边界约束 测试
# 参照设计文档 .trae/specs/scroll-zoom/design.md
# ============================================================================

def _make_scroll_event(button="up", x=100, y=200, xdata=50.0, ydata=25.0, inaxes=None):
    """创建模拟 matplotlib scroll_event 的对象。

    Args:
        button: "up"（上滚，放大）或 "down"（下滚，缩小）
        x: 鼠标 x 像素坐标
        y: 鼠标 y 像素坐标
        xdata: 鼠标 x 数据坐标（时间轴位置）
        ydata: 鼠标 y 数据坐标
        inaxes: 鼠标所在的 Axes 对象（None 表示在子图外）
    """
    evt = MagicMock()
    evt.button = button
    evt.x = x
    evt.y = y
    evt.xdata = xdata
    evt.ydata = ydata
    evt.inaxes = inaxes
    return evt


class TestScrollZoom:
    """测试滚轮缩放功能（CrossingAnalyzer.on_scroll_zoom）。

    参照设计文档第2节：以鼠标位置为缩放中心，所有子图X轴同步缩放。
    """

    def _make_analyzer(self, n_axes=2, time_sec=None, xlim_list=None):
        """创建 CrossingAnalyzer 实例（mock widget）。"""
        from ftpa.gui._crossing_analyzer import CrossingAnalyzer

        widget = _make_widget_mock(n_axes=n_axes, time_sec=time_sec, xlim_list=xlim_list)
        analyzer = CrossingAnalyzer(widget)
        return analyzer, widget

    def test_scroll_up_zooms_in(self):
        """上滚→span缩小为原来的0.92倍。"""
        # data: [0, 50, 100], data_span=100
        # 当前视图: (0, 100), span=100
        # 上滚 (factor=0.92): new_span = 92
        # 鼠标位置 center=50, ratio = (50-0)/100 = 0.5
        # new_start = 50 - 0.5*92 = 4, new_end = 4+92 = 96
        analyzer, widget = self._make_analyzer(
            n_axes=2,
            time_sec=np.array([0.0, 50.0, 100.0]),
            xlim_list=[(0.0, 100.0), (0.0, 100.0)],
        )
        event = _make_scroll_event(button="up", xdata=50.0, inaxes=widget.axes[0])

        with patch.object(analyzer, 'on_canvas_zoom') as mock_zoom:
            analyzer.on_scroll_zoom(event)
            mock_zoom.assert_called_once()

        # 验证所有子图都被设置为 (4, 96)
        for ax in widget.axes:
            ax.set_xlim.assert_called_once_with(4.0, 96.0)

    def test_scroll_down_zooms_out(self):
        """下滚→span扩大为原来的1.087倍。"""
        # data: [0, 50, 100], data_span=100, max_span = 200
        # 当前视图: (40, 60), span=20
        # 下滚 (factor=1.087): new_span = 21.74
        # 鼠标位置 center=50, ratio = (50-40)/20 = 0.5
        # new_start = 50 - 0.5*21.74 = 39.13, new_end = 39.13+21.74 = 60.87
        analyzer, widget = self._make_analyzer(
            n_axes=2,
            time_sec=np.array([0.0, 50.0, 100.0]),
            xlim_list=[(40.0, 60.0), (40.0, 60.0)],
        )
        event = _make_scroll_event(button="down", xdata=50.0, inaxes=widget.axes[0])

        with patch.object(analyzer, 'on_canvas_zoom'):
            analyzer.on_scroll_zoom(event)

        for ax in widget.axes:
            ax.set_xlim.assert_called_once_with(pytest.approx(39.13, abs=0.01),
                                                 pytest.approx(60.87, abs=0.01))

    def test_zoom_center_preserved(self):
        """缩放后鼠标位置的时间点不变。"""
        # 鼠标在 center=30，缩放后该时间点应仍在视图内且相对位置不变
        # 当前视图: (0, 100), span=100, center=30, ratio=0.3
        # 上滚 factor=0.92: new_span = 92
        # new_start = 30 - 0.3*92 = 2.4, new_end = 94.4
        # 验证: ratio_in_new_view = (30-2.4)/92 = 0.3 ✓
        analyzer, widget = self._make_analyzer(
            n_axes=1,
            time_sec=np.array([0.0, 50.0, 100.0]),
            xlim_list=[(0.0, 100.0)],
        )
        center = 30.0
        event = _make_scroll_event(button="up", xdata=center, inaxes=widget.axes[0])

        with patch.object(analyzer, 'on_canvas_zoom'):
            analyzer.on_scroll_zoom(event)

        # 获取设置的 xlim
        call_args = widget.axes[0].set_xlim.call_args
        new_start, new_end = call_args[0]
        # 验证鼠标位置仍在新视图内且相对位置不变
        new_span = new_end - new_start
        ratio_in_new = (center - new_start) / new_span
        assert ratio_in_new == pytest.approx(0.3)

    def test_span_min_limit(self):
        """span不会小于1.0秒。"""
        # 当前视图: (49.5, 50.5), span=1.0
        # center=50, ratio=0.5, factor=0.92: new_span=0.92 < 1.0 → 强制 new_span=1.0
        # 以center为中心重新计算: new_start=50-0.5=49.5, new_end=50.5
        analyzer, widget = self._make_analyzer(
            n_axes=1,
            time_sec=np.array([0.0, 50.0, 100.0]),
            xlim_list=[(49.5, 50.5)],
        )
        event = _make_scroll_event(button="up", xdata=50.0, inaxes=widget.axes[0])

        with patch.object(analyzer, 'on_canvas_zoom'):
            analyzer.on_scroll_zoom(event)

        call_args = widget.axes[0].set_xlim.call_args
        new_start, new_end = call_args[0]
        new_span = new_end - new_start
        # span 不应小于 1.0
        assert new_span >= 1.0
        # 应该恰好是 1.0
        assert new_span == pytest.approx(1.0)

    def test_span_max_limit(self):
        """span不会超过 data_span × 2。"""
        # data: [0, 50, 100], data_span=100, max_span=200
        # 当前视图: (-40, 140), span=180
        # center=50, ratio=0.5, factor=1.087: new_span=195.66 < 200 → 不触发限制
        # 需要更大的 span 才能触发 max 限制
        # 当前视图: (-50, 160), span=210
        # center=50, ratio=(50-(-50))/210=100/210≈0.476, factor=1.087: new_span=228.27 > 200 → 强制 new_span=200
        # 以center为中心重新计算: new_start=50-100=-50, new_end=50+100=150
        analyzer, widget = self._make_analyzer(
            n_axes=1,
            time_sec=np.array([0.0, 50.0, 100.0]),
            xlim_list=[(-50.0, 160.0)],
        )
        event = _make_scroll_event(button="down", xdata=50.0, inaxes=widget.axes[0])

        with patch.object(analyzer, 'on_canvas_zoom'):
            analyzer.on_scroll_zoom(event)

        call_args = widget.axes[0].set_xlim.call_args
        new_start, new_end = call_args[0]
        new_span = new_end - new_start
        # 不应超过 data_span*2 = 200
        assert new_span <= 200.0
        # 应恰好等于 200
        assert new_span == pytest.approx(200.0)

    def test_no_data_returns_early(self):
        """无数据时不报错。"""
        # ctx 为 None
        widget = _make_widget_mock(n_axes=1, xlim_list=[(0.0, 100.0)])
        widget.ctx = None
        from ftpa.gui._crossing_analyzer import CrossingAnalyzer
        analyzer = CrossingAnalyzer(widget)

        event = _make_scroll_event(button="up", xdata=50.0, inaxes=widget.axes[0])

        # 不应抛出异常，不应调用 set_xlim 和 on_canvas_zoom
        with patch.object(analyzer, 'on_canvas_zoom') as mock_zoom:
            analyzer.on_scroll_zoom(event)
            mock_zoom.assert_not_called()

        widget.axes[0].set_xlim.assert_not_called()

    def test_outside_axes_returns_early(self):
        """鼠标在子图外不报错。"""
        analyzer, widget = self._make_analyzer(
            n_axes=1,
            time_sec=np.array([0.0, 50.0, 100.0]),
            xlim_list=[(0.0, 100.0)],
        )
        # inaxes 为 None
        event = _make_scroll_event(button="up", xdata=50.0, inaxes=None)

        with patch.object(analyzer, 'on_canvas_zoom') as mock_zoom:
            analyzer.on_scroll_zoom(event)
            mock_zoom.assert_not_called()

        widget.axes[0].set_xlim.assert_not_called()

    def test_multi_axes_synced(self):
        """多个子图同步缩放。"""
        # 3个子图，所有子图初始 xlim 相同
        # 上滚 center=50: new_xlim = (4, 96)
        analyzer, widget = self._make_analyzer(
            n_axes=3,
            time_sec=np.array([0.0, 50.0, 100.0]),
            xlim_list=[(0.0, 100.0), (0.0, 100.0), (0.0, 100.0)],
        )
        # 鼠标在第2个子图上
        event = _make_scroll_event(button="up", xdata=50.0, inaxes=widget.axes[1])

        with patch.object(analyzer, 'on_canvas_zoom'):
            analyzer.on_scroll_zoom(event)

        # 验证所有3个子图都被设置相同的 xlim
        expected = (4.0, 96.0)
        for ax in widget.axes:
            ax.set_xlim.assert_called_once_with(*expected)


class TestBoundaryConstraintConditional:
    """测试 _apply_pan 的自由平移行为。

    自由平移模式：无论 span 大小，均不施加边界约束。
    水平移动仅受 X 轴参数影响，与 Y 轴缩放状态无关。
    """

    def test_boundary_disabled_when_full_view(self):
        """全视图时自由平移。"""
        widget = _make_widget_mock(
            n_axes=1,
            time_sec=np.array([0.0, 50.0, 100.0]),
            xlim_list=[(0.0, 100.0)],
        )
        pan = PanController(widget)
        pan._press_xlim = [(0.0, 100.0)]

        pan._apply_pan(-50.0)
        widget.axes[0].set_xlim.assert_called_once_with(-50.0, 50.0)

    def test_boundary_enabled_when_zoomed(self):
        """缩放后自由平移（不再施加条件性约束）。"""
        widget = _make_widget_mock(
            n_axes=1,
            time_sec=np.array([0.0, 50.0, 100.0]),
            xlim_list=[(40.0, 60.0)],
        )
        pan = PanController(widget)
        pan._press_xlim = [(40.0, 60.0)]

        pan._apply_pan(-50.0)
        # 自由平移：new_start = -10, new_end = 10（无约束）
        widget.axes[0].set_xlim.assert_called_once_with(-10.0, 10.0)

    def test_boundary_threshold_exact_95_percent(self):
        """临界条件：自由平移，无约束。"""
        widget = _make_widget_mock(
            n_axes=1,
            time_sec=np.array([0.0, 50.0, 100.0]),
            xlim_list=[(0.0, 95.0)],
        )
        pan = PanController(widget)
        pan._press_xlim = [(0.0, 95.0)]

        pan._apply_pan(-10.0)
        widget.axes[0].set_xlim.assert_called_once_with(-10.0, 85.0)


class TestScrollPanInteraction:
    """测试滚轮缩放与平移的协同。

    参照设计文档第3.2节：平移中忽略滚轮，缩放后平移正常工作。
    """

    def test_scroll_ignored_during_pan(self):
        """平移中滚轮事件被忽略（_on_scroll 路由逻辑）。"""
        # 模拟 panel_plot._on_scroll 的路由逻辑：
        #   if self._pan.is_panning(): return
        #   self._crossing.on_scroll_zoom(event)
        from ftpa.gui._crossing_analyzer import CrossingAnalyzer

        widget = _make_widget_mock(
            n_axes=1,
            time_sec=np.array([0.0, 50.0, 100.0]),
            xlim_list=[(0.0, 100.0)],
        )
        pan = PanController(widget)
        analyzer = CrossingAnalyzer(widget)

        # 模拟平移中
        pan._is_panning = True

        event = _make_scroll_event(button="up", xdata=50.0, inaxes=widget.axes[0])

        # 复用 panel_plot._on_scroll 的路由逻辑
        with patch.object(analyzer, 'on_scroll_zoom') as mock_zoom:
            if not pan.is_panning():
                analyzer.on_scroll_zoom(event)
            mock_zoom.assert_not_called()

        # 子图 xlim 不应被修改
        widget.axes[0].set_xlim.assert_not_called()

    def test_pan_works_after_zoom(self):
        """缩放后平移正常工作（自由平移，无约束）。"""
        from ftpa.gui._crossing_analyzer import CrossingAnalyzer

        widget = _make_widget_mock(
            n_axes=1,
            time_sec=np.array([0.0, 50.0, 100.0]),
            xlim_list=[(0.0, 100.0)],
        )
        analyzer = CrossingAnalyzer(widget)
        pan = PanController(widget)

        # 1. 滚轮缩放：上滚，center=50
        # 当前 (0, 100), span=100, factor=0.92, new_span=92
        # new_start = 50 - 0.5*92 = 4, new_end = 96
        zoom_event = _make_scroll_event(button="up", xdata=50.0, inaxes=widget.axes[0])
        with patch.object(analyzer, 'on_canvas_zoom'):
            analyzer.on_scroll_zoom(zoom_event)

        # 验证缩放生效
        widget.axes[0].set_xlim.assert_called_once_with(4.0, 96.0)

        # 2. 模拟缩放后的状态：更新 widget 的 get_xlim 返回值
        widget.axes[0].get_xlim.return_value = (4.0, 96.0)

        # 3. 平移：自由平移（无约束）
        # dx_data = -20: new_start = -16, new_end = 76
        pan._press_xlim = [(4.0, 96.0)]
        pan._apply_pan(-20.0)

        widget.axes[0].set_xlim.assert_called_with(-16.0, 76.0)
