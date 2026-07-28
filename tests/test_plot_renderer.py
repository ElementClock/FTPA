"""PlotRenderer 辅助方法单元测试。

验证 V7 重构提取的 5 个辅助方法的正确性：
_compute_ylabel, _create_empty_text, _create_line_for_field,
_apply_legend, _render_subplot_from_scratch
"""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

# 确保 matplotlib 使用非交互后端
import matplotlib
matplotlib.use("Agg")

from ftpa.gui._plot_renderer import PlotRenderer


# ── Fixtures ──


@pytest.fixture
def mock_widget():
    """创建模拟 PlotCanvasWidget。"""
    w = MagicMock()
    w.subplot_fields = {0: ["ALT"], 1: []}
    w.ctx = MagicMock()
    w.ctx.get_label = lambda f: f"标签_{f}"
    w.ctx.data = {"ALT": np.array([1.0, 2.0, 3.0])}
    w.ctx.time_sec = np.array([0.0, 1.0, 2.0])
    w.axes = [MagicMock(), MagicMock()]
    return w


@pytest.fixture
def renderer(mock_widget):
    """创建 PlotRenderer 实例。"""
    r = PlotRenderer(mock_widget)
    return r


# ── _compute_ylabel ──


class TestComputeYlabel:
    def test_single_field_returns_label(self, renderer):
        result = renderer._compute_ylabel(["ALT"], 0)
        assert result == "标签_ALT"

    def test_multiple_fields_returns_subplot_label(self, renderer):
        result = renderer._compute_ylabel(["ALT", "SPD"], 2)
        assert result == "子图3"

    def test_empty_fields_returns_empty_string(self, renderer):
        result = renderer._compute_ylabel([], 0)
        assert result == ""


# ── _create_empty_text ──


class TestCreateEmptyText:
    def test_creates_text_and_caches(self, renderer, mock_widget):
        ax = MagicMock()
        mock_text = MagicMock()
        ax.text.return_value = mock_text

        result = renderer._create_empty_text(ax, 0)

        ax.text.assert_called_once()
        call_kwargs = ax.text.call_args
        assert "子图 1（空）" in call_kwargs[0][2]
        assert 0 in renderer._empty_text_cache
        assert renderer._empty_text_cache[0] is mock_text
        assert result is mock_text

    def test_text_uses_config_params(self, renderer, mock_widget):
        ax = MagicMock()
        ax.text.return_value = MagicMock()

        renderer._create_empty_text(ax, 1)

        call_kwargs = ax.text.call_args[1]
        assert "fontsize" in call_kwargs
        assert "alpha" in call_kwargs


# ── _create_line_for_field ──


class TestCreateLineForField:
    def test_creates_line_and_caches(self, renderer, mock_widget):
        ax = MagicMock()
        mock_line = MagicMock()
        ax.plot.return_value = [mock_line]

        crossing = set()
        result = renderer._create_line_for_field(ax, 0, "ALT", crossing)

        ax.plot.assert_called_once()
        assert (0, "ALT") in renderer._line_cache
        assert renderer._line_cache[(0, "ALT")] is mock_line
        assert "ALT" in crossing
        assert result is mock_line

    def test_returns_none_when_no_data(self, renderer, mock_widget):
        ax = MagicMock()
        # 数据不存在
        mock_widget.ctx.data = {}

        crossing = set()
        result = renderer._create_line_for_field(ax, 0, "NONEXIST", crossing)

        assert result is None
        ax.plot.assert_not_called()
        assert "NONEXIST" not in crossing

    def test_crossing_fields_optional(self, renderer, mock_widget):
        ax = MagicMock()
        ax.plot.return_value = [MagicMock()]

        # crossing_fields=None 不应报错
        result = renderer._create_line_for_field(ax, 0, "ALT", None)
        assert result is not None

    def test_no_crossing_fields_default(self, renderer, mock_widget):
        ax = MagicMock()
        ax.plot.return_value = [MagicMock()]

        # 不传 crossing_fields
        result = renderer._create_line_for_field(ax, 0, "ALT")
        assert result is not None


# ── _apply_legend ──


class TestApplyLegend:
    def test_no_legend_when_single_field(self, renderer):
        ax = MagicMock()
        ax.get_legend.return_value = None

        renderer._apply_legend(ax, ["ALT"])

        ax.legend.assert_not_called()

    def test_creates_legend_when_multiple_fields(self, renderer):
        ax = MagicMock()
        ax.get_legend.return_value = None

        renderer._apply_legend(ax, ["ALT", "SPD"])

        ax.legend.assert_called_once()

    def test_incremental_removes_old_legend(self, renderer):
        ax = MagicMock()
        old_legend = MagicMock()
        ax.get_legend.return_value = old_legend

        renderer._apply_legend(ax, ["ALT"], incremental=True)

        old_legend.remove.assert_called_once()
        ax.legend.assert_not_called()

    def test_incremental_rebuilds_legend(self, renderer):
        ax = MagicMock()
        old_legend = MagicMock()
        ax.get_legend.return_value = old_legend

        renderer._apply_legend(ax, ["ALT", "SPD"], incremental=True)

        old_legend.remove.assert_called_once()
        ax.legend.assert_called_once()


# ── _render_subplot_from_scratch ──


class TestRenderSubplotFromScratch:
    def test_with_fields_creates_lines_and_ylabel(self, renderer, mock_widget):
        ax = MagicMock()
        ax.plot.return_value = [MagicMock()]

        crossing = set()
        renderer._render_subplot_from_scratch(ax, 0, crossing)

        ax.plot.assert_called()  # 至少创建一条 Line2D
        ax.set_ylabel.assert_called_once_with("标签_ALT")
        assert "ALT" in crossing

    def test_with_empty_creates_text(self, renderer, mock_widget):
        ax = MagicMock()
        ax.text.return_value = MagicMock()

        crossing = set()
        renderer._render_subplot_from_scratch(ax, 1, crossing)

        ax.text.assert_called_once()
        ax.set_ylabel.assert_not_called()

    def test_legend_created_for_multiple_fields(self, renderer, mock_widget):
        ax = MagicMock()
        ax.plot.return_value = [MagicMock()]
        mock_widget.subplot_fields = {0: ["ALT", "SPD"]}

        crossing = set()
        renderer._render_subplot_from_scratch(ax, 0, crossing)

        ax.legend.assert_called_once()


# ── plot_subplot 委托验证 ──


class TestPlotSubplotDelegates:
    def test_delegates_to_render_from_scratch(self, renderer):
        with patch.object(renderer, "_render_subplot_from_scratch") as mock_render:
            ax = MagicMock()
            crossing = set()
            renderer.plot_subplot(ax, 0, crossing)

            mock_render.assert_called_once_with(ax, 0, crossing)


# ── _full_rebuild 委托验证 ──


class TestFullRebuildUsesRenderFromScratch:
    def test_clears_and_renders_each_subplot(self, renderer, mock_widget):
        with patch.object(renderer, "_render_subplot_from_scratch") as mock_render:
            with patch.object(renderer, "_apply_axis_decorations"):
                renderer._full_rebuild()

                # 每个子图应调用一次 _render_subplot_from_scratch
                assert mock_render.call_count == len(mock_widget.axes)
                for call_args in mock_render.call_args_list:
                    # 每次调用传入 crossing_fields 集合
                    assert isinstance(call_args[0][2], set)
