"""MainWindow 信号下拉框测试：主穿越与区间分析目标信号同源复用。

共享 offscreen MainWindow 夹具来自 conftest.py。
"""

from __future__ import annotations

from unittest.mock import MagicMock

import numpy as np


class _FakeCtx:
    """最小 DataContext 模拟：提供 get_label。"""

    def __init__(self, labels: dict[str, str]):
        self._labels = labels

    def get_label(self, field: str) -> str:
        return self._labels.get(field, field)


def _attach_ctx(main_window, labels: dict[str, str]) -> None:
    """注入带中文标签映射的假数据上下文。"""
    main_window.data_context = _FakeCtx(labels)


def _set_subplots(main_window, mapping: dict[int, list[str]]) -> None:
    """设置子图字段（触发 subplot_fields_changed 信号 → 带动两个下拉刷新）。"""
    main_window.plot_widget.subplot_fields = mapping


def test_target_combo_lists_subplot_fields_only(main_window):
    """区间目标信号下拉只含已上图参数（不包含全量字段）。"""
    _attach_ctx(main_window, {"a": "A信号", "b": "B信号", "c": "C信号"})
    _set_subplots(main_window, {0: ["a", "c"]})

    items = [main_window.target_signal_combo.itemText(i)
             for i in range(main_window.target_signal_combo.count())]
    assert items == ["A信号", "C信号"]  # 按标签排序，b 未上图故不出现
    assert main_window.target_signal_combo.isEnabled() is True


def test_target_combo_mirrors_master_combo(main_window):
    """区间与主穿越下拉共享同一数据源与排序（同源复用）。"""
    _attach_ctx(main_window, {"a": "A信号", "b": "B信号"})
    _set_subplots(main_window, {0: ["a"], 1: ["b"]})

    target_items = [main_window.target_signal_combo.itemText(i)
                    for i in range(main_window.target_signal_combo.count())]
    master_items = [main_window.master_combo.itemText(i)
                    for i in range(main_window.master_combo.count())]
    assert target_items == master_items == ["A信号", "B信号"]


def test_empty_subplots_disables_all_controls(main_window):
    """无任何已上图参数时：两下拉 + 功能/执行按钮全部禁用。"""
    _attach_ctx(main_window, {"a": "A信号"})
    _set_subplots(main_window, {0: []})

    assert main_window.target_signal_combo.isEnabled() is False
    assert main_window.analysis_op_combo.isEnabled() is False
    assert main_window.analysis_run_btn.isEnabled() is False
    assert main_window.master_combo.isEnabled() is False


def test_clearing_subplots_does_not_reset_interval_label(main_window):
    """清空子图后区间标签不被下拉刷新重置（生命周期属于视图同步，见问题5）。"""
    _attach_ctx(main_window, {"a": "A信号"})
    main_window.analysis_interval_label.setText("区间: 10.5 - 20.5")
    _set_subplots(main_window, {0: []})

    assert "当前视图" not in main_window.analysis_interval_label.text()
    assert main_window.analysis_interval_label.text() == "区间: 10.5 - 20.5"


def test_combos_keep_selection_when_field_set_grows(main_window):
    """选中项仍存在于新字段集时，下拉刷新保持该选中项不被挤掉。"""
    _attach_ctx(main_window, {"a": "A信号", "b": "B信号", "c": "C信号"})
    _set_subplots(main_window, {0: ["a", "b"]})
    main_window.master_combo.setCurrentText("B信号")
    main_window.target_signal_combo.setCurrentText("B信号")

    _set_subplots(main_window, {0: ["a", "b", "c"]})  # 新增 c，b 仍存在
    assert main_window.master_combo.currentText() == "B信号"
    assert main_window.target_signal_combo.currentText() == "B信号"


def test_do_interval_analysis_resolves_field_via_mapping(main_window):
    """执行区间分析：从目标下拉反查 field，走当前视图区间并调用计算层。"""
    import ftpa.gui.main_window as mw_mod

    _attach_ctx(main_window, {"a": "A信号"})
    _set_subplots(main_window, {0: ["a"]})

    ctx = MagicMock()
    ctx.is_loaded = True
    time_sec = np.linspace(0, 10, 11)
    ctx.query.get_time_sec.return_value = time_sec
    ctx.query.get_signal_data.return_value = time_sec
    main_window.data_context = ctx

    orig = mw_mod.run_interval_analysis
    mw_mod.run_interval_analysis = MagicMock(return_value="OK")
    try:
        main_window.target_signal_combo.setCurrentText("A信号")
        main_window._do_interval_analysis()
        mw_mod.run_interval_analysis.assert_called_once()
        # label→field 反查正确（「A信号」→ "a"），且时间/值切片均来自当前视图窗口
        ctx.query.get_signal_data.assert_called_once_with("a")
        args = mw_mod.run_interval_analysis.call_args.args
        assert len(args[0]) == len(args[1]) > 0  # time 与 values 切片长度一致
    finally:
        mw_mod.run_interval_analysis = orig