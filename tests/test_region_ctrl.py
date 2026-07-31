"""
测试 RegionController — 右键拖动框选时间区间。
"""

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from ftpa.gui._region_ctrl import RegionController


def _make_widget_mock(n_axes=2, time_sec=None, xlim_list=None):
    """创建模拟 PlotCanvasWidget 的 mock 对象。

    Args:
        n_axes: 子图数量
        time_sec: DataContext 中的 time_sec 数组（None 表示使用默认值）
        xlim_list: 每个子图的初始 xlim，默认 (0, 100)
    """
    widget = MagicMock()
    axes = []
    for i in range(n_axes):
        ax = MagicMock()
        xlim = xlim_list[i] if xlim_list and i < len(xlim_list) else (0.0, 100.0)
        ax.get_xlim.return_value = xlim
        ax.get_visible.return_value = True
        axes.append(ax)
    widget.axes = axes

    # DataContext mock
    if time_sec is not None:
        ctx = MagicMock()
        ctx.time_sec = time_sec
        ctx.query.get_time_sec.return_value = time_sec
    else:
        ctx = MagicMock()
        ctx.time_sec = np.array([0.0, 50.0, 100.0])
        ctx.query.get_time_sec.return_value = np.array([0.0, 50.0, 100.0])
    widget.ctx = ctx

    # canvas mock
    canvas = MagicMock()
    canvas.devicePixelRatio.return_value = 1.0
    canvas.get_width_height.return_value = (1000, 600)
    canvas.width.return_value = 1000
    canvas.height.return_value = 600
    widget.canvas = canvas

    # log_message 信号
    widget.log_message = MagicMock()

    # _crossing mock
    widget._crossing = MagicMock()

    return widget


def _make_event(button=3, x=100, y=200, xdata=50.0, ydata=25.0, inaxes=None):
    """创建模拟 matplotlib 事件的对象。"""
    evt = MagicMock()
    evt.button = button
    evt.x = x
    evt.y = y
    evt.xdata = xdata
    evt.ydata = ydata
    evt.inaxes = inaxes
    return evt


# ── 状态机转换测试 ──


