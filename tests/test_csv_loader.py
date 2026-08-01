"""
csv_loader 完整路径测试
=======================

覆盖 csv_param_extract() 端到端流程（P1-TEST-2）：
- 编码自动检测与显式指定
- 时间列合并转换（日期 + 标识符 + 时间 → timedelta64）
- 可靠性过滤（filter_reliable）
- 缓存命中
- 输出格式（dict[str, np.ndarray]、filename 元数据、列名保留）
- 日期格式解析（YYYY/MM/DD 与 YY-MM-DD）

使用临时 CSV 文件，patch _trim_data 避免小数据集被裁剪。
"""

from __future__ import annotations

import os
import tempfile

import numpy as np
import pandas as pd
import pytest

from ftpa.data import cache as cache_module
from ftpa.data.csv_loader import csv_param_extract


# ── 辅助函数 ──


def _make_csv_content(
    n_rows: int = 12,
    flag_values: list[int] | None = None,
    date_str: str = '2025/10/13',
    time_strs: list[str] | None = None,
    extra_numeric_col: str = '温度',
) -> str:
    """生成模拟 CSV 文件内容。

    列结构（索引对应 _get_time_column_names 的 3/4/5）：
        0: 飞参内部时间
        1: col1
        2: col2
        3: 日期        ← date_col
        4: 标识符      ← flag_col
        5: 时间        ← time_col
        6: 温度（数值列）

    Args:
        n_rows: 数据行数。
        flag_values: 标识符列的值。None 时全部为 1。
        date_str: 日期字符串。
        time_strs: 时间字符串列表。None 时自动生成。
        extra_numeric_col: 额外数值列名。
    """
    if flag_values is None:
        flag_values = [1] * n_rows
    if time_strs is None:
        time_strs = [f'0:00:{i:02d}' for i in range(n_rows)]
    assert len(flag_values) == n_rows
    assert len(time_strs) == n_rows

    lines = ['飞参内部时间,col1,col2,日期,标识符,时间,' + extra_numeric_col]
    for i in range(n_rows):
        lines.append(f'0:00:{i:02d}.000,{i},{i * 2},{date_str},{flag_values[i]},{time_strs[i]},{20.0 + i}')
    return '\n'.join(lines) + '\n'


def _write_csv(content: str, encoding: str = 'utf-8') -> str:
    """将 CSV 内容写入临时文件，返回路径。"""
    fd, path = tempfile.mkstemp(suffix='.csv', prefix='ftpa_test_')
    with os.fdopen(fd, 'w', encoding=encoding) as f:
        f.write(content)
    return path


@pytest.fixture(autouse=True)
def _clear_cache_and_disable_trim(monkeypatch):
    """每个测试前清空文件缓存，并禁用头尾裁剪以适配小数据集。"""
    cache_module._file_cache.clear()
    # 禁用裁剪：小数据集（<100 行）不会被 trim_head/trim_tail 清空
    monkeypatch.setattr('ftpa.data.csv_loader._trim_data', lambda arr, **kw: arr)
    yield
    cache_module._file_cache.clear()
    # 清理可能残留的缓存条目


# ── 测试类 ──


class TestCsvParamExtractBasic:
    """csv_param_extract 基础加载流程。"""

    def test_basic_load_returns_dict(self):
        """加载后返回 dict[str, np.ndarray]。"""
        path = _write_csv(_make_csv_content(n_rows=12))
        try:
            data = csv_param_extract(path)
            assert isinstance(data, dict)
            assert len(data) > 0
        finally:
            os.unlink(path)

    def test_time_key_is_timedelta(self):
        """TIME 键为 timedelta64 数组。"""
        path = _write_csv(_make_csv_content(n_rows=12))
        try:
            data = csv_param_extract(path)
            assert 'TIME' in data
            assert np.issubdtype(data['TIME'].dtype, np.timedelta64)
            assert len(data['TIME']) > 0
        finally:
            os.unlink(path)

    def test_numeric_columns_are_float64(self):
        """数值列转换为 float64 numpy 数组。"""
        path = _write_csv(_make_csv_content(n_rows=12))
        try:
            data = csv_param_extract(path)
            # '温度' 列应为 float64
            assert '温度' in data
            assert data['温度'].dtype == np.float64
            # 第一行温度应为 20.0
            assert data['温度'][0] == pytest.approx(20.0)
        finally:
            os.unlink(path)

    def test_filename_metadata(self):
        """data['filename'] 存储绝对路径。"""
        path = _write_csv(_make_csv_content(n_rows=12))
        try:
            data = csv_param_extract(path)
            assert 'filename' in data
            assert os.path.abspath(path) == data['filename']
        finally:
            os.unlink(path)

    def test_preserves_chinese_column_names(self):
        """CSV 原始列名（含中文）被保留，不转换为 ASCII。"""
        path = _write_csv(_make_csv_content(n_rows=12, extra_numeric_col='发动机温度'))
        try:
            data = csv_param_extract(path)
            assert '发动机温度' in data
            # 不应出现 ASCII 化的列名
            ascii_names = [k for k in data if k not in ('TIME', 'filename') and not any(ord(c) > 127 for c in k)]
            # 飞行时间列是中文，col1/col2 是 ASCII（原始即为 ASCII）
            assert '发动机温度' in data
        finally:
            os.unlink(path)


