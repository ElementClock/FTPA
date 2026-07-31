"""
主程序：飞机性能操稳数据分析工具
入口 — 默认启动 GUI，支持 --dry-run 模式。

CLI 分析模式（verify/chunked/analysis/stats/interactive）已归档到 references/cli/。
"""

import sys


def main() -> int:
    """启动 FTPA 应用（默认 GUI 模式）。"""
    try:
        from PySide6 import QtWidgets  # noqa: F401
    except Exception as exc:
        print(f"PySide6 未可用: {exc}")
        print("请先安装 PySide6，例如：pip install PySide6")
        return 1

    # --dry-run 支持
    dry_run = "--dry-run" in sys.argv

    from .gui.app import main as gui_main
    return gui_main(dry_run=dry_run)


if __name__ == "__main__":
    main()
