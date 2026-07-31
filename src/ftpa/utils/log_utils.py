"""
纯 Python 日志配置工具（零 Qt 依赖）。

用法：
    from ftpa.utils.log_utils import setup_logging
    setup_logging(log_file="ftpa.log")

然后在任意模块中：
    import logging
    logger = logging.getLogger(__name__)
    logger.info("消息")
"""

from __future__ import annotations

import logging
import sys

_initialized = False


def setup_logging(log_file: str | None = None) -> None:
    """配置 root logger：控制台(INFO) + 可选文件(DEBUG)。"""
    global _initialized
    if _initialized:
        return
    _initialized = True

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)

    # 控制台 handler（INFO 以上）
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.INFO)
    console.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    ))
    root.addHandler(console)

    # 文件 handler（DEBUG 以上，可选）
    if log_file:
        fh = logging.FileHandler(log_file, encoding="utf-8")
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        ))
        root.addHandler(fh)

    # 抑制第三方库 DEBUG noise
    logging.getLogger('matplotlib').setLevel(logging.WARNING)
