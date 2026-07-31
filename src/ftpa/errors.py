"""FTPA 自定义异常层次。

提供结构化的错误类型，使调用方能够区分不同类型的加载失败。
loading.py 中的 Loader 将内置异常转换为此层次中的对应类型
（raise X from e），worker.py 按 FtpaError 子类映射为用户友好消息。
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
