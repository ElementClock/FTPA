"""ParameterPickerDialog 搜索式参数选择对话框测试。"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from ftpa.gui.parameter_picker import ParameterPickerDialog


def _app() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


class TestParameterPickerDialog:
    def setup_method(self):
        self._app = _app()

    def test_unavailable_item_disabled(self):
        dialog = ParameterPickerDialog(
            field_labels={"FIELD_A": "参数A", "FIELD_B": "参数B (m)"},
            available_fields={"FIELD_A"},
        )
        items = {
            dialog.list_widget.item(i).data(Qt.UserRole): dialog.list_widget.item(i)
            for i in range(dialog.list_widget.count())
        }
        assert items["FIELD_A"].flags() & Qt.ItemIsEnabled
        assert not (items["FIELD_B"].flags() & Qt.ItemIsEnabled)

    def test_search_filters_items(self):
        dialog = ParameterPickerDialog(
            field_labels={"FIELD_A": "参数A", "FIELD_B": "参数B (m)"},
            available_fields={"FIELD_A", "FIELD_B"},
        )
        dialog.search_box.setText("参数B")
        visible = [
            dialog.list_widget.item(i).text()
            for i in range(dialog.list_widget.count())
            if not dialog.list_widget.item(i).isHidden()
        ]
        assert visible == ["参数B (m)"]

    def test_accept_selects_enabled_item(self):
        dialog = ParameterPickerDialog(
            field_labels={"FIELD_A": "参数A", "FIELD_B": "参数B (m)"},
            available_fields={"FIELD_A"},
        )
        for i in range(dialog.list_widget.count()):
            item = dialog.list_widget.item(i)
            if item.data(Qt.UserRole) == "FIELD_A":
                dialog.list_widget.setCurrentItem(item)
                break
        dialog._on_accept()
        assert dialog.selected_field() == "FIELD_A"
