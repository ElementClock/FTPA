"""
Qt 桥接：将 Python logging 消息路由到 GUI 信息显示框。

安装：
    from ftpa.gui.log_handler import install_gui_logger
    install_gui_logger(window._append_log)

之后任何 logging.getLogger(__name__).info("…") 都会出现在 GUI 中。
"""

from __future__ import annotations

import logging

from PySide6.QtCore import QObject, Signal, Qt


class LogSignalEmitter(QObject):
    """跨线程信号载体。"""
    log_record = Signal(str)


class GuiLogHandler(logging.Handler):
    """logging.Handler → Qt Signal。"""

    def __init__(self, emitter: LogSignalEmitter):
        super().__init__()
        self._emitter = emitter
        # 不加时间戳——_append_log 已加
        self.setFormatter(logging.Formatter("%(message)s"))

    def emit(self, record: logging.LogRecord):
        try:
            msg = self.format(record)
            self._emitter.log_record.emit(msg)
        except Exception:
            self.handleError(record)


_installed_handlers: list[GuiLogHandler] = []


def install_gui_logger(sink) -> GuiLogHandler:
    """安装日志桥接。sink 是接收 str 的可调用对象（如 window._append_log）。"""
    emitter = LogSignalEmitter()
    # QueuedConnection 保证从工作线程安全发到主线程
    emitter.log_record.connect(sink, Qt.QueuedConnection)

    handler = GuiLogHandler(emitter)
    handler.setLevel(logging.INFO)

    root = logging.getLogger()
    root.addHandler(handler)
    _installed_handlers.append(handler)
    return handler


def uninstall_gui_logger(handler: GuiLogHandler) -> None:
    """移除日志桥接。"""
    root = logging.getLogger()
    root.removeHandler(handler)
    if handler in _installed_handlers:
        _installed_handlers.remove(handler)
