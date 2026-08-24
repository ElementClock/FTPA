"""ParameterTreeWidget 参数树测试。"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from ftpa.gui.widgets import ParameterTreeWidget


def _app() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


class TestSetParamsFiltering:
    """set_params 的可用性过滤测试。"""

    def setup_method(self):
        self._app = _app()

    @staticmethod
    def _visible_fields(tree: ParameterTreeWidget) -> list[str]:
        return [
            tree.tree.topLevelItem(i).data(0, Qt.UserRole)
            for i in range(tree.tree.topLevelItemCount())
        ]

    def test_unavailable_fields_hidden(self):
        """当前数据不包含的参数不应显示（而非置灰）。"""
        tree = ParameterTreeWidget()
        labels = {"sig_a": "信号A", "sig_b": "信号B", "sig_c": "信号C"}
        tree.set_params(labels, available_fields={"sig_a", "sig_c"})

        visible = self._visible_fields(tree)
        assert set(visible) == {"sig_a", "sig_c"}
        assert "sig_b" not in visible
        assert tree.tree.topLevelItemCount() == 2

    def test_none_shows_all(self):
        """available_fields 为 None 时全部显示（保持旧行为）。"""
        tree = ParameterTreeWidget()
        labels = {"sig_a": "信号A", "sig_b": "信号B"}
        tree.set_params(labels, available_fields=None)
        assert tree.tree.topLevelItemCount() == 2

    def test_field_map_consistent_with_visible_items(self):
        """_field_map 应只包含可见参数，保证搜索/点击/拖拽一致。"""
        tree = ParameterTreeWidget()
        labels = {"sig_a": "信号A", "sig_b": "信号B"}
        tree.set_params(labels, available_fields={"sig_b"})

        assert set(tree._field_map.keys()) == {"信号B"}
        assert tree._field_map["信号B"] == "sig_b"
