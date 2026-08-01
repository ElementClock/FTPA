"""
文件缓存（私有模块，不直接对外暴露）

提供模块级数据缓存，替代 MATLAB 的 persistent 变量。
线程安全，LRU 驱逐，可选 mtime 失效校验。

支持两种驱逐策略（同时生效，先达先淘汰）：
1. 条目数上限（max_size）：超过时淘汰最久未访问的条目
2. 内存占用上限（max_memory_bytes）：总内存超过限制时按 LRU 淘汰
"""

import os
import sys
import threading
from collections import OrderedDict
from typing import Any

from ..config import CONFIG


def _estimate_size(obj: Any) -> int:
    """估算对象占用的内存字节数。

    - numpy 数组使用 nbytes（精确）
    - dict/list/tuple 递归估算其元素
    - 其他对象使用 sys.getsizeof（浅层估算）

    递归深度限制为 3 层，避免深层嵌套结构的性能开销。
    """
    return _estimate_size_recursive(obj, depth=0, max_depth=3)


def _estimate_size_recursive(obj: Any, depth: int, max_depth: int) -> int:
    """递归估算对象内存大小（内部实现）。"""
    # numpy 数组：直接使用 nbytes（精确值）
    nbytes = getattr(obj, "nbytes", None)
    if isinstance(nbytes, int):
        return nbytes

    # 基础对象开销
    try:
        total = sys.getsizeof(obj)
    except TypeError:
        # 某些对象不支持 getsizeof
        total = 0

    if depth >= max_depth:
        return total

    # dict：递归估算值（键通常较短，仅计入 getsizeof 已覆盖）
    if isinstance(obj, dict):
        for v in obj.values():
            total += _estimate_size_recursive(v, depth + 1, max_depth)
        return total

    # list/tuple：递归估算元素
    if isinstance(obj, (list, tuple)):
        for item in obj:
            total += _estimate_size_recursive(item, depth + 1, max_depth)
        return total

    return total


class FileCache:
    """线程安全的 LRU 文件数据缓存。

    - 使用 OrderedDict 实现 LRU 语义（get 命中时 move_to_end）
    - max_size 控制最大缓存条目数，超出时淘汰最久未访问的条目
    - max_memory_bytes 控制最大内存占用，超出时按 LRU 淘汰最旧条目
    - 可选 mtime 校验：get 时若 key 对应的文件已被修改，自动失效
    - hits / misses 计数器用于调试和性能监控
    """

    @staticmethod
    def _normalize_key(key: str) -> str:
        """规范化缓存键：统一大小写（Windows）和路径格式。"""
        return os.path.normcase(os.path.abspath(key))

    def __init__(
        self,
        max_size: int | None = None,
        check_mtime: bool = True,
        max_memory_bytes: int | None = None,
    ):
        """
        参数:
            max_size: 最大缓存条目数（默认 5，对应约 5 个文件的数据字典）
            check_mtime: 是否在 get 时检查文件修改时间（默认 True）
            max_memory_bytes: 最大缓存内存占用（字节）。
                默认从 CONFIG.data.cache_max_memory_mb 读取。
                设为 0 或负数表示不限制内存。
        """
        if max_size is None:
            max_size = CONFIG.data.cache_max_size
        if max_memory_bytes is None:
            max_memory_bytes = CONFIG.data.cache_max_memory_mb * 1024 * 1024
        self._cache: OrderedDict[str, Any] = OrderedDict()
        self._lock = threading.Lock()
        self._max_size = max_size
        self._max_memory_bytes = max_memory_bytes
        self._check_mtime = check_mtime
        self._mtimes: dict[str, float] = {}  # key → 文件 mtime
        self._sizes: dict[str, int] = {}  # key → 估算内存大小（字节）
        self._total_bytes: int = 0
        self.hits = 0
        self.misses = 0

    def get(self, key: str):
        """获取缓存值。若启用 mtime 校验且文件已修改，返回 None 并移除条目。"""
        key = self._normalize_key(key)
        with self._lock:
            if key not in self._cache:
                self.misses += 1
                return None

            # mtime 校验：文件被修改则失效
            if self._check_mtime and key in self._mtimes:
                try:
                    current_mtime = os.path.getmtime(key)
                    if current_mtime != self._mtimes[key]:
                        # 文件已修改，移除过期条目
                        self._remove_entry(key)
                        self.misses += 1
                        return None
                except OSError:
                    # 文件不存在（可能是非文件路径的缓存键），跳过 mtime 校验
                    pass

            # LRU：命中时移至末尾
            self._cache.move_to_end(key)
            self.hits += 1
            return self._cache[key]

    def set(self, key: str, value):
        """设置缓存值。超出 max_size 或 max_memory_bytes 时淘汰最久未访问的条目。"""
        key = self._normalize_key(key)
        with self._lock:
            # 若已存在，先移除旧条目以更新内存计数
            if key in self._cache:
                self._remove_entry(key)

            self._cache[key] = value

            # 估算并记录内存大小
            size = _estimate_size(value)
            self._sizes[key] = size
            self._total_bytes += size

            # 记录 mtime
            if self._check_mtime:
                try:
                    self._mtimes[key] = os.path.getmtime(key)
                except OSError:
                    pass

            # LRU 驱逐：超出条目数上限时删除最久未访问的条目
            while len(self._cache) > self._max_size:
                oldest_key = next(iter(self._cache))
                self._remove_entry(oldest_key)

            # 内存驱逐：总内存超限时按 LRU 淘汰，但至少保留当前条目
            self._evict_by_memory()

    def _evict_by_memory(self):
        """当总内存超过限制时，按 LRU 淘汰最旧条目（至少保留 1 个）。"""
        if self._max_memory_bytes <= 0:
            return
        while self._total_bytes > self._max_memory_bytes and len(self._cache) > 1:
            oldest_key = next(iter(self._cache))
            self._remove_entry(oldest_key)

    def _remove_entry(self, key: str):
        """移除单个缓存条目并更新内存计数（调用方需持锁）。"""
        if key in self._cache:
            del self._cache[key]
        self._mtimes.pop(key, None)
        size = self._sizes.pop(key, 0)
        self._total_bytes -= size
        if self._total_bytes < 0:
            self._total_bytes = 0

    def has(self, key: str) -> bool:
        """检查缓存中是否存在指定键（不做 mtime 校验）。"""
        key = self._normalize_key(key)
        with self._lock:
            return key in self._cache

    def clear(self):
        """清除所有缓存。"""
        with self._lock:
            self._cache.clear()
            self._mtimes.clear()
            self._sizes.clear()
            self._total_bytes = 0
            self.hits = 0
            self.misses = 0

    def stats(self) -> dict:
        """返回缓存统计信息。"""
        with self._lock:
            return {
                'size': len(self._cache),
                'max_size': self._max_size,
                'hits': self.hits,
                'misses': self.misses,
                'memory_bytes': self._total_bytes,
                'max_memory_bytes': self._max_memory_bytes,
            }


# 模块级单例（兼容原有的模块级全局变量用法）
_file_cache = FileCache()