class TestCsvParamExtractEncoding:
    """编码检测。"""

    def test_gbk_encoding_auto_detected(self):
        """GBK 编码文件自动检测。"""
        path = _write_csv(_make_csv_content(n_rows=12), encoding='gbk')
        try:
            data = csv_param_extract(path)
            assert 'TIME' in data
            assert len(data['TIME']) > 0
        finally:
            os.unlink(path)

    def test_explicit_encoding(self):
        """显式指定 encoding 时跳过自动检测。"""
        path = _write_csv(_make_csv_content(n_rows=12), encoding='utf-8')
        try:
            data = csv_param_extract(path, encoding='utf-8')
            assert 'TIME' in data
            assert data['温度'][0] == pytest.approx(20.0)
        finally:
            os.unlink(path)


class TestCsvParamExtractFilter:
    """可靠性过滤。"""

    def test_filter_removes_unreliable_rows(self):
        """filter_reliable=True 移除标识符 != 1 的行。"""
        flags = [1, 1, 1, 0, 0, 1, 1, 1, 1, 1, 1, 1]  # 12 行，2 行不可信
        path = _write_csv(_make_csv_content(n_rows=12, flag_values=flags))
        try:
            data = csv_param_extract(path, filter_reliable=True)
            # 12 - 2 = 10 行
            assert len(data['TIME']) == 10
            assert len(data['温度']) == 10
        finally:
            os.unlink(path)

    def test_filter_disabled_keeps_all(self):
        """filter_reliable=False 保留所有行。"""
        flags = [1, 1, 1, 0, 0, 1, 1, 1, 1, 1, 1, 1]
        path = _write_csv(_make_csv_content(n_rows=12, flag_values=flags))
        try:
            data = csv_param_extract(path, filter_reliable=False)
            assert len(data['TIME']) == 12
        finally:
            os.unlink(path)

    def test_all_unreliable_falls_back_to_keep_all(self):
        """全部不可信时回退保留全部数据（不抛异常，数值列保留全部行）。"""
        flags = [0] * 12
        path = _write_csv(_make_csv_content(n_rows=12, flag_values=flags))
        try:
            data = csv_param_extract(path, filter_reliable=True)
            # 全部不可信 → 回退保留全部（_convert_flight_time 提前返回，
            # 跳过时间列重命名，TIME 可能缺失，但数值列应保留全部 12 行）
            assert '温度' in data
            assert len(data['温度']) == 12
            assert data['温度'][0] == pytest.approx(20.0)
        finally:
            os.unlink(path)


class TestCsvParamExtractCaching:
    """文件缓存行为。"""

    def test_cache_hit_returns_same_object(self):
        """第二次加载命中缓存，返回同一对象（is 判断）。"""
        path = _write_csv(_make_csv_content(n_rows=12))
        try:
            data1 = csv_param_extract(path)
            data2 = csv_param_extract(path)
            assert data1 is data2
        finally:
            os.unlink(path)

    def test_cache_cleared_between_tests(self):
        """缓存被 fixture 清空后重新加载得到新对象。"""
        path = _write_csv(_make_csv_content(n_rows=12))
        try:
            data1 = csv_param_extract(path)
            cache_module._file_cache.clear()
            data2 = csv_param_extract(path)
            assert data1 is not data2
            # 但内容相同
            np.testing.assert_array_equal(data1['温度'], data2['温度'])
        finally:
            os.unlink(path)


class TestCsvParamExtractDateFormat:
    """日期格式解析。"""

    def test_yyyy_slash_format(self):
        """YYYY/MM/DD 日期格式正确解析。"""
        path = _write_csv(_make_csv_content(n_rows=12, date_str='2025/10/13'))
        try:
            data = csv_param_extract(path)
            assert len(data['TIME']) > 0
        finally:
            os.unlink(path)

    def test_yy_dash_format(self):
        """YY-MM-DD 日期格式正确解析。"""
        path = _write_csv(_make_csv_content(n_rows=12, date_str='25-10-13'))
        try:
            data = csv_param_extract(path)
            assert len(data['TIME']) > 0
        finally:
            os.unlink(path)

    def test_time_values_are_relative(self):
        """TIME 数组为相对时间（timedelta64），首点为 0。"""
        path = _write_csv(_make_csv_content(n_rows=12))
        try:
            data = csv_param_extract(path)
            time_sec = data['TIME'].astype('timedelta64[ns]').astype(np.float64) / 1e9
            # 第一个时间点应为 0（相对时间基准）
            assert time_sec[0] == pytest.approx(0.0)
            # 长度与过滤后行数一致
            assert len(time_sec) == len(data['温度'])
        finally:
            os.unlink(path)


class TestCsvParamExtractEdgeCases:
    """边界情况。"""

    def test_single_row(self):
        """单行数据正确加载。"""
        path = _write_csv(_make_csv_content(n_rows=1))
        try:
            data = csv_param_extract(path)
            assert len(data['TIME']) == 1
            assert data['温度'][0] == pytest.approx(20.0)
        finally:
            os.unlink(path)

    def test_custom_time_values(self):
        """自定义时间字符串正确解析，TIME 为相对时间。"""
        time_strs = ['1:00:00', '1:00:01', '1:00:02', '1:00:03',
                     '1:00:04', '1:00:05', '1:00:06', '1:00:07',
                     '1:00:08', '1:00:09', '1:00:10', '1:00:11']
        path = _write_csv(_make_csv_content(n_rows=12, time_strs=time_strs))
        try:
            data = csv_param_extract(path)
            time_sec = data['TIME'].astype('timedelta64[ns]').astype(np.float64) / 1e9
            # 第一个时间点为 0（相对时间基准）
            assert time_sec[0] == pytest.approx(0.0)
            # 长度与数据行数一致
            assert len(time_sec) == len(data['温度'])
        finally:
            os.unlink(path)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