class TestRegionControllerStateMachine:
    """测试 RegionController 的状态机转换。"""

    def test_initial_state_is_idle(self):
        """初始状态应为 IDLE。"""
        widget = _make_widget_mock()
        ctrl = RegionController(widget)
        assert ctrl.get_state() == RegionController.IDLE

    def test_right_press_in_axes_enters_pressed(self):
        """右键在 axes 内按下应进入 PRESSED 状态。"""
        widget = _make_widget_mock()
        ctrl = RegionController(widget)

        event = _make_event(button=3, xdata=30.0, inaxes=widget.axes[0])
        ctrl.on_press(event)

        assert ctrl.get_state() == RegionController.PRESSED
        assert ctrl._press_event is event

    def test_left_press_ignored(self):
        """左键按下应被忽略。"""
        widget = _make_widget_mock()
        ctrl = RegionController(widget)

        event = _make_event(button=1, xdata=30.0, inaxes=widget.axes[0])
        ctrl.on_press(event)

        assert ctrl.get_state() == RegionController.IDLE
        assert ctrl._press_event is None

    def test_press_outside_axes_ignored(self):
        """右键在 axes 外按下应被忽略。"""
        widget = _make_widget_mock()
        ctrl = RegionController(widget)

        event = _make_event(button=3, xdata=30.0, inaxes=None)
        ctrl.on_press(event)

        assert ctrl.get_state() == RegionController.IDLE

    def test_press_no_data_ignored(self):
        """无数据时右键按下应被忽略。"""
        widget = _make_widget_mock(time_sec=None)
        widget.ctx.time_sec = None
        widget.ctx.query.get_time_sec.return_value = None
        ctrl = RegionController(widget)

        event = _make_event(button=3, xdata=30.0, inaxes=widget.axes[0])
        ctrl.on_press(event)

        assert ctrl.get_state() == RegionController.IDLE

    def test_drag_above_threshold_enters_selecting(self):
        """拖动距离超过阈值应进入 SELECTING 状态。"""
        widget = _make_widget_mock()
        ctrl = RegionController(widget)

        press_event = _make_event(button=3, x=100, y=200, xdata=30.0, inaxes=widget.axes[0])
        ctrl.on_press(press_event)

        motion_event = _make_event(x=120, y=200, xdata=40.0, inaxes=widget.axes[0])
        ctrl.on_motion(motion_event)

        assert ctrl.get_state() == RegionController.SELECTING

    def test_drag_below_threshold_stays_pressed(self):
        """拖动距离未超过阈值应保持 PRESSED 状态。"""
        widget = _make_widget_mock()
        ctrl = RegionController(widget)

        press_event = _make_event(button=3, x=100, y=200, xdata=30.0, inaxes=widget.axes[0])
        ctrl.on_press(press_event)

        motion_event = _make_event(x=103, y=202, xdata=31.0, inaxes=widget.axes[0])
        ctrl.on_motion(motion_event)

        assert ctrl.get_state() == RegionController.PRESSED

    def test_release_after_drag_enters_selected(self):
        """拖动后释放应进入 SELECTED 状态。"""
        widget = _make_widget_mock()
        ctrl = RegionController(widget)

        press_event = _make_event(button=3, x=100, y=200, xdata=30.0, inaxes=widget.axes[0])
        ctrl.on_press(press_event)

        motion_event = _make_event(x=120, y=200, xdata=70.0, inaxes=widget.axes[0])
        ctrl.on_motion(motion_event)

        release_event = _make_event(button=3, x=120, y=200, xdata=70.0, inaxes=widget.axes[0])
        was_drag = ctrl.on_release(release_event)

        assert was_drag is True
        assert ctrl.get_state() == RegionController.SELECTED

    def test_release_without_drag_returns_false(self):
        """未拖动时释放应返回 False（表示单击）。"""
        widget = _make_widget_mock()
        ctrl = RegionController(widget)

        press_event = _make_event(button=3, x=100, y=200, xdata=30.0, inaxes=widget.axes[0])
        ctrl.on_press(press_event)

        release_event = _make_event(button=3, x=101, y=201, xdata=30.5, inaxes=widget.axes[0])
        was_drag = ctrl.on_release(release_event)

        assert was_drag is False
        assert ctrl.get_state() == RegionController.IDLE

    def test_cancel_returns_to_idle(self):
        """取消操作应回到 IDLE 状态。"""
        widget = _make_widget_mock()
        ctrl = RegionController(widget)

        # 模拟完成框选
        ctrl._state = RegionController.SELECTED
        ctrl._region_start = 10.0
        ctrl._region_end = 80.0

        ctrl.cancel_selection()

        assert ctrl.get_state() == RegionController.IDLE
        assert ctrl.get_region() is None

    def test_reset_returns_to_idle(self):
        """强制重置应回到 IDLE 状态。"""
        widget = _make_widget_mock()
        ctrl = RegionController(widget)

        ctrl._state = RegionController.SELECTING
        ctrl._region_start = 10.0
        ctrl._region_end = 80.0

        ctrl.reset()

        assert ctrl.get_state() == RegionController.IDLE
        assert ctrl.get_region() is None


# ── 时间区间计算测试 ──


class TestRegionControllerTimeRange:
    """测试框选时间区间的精确计算。"""

    def test_region_start_end_correct(self):
        """框选完成后起止时间应正确记录。"""
        widget = _make_widget_mock()
        ctrl = RegionController(widget)

        press_event = _make_event(button=3, x=100, y=200, xdata=30.0, inaxes=widget.axes[0])
        ctrl.on_press(press_event)

        motion_event = _make_event(x=200, y=200, xdata=70.0, inaxes=widget.axes[0])
        ctrl.on_motion(motion_event)

        release_event = _make_event(button=3, x=200, y=200, xdata=70.0, inaxes=widget.axes[0])
        ctrl.on_release(release_event)

        region = ctrl.get_region()
        assert region is not None
        assert region[0] == 30.0
        assert region[1] == 70.0

    def test_region_auto_swaps_start_end(self):
        """框选从右到左拖动时应自动交换起止时间（start < end）。"""
        widget = _make_widget_mock()
        ctrl = RegionController(widget)

        # 从右往左拖：xdata 从大到小
        press_event = _make_event(button=3, x=200, y=200, xdata=70.0, inaxes=widget.axes[0])
        ctrl.on_press(press_event)

        motion_event = _make_event(x=100, y=200, xdata=30.0, inaxes=widget.axes[0])
        ctrl.on_motion(motion_event)

        release_event = _make_event(button=3, x=100, y=200, xdata=30.0, inaxes=widget.axes[0])
        ctrl.on_release(release_event)

        region = ctrl.get_region()
        assert region is not None
        assert region[0] == 30.0  # start 应为较小值
        assert region[1] == 70.0  # end 应为较大值

    def test_get_region_returns_none_when_idle(self):
        """IDLE 状态下 get_region 应返回 None。"""
        widget = _make_widget_mock()
        ctrl = RegionController(widget)
        assert ctrl.get_region() is None

    def test_realistic_time_range(self):
        """使用模拟飞行数据时间范围进行测试。"""
        time_data = np.arange(0, 3600, 0.1)  # 0 到 3600 秒
        widget = _make_widget_mock(
            time_sec=time_data,
            xlim_list=[(0.0, 3600.0), (0.0, 3600.0)]
        )
        ctrl = RegionController(widget)

        # 框选 300秒 到 600秒 的区间
        press_event = _make_event(button=3, x=100, y=200, xdata=300.0, inaxes=widget.axes[0])
        ctrl.on_press(press_event)

        motion_event = _make_event(x=150, y=200, xdata=600.0, inaxes=widget.axes[0])
        ctrl.on_motion(motion_event)

        release_event = _make_event(button=3, x=150, y=200, xdata=600.0, inaxes=widget.axes[0])
        ctrl.on_release(release_event)

        region = ctrl.get_region()
        assert region is not None
        assert abs(region[0] - 300.0) < 1.0  # 误差 < 1秒
        assert abs(region[1] - 600.0) < 1.0


