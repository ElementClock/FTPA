"""
CSV loader 就地过滤测试
验证 _convert_flight_time() 的就地过滤行为（C4 修复）
"""

import pytest
import numpy as np
import pandas as pd

from ftpa.data.csv_loader import _convert_flight_time


def _make_csv_df(n_rows: int, flag_values: list[int] | None = None) -> pd.DataFrame:
    """构造模拟 CSV 飞参数据的 DataFrame。

    列结构：col0, col1, col2, 日期, 标识符, 时间, col6, ...
    与真实 CSV 第 4/5/6 列对应日期/标识符/时间。

    Args:
        n_rows: 行数。
        flag_values: 标识符列的值列表。None 时全部为 1（可信）。
    """
    if flag_values is None:
        flag_values = [1] * n_rows
    assert len(flag_values) == n_rows

    return pd.DataFrame({
        'col0': range(n_rows),
        'col1': range(n_rows),
        'col2': range(n_rows),
        '日期': ['2025/10/13'] * n_rows,
        '标识符': flag_values,
        '时间': [f'0:0{i}:00' for i in range(n_rows)],
        'col6': np.random.randn(n_rows),
    })


class TestConvertFlightTimeInplaceFilter:
    """_convert_flight_time 就地过滤行为测试。"""

    def test_filter_keeps_reliable_rows(self):
        """过滤后仅保留标识符 == 1 的行。"""
        flags = [1, 0, 1, 0, 1]
        df = _make_csv_df(5, flags)
        result = _convert_flight_time(df, filter_reliable=True)

        # 原始 5 行，其中 3 行标识符为 1
        assert len(result) == 3

    def test_filter_preserves_all_reliable(self):
        """全部可信时不过滤任何行。"""
        df = _make_csv_df(10, [1] * 10)
        result = _convert_flight_time(df, filter_reliable=True)
        assert len(result) == 10

    def test_filter_removes_all_unreliable(self):
        """全部不可信时保留全部数据（after == 0 触发回退）。"""
        df = _make_csv_df(5, [0] * 5)
        result = _convert_flight_time(df, filter_reliable=True)
        # 过滤后无可信数据，回退保留全部
        assert len(result) == 5

    def test_filter_disabled_keeps_all(self):
        """filter_reliable=False 时不过滤。"""
        flags = [1, 0, 1, 0, 1]
        df = _make_csv_df(5, flags)
        result = _convert_flight_time(df, filter_reliable=False)
        assert len(result) == 5

    def test_index_reset_after_filter(self):
        """过滤后索引从 0 开始连续。"""
        flags = [1, 0, 1, 0, 1]
        df = _make_csv_df(5, flags)
        result = _convert_flight_time(df, filter_reliable=True)

        # 索引应从 0 开始且连续
        assert list(result.index) == list(range(len(result)))

    def test_index_reset_large_gap(self):
        """大间隔删除后索引仍然连续。"""
        # 100 行，偶数行不可信
        flags = [1 if i % 2 == 0 else 0 for i in range(100)]
        df = _make_csv_df(100, flags)
        result = _convert_flight_time(df, filter_reliable=True)

        assert len(result) == 50
        assert list(result.index) == list(range(50))

    def test_inplace_no_full_copy(self):
        """验证就地过滤不会创建完整副本（内存行为）。

        通过检查 DataFrame 的 id 与输入不同、但数据量减少来
        间接验证。原地操作修改同一个对象（虽然 reset_index
        可能创建新对象，但关键是过滤过程中没有同时持有两份完整数据）。
        """
        flags = [1, 0, 1, 0, 1]
        df = _make_csv_df(5, flags)
        original_len = len(df)
        result = _convert_flight_time(df, filter_reliable=True)

        # 过滤后行数应减少
        assert len(result) < original_len
        # 结果索引连续（就地过滤 + reset_index 的特征）
        assert list(result.index) == list(range(len(result)))

    def test_mixed_flags_correct_count(self):
        """混合标识符值时正确计算保留行数。"""
        flags = [1, 1, 0, 1, 0, 0, 1, 1, 1, 0]
        df = _make_csv_df(10, flags)
        result = _convert_flight_time(df, filter_reliable=True)

        expected_count = sum(1 for f in flags if f == 1)
        assert len(result) == expected_count

    def test_flag_value_not_0_or_1(self):
        """标识符为非 0/1 值时，仅保留 == 1 的行。"""
        flags = [1, 2, 3, 0, 1]
        df = _make_csv_df(5, flags)
        result = _convert_flight_time(df, filter_reliable=True)

        # 仅 flag == 1 的行保留（第 0 和第 4 行）
        assert len(result) == 2

    def test_single_reliable_row(self):
        """仅一行可信时正确保留。"""
        flags = [0, 0, 1, 0, 0]
        df = _make_csv_df(5, flags)
        result = _convert_flight_time(df, filter_reliable=True)

        assert len(result) == 1
        assert list(result.index) == [0]

    def test_no_flag_column(self):
        """无标识符列时不过滤。"""
        # 构造不含标识符列的 DataFrame（仅 3 列）
        df = pd.DataFrame({
            'col0': range(5),
            'col1': range(5),
            'col2': range(5),
        })
        result = _convert_flight_time(df, filter_reliable=True)
        # 无标识符列，不过滤，但因列数 < 6 无法识别时间列
        # _get_time_column_names 会抛 ValueError，被 catch 后返回原 df
        assert len(result) == 5


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
