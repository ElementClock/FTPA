"""
可复用的 PySide6 控件组件
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QLineEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)


class ParameterTreeWidget(QWidget):
    """参数树面板：搜索 + 树形列表。"""

    # 信号
    param_selected = Signal(str)       # 参数 field_name

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._field_map: dict[str, str] = {}         # display_label -> field_name
        self._selected_subplot: int | None = None
        self._subplot_fields: dict[int, list[str]] = {}
        self._selected_param: str | None = None
        self._build_ui()

        # 拖拽辅助：安装在 tree.viewport() 上，处理拖拽发起
        from ._drop_ctrl import TreeDragHelper
        self._drag_helper = TreeDragHelper(self)
        self.tree.viewport().installEventFilter(self._drag_helper)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        # 搜索框
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("搜索参数...")
        self.search_box.textChanged.connect(self._on_search)
        layout.addWidget(self.search_box)

        # 参数树
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setRootIsDecorated(False)
        self.tree.setAnimated(True)
        self.tree.setSelectionMode(QTreeWidget.SingleSelection)
        self.tree.itemClicked.connect(self._on_item_clicked)
        layout.addWidget(self.tree, 1)

    def set_params(self, field_labels: dict[str, str], available_fields: set[str] | None = None):
        """设置参数列表：field_name -> display_label。

        Args:
            field_labels: 字段名 -> 显示标签（可含单位）。
            available_fields: 当前数据中可用的字段名集合；不在集合中的参数置灰不可选。
                为 None 时全部可用（保持旧行为）。
        """
        self._field_map = {}
        self.tree.clear()
        for field_name, display_label in sorted(field_labels.items(), key=lambda x: x[1]):
            self._field_map[display_label] = field_name
            item = QTreeWidgetItem([display_label])
            item.setData(0, Qt.UserRole, field_name)
            if available_fields is not None and field_name not in available_fields:
                # 参数库中存在但当前数据中不存在：置灰、不可选、不可拖拽
                item.setFlags(item.flags() & ~Qt.ItemIsEnabled)
                item.setForeground(0, QBrush(QColor("#999999")))
            else:
                item.setFlags(item.flags() | Qt.ItemIsSelectable)
            self.tree.addTopLevelItem(item)

    def clear_params(self) -> None:
        """清空参数列表和数据映射。"""
        self._field_map = {}
        self.tree.clear()

    def update_indicators(self, subplot_fields: dict[int, list[str]]):
        """更新树中每个参数的使用状态指示器。"""
        self._subplot_fields = subplot_fields
        # 构建 field_name -> list of subplot indices
        field_to_subplots: dict[str, list[int]] = {}
        for idx, fields in subplot_fields.items():
            for f in fields:
                field_to_subplots.setdefault(f, []).append(idx + 1)  # 1-based

        for i in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(i)
            if item is None:
                continue
            field_name = item.data(0, Qt.UserRole)
            display = item.text(0)
            # 去掉可能已有的后缀
            base_display = display.split("  (子图")[0].strip()
            if field_name in field_to_subplots:
                subplot_str = ", ".join(str(s) for s in field_to_subplots[field_name])
                item.setText(0, f"{base_display}  (子图 {subplot_str})")
                # 加粗显示
                f = item.font(0)
                f.setBold(True)
                item.setFont(0, f)
            else:
                item.setText(0, base_display)
                f = item.font(0)
                f.setBold(False)
                item.setFont(0, f)

    def set_selected_subplot(self, idx: int | None):
        """设置当前选中的子图索引。"""
        self._selected_subplot = idx

    def _on_search(self, text: str):
        """搜索过滤：隐藏不匹配的参数项。"""
        for i in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(i)
            if item is None:
                continue
            if not text or text.lower() in item.text(0).lower():
                item.setHidden(False)
            else:
                item.setHidden(True)

    def _on_item_clicked(self, item: QTreeWidgetItem, _column: int):
        """参数树点击处理。"""
        field_name = item.data(0, Qt.UserRole)
        self._selected_param = field_name
        self.param_selected.emit(field_name)