# ── 视觉反馈测试 ──


class TestRegionControllerVisualFeedback:
    """测试框选视觉反馈（覆盖层和标注）。"""

    def test_draw_region_creates_artists(self):
        """_draw_region 应在所有子图上创建 axvspan + axvline artist。"""
        widget = _make_widget_mock(n_axes=2)
        ctrl = RegionController(widget)

        ctrl._draw_region(20.0, 60.0)

        # 每个 axes 应被调用 axvspan 一次 + axvline 两次
        assert len(ctrl._span_artists) == 2  # 2 个子图
        assert len(ctrl._line_artists) == 4  # 2 子图 × 2 条边界线
        assert len(ctrl._label_artists) == 1  # 仅第一个子图显示标注

        # 验证 axvspan 和 axvline 被调用
        for ax in widget.axes:
            ax.axvspan.assert_called_once()
            assert ax.axvline.call_count == 2

    def test_clear_region_removes_artists(self):
        """_clear_region 应移除所有 artist。"""
        widget = _make_widget_mock()
        ctrl = RegionController(widget)

        ctrl._draw_region(20.0, 60.0)
        assert len(ctrl._span_artists) > 0

        ctrl._clear_region()
        assert len(ctrl._span_artists) == 0
        assert len(ctrl._line_artists) == 0
        assert len(ctrl._label_artists) == 0

    def test_draw_region_clears_previous_first(self):
        """_draw_region 应先清除之前的 artist 再绘制新的。"""
        widget = _make_widget_mock()
        ctrl = RegionController(widget)

        ctrl._draw_region(20.0, 60.0)
        first_span_count = len(ctrl._span_artists)

        ctrl._draw_region(30.0, 70.0)
        # artist 数量应相同（旧的被清除，新的被创建）
        assert len(ctrl._span_artists) == first_span_count

    def test_cancel_selection_clears_artists(self):
        """取消框选应清除所有 artist。"""
        widget = _make_widget_mock()
        ctrl = RegionController(widget)

        ctrl._state = RegionController.SELECTED
        ctrl._region_start = 20.0
        ctrl._region_end = 60.0
        ctrl._draw_region(20.0, 60.0)

        ctrl.cancel_selection()

        assert len(ctrl._span_artists) == 0
        assert len(ctrl._line_artists) == 0
        assert len(ctrl._label_artists) == 0


# ── 应用/取消测试 ──


