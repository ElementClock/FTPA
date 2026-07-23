"""
Tab 1: 数据与配置 — 文件选择、加载数据、信号列表、时间窗口、重量重心覆盖。
"""

from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import Qt, QThread
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ..constants import BASE_OIL, BASE_REL_CG, BASE_WEIGHT
from ..utils.paths import resolve_excel_path
from .widgets import SignalSearchPanel, TimeWindowCtrl


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_TXT = PROJECT_ROOT / "FTPD-AG600-007-QD-260509-G-1-飞机性能操稳-32.txt"
DEFAULT_EXCEL = resolve_excel_path()


class DataConfigPanel(QWidget):
    """数据与配置 Tab。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._data_loaded = False
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        # -- 文件配置 --
        gb = QGroupBox("文件配置")
        fl = QFormLayout(gb)

        row_data = QHBoxLayout()
        self.data_path = QLineEdit(str(DEFAULT_TXT))
        row_data.addWidget(self.data_path)
        btn_data = QPushButton("浏览")
        btn_data.clicked.connect(self._browse_data)
        row_data.addWidget(btn_data)
        fl.addRow("数据文件:", row_data)

        row_excel = QHBoxLayout()
        self.excel_path = QLineEdit(str(DEFAULT_EXCEL))
        row_excel.addWidget(self.excel_path)
        btn_excel = QPushButton("浏览")
        btn_excel.clicked.connect(self._browse_excel)
        row_excel.addWidget(btn_excel)
        fl.addRow("标签文件:", row_excel)

        layout.addWidget(gb)

        # -- 重量重心覆盖 --
        gb_w = QGroupBox("重量重心参数（可选覆盖）")
        wl = QHBoxLayout(gb_w)
        wl.addWidget(QLabel("基本重量:"))
        self.base_w = QSpinBox()
        self.base_w.setRange(0, 100000)
        self.base_w.setValue(int(BASE_WEIGHT))
        self.base_w.setSuffix(" kg")
        wl.addWidget(self.base_w)
        wl.addWidget(QLabel("重心:"))
        self.base_cg = QSpinBox()
        self.base_cg.setRange(0, 100)
        self.base_cg.setValue(int(BASE_REL_CG))
        self.base_cg.setSuffix(" %")
        wl.addWidget(self.base_cg)
        wl.addWidget(QLabel("油量:"))
        self.base_oil = QSpinBox()
        self.base_oil.setRange(0, 20000)
        self.base_oil.setValue(int(BASE_OIL))
        self.base_oil.setSuffix(" kg")
        wl.addWidget(self.base_oil)
        btn_reset = QPushButton("恢复默认")
        btn_reset.clicked.connect(self._reset_weight_cg)
        wl.addWidget(btn_reset)
        wl.addStretch()
        layout.addWidget(gb_w)

        # -- 操作按钮 --
        btn_row = QHBoxLayout()
        self.load_btn = QPushButton("加载数据")
        self.load_btn.clicked.connect(self._load_data)
        btn_row.addWidget(self.load_btn)
        self.verify_btn = QPushButton("快速验证")
        self.verify_btn.clicked.connect(self._quick_verify)
        btn_row.addWidget(self.verify_btn)
        self.status_label = QLabel("状态: 就绪")
        btn_row.addWidget(self.status_label)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        # -- 信号搜索面板 --
        self.signal_panel = SignalSearchPanel()
        layout.addWidget(self.signal_panel, 1)

        # -- 数据预览 --
        self.preview = QTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setMaximumHeight(150)
        self.preview.setPlaceholderText("加载数据后显示预览信息...")
        layout.addWidget(self.preview)

    def _browse_data(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择数据文件", "", "文本文件 (*.txt);;所有文件 (*)")
        if path:
            self.data_path.setText(path)

    def _browse_excel(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择标签文件", "", "Excel 文件 (*.xlsx *.xls);;所有文件 (*)")
        if path:
            self.excel_path.setText(path)

    def _reset_weight_cg(self):
        self.base_w.setValue(int(BASE_WEIGHT))
        self.base_cg.setValue(int(BASE_REL_CG))
        self.base_oil.setValue(int(BASE_OIL))

    def _set_status(self, text: str):
        self.status_label.setText(f"状态: {text}")

    def _load_data(self):
        """后台线程加载数据，完成后刷新信号列表。"""
        from .worker import DataLoaderWorker, QThread

        dp = self.data_path.text().strip()
        ep = self.excel_path.text().strip()
        if not os.path.exists(dp):
            QMessageBox.warning(self, "文件错误", f"数据文件不存在:\n{dp}")
            return

        self._set_status("加载中...")
        self.load_btn.setEnabled(False)
        self.verify_btn.setEnabled(False)
        self.preview.clear()

        self._load_thread = QThread()
        self._load_worker = DataLoaderWorker(dp, ep)
        self._load_worker.moveToThread(self._load_thread)
        self._load_worker.progress.connect(lambda p, m: self._set_status(m))
        self._load_worker.finished.connect(self._on_load_finished)
        self._load_thread.started.connect(self._load_worker.run)
        self._load_worker.finished.connect(self._load_thread.quit)
        self._load_worker.finished.connect(self._load_worker.deleteLater)
        self._load_thread.finished.connect(self._load_thread.deleteLater)
        self._load_thread.start()

    def _on_load_finished(self, ok: bool, msg: str):
        self.load_btn.setEnabled(True)
        self.verify_btn.setEnabled(True)

        if not ok:
            self._set_status("加载失败")
            QMessageBox.critical(self, "加载失败", msg)
            return

        from .services import DataContext

        ctx = DataContext()
        ctx.load(self.data_path.text().strip(), self.excel_path.text().strip())
        self._data_loaded = True

        # 填充信号列表
        field_labels = ctx.get_field_labels()
        display_names = []
        for f in ctx.get_field_names():
            display_names.append(field_labels.get(f, f))
        self.signal_panel.set_signals(display_names)

        # 显示预览
        lines = [
            f"数据文件: {ctx.data_path}",
            f"行数: {ctx.get_row_count()}, 列数: {ctx.get_column_count()}",
            f"时间范围: {ctx.get_time_range_sec()[0]:.1f}s - {ctx.get_time_range_sec()[1]:.1f}s",
            f"信号数量: {len(display_names)}",
        ]
        self.preview.setPlainText("\n".join(lines))
        self._set_status(f"已加载: {ctx.get_row_count()} 行, {ctx.get_column_count()} 列")

        # 通过父窗口广播加载完成事件
        parent = self.parent()
        while parent and not hasattr(parent, 'on_data_loaded'):
            parent = parent.parent()
        if parent and hasattr(parent, 'on_data_loaded'):
            parent.on_data_loaded(ctx)

    def _quick_verify(self):
        """快速验证：读取文件头 + 前5行。"""
        dp = self.data_path.text().strip()
        if not os.path.exists(dp):
            # 友好占位
            self.preview.setPlainText("文件不存在，已启用友好占位模式。\n请提供有效的数据文件路径。")
            self._set_status("文件不存在")
            return

        try:
            with open(dp, "r", encoding="utf-8") as f:
                header = f.readline().strip()
            cols = header.split("\t")
            self.preview.setPlainText(
                f"文件: {dp}\n"
                f"总列数: {len(cols)}\n"
                f"前10列: {', '.join(cols[:10])}\n"
                f"后10列: {', '.join(cols[-10:])}"
            )
            self._set_status("验证完成")
        except Exception as e:
            self.preview.setPlainText(f"验证失败: {e}")
            self._set_status("验证失败")

    def get_selected_signals(self) -> list[str]:
        """返回用户勾选的信号列表。"""
        return self.signal_panel.get_checked()
