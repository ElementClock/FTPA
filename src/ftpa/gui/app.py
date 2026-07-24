"""
FTPA GUI 入口 — 保持与原有 main.py --gui 兼容的接口。
"""

from __future__ import annotations

import sys


def main(dry_run: bool = False) -> int:
    """启动 PySide6 GUI 主窗口。

    保持与旧版 wxPython 相同的签名：main(dry_run=False) -> int。
    """
    if dry_run:
        print("GUI dry run: PySide6 GUI entrypoint is ready.")
        return 0

    from PySide6.QtGui import QFont
    from PySide6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    app.setApplicationName("FTPA")
    app.setOrganizationName("FTPA Team")

    # 全局字体：微软雅黑 Light 降级链
    font = QFont()
    font.setFamilies(["Microsoft YaHei Light", "Microsoft YaHei", "SimHei", "Arial"])
    font.setPointSize(9)
    app.setFont(font)

    from .main_window import MainWindow

    window = MainWindow(dry_run=dry_run)

    # 安装 GUI 日志桥接：logging → info_display
    from .log_handler import install_gui_logger
    install_gui_logger(window._append_log)

    window.show()
    rc = app.exec()

    # 显式清理顶层窗口，避免 matplotlib canvas 等 C++ 对象
    # 在 QApplication 销毁后才被释放，从而引发 0xC0000409 崩溃。
    window.close()
    window.deleteLater()
    app.processEvents()
    del window
    app = None
    return rc