class TestRegionControllerApplyCancel:
    """测试框选应用和取消操作。"""

    def test_apply_success_clears_region(self):
        """应用成功应自动清除框选并回到 IDLE。"""
        widget = _make_widget_mock()
        ctrl = RegionController(widget)

        # 模拟穿越检测成功
        widget._crossing.apply_crossing_in_region.return_value = True

        ctrl._state = RegionController.SELECTED
        ctrl._region_start = 20.0
        ctrl._region_end = 60.0

        result = ctrl.apply_selection()

        assert result is True
        assert ctrl.get_state() == RegionController.IDLE
        assert ctrl.get_region() is None

    def test_apply_failure_keeps_region(self):
        """应用失败应保持框选状态。"""
        widget = _make_widget_mock()
        ctrl = RegionController(widget)

        # 模拟穿越检测失败
        widget._crossing.apply_crossing_in_region.return_value = False

        ctrl._state = RegionController.SELECTED
        ctrl._region_start = 20.0
        ctrl._region_end = 60.0

        result = ctrl.apply_selection()

        assert result is False
        assert ctrl.get_state() == RegionController.SELECTED
        assert ctrl.get_region() == (20.0, 60.0)

    def test_apply_no_region_returns_false(self):
        """无有效框选区域时应用应返回 False。"""
        widget = _make_widget_mock()
        ctrl = RegionController(widget)

        result = ctrl.apply_selection()

        assert result is False

    def test_apply_calls_crossing_with_correct_range(self):
        """应用应将框选区间传递给 CrossingAnalyzer。"""
        widget = _make_widget_mock()
        ctrl = RegionController(widget)
        widget._crossing.apply_crossing_in_region.return_value = True

        ctrl._state = RegionController.SELECTED
        ctrl._region_start = 100.0
        ctrl._region_end = 500.0

        ctrl.apply_selection()

        widget._crossing.apply_crossing_in_region.assert_called_once_with(100.0, 500.0)

    def test_cancel_clears_state(self):
        """取消操作应正确重置状态。"""
        widget = _make_widget_mock()
        ctrl = RegionController(widget)

        ctrl._state = RegionController.SELECTED
        ctrl._region_start = 20.0
        ctrl._region_end = 60.0

        ctrl.cancel_selection()

        assert ctrl.get_state() == RegionController.IDLE

    def test_apply_success_sends_log(self):
        """应用成功应发送日志消息。"""
        widget = _make_widget_mock()
        ctrl = RegionController(widget)
        widget._crossing.apply_crossing_in_region.return_value = True

        ctrl._state = RegionController.SELECTED
        ctrl._region_start = 20.0
        ctrl._region_end = 60.0

        ctrl.apply_selection()

        # 验证日志消息被发送
        widget.log_message.emit.assert_called()


# ── 状态查询测试 ──


class TestRegionControllerQueries:
    """测试状态查询方法。"""

    def test_is_selecting(self):
        """is_selecting 应正确反映 SELECTING 状态。"""
        widget = _make_widget_mock()
        ctrl = RegionController(widget)

        assert ctrl.is_selecting() is False

        ctrl._state = RegionController.SELECTING
        assert ctrl.is_selecting() is True

    def test_is_selected(self):
        """is_selected 应正确反映 SELECTED 状态。"""
        widget = _make_widget_mock()
        ctrl = RegionController(widget)

        assert ctrl.is_selected() is False

        ctrl._state = RegionController.SELECTED
        assert ctrl.is_selected() is True


# ── 边界情况测试 ──


