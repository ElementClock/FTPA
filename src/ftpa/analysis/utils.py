"""
分析辅助函数
============

提供时间段合并、数值阈值检测等通用分析工具。
"""

from __future__ import annotations

import logging
from typing import List, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def merge_continuous_time_periods(
    periods: List[Tuple[float, float]],
    gap_threshold: float = 1.0,
) -> List[Tuple[float, float]]:
    """合并连续或接近的时间段。

    Args:
        periods: 时间段列表 [(start, end), ...]。
        gap_threshold: 间隔小于此阈值的时间段将被合并。

    Returns:
        合并后的时间段列表。
    """
    if not periods:
        return []

    sorted_periods = sorted(periods, key=lambda x: x[0])
    merged = [sorted_periods[0]]

    for start, end in sorted_periods[1:]:
        prev_start, prev_end = merged[-1]
        if start - prev_end <= gap_threshold:
            merged[-1] = (prev_start, max(prev_end, end))
        else:
            merged.append((start, end))

    return merged


def find_threshold_crossings(
    values: np.ndarray,
    threshold: float,
    direction: str = "up",
) -> List[int]:
    """查找数组穿越阈值的索引。"""
    if len(values) < 2:
        return []

    if direction == "up":
        mask = (values[:-1] < threshold) & (values[1:] >= threshold)
    elif direction == "down":
        mask = (values[:-1] >= threshold) & (values[1:] < threshold)
    else:
        raise ValueError(f"direction 必须为 'up' 或 'down'，收到 '{direction}'")

    return np.where(mask)[0].tolist()


def compute_statistics(values: np.ndarray) -> dict:
    """计算数组的统计特征。"""
    if len(values) == 0:
        return {"mean": 0.0, "std": 0.0, "min": 0.0, "max": 0.0,
                "median": 0.0, "count": 0}

    return {
        "mean": float(np.mean(values)),
        "std": float(np.std(values)),
        "min": float(np.min(values)),
        "max": float(np.max(values)),
        "median": float(np.median(values)),
        "count": len(values),
    }
