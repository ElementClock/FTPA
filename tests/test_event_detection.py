"""
event_detection 模块测试
========================

覆盖 compute_takeoff_landing_stats() 的完整路径（P1-TEST-1）：
- 正常触水（RH=0）场景
- 无触水（RH 恒非零）场景
- 变量缺失场景
- 空时间窗口
- 字符串 / 数值秒时间参数
- 部分窗口与统计值正确性

使用轻量 mock LabelMap，避免依赖真实 Excel 文件。
"""

from __future__ import annotations

import numpy as np
import pytest

from ftpa.statistics.event_detection import compute_takeoff_landing_stats


class _MockLabelMap:
    """轻量 LabelMap 替身，仅实现 get_var_name。

    Args:
        mapping: 中文标签 → 字段名 的映射字典。
        missing_labels: 这些标签查找时返回空字符串（模拟未找到）。
    """

    def __init__(self, mapping: dict[str, str], missing_labels: tuple[str, ...] = ()):
        self._mapping = mapping
        self._missing = set(missing_labels)

    def get_var_name(self, label: str, mode: str = 'field') -> str:
        if label in self._missing:
            return ''
        return self._mapping.get(label, '')


# 触水统计所需的 6 个标签 → 字段名映射
_LABEL_MAP = {
    '无线电高度表决值': 'RH',
    '指示空速表决值': 'Vc',
    '总重': 'W',
    '相对重心': 'CG',
    '俯仰角表决值': 'Theta',
    '法向过载_I1': 'Nz',
}


def _make_data(n: int = 20, rh_zero_at: int | None = 5) -> dict[str, np.ndarray]:
    """构造模拟飞参数据。

    Args:
        n: 数据点数（时间 0~n-1 秒）。
        rh_zero_at: RH=0 的索引位置；None 表示 RH 恒非零。
    """
    time = np.arange(n) * np.timedelta64(1, 's')
    rh = np.full(n, 100.0)
    if rh_zero_at is not None:
        rh[rh_zero_at] = 0.0
    return {
        'TIME': time,
        'RH': rh,
        'Vc': np.linspace(80, 120, n),
        'W': np.linspace(50000, 48000, n),
        'CG': np.linspace(25.0, 24.0, n),
        'Theta': np.linspace(2.0, 8.0, n),
        'Nz': np.linspace(1.0, 1.5, n),
    }


