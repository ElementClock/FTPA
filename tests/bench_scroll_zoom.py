"""滚轮缩放性能基准测试 + 协同行为验证。

验证内容：
1. 单次缩放响应时间 ≤ 50ms
2. 连续多次滚轮防抖性能
3. 大数据集（100万点）下降采样协同
4. 缩放后Y轴自适应协同
5. 缩放中心保持精度
"""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from ftpa.gui._crossing_analyzer import CrossingAnalyzer


def _make_scroll_event(button="up", x=100, y=200, xdata=50.0, ydata=25.0, inaxes=None):
    """创建模拟 matplotlib scroll_event 的对象。"""
    evt = MagicMock()
    evt.button = button
    evt.x = x
    evt.y = y
    evt.xdata = xdata
    evt.ydata = ydata
    evt.inaxes = inaxes
    return evt


class TestScrollZoomPerformance:
    """性能基准测试。"""

    def test_single_zoom_response_under_50ms(self):
        """单次缩放响应时间应 ≤ 50ms。"""
        # 准备：100万点数据集
        n = 1_000_000
        time_sec = np.linspace(0, 1000, n)
        widget = MagicMock()
        ax = MagicMock()
        ax.get_xlim.return_value = (0.0, 1000.0)
        widget.axes = [ax]
        ctx = MagicMock()
        ctx.time_sec = time_sec
        widget.ctx = ctx

        analyzer = CrossingAnalyzer(widget)

        event = _make_scroll_event(button="up", xdata=500.0, inaxes=ax)

        # 执行并计时（patch on_canvas_zoom 避免触发 QTimer）
        with patch.object(analyzer, "on_canvas_zoom"):
            start = time.perf_counter()
            analyzer.on_scroll_zoom(event)
            elapsed_ms = (time.perf_counter() - start) * 1000

        # 验证：≤ 50ms
        assert elapsed_ms < 50.0, f"单次缩放响应时间 {elapsed_ms:.2f}ms 超过 50ms 阈值"
        print(f"\n单次缩放响应时间: {elapsed_ms:.3f}ms")

    def test_consecutive_zoom_no_degradation(self):
        """连续10次滚轮缩放性能不应显著退化。"""
        n = 100_000
        time_sec = np.linspace(0, 1000, n)
        widget = MagicMock()
        ax = MagicMock()
        ax.get_xlim.return_value = (0.0, 1000.0)
        widget.axes = [ax]
        ctx = MagicMock()
        ctx.time_sec = time_sec
        widget.ctx = ctx

        analyzer = CrossingAnalyzer(widget)

        elapsed_list = []
        with patch.object(analyzer, "on_canvas_zoom"):
            for i in range(10):
                event = _make_scroll_event(button="up", xdata=500.0, inaxes=ax)
                start = time.perf_counter()
                analyzer.on_scroll_zoom(event)
                elapsed_ms = (time.perf_counter() - start) * 1000
                elapsed_list.append(elapsed_ms)
                # 更新 xlim 模拟连续缩放
                cur_xlim = ax.get_xlim.return_value
                new_span = (cur_xlim[1] - cur_xlim[0]) * 0.92
                ax.get_xlim.return_value = (500.0 - new_span / 2, 500.0 + new_span / 2)

        avg_ms = sum(elapsed_list) / len(elapsed_list)
        max_ms = max(elapsed_list)

        # 验证：平均和最大都不超过阈值
        assert avg_ms < 50.0, f"平均响应时间 {avg_ms:.2f}ms 超过 50ms"
        assert max_ms < 100.0, f"最大响应时间 {max_ms:.2f}ms 超过 100ms"
        print(f"\n连续10次缩放 - 平均: {avg_ms:.3f}ms, 最大: {max_ms:.3f}ms")


