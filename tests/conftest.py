"""共享测试夹具 — offscreen MainWindow（保护用户真实 QSettings）。"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from ftpa.gui.main_window import MainWindow

# MainWindow 生命周期内会被读写/落盘的 QSettings 键，测试前后必须备份恢复
_SETTINGS_KEYS_TO_BACKUP = ("splitter_sizes", "preview_panel_visible")


def _app() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


class FakeCloseEvent:
    """closeEvent 所需的最小事件接口。"""

    def __init__(self):
        self._accepted = False

    def accept(self):
        self._accepted = True

    def ignore(self):
        self._accepted = False


@pytest.fixture()
def main_window():
    """创建 MainWindow，并在测试前后备份/恢复用户真实的 QSettings 值。"""
    _app()
    settings = QSettings("FTPA", "FTPA")
    backup = {k: settings.value(k) for k in _SETTINGS_KEYS_TO_BACKUP}
    for k in _SETTINGS_KEYS_TO_BACKUP:
        settings.remove(k)
    settings.sync()

    win = MainWindow()
    yield win
    win.deleteLater()

    settings = QSettings("FTPA", "FTPA")
    for k in _SETTINGS_KEYS_TO_BACKUP:
        if backup[k] is not None:
            settings.setValue(k, backup[k])
        else:
            settings.remove(k)
    settings.sync()
