"""
文件缓存（私有模块，不直接对外暴露）

提供模块级数据缓存，替代 MATLAB 的 persistent 变量。
线程安全。
"""

import threading


class FileCache:
    """简单的线程安全文件数据缓存。"""

    def __init__(self):
        self._cache = {}
        self._lock = threading.Lock()

    def get(self, key: str):
        with self._lock:
            return self._cache.get(key)

    def set(self, key: str, value):
        with self._lock:
            self._cache[key] = value

    def has(self, key: str) -> bool:
        with self._lock:
            return key in self._cache

    def clear(self):
        with self._lock:
            self._cache.clear()


# 模块级单例（兼容原有的模块级全局变量用法）
_file_cache = FileCache()
