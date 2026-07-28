"""
文件缓存（私有模块，不直接对外暴露）

提供模块级数据缓存，替代 MATLAB 的 persistent 变量。
线程安全，LRU 驱逐，可选 mtime 失效校验。
"""

import os
import threading
from collections import OrderedDict
from typing import Any

from ..config import CONFIG


class FileCache:
    """线程安全的 LRU 文件数据缓存。

    - 使用 OrderedDict 实现 LRU 语义（get 命中时 move_to_end）
    - max_size 控制最大缓存条目数，超出时淘汰最久未访问的条目
    - 可选 mtime 校验：get 时若 key 对应的文件已被修改，自动失效
    - hits / misses 计数器用于调试和性能监控
    """

    @staticmethod
    def _normalize_key(key: str) -> str:
        """规范化缓存键：统一大小写（Windows）和路径格式。"""
        return os.path.normcase(os.path.abspath(key))

    def __init__(self, max_size: int | None = None, check_mtime: bool = True):
        """
        参数:
            max_size: 最大缓存条目数（默认 5，对应约 5 个文件的数据字典）
            check_mtime: 是否在 get 时检查文件修改时间（默认 True）
        """
        if max_size is None:
            max_size = CONFIG.data.cache_max_size
        self._cache: OrderedDict[str, Any] = OrderedDict()
        self._lock = threading.Lock()
        self._max_size = max_size
        self._check_mtime = check_mtime
        self._mtimes: dict[str, float] = {}  # key → 文件 mtime
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
                        del self._cache[key]
                        del self._mtimes[key]
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
        """设置缓存值。超出 max_size 时淘汰最久未访问的条目。"""
        key = self._normalize_key(key)
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
            self._cache[key] = value

            # 记录 mtime
            if self._check_mtime:
                try:
                    self._mtimes[key] = os.path.getmtime(key)
                except OSError:
                    pass

            # LRU 驱逐：超出上限时删除最久未访问的条目
            while len(self._cache) > self._max_size:
                oldest_key, _ = self._cache.popitem(last=False)
                self._mtimes.pop(oldest_key, None)

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
            self.hits = 0
            self.misses = 0

    def stats(self) -> dict[str, int]:
        """返回缓存统计信息。"""
        with self._lock:
            return {
                'size': len(self._cache),
                'max_size': self._max_size,
                'hits': self.hits,
                'misses': self.misses,
            }


# 模块级单例（兼容原有的模块级全局变量用法）
_file_cache = FileCache()
