"""搜索式参数选择对话框。

用于右键“添加参数...”场景：参数库较大时避免在 QMenu 中展开大量条目，
改为弹出一个带搜索框的对话框，用户可快速定位并选择参数。
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
)


class ParameterPickerDialog(QDialog):
    """参数选择对话框。

    Args:
        field_labels: 字段名 -> 显示标签（可含单位）。
        available_fields: 当前数据中可用的字段名集合；不在集合中的参数置灰不可选。
    """

    def __init__(
        self,
        parent=None,
        field_labels: dict[str, str] | None = None,
        available_fields: set[str] | None = None,
    ):
        super().__init__(parent)
        self._field_labels = field_labels or {}
        self._available_fields = available_fields
        self._selected_field: str | None = None

        self.setWindowTitle("添加参数")
        self.setMinimumWidth(460)
        self.setMinimumHeight(520)

        self._build_ui()
        self._populate()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("搜索参数（中文名 / 字段名 / 单位）...")
        self.search_box.textChanged.connect(self._on_search)
        layout.addWidget(self.search_box)

        self.list_widget = QListWidget()
        self.list_widget.setSelectionMode(QListWidget.SingleSelection)
        self.list_widget.itemDoubleClicked.connect(self._on_item_double_clicked)
        layout.addWidget(self.list_widget, 1)

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        self.button_box.accepted.connect(self._on_accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

    def _populate(self) -> None:
        self.list_widget.clear()
        for field, label in sorted(self._field_labels.items(), key=lambda x: x[1]):
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, field)
            if self._available_fields is not None and field not in self._available_fields:
                item.setFlags(item.flags() & ~Qt.ItemIsEnabled)
                item.setForeground(QBrush(QColor("#999999")))
            self.list_widget.addItem(item)

    def _on_search(self, text: str) -> None:
        keyword = text.strip().lower()
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            item.setHidden(bool(keyword) and keyword not in item.text().lower())

    def _on_item_double_clicked(self, item: QListWidgetItem) -> None:
        if item.flags() & Qt.ItemIsEnabled:
            self._selected_field = item.data(Qt.UserRole)
            self.accept()

    def _on_accept(self) -> None:
        item = self.list_widget.currentItem()
        if item is not None and (item.flags() & Qt.ItemIsEnabled):
            self._selected_field = item.data(Qt.UserRole)
            self.accept()

    def selected_field(self) -> str | None:
        """返回选中的字段名；未选择或取消时返回 None。"""
        return self._selected_field
