"""区间分析功能测试。"""

from __future__ import annotations

import numpy as np
import pytest

from ftpa.analysis.interval_analysis import (
    INTERVAL_OPERATIONS,
    run_interval_analysis,
)


class TestIntervalAnalysis:
    def test_integral(self):
        time = np.linspace(0, 10, 101)
        values = np.ones_like(time)
        result = run_interval_analysis(time, values, "积分")
        assert result.startswith("积分：")
        assert abs(float(result.split("：")[1]) - 10.0) < 1e-6

    def test_max(self):
        time = np.array([0.0, 1.0, 2.0, 3.0])
        values = np.array([1.0, 5.0, 2.0, 4.0])
        result = run_interval_analysis(time, values, "最大值")
        assert result == "最大值：5 @ 1.000s"

    def test_min(self):
        time = np.array([0.0, 1.0, 2.0, 3.0])
        values = np.array([1.0, 5.0, -2.0, 4.0])
        result = run_interval_analysis(time, values, "最小值")
        assert result == "最小值：-2 @ 2.000s"

    def test_mean(self):
        time = np.array([0.0, 1.0, 2.0, 3.0])
        values = np.array([1.0, 2.0, 3.0, 4.0])
        result = run_interval_analysis(time, values, "平均值")
        assert result == "平均值：2.5"

    def test_extrema(self):
        time = np.array([0.0, 1.0, 2.0, 3.0])
        values = np.array([1.0, 5.0, -2.0, 4.0])
        result = run_interval_analysis(time, values, "极值")
        assert "最大=5" in result
        assert "最小=-2" in result

    def test_nan_handling(self):
        time = np.array([0.0, 1.0, 2.0])
        values = np.array([np.nan, 2.0, np.nan])
        result = run_interval_analysis(time, values, "平均值")
        assert result == "平均值：2"

    def test_all_nan(self):
        time = np.array([0.0, 1.0])
        values = np.array([np.nan, np.nan])
        assert run_interval_analysis(time, values, "最大值").startswith("最大值：无有效数据")

    def test_unknown_operation(self):
        with pytest.raises(ValueError, match="不支持的区间分析功能"):
            run_interval_analysis(np.array([0.0]), np.array([1.0]), "不存在")

    def test_registry_has_expected_operations(self):
        assert set(INTERVAL_OPERATIONS.keys()) == {
            "积分",
            "最大值",
            "最小值",
            "平均值",
            "极值",
        }
