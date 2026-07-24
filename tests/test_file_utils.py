"""
测试 file_utils 模块
"""

import os
import tempfile
import pytest

from ftpa.utils.file_utils import detect_encoding, is_safe_path, sanitize_filename


class TestDetectEncoding:
    """编码检测测试。"""

    def test_utf8_file(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("hello world", encoding="utf-8")
        assert detect_encoding(str(f)) == "utf-8"

    def test_gbk_file(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("中文测试", encoding="gbk")
        enc = detect_encoding(str(f))
        # GBK 或兼容编码
        assert enc.lower() in ("gbk", "gb2312", "gb18030", "utf-8")

    def test_empty_file(self, tmp_path):
        f = tmp_path / "empty.txt"
        f.write_bytes(b"")
        assert detect_encoding(str(f)) == "utf-8"

    def test_nonexistent_file(self):
        enc = detect_encoding("/nonexistent/file.txt")
        assert enc == "utf-8"


class TestIsSafePath:
    """路径安全校验测试。"""

    def test_safe_subpath(self):
        assert is_safe_path("/home/user", "/home/user/docs/file.txt")

    def test_unsafe_traversal(self):
        assert not is_safe_path("/home/user", "/home/user/../etc/passwd")

    def test_exact_match(self):
        assert is_safe_path("/home/user", "/home/user")


class TestSanitizeFilename:
    """文件名清理测试。"""

    def test_normal_filename(self):
        assert sanitize_filename("data.txt") == "data.txt"

    def test_illegal_chars(self):
        result = sanitize_filename('file<>:"/\\|?*name.txt')
        assert "<" not in result
        assert ">" not in result

    def test_empty_filename(self):
        assert sanitize_filename("") == "unnamed"

    def test_dots_only(self):
        assert sanitize_filename("...") == "unnamed"
