"""parse_threshold_text 阈值解析纯函数测试（无 Qt 依赖）。"""

from __future__ import annotations

import math
from unittest.mock import MagicMock

import pytest

from ftpa.gui.main_window import parse_threshold_text


@pytest.mark.parametrize("text", ["", "   ", "\t\n"])
def test_empty_or_blank_returns_error(text):
    value, err = parse_threshold_text(text, "左阈值")
    assert value is None
    assert err is not None and "左阈值为空" in err


@pytest.mark.parametrize("text", ["abc", "1.2.3", "12abc", "--5"])
def test_invalid_number_returns_error(text):
    value, err = parse_threshold_text(text, "右阈值")
    assert value is None
    assert err is not None and "右阈值不是有效数字" in err


@pytest.mark.parametrize("text", ["nan", "inf", "-inf", "+inf", "NaN", "Infinity"])
def test_non_finite_returns_error(text):
    value, err = parse_threshold_text(text, "左阈值")
    assert value is None
    assert err is not None and "必须为有限数值" in err


@pytest.mark.parametrize(
    "text,expected",
    [
        ("3.14", 3.14),
        ("  -5 ", -5.0),
        ("1e3", 1000.0),
        ("0", 0.0),
        ("+2.5", 2.5),
    ],
)
def test_valid_number_parsed(text, expected):
    value, err = parse_threshold_text(text, "左阈值")
    assert err is None
    assert value == expected


def test_finite_check_matches_math_isfinite():
    """非有限值与 math.isfinite 判定一致。"""
    for text in ("nan", "inf", "-inf"):
        value, _ = parse_threshold_text(text, "左阈值")
        assert value is None or math.isfinite(value)


# ── 集成：MainWindow 空阈值点应用不触发穿越缩放 ──


def _setup_master(main_window):
    """让 master_combo 有选中项，使穿越流程能走到 apply_crossing 调用点。"""
    main_window._combo_label_to_field = {"信号": "sig"}
    main_window.master_combo.clear()
    main_window.master_combo.addItem("信号")


def test_empty_threshold_blocks_apply(main_window):
    """左阈值为空时点应用：不调用 apply_crossing，并提示。"""
    main_window.plot_widget.apply_crossing = MagicMock()
    _setup_master(main_window)
    main_window.right_threshold.setText("5.0")

    main_window._on_apply_crossing()

    main_window.plot_widget.apply_crossing.assert_not_called()
    assert "左阈值为空" in main_window.info_display.toPlainText()


def test_invalid_threshold_blocks_apply(main_window):
    """右阈值非法时点应用：不调用 apply_crossing，并提示。"""
    main_window.plot_widget.apply_crossing = MagicMock()
    _setup_master(main_window)
    main_window.left_threshold.setText("1.0")
    main_window.right_threshold.setText("abc")

    main_window._on_apply_crossing()

    main_window.plot_widget.apply_crossing.assert_not_called()
    assert "右阈值不是有效数字" in main_window.info_display.toPlainText()


def test_valid_thresholds_reach_apply(main_window):
    """左右阈值均合法时正常调起 apply_crossing。"""
    main_window.plot_widget.apply_crossing = MagicMock()
    _setup_master(main_window)
    main_window.left_threshold.setText("1")
    main_window.right_threshold.setText("2")

    main_window._on_apply_crossing()

    main_window.plot_widget.apply_crossing.assert_called_once()
    args = main_window.plot_widget.apply_crossing.call_args.args
    assert args[0] == 1.0 and args[2] == 2.0
    assert args[4] == "sig"
