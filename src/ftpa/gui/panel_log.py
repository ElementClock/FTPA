"""
Tab 7: 结果与日志 — 纯文本摘要 + 日志控制台 + 清空/复制按钮。
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from PySide6.QtGui import QClipboard


class LogPanel(QWidget):
    """结果与日志面板。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        # 摘要区域
        self.summary = QTextEdit()
        self.summary.setReadOnly(True)
        self.summary.setMaximumHeight(120)
        self.summary.setPlaceholderText("分析摘要将显示在这里...")
        layout.addWidget(self.summary)

        # 按钮行
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_clear = QPushButton("清空日志")
        btn_clear.clicked.connect(self.clear_log)
        btn_row.addWidget(btn_clear)
        btn_copy = QPushButton("复制日志")
        btn_copy.clicked.connect(self.copy_log)
        btn_row.addWidget(btn_copy)
        layout.addLayout(btn_row)

        # 日志区域
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setPlaceholderText("欢迎使用 FTPA 分析系统\n操作日志将显示在这里...")
        layout.addWidget(self.log, 1)

    def set_summary(self, text: str):
        self.summary.setPlainText(text)

    def append_log(self, message: str):
        self.log.appendPlainText(str(message))

    def clear_log(self):
        self.log.clear()

    def copy_log(self):
        cb = QClipboard()
        cb.setText(self.log.toPlainText())

    def clear_summary(self):
        self.summary.clear()
