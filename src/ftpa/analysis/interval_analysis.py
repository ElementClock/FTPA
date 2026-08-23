"""区间分析功能模块。

提供可扩展的区间分析操作注册表，当前支持：
- 积分
- 最大值
- 最小值
- 平均值
- 极值（最大+最小）

后续新增分析功能时，继承 IntervalOperation 并注册到 INTERVAL_OPERATIONS 即可。
"""

from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np


class IntervalOperation(ABC):
    """区间分析操作基类。"""

    name: str = ""

    @abstractmethod
    def execute(self, time_sec: np.ndarray, values: np.ndarray) -> str:
        """执行分析并返回格式化结果文本。"""


def _valid_data(time_sec: np.ndarray, values: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """过滤 NaN，返回有效的时间与数值数组。"""
    valid = ~np.isnan(values)
    return time_sec[valid], values[valid]


class IntegralOperation(IntervalOperation):
    """数值积分。"""

    name = "积分"

    def execute(self, time_sec: np.ndarray, values: np.ndarray) -> str:
        t, v = _valid_data(time_sec, values)
        if len(t) < 2:
            return "积分：有效数据不足"
        return f"积分：{np.trapezoid(v, t):.6g}"


class MaxOperation(IntervalOperation):
    """最大值及对应时间。"""

    name = "最大值"

    def execute(self, time_sec: np.ndarray, values: np.ndarray) -> str:
        if len(values) == 0 or np.isnan(values).all():
            return "最大值：无有效数据"
        idx = int(np.nanargmax(values))
        return f"最大值：{values[idx]:.6g} @ {time_sec[idx]:.3f}s"


class MinOperation(IntervalOperation):
    """最小值及对应时间。"""

    name = "最小值"

    def execute(self, time_sec: np.ndarray, values: np.ndarray) -> str:
        if len(values) == 0 or np.isnan(values).all():
            return "最小值：无有效数据"
        idx = int(np.nanargmin(values))
        return f"最小值：{values[idx]:.6g} @ {time_sec[idx]:.3f}s"


class MeanOperation(IntervalOperation):
    """平均值。"""

    name = "平均值"

    def execute(self, time_sec: np.ndarray, values: np.ndarray) -> str:
        if len(values) == 0 or np.isnan(values).all():
            return "平均值：无有效数据"
        return f"平均值：{np.nanmean(values):.6g}"


class ExtremaOperation(IntervalOperation):
    """极值：同时输出最大值和最小值。"""

    name = "极值"

    def execute(self, time_sec: np.ndarray, values: np.ndarray) -> str:
        if len(values) == 0 or np.isnan(values).all():
            return "极值：无有效数据"
        max_idx = int(np.nanargmax(values))
        min_idx = int(np.nanargmin(values))
        return (
            f"极值：最大={values[max_idx]:.6g} @ {time_sec[max_idx]:.3f}s, "
            f"最小={values[min_idx]:.6g} @ {time_sec[min_idx]:.3f}s"
        )


INTERVAL_OPERATIONS: dict[str, IntervalOperation] = {
    operation.name: operation
    for operation in (
        IntegralOperation(),
        MaxOperation(),
        MinOperation(),
        MeanOperation(),
        ExtremaOperation(),
    )
}


def run_interval_analysis(
    time_sec: np.ndarray,
    values: np.ndarray,
    operation_name: str,
) -> str:
    """执行指定名称的区间分析。

    Args:
        time_sec: 时间数组（秒）。
        values: 信号数值数组，与 time_sec 等长。
        operation_name: 操作名称，见 INTERVAL_OPERATIONS。

    Returns:
        格式化分析结果文本。
    """
    time_arr = np.asarray(time_sec, dtype=float)
    value_arr = np.asarray(values, dtype=float)

    if len(time_arr) != len(value_arr):
        raise ValueError("时间数组与信号数组长度不一致")

    operation = INTERVAL_OPERATIONS.get(operation_name)
    if operation is None:
        raise ValueError(f"不支持的区间分析功能: {operation_name}")

    return operation.execute(time_arr, value_arr)