class TestRegionControllerEdgeCases:
    """测试边界情况和异常处理。"""

    def test_no_press_event_motion_ignored(self):
        """未按下时移动应被忽略。"""
        widget = _make_widget_mock()
        ctrl = RegionController(widget)

        motion_event = _make_event(xdata=50.0)
        ctrl.on_motion(motion_event)

        assert ctrl.get_state() == RegionController.IDLE

    def test_no_press_event_release_returns_false(self):
        """未按下时释放应返回 False。"""
        widget = _make_widget_mock()
        ctrl = RegionController(widget)

        release_event = _make_event(button=3, xdata=50.0)
        result = ctrl.on_release(release_event)

        assert result is False

    def test_motion_with_none_x_ignored(self):
        """motion 事件 x 为 None 时应被忽略。"""
        widget = _make_widget_mock()
        ctrl = RegionController(widget)

        press_event = _make_event(button=3, x=100, y=200, xdata=30.0, inaxes=widget.axes[0])
        ctrl.on_press(press_event)

        motion_event = _make_event(x=None, y=None, xdata=40.0, inaxes=widget.axes[0])
        ctrl.on_motion(motion_event)

        # PRESSED 状态下，x=None 不应进入 SELECTING
        # (threshold check 无法通过)
        assert ctrl.get_state() == RegionController.PRESSED

    def test_release_with_none_xdata_keeps_previous_end(self):
        """释放事件 xdata 为 None 时应保持之前的终点。"""
        widget = _make_widget_mock()
        ctrl = RegionController(widget)

        press_event = _make_event(button=3, x=100, y=200, xdata=30.0, inaxes=widget.axes[0])
        ctrl.on_press(press_event)

        motion_event = _make_event(x=120, y=200, xdata=70.0, inaxes=widget.axes[0])
        ctrl.on_motion(motion_event)

        # 释放时 xdata 为 None
        release_event = _make_event(button=3, x=120, y=200, xdata=None, inaxes=widget.axes[0])
        ctrl.on_release(release_event)

        # region_end 应保持 motion 时设置的值
        region = ctrl.get_region()
        assert region is not None
        assert region[1] == 70.0

    def test_reset_clears_everything(self):
        """reset 应清除所有状态和 artist。"""
        widget = _make_widget_mock()
        ctrl = RegionController(widget)

        ctrl._state = RegionController.SELECTED
        ctrl._region_start = 20.0
        ctrl._region_end = 60.0
        ctrl._press_event = MagicMock()
        ctrl._span_artists = [MagicMock()]
        ctrl._line_artists = [MagicMock()]

        ctrl.reset()

        assert ctrl.get_state() == RegionController.IDLE
        assert ctrl.get_region() is None
        assert ctrl._press_event is None
        assert len(ctrl._span_artists) == 0

    def test_empty_time_sec_prevents_selection(self):
        """空 time_sec 数组应禁止框选。"""
        widget = _make_widget_mock(time_sec=np.array([]))
        ctrl = RegionController(widget)

        event = _make_event(button=3, xdata=30.0, inaxes=widget.axes[0])
        ctrl.on_press(event)

        assert ctrl.get_state() == RegionController.IDLE

    def test_draw_region_handles_invisible_axes(self):
        """不可见的 axes 不应绘制覆盖层。"""
        widget = _make_widget_mock(n_axes=2)
        widget.axes[1].get_visible.return_value = False
        ctrl = RegionController(widget)

        ctrl._draw_region(20.0, 60.0)

        # 仅 1 个可见子图应绘制覆盖层
        assert len(ctrl._span_artists) == 1


# ── 与 CrossingAnalyzer 集成测试 ──


class TestRegionControllerCrossingIntegration:
    """测试 RegionController 与 CrossingAnalyzer 的集成。"""

    def test_apply_delegates_to_crossing_analyzer(self):
        """应用框选应委托给 CrossingAnalyzer.apply_crossing_in_region。"""
        widget = _make_widget_mock()
        ctrl = RegionController(widget)
        widget._crossing.apply_crossing_in_region.return_value = True

        ctrl._state = RegionController.SELECTED
        ctrl._region_start = 100.0
        ctrl._region_end = 400.0

        ctrl.apply_selection()

        widget._crossing.apply_crossing_in_region.assert_called_once_with(100.0, 400.0)

    def test_apply_success_auto_clears_and_returns_true(self):
        """穿越检测成功后应自动清除框选并返回 True。"""
        widget = _make_widget_mock()
        ctrl = RegionController(widget)
        widget._crossing.apply_crossing_in_region.return_value = True

        ctrl._state = RegionController.SELECTED
        ctrl._region_start = 100.0
        ctrl._region_end = 400.0

        result = ctrl.apply_selection()

        assert result is True
        assert ctrl.get_state() == RegionController.IDLE
        assert ctrl.get_region() is None

    def test_apply_failure_keeps_selection(self):
        """穿越检测失败后应保持框选状态。"""
        widget = _make_widget_mock()
        ctrl = RegionController(widget)
        widget._crossing.apply_crossing_in_region.return_value = False

        ctrl._state = RegionController.SELECTED
        ctrl._region_start = 100.0
        ctrl._region_end = 400.0

        result = ctrl.apply_selection()

        assert result is False
        assert ctrl.get_state() == RegionController.SELECTED
        region = ctrl.get_region()
        assert region == (100.0, 400.0)

    def test_apply_sends_stats_on_success(self):
        """应用成功后应发送统计信息。"""
        widget = _make_widget_mock()
        ctrl = RegionController(widget)
        widget._crossing.apply_crossing_in_region.return_value = True
        widget._crossing.get_stats_text.return_value = "时间窗口: 00:05:00.000 - 00:10:00.000"

        ctrl._state = RegionController.SELECTED
        ctrl._region_start = 300.0
        ctrl._region_end = 600.0

        ctrl.apply_selection()

        # 验证统计文本被发送
        calls = widget.log_message.emit.call_args_list
        stat_calls = [c for c in calls if c[0][0].startswith("时间窗口")]
        assert len(stat_calls) >= 1
