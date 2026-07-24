"""
可复用的 PySide6 控件组件
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QSortFilterProxyModel, QStringListModel, Signal
from PySide6.QtGui import QStandardItem, QStandardItemModel, QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListView,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)


class TimeWindowCtrl(QWidget):
    """时间窗口控件：起始/结束时间输入 + 全时段勾选。"""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        gb = QGroupBox("时间窗口", self)
        layout = QVBoxLayout(gb)

        row1 = QHBoxLayout()
        row1.addWidget(QLabel("起始:"))
        self.t_start = QLineEdit()
        self.t_start.setPlaceholderText("HH:MM:SS.mmm")
        row1.addWidget(self.t_start)
        row1.addWidget(QLabel("结束:"))
        self.t_end = QLineEdit()
        self.t_end.setPlaceholderText("HH:MM:SS.mmm")
        row1.addWidget(self.t_end)
        layout.addLayout(row1)

        row2 = QHBoxLayout()
        self.full_range = QCheckBox("全时段")
        self.full_range.setChecked(True)
        row2.addWidget(self.full_range)
        layout.addLayout(row2)

        # 全时段时禁用输入
        self.full_range.toggled.connect(self.t_start.setDisabled)
        self.full_range.toggled.connect(self.t_end.setDisabled)

        outer = QVBoxLayout(self)
        outer.addWidget(gb)

    def get_time_range(self) -> tuple[str | None, str | None]:
        """返回 (t_start, t_end)，全时段返回 (None, None)。"""
        if self.full_range.isChecked():
            return None, None
        return self.t_start.text().strip() or None, self.t_end.text().strip() or None

    def set_time_range(self, t_start: str | None, t_end: str | None):
        if t_start is None or t_end is None:
            self.full_range.setChecked(True)
        else:
            self.full_range.setChecked(False)
            self.t_start.setText(t_start)
            self.t_end.setText(t_end)


class SignalSearchPanel(QWidget):
    """信号搜索+过滤+勾选列表面板。"""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._signals: list[str] = []
        self._model = QStandardItemModel()
        self._proxy = QSortFilterProxyModel()
        self._proxy.setFilterCaseSensitivity(Qt.CaseInsensitive)
        self._proxy.setSourceModel(self._model)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("搜索信号...")
        self.search_box.textChanged.connect(self._on_search)
        layout.addWidget(self.search_box)

        self.list_view = QListView()
        self.list_view.setModel(self._proxy)
        self.list_view.setEditTriggers(QListView.NoEditTriggers)
        layout.addWidget(self.list_view, 1)

    def _on_search(self, text: str):
        self._proxy.setFilterFixedString(text)

    def set_signals(self, signal_names: list[str]):
        """设置全部信号列表（替换）。"""
        self._signals = list(signal_names)
        self._model.clear()
        for name in self._signals:
            item = QStandardItem(name)
            item.setCheckable(True)
            item.setCheckState(Qt.Unchecked)
            self._model.appendRow(item)

    def get_checked(self) -> list[str]:
        """返回当前勾选的信号名。"""
        checked: list[str] = []
        for row in range(self._model.rowCount()):
            item = self._model.item(row)
            if item and item.checkState() == Qt.Checked:
                checked.append(item.text())
        return checked

    def set_checked(self, signal_names: list[str]):
        """勾选指定信号。"""
        checked_set = set(signal_names)
        for row in range(self._model.rowCount()):
            item = self._model.item(row)
            if item:
                item.setCheckState(Qt.Checked if item.text() in checked_set else Qt.Unchecked)

    def get_all_signals(self) -> list[str]:
        return list(self._signals)

    def signal_checked_changed(self, callback):
        """连接勾选变化信号。"""
        self._model.itemChanged.connect(callback)  # type: ignore

    @property
    def model(self):
        return self._model


class CrossingCtrl(QWidget):
    """穿越控制组件（单个阈值+模式）。"""

    def __init__(self, label: str, parent: QWidget | None = None):
        super().__init__(parent)
        self._build_ui(label)

    def _build_ui(self, label: str):
        hbox = QHBoxLayout(self)
        hbox.setContentsMargins(0, 0, 0, 0)
        hbox.addWidget(QLabel(label))

        self.threshold = QLineEdit()
        self.threshold.setPlaceholderText("阈值")
        self.threshold.setFixedWidth(80)
        hbox.addWidget(self.threshold)

        self.mode = QComboBox()
        self.mode.addItems(["FirstUp", "LastUp", "FirstDown", "LastDown"])
        self.mode.setCurrentText("FirstUp")
        hbox.addWidget(self.mode)

    def get_value(self) -> tuple[float, str]:
        try:
            val = float(self.threshold.text())
        except (ValueError, TypeError):
            val = 0.0
        return val, self.mode.currentText()

    def set_value(self, threshold: float, mode: str):
        self.threshold.setText(str(threshold))
        if mode in ["FirstUp", "LastUp", "FirstDown", "LastDown"]:
            self.mode.setCurrentText(mode)

    def clear(self):
        self.threshold.clear()


class ParameterTreeWidget(QWidget):
    """参数树面板：搜索 + 树形列表 + 加入/删除按钮。"""

    # 信号
    add_clicked = Signal(str)          # 参数 field_name
    remove_clicked = Signal(str)       # 参数 field_name
    clear_clicked = Signal()           # 清空当前选中子图所有参数
    param_selected = Signal(str)       # 参数 field_name

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._field_map: dict[str, str] = {}         # display_label -> field_name
        self._selected_subplot: int | None = None
        self._subplot_fields: dict[int, list[str]] = {}
        self._selected_param: str | None = None
        self._build_ui()

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

        # 加入/删除按钮
        btn_layout = QHBoxLayout()
        self.add_btn = QPushButton("加入")
        self.add_btn.setEnabled(False)
        self.add_btn.clicked.connect(self._on_add)
        btn_layout.addWidget(self.add_btn)

        self.remove_btn = QPushButton("删除")
        self.remove_btn.setEnabled(False)
        self.remove_btn.clicked.connect(self._on_remove)
        btn_layout.addWidget(self.remove_btn)

        self.clear_btn = QPushButton("清空")
        self.clear_btn.setEnabled(False)
        self.clear_btn.clicked.connect(self._on_clear)
        btn_layout.addWidget(self.clear_btn)

        layout.addLayout(btn_layout)

    def set_params(self, field_labels: dict[str, str]):
        """设置参数列表：field_name -> display_label。"""
        self._field_map = {}
        self.tree.clear()
        for field_name, display_label in sorted(field_labels.items(), key=lambda x: x[1]):
            self._field_map[display_label] = field_name
            item = QTreeWidgetItem([display_label])
            item.setData(0, Qt.UserRole, field_name)
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
        self._update_button_states()

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
        self._update_button_states()

    def _on_add(self):
        if self._selected_param:
            self.add_clicked.emit(self._selected_param)

    def _on_remove(self):
        if self._selected_param:
            self.remove_clicked.emit(self._selected_param)

    def _on_clear(self):
        self.clear_clicked.emit()

    def _update_button_states(self):
        """根据当前选择状态更新按钮启用/禁用。"""
        subplot_selected = self._selected_subplot is not None
        param_selected = self._selected_param is not None

        if not subplot_selected or not param_selected:
            self.add_btn.setEnabled(False)
            self.remove_btn.setEnabled(False)
            self._update_clear_btn()
            return

        # 检查参数是否已在选中的子图中
        in_subplot = False
        if self._selected_subplot in self._subplot_fields:
            in_subplot = self._selected_param in self._subplot_fields[self._selected_subplot]

        self.add_btn.setEnabled(not in_subplot)
        self.remove_btn.setEnabled(in_subplot)
        self._update_clear_btn()

    def _update_clear_btn(self):
        """更新清空按钮状态：需要选中子图且子图内有信号。"""
        subplot_selected = self._selected_subplot is not None
        has_fields = False
        if subplot_selected and self._selected_subplot in self._subplot_fields:
            has_fields = len(self._subplot_fields[self._selected_subplot]) > 0
        self.clear_btn.setEnabled(subplot_selected and has_fields)


class StatsTableWidget(QTableWidget):
    """参数统计结果表格（7 列预定义）。"""

    COLUMNS = ["信号名", "起始值", "结束值", "最小值", "最大值", "平均值", "标准差", "点数"]

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setColumnCount(len(self.COLUMNS))
        self.setHorizontalHeaderLabels(self.COLUMNS)
        self.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.setEditTriggers(QTableWidget.NoEditTriggers)
        self.setAlternatingRowColors(True)

    def populate(self, stats_lines: list[str]):
        """从 statistics_params 的字符串列表填充表格。"""
        self.setRowCount(0)
        for line in stats_lines:
            # 格式例如: "信号名  起始值  结束值  最小值  最大值  平均值  标准差  点数"
            parts = line.split("\t")
            if len(parts) < 2:
                continue
            row = self.rowCount()
            self.insertRow(row)
            for col, part in enumerate(parts):
                if col < self.columnCount():
                    self.setItem(row, col, QTableWidgetItem(part.strip()))

    def clear_data(self):
        self.setRowCount(0)
