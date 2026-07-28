"""
测试 FileCache 模块

覆盖：LRU 驱逐、mtime 校验、缓存键大小写规范化。
"""

import os
import time
import pytest

from ftpa.data.cache import FileCache


class TestFileCacheBasic:
    """FileCache 基本功能测试。"""

    def test_set_and_get(self):
        cache = FileCache(max_size=10, check_mtime=False)
        cache.set("key1", "value1")
        assert cache.get("key1") == "value1"

    def test_get_miss(self):
        cache = FileCache(max_size=10, check_mtime=False)
        assert cache.get("nonexistent") is None
        assert cache.misses == 1

    def test_has(self):
        cache = FileCache(max_size=10, check_mtime=False)
        cache.set("key1", "value1")
        assert cache.has("key1") is True
        assert cache.has("key2") is False

    def test_clear(self):
        cache = FileCache(max_size=10, check_mtime=False)
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.clear()
        assert cache.get("key1") is None
        assert cache.stats()["size"] == 0
        assert cache.hits == 0
        # clear 后 get 产生一次 miss
        assert cache.misses == 1

    def test_stats(self):
        cache = FileCache(max_size=5, check_mtime=False)
        cache.set("k", "v")
        cache.get("k")
        cache.get("miss")
        s = cache.stats()
        assert s["size"] == 1
        assert s["max_size"] == 5
        assert s["hits"] == 1
        assert s["misses"] == 1

    def test_lru_eviction(self):
        cache = FileCache(max_size=2, check_mtime=False)
        cache.set("a", 1)
        cache.set("b", 2)
        cache.set("c", 3)  # 应驱逐 "a"
        assert cache.has("a") is False
        assert cache.has("b") is True
        assert cache.has("c") is True

    def test_lru_access_reorder(self):
        cache = FileCache(max_size=2, check_mtime=False)
        cache.set("a", 1)
        cache.set("b", 2)
        cache.get("a")  # 访问 "a"，使其移到末尾
        cache.set("c", 3)  # 应驱逐 "b" 而非 "a"
        assert cache.has("a") is True
        assert cache.has("b") is False


class TestFileCacheMtime:
    """FileCache mtime 校验测试。"""

    def test_mtime_invalidation(self, tmp_path):
        f = tmp_path / "data.csv"
        f.write_text("hello", encoding="utf-8")

        cache = FileCache(max_size=10, check_mtime=True)
        cache.set(str(f), "cached_data")
        assert cache.get(str(f)) == "cached_data"

        # 修改文件（确保 mtime 变化）
        time.sleep(0.1)
        f.write_text("modified", encoding="utf-8")
        os.utime(str(f), None)  # 确保 mtime 更新

        assert cache.get(str(f)) is None

    def test_mtime_check_disabled(self, tmp_path):
        f = tmp_path / "data.csv"
        f.write_text("hello", encoding="utf-8")

        cache = FileCache(max_size=10, check_mtime=False)
        cache.set(str(f), "cached_data")

        # 修改文件
        time.sleep(0.1)
        f.write_text("modified", encoding="utf-8")

        # 禁用 mtime 校验，缓存应仍然命中
        assert cache.get(str(f)) == "cached_data"

    def test_mtime_with_normalized_key(self, tmp_path):
        """规范化后的 key 仍然正确记录和校验 mtime。"""
        f = tmp_path / "data.csv"
        f.write_text("hello", encoding="utf-8")

        cache = FileCache(max_size=10, check_mtime=True)
        # 使用不同大小写路径 set
        cache.set(str(f), "cached_data")
        # 使用不同大小写路径 get — 应命中
        alt_path = self._make_alt_case(str(f))
        assert cache.get(alt_path) == "cached_data"

        # 修改文件后，用原始路径 get 应失效
        time.sleep(0.1)
        f.write_text("modified", encoding="utf-8")
        os.utime(str(f), None)
        assert cache.get(str(f)) is None

    @staticmethod
    def _make_alt_case(path: str) -> str:
        """生成一个大小写不同的路径变体。"""
        # 在路径中间部分翻转大小写
        base, ext = os.path.splitext(path)
        if base != base.lower():
            return base.lower() + ext.lower()
        return base.upper() + ext.upper()


class TestFileCacheNormalizeKey:
    """缓存键大小写规范化测试。"""

    def test_normalize_key_is_deterministic(self):
        key = FileCache._normalize_key("C:/Data/file.csv")
        assert isinstance(key, str)
        assert key == FileCache._normalize_key("C:/Data/file.csv")

    def test_case_insensitive_hit_via_set_get(self, tmp_path):
        """不同大小写的路径应命中同一缓存条目。"""
        f = tmp_path / "Data.csv"
        f.write_text("content", encoding="utf-8")

        cache = FileCache(max_size=10, check_mtime=True)
        original_path = str(f)
        alt_path = self._alt_case(original_path)

        cache.set(original_path, "data_value")
        # 使用不同大小写路径获取
        assert cache.get(alt_path) == "data_value"
        assert cache.hits == 1

    def test_case_insensitive_hit_via_has(self, tmp_path):
        """不同大小写路径的 has() 应返回 True。"""
        f = tmp_path / "Data.csv"
        f.write_text("content", encoding="utf-8")

        cache = FileCache(max_size=10, check_mtime=False)
        original_path = str(f)
        alt_path = self._alt_case(original_path)

        cache.set(original_path, "data_value")
        assert cache.has(alt_path) is True

    def test_case_insensitive_overwrite(self, tmp_path):
        """不同大小写路径的 set 应覆盖同一缓存条目。"""
        f = tmp_path / "Data.csv"
        f.write_text("content", encoding="utf-8")

        cache = FileCache(max_size=10, check_mtime=False)
        original_path = str(f)
        alt_path = self._alt_case(original_path)

        cache.set(original_path, "first")
        cache.set(alt_path, "second")
        # 应只有一个缓存条目（而非两个）
        assert cache.stats()["size"] == 1
        assert cache.get(original_path) == "second"

    def test_non_file_path_key(self):
        """非文件路径的 key（如纯字符串标识符）不应因 normcase/abspath 出错。"""
        cache = FileCache(max_size=10, check_mtime=True)
        # 纯字符串 key，normcase+abspath 会将其视为相对路径并拼接 cwd
        # 但不会出错，且 get/set 行为应一致
        cache.set("my_cache_id", {"a": 1})
        assert cache.get("my_cache_id") == {"a": 1}

    def test_non_file_path_key_no_mtime_invalidation(self):
        """非文件路径的 key 不应因 mtime 校验而意外失效。"""
        cache = FileCache(max_size=10, check_mtime=True)
        cache.set("nonexistent_path_key", "value")
        # 由于文件不存在，mtime 校验会跳过（OSError 被捕获）
        result = cache.get("nonexistent_path_key")
        assert result == "value"

    def test_cross_platform_normalize(self):
        """验证 _normalize_key 在当前平台行为一致。"""
        key1 = FileCache._normalize_key("C:/Data/file.csv")
        key2 = FileCache._normalize_key("c:/data/file.csv")
        # 在 Windows 上应相等，在 Linux 上取决于文件系统
        if os.name == "nt":
            assert key1 == key2

    @staticmethod
    def _alt_case(path: str) -> str:
        """生成大小写不同的路径变体。"""
        base, ext = os.path.splitext(path)
        if base != base.lower():
            return base.lower() + ext.lower()
        return base.upper() + ext.upper()