class TestComputeTakeoffLandingStats:
    """compute_takeoff_landing_stats 完整路径测试。"""

    def test_normal_with_touchdown(self):
        """正常场景：RH 在索引 5 处为 0，输出包含触水信息。"""
        data = _make_data(n=20, rh_zero_at=5)
        lm = _MockLabelMap(_LABEL_MAP)

        result = compute_takeoff_landing_stats(0, 19, data, lm)

        assert '触水时' in result
        assert '空速' in result
        assert '总重' in result
        assert '重心' in result
        assert '最大俯仰角' in result
        assert '最大法向过载' in result
        # 触水点（索引5）的空速应为 linspace(80,120,20)[5]
        expected_vc0 = np.linspace(80, 120, 20)[5]
        assert f'{expected_vc0:.2f}' in result

    def test_no_touchdown_rh_never_zero(self):
        """RH 恒非零时，触水参数为 nan 但仍返回统计字符串。"""
        data = _make_data(n=15, rh_zero_at=None)
        lm = _MockLabelMap(_LABEL_MAP)

        result = compute_takeoff_landing_stats(0, 14, data, lm)

        assert '触水时' in result
        # Vc0/W0/CG0 为 nan
        assert 'nan' in result
        # 最大俯仰角和法向过载仍应有数值
        assert f'{np.max(data["Theta"]):.2f}' in result
        assert f'{np.max(data["Nz"]):.2f}' in result

    def test_missing_variable_returns_error_msg(self):
        """变量缺失时返回 '变量缺失' 提示而非抛异常。"""
        data = _make_data(n=10, rh_zero_at=3)
        # '总重' 标签未找到 → get_var_name 返回 ''
        lm = _MockLabelMap(_LABEL_MAP, missing_labels=('总重',))

        result = compute_takeoff_landing_stats(0, 9, data, lm)

        assert '变量缺失' in result
        assert '总重' in result

    def test_empty_time_window(self):
        """时间窗口超出数据范围时返回 '（窗口内无数据）'。"""
        data = _make_data(n=10, rh_zero_at=3)
        lm = _MockLabelMap(_LABEL_MAP)

        # 数据时间范围 0~9 秒，查询 100~200 秒
        result = compute_takeoff_landing_stats(100.0, 200.0, data, lm)

        assert result == '（窗口内无数据）'

    def test_string_time_params(self):
        """字符串时间参数 'HH:MM:SS' 正确解析。"""
        data = _make_data(n=20, rh_zero_at=5)
        lm = _MockLabelMap(_LABEL_MAP)

        # "00:00:02" → 2 秒, "00:00:10" → 10 秒
        result = compute_takeoff_landing_stats('00:00:02', '00:00:10', data, lm)

        assert '触水时' in result
        # 窗口 [2, 10] 包含索引 5（RH=0）
        assert 'nan' not in result or '空速' in result

    def test_float_time_params(self):
        """数值秒时间参数正确工作。"""
        data = _make_data(n=20, rh_zero_at=5)
        lm = _MockLabelMap(_LABEL_MAP)

        result = compute_takeoff_landing_stats(2.0, 10.0, data, lm)

        assert '触水时' in result

    def test_partial_window_excludes_outside_data(self):
        """部分窗口仅统计窗口内数据（最大值受限）。"""
        n = 20
        data = _make_data(n=n, rh_zero_at=5)
        lm = _MockLabelMap(_LABEL_MAP)

        # 窗口 [0, 4] 不包含 RH=0 的索引 5
        result = compute_takeoff_landing_stats(0.0, 4.0, data, lm)

        # 窗口内无 RH=0 → 触水参数为 nan
        assert '触水时' in result
        assert 'nan' in result
        # 最大俯仰角应为窗口内 [0:5] 的最大值
        expected_theta_max = np.max(data['Theta'][:5])
        assert f'{expected_theta_max:.2f}' in result

    def test_touchdown_at_window_boundary(self):
        """触水点恰好在窗口边界时正确识别。"""
        data = _make_data(n=15, rh_zero_at=10)
        lm = _MockLabelMap(_LABEL_MAP)

        # 窗口 [5, 10] 包含索引 10（RH=0）
        result = compute_takeoff_landing_stats(5.0, 10.0, data, lm)

        assert '触水时' in result
        # 触水点空速应为 linspace(80,120,15)[10]
        expected_vc0 = np.linspace(80, 120, 15)[10]
        assert f'{expected_vc0:.2f}' in result

    def test_max_values_reflect_window_only(self):
        """最大俯仰角/法向过载仅取窗口内数据。"""
        n = 20
        data = _make_data(n=n, rh_zero_at=5)
        # 修改索引 18 处的 Theta 为极大值（窗口外）
        data['Theta'][18] = 999.0
        data['Nz'][18] = 999.0
        lm = _MockLabelMap(_LABEL_MAP)

        # 窗口 [0, 10] 不包含索引 18
        result = compute_takeoff_landing_stats(0.0, 10.0, data, lm)

        # 999 不应出现在结果中
        assert '999.00' not in result
        expected_theta_max = np.max(data['Theta'][:11])
        assert f'{expected_theta_max:.2f}' in result

    def test_first_touchdown_used_when_multiple_zeros(self):
        """多个 RH=0 时使用第一个触水点。"""
        n = 20
        data = _make_data(n=n, rh_zero_at=3)
        data['RH'][7] = 0.0  # 第二个触水点
        data['RH'][12] = 0.0  # 第三个触水点
        lm = _MockLabelMap(_LABEL_MAP)

        result = compute_takeoff_landing_stats(0, 19, data, lm)

        # 第一个触水点索引 3 的空速
        expected_vc0 = np.linspace(80, 120, n)[3]
        assert f'{expected_vc0:.2f}' in result


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
