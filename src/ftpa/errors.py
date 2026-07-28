"""FTPA 自定义异常层次。

提供结构化的错误类型，使调用方能够区分不同类型的加载失败。

注意：当前 services.py/worker.py 中的异常捕获使用内置类型分层
(FileNotFoundError → ValueError → MemoryError → OSError → Exception)，
而非此模块的自定义类型。本模块为未来统一异常处理预留，
当需要让调用方按异常类型执行不同恢复策略时，可将内置异常
转换为此层次中的对应类型（raise X from e）。
"""
from __future__ import annotations


class FtpaError(Exception):
    """FTPA 基础异常类。"""
    pass


class LoadError(FtpaError):
    """数据加载错误基类。"""

    def __init__(self, message: str, path: str = "") -> None:
        super().__init__(message)
        self.path = path


class FileNotFoundLoadError(LoadError):
    """文件不存在 / 路径无效。"""
    pass


class FormatLoadError(LoadError):
    """文件格式错误 / 解析失败。"""

    def __init__(self, message: str, path: str = "", detail: str = "") -> None:
        super().__init__(message, path)
        self.detail = detail


class ResourceLoadError(LoadError):
    """内存不足 / I/O 错误。"""
    pass


class LabelMapLoadError(LoadError):
    """映射表加载失败（不阻塞主流程，降级到无标签模式）。"""
    pass
