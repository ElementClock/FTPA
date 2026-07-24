"""
测试 GUI 服务层 —— DataContext 及其方法。
"""

import os
import tempfile
import numpy as np
import pytest

from ftpa.gui.services import DataContext


class TestDataContext:
    """测试 DataContext 核心数据模型。"""

    def test_resolve_path_absolute_existing(self, tmp_path):
        """绝对路径且存在时直接返回。"""
        f = tmp_path / "test.txt"
        f.write_text("hello")
        result = DataContext.resolve_path(str(f))
        assert os.path.samefile(result, str(f))

    def test_resolve_path_empty_returns_default(self):
        """空路径返回默认值。"""
        result = DataContext.resolve_path("", default="fallback")
        assert result == "fallback"

    def test_resolve_path_none_returns_default(self):
        """None 路径返回默认值。"""
        result = DataContext.resolve_path(None, default="fallback")
        assert result == "fallback"

    def test_data_context_initial_state(self):
        """DataContext 初始状态应为未加载。"""
        ctx = DataContext()
        assert not ctx.is_loaded
        assert ctx.data == {}
        assert ctx.get_row_count() == 0
        assert ctx.get_column_count() == 0
        assert ctx.get_field_names() == []

    def test_data_context_load_missing_file(self):
        """加载不存在的文件应返回失败。"""
        ctx = DataContext()
        ok, msg = ctx.load("/nonexistent/path.txt", "/nonexistent/labels.xlsx")
        assert not ok
        assert "不存在" in msg

    def test_get_field_labels_without_labelmap(self):
        """无 LabelMap 时字段标签应等于字段名本身。"""
        ctx = DataContext()
        ctx.data = {"TIME": np.array([]), "signal1": np.array([1.0, 2.0])}
        ctx._loaded = True
        labels = ctx.get_field_labels()
        assert "signal1" in labels
        assert labels["signal1"] == "signal1"

    def test_resolve_field_direct_match(self):
        """字段名直接匹配时 resolve_field 应返回原字段名。"""
        ctx = DataContext()
        ctx.data = {"TIME": np.array([]), "signal1": np.array([1.0])}
        result = ctx.resolve_field("signal1")
        assert result == "signal1"

    def test_resolve_field_not_found(self):
        """找不到字段时 resolve_field 应返回 None。"""
        ctx = DataContext()
        ctx.data = {"TIME": np.array([]), "signal1": np.array([1.0])}
        result = ctx.resolve_field("nonexistent")
        assert result is None

    def test_get_time_range_sec_unloaded(self):
        """未加载时时间范围应为 (0, 0)。"""
        ctx = DataContext()
        assert ctx.get_time_range_sec() == (0.0, 0.0)

    def test_generate_summary_unloaded(self):
        """未加载时 generate_summary 应返回空字典。"""
        ctx = DataContext()
        assert ctx.generate_summary() == {}

    def test_unload_clears_all_state(self):
        """unload() 应清除所有数据状态。"""
        ctx = DataContext()
        # 模拟加载状态
        ctx.data = {"TIME": np.array([0.0]), "sig": np.array([1.0])}
        ctx.time_vec = np.array([0.0])
        ctx.time_sec = np.array([0.0])
        ctx._loaded = True
        ctx.data_path = "/some/file.txt"
        ctx.excel_path = "/some/labels.xlsx"
        ctx._label_cache = {"sig": "信号"}

        # 卸载
        ctx.unload()

        assert not ctx.is_loaded
        assert ctx.data == {}
        assert ctx.time_vec is None
        assert ctx.time_sec is None
        assert ctx.data_path == ""
        assert ctx.excel_path == ""
        assert ctx._label_cache is None
        assert ctx.get_row_count() == 0
        assert ctx.get_column_count() == 0
        assert ctx.get_field_names() == []

    def test_unload_idempotent(self):
        """多次调用 unload() 不应出错。"""
        ctx = DataContext()
        ctx.unload()
        ctx.unload()
        assert not ctx.is_loaded

    def test_unload_then_load_cycle(self):
        """卸载后重新加载应正常工作。"""
        ctx = DataContext()
        # 模拟加载
        ctx.data = {"TIME": np.array([0.0]), "sig": np.array([1.0])}
        ctx._loaded = True
        # 卸载
        ctx.unload()
        assert not ctx.is_loaded
        # 尝试加载不存在的文件（验证状态可正常切换）
        ok, msg = ctx.load("/nonexistent/path.txt", "")
        assert not ok


class TestDataContextWithFile:
    """使用临时数据文件测试 DataContext 加载流程。"""

    @pytest.fixture
    def sample_data_file(self, tmp_path):
        """创建最简 TSV 数据文件。"""
        f = tmp_path / "test_data.txt"
        lines = ["TIME\tCol1\tCol2"]
        for i in range(120):
            lines.append(f"00:00:{i:02d}:000\t{i}.0\t{i * 2}.0")
        f.write_text("\n".join(lines), encoding="utf-8")
        return str(f)

    def test_load_valid_file(self, sample_data_file):
        """加载有效文件应成功。"""
        ctx = DataContext()
        ok, msg = ctx.load(sample_data_file, "/nonexistent/labels.xlsx")
        assert ok, f"加载失败: {msg}"
        assert ctx.is_loaded
        assert ctx.get_row_count() > 0
        assert ctx.get_column_count() > 1

    def test_get_field_names_after_load(self, sample_data_file):
        """加载后应能列出字段名（不含 TIME）。"""
        ctx = DataContext()
        ctx.load(sample_data_file, "/nonexistent/labels.xlsx")
        fields = ctx.get_field_names()
        assert "Col1" in fields or any("Col1" in f for f in fields)
        assert "TIME" not in fields

    def test_get_time_range_after_load(self, sample_data_file):
        """加载后时间范围应合理。"""
        ctx = DataContext()
        ctx.load(sample_data_file, "/nonexistent/labels.xlsx")
        t0, t1 = ctx.get_time_range_sec()
        assert t0 >= 0
        assert t1 > t0