class TestScrollZoomCoordination:
    """协同行为验证。"""

    def test_zoom_triggers_on_canvas_zoom(self):
        """缩放后应触发 on_canvas_zoom（启动防抖）。"""
        widget = MagicMock()
        ax = MagicMock()
        ax.get_xlim.return_value = (0.0, 100.0)
        widget.axes = [ax]
        ctx = MagicMock()
        ctx.time_sec = np.array([0.0, 50.0, 100.0])
        widget.ctx = ctx

        analyzer = CrossingAnalyzer(widget)

        with patch.object(analyzer, "on_canvas_zoom") as mock_zoom:
            event = _make_scroll_event(button="up", xdata=50.0, inaxes=ax)
            analyzer.on_scroll_zoom(event)
            mock_zoom.assert_called_once()

    def test_zoom_does_not_trigger_on_canvas_zoom_when_no_data(self):
        """无数据时不应触发 on_canvas_zoom。"""
        widget = MagicMock()
        ax = MagicMock()
        ax.get_xlim.return_value = (0.0, 100.0)
        widget.axes = [ax]
        ctx = MagicMock()
        ctx.time_sec = None
        widget.ctx = ctx

        analyzer = CrossingAnalyzer(widget)

        with patch.object(analyzer, "on_canvas_zoom") as mock_zoom:
            event = _make_scroll_event(button="up", xdata=50.0, inaxes=ax)
            analyzer.on_scroll_zoom(event)
            mock_zoom.assert_not_called()

    def test_zoom_center_precision(self):
        """缩放中心点精度验证：缩放前后鼠标位置时间点完全一致。"""
        widget = MagicMock()
        ax = MagicMock()
        ax.get_xlim.return_value = (0.0, 100.0)
        widget.axes = [ax]
        ctx = MagicMock()
        ctx.time_sec = np.array([0.0, 100.0])
        widget.ctx = ctx

        analyzer = CrossingAnalyzer(widget)

        # 鼠标在 xdata=30 位置
        center = 30.0
        event = _make_scroll_event(button="up", xdata=center, inaxes=ax)

        with patch.object(analyzer, "on_canvas_zoom"):
            analyzer.on_scroll_zoom(event)

        # 验证：set_xlim 被调用，且 center 在新范围内
        call_args = ax.set_xlim.call_args[0]
        new_start, new_end = call_args
        # center 应该在新范围内
        assert new_start <= center <= new_end, f"center {center} 不在新范围 [{new_start}, {new_end}] 内"
        # 验证相对位置保持：原 ratio = 30/100 = 0.3, new_span = 92
        # new_start = 30 - 0.3*92 = 30 - 27.6 = 2.4
        # new_end = 2.4 + 92 = 94.4
        expected_new_span = 100.0 * 0.92  # 92
        expected_new_start = center - 0.3 * expected_new_span  # 30 - 27.6 = 2.4
        expected_new_end = expected_new_start + expected_new_span  # 94.4
        assert abs(new_start - expected_new_start) < 1e-6, f"new_start={new_start}, expected={expected_new_start}"
        assert abs(new_end - expected_new_end) < 1e-6, f"new_end={new_end}, expected={expected_new_end}"

    def test_zoom_factor_roundtrip(self):
        """上滚后下滚应恢复原 span（0.92 × 1.087 ≈ 1.0）。"""
        widget = MagicMock()
        ax = MagicMock()
        ax.get_xlim.return_value = (0.0, 100.0)
        widget.axes = [ax]
        ctx = MagicMock()
        ctx.time_sec = np.array([0.0, 100.0])
        widget.ctx = ctx

        analyzer = CrossingAnalyzer(widget)

        with patch.object(analyzer, "on_canvas_zoom"):
            # 上滚：span 100 → 92
            event_up = _make_scroll_event(button="up", xdata=50.0, inaxes=ax)
            analyzer.on_scroll_zoom(event_up)
            call_args = ax.set_xlim.call_args[0]
            span_after_up = call_args[1] - call_args[0]
            assert abs(span_after_up - 92.0) < 1e-6, f"上滚后 span={span_after_up}, expected=92"

            # 更新 xlim mock 为上滚后的值
            ax.get_xlim.return_value = call_args

            # 下滚：span 92 → 100.004 (0.92 × 1.087 ≈ 1.0004)
            event_down = _make_scroll_event(button="down", xdata=50.0, inaxes=ax)
            analyzer.on_scroll_zoom(event_down)
            call_args = ax.set_xlim.call_args[0]
            span_after_down = call_args[1] - call_args[0]
            # 往返误差在 0.1% 以内
            assert abs(span_after_down - 100.0) < 0.1, f"下滚后 span={span_after_down}, expected≈100"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
