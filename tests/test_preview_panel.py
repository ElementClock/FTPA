"""PreviewPanel 曲线预览区测试。"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
from PySide6.QtWidgets import QApplication

from ftpa.gui.panel_preview import PreviewPanel


def _app() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


class _FakeLabelMap:
    def get_unit(self, field_name: str) -> str | None:
        return "m" if field_name == "sig" else None


class _FakeQuery:
    def __init__(self):
        self._label_map = _FakeLabelMap()

    def get_time_sec(self):
        return np.linspace(0, 10, 11)

    def get_signal_data(self, field_name: str):
        return np.linspace(0, 10, 11) if field_name == "sig" else None

    def get_label_map(self):
        return self._label_map


class _FakeCtx:
    is_loaded = True

    def __init__(self):
        self.query = _FakeQuery()

    def get_label(self, field_name: str) -> str:
        return "信号" if field_name == "sig" else field_name


class TestPreviewPanel:
    def setup_method(self):
        self._app = _app()

    def test_preview_field_draws_curve(self):
        panel = PreviewPanel()
        panel.set_data_context(_FakeCtx())
        panel.preview_field("sig")
        assert len(panel.figure.axes) == 1
        ax = panel.figure.axes[0]
        # 预览区不显示参数名/时间/刻度，最大化曲线区域
        assert ax.get_title() == ""
        assert ax.get_xlabel() == ""
        assert ax.get_ylabel() == ""

    def test_preview_missing_field_shows_placeholder(self):
        panel = PreviewPanel()
        panel.set_data_context(_FakeCtx())
        panel.preview_field("missing")
        assert len(panel.figure.axes) == 1

    def test_clear_preview(self):
        panel = PreviewPanel()
        panel.set_data_context(_FakeCtx())
        panel.preview_field("sig")
        panel.clear_preview()
        assert len(panel.figure.axes) == 1
