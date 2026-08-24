"""MainWindow 视图状态持久化测试（曲线预览可见性等）。

主窗口夹具与 FakeCloseEvent 由 conftest.py 共享提供。
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from PySide6.QtCore import QSettings

from ftpa.gui.main_window import MainWindow
from tests.conftest import FakeCloseEvent


def test_default_preview_hidden_when_no_settings(main_window):
    """无历史记录启动：曲线预览默认关闭且菜单项未勾选。"""
    assert main_window._act_preview.isChecked() is False
    # 未 show 的父窗口下用 isHidden 判断显式可见性
    assert main_window.preview_panel.isHidden() is True


def test_preview_restored_visible_from_settings(main_window):
    """历史记录为 True 时启动：预览区恢复显示且菜单项勾选。"""
    from PySide6.QtCore import QSettings

    QSettings("FTPA", "FTPA").setValue("preview_panel_visible", True)

    # 重新构造一个窗口读取已写入的设置
    win = MainWindow()
    try:
        assert win._act_preview.isChecked() is True
        assert win.preview_panel.isHidden() is False
    finally:
        win.deleteLater()


def test_menu_toggle_updates_panel_and_action(main_window):
    """菜单 trigger（用户真实路径）同步切换面板与勾选态。"""
    main_window._act_preview.trigger()
    assert main_window._act_preview.isChecked() is True
    assert main_window.preview_panel.isHidden() is False

    main_window._act_preview.trigger()
    assert main_window._act_preview.isChecked() is False
    assert main_window.preview_panel.isHidden() is True


def test_visible_state_persists_via_close_event(main_window):
    """打开预览后经 closeEvent 落盘，QSettings 读回 True。"""
    main_window._act_preview.trigger()
    # isVisible 依赖整条祖先链可见，show 后再关闭才与真实路径一致
    main_window.show()
    main_window.closeEvent(FakeCloseEvent())
    saved = QSettings("FTPA", "FTPA").value("preview_panel_visible", None, type=bool)
    assert saved is True


def test_hidden_preview_skips_refresh(main_window):
    """预览面板隐藏时点选参数不触发任何预览刷新。"""
    calls = []
    main_window.preview_panel.show()
    main_window.preview_panel.preview_field = lambda f: calls.append(f)
    main_window.data_context = None

    main_window._on_param_selected_for_preview("sig")  # 面板可见但未加载 → 清空分支
    assert calls == []

    main_window.preview_panel.hide()
    main_window._on_param_selected_for_preview("sig")  # 面板隐藏 → 直接跳过
    assert calls == []


# ── 区间分析时间区间标签同步（问题5）──


def test_view_range_changed_updates_interval_label(main_window):
    """窗口缩放/平移后区间标签应实时同步为当前视图范围。"""
    ctx = MagicMock()
    ctx.is_loaded = True
    main_window.data_context = ctx
    main_window.plot_widget.axes[0].set_xlim(100.0, 200.0)

    main_window.plot_widget.view_range_changed.emit(100.0, 200.0)

    assert main_window.analysis_interval_label.text() == \
        "区间: 00:01:40.000 - 00:03:20.000"
    assert "当前视图" not in main_window.analysis_interval_label.text()


def test_view_range_changed_ignored_when_no_data(main_window):
    """数据未加载时视图变化不修改区间标签。"""
    main_window.analysis_interval_label.setText("区间: 当前视图")
    main_window.data_context = None

    main_window.plot_widget.view_range_changed.emit(100.0, 200.0)

    assert "当前视图" in main_window.analysis_interval_label.text()


def test_region_selection_takes_priority_over_view(main_window):
    """有框选区域时区间标签显示区域范围（优先于视图 xlim）。"""
    ctx = MagicMock()
    ctx.is_loaded = True
    main_window.data_context = ctx
    main_window.plot_widget.has_region_selection = lambda: True
    main_window.plot_widget.get_region_time_range = lambda: (30.0, 70.0)

    main_window.plot_widget.view_range_changed.emit(100.0, 200.0)

    text = main_window.analysis_interval_label.text()
    assert "当前视图" not in text