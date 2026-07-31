"""
基础统计函数
"""

from __future__ import annotations

from enum import StrEnum

import numpy as np
from typing import Optional


class StatType(StrEnum):
    """统计类型枚举（StrEnum，可直接当字符串使用）。

    用法:
        compute_stat(data, StatType.MEAN)   # 等价于 compute_stat(data, 'mean')
        StatType.MEAN == 'mean'             # True
    """
    START = 'start'
    END = 'end'
    MIN = 'min'
    MAX = 'max'
    RANGE = 'range'
    MEAN = 'mean'
    STD = 'std'
    POINTS = 'points'


def compute_stat(data: np.ndarray, stat_type: str | StatType):
    """
    计算单变量的统计值

    对应 MATLAB: computeStat.m

    参数:
        data: 数据数组（numpy 数组）
        stat_type: 统计类型，可选值：
            - 'start' / StatType.START: 起始值
            - 'end' / StatType.END: 结束值
            - 'min' / StatType.MIN: 最小值
            - 'max' / StatType.MAX: 最大值
            - 'range' / StatType.RANGE: 范围（格式化为 "min ~ max"）
            - 'mean' / StatType.MEAN: 平均值
            - 'std' / StatType.STD: 标准差
            - 'points' / StatType.POINTS: 数据点数

    返回:
        (value, description): 统计值和描述字符串的元组
    """
    if len(data) == 0:
        raise ValueError("数据数组不能为空")

    # 兼容 StatType 枚举和普通字符串（非破坏性变更）
    stat_type = str(stat_type).lower()

    if stat_type == 'start':
        return data[0], '起始值'
    elif stat_type == 'end':
        return data[-1], '结束值'
    elif stat_type == 'min':
        return np.min(data), '最小值'
    elif stat_type == 'max':
        return np.max(data), '最大值'
    elif stat_type == 'range':
        min_val = np.min(data)
        max_val = np.max(data)
        return float(min_val), float(max_val), '范围'
    elif stat_type == 'mean':
        return np.mean(data), '平均值'
    elif stat_type == 'std':
        return np.std(data, ddof=1), '标准差'
    elif stat_type == 'points':
        return len(data), '数据点数'
    else:
        raise ValueError(f'不支持的统计类型: {stat_type}。可用: start/end/min/max/range/mean/std/points')


def find_crossing_points(values: np.ndarray, threshold: float, mode: str) -> Optional[int]:
    """
    以 MATLAB 风格检测阈值穿越点。

    参数:
        values: 输入序列
        threshold: 阈值
        mode: 支持 'FirstDown' / 'LastDown' / 'FirstUp' / 'LastUp'

    返回:
        穿越位置的索引（0-based），即穿越发生在 values[idx] 与 values[idx+1] 之间。
        若未检测到穿越则返回 None。
    """
    values = np.asarray(values)
    if len(values) < 2:
        raise ValueError('至少需要两个数据点才能检测穿越。')

    if mode in ['FirstDown', 'LastDown']:
        condition = (values[:-1] > threshold) & (values[1:] <= threshold)
    elif mode in ['FirstUp', 'LastUp']:
        condition = (values[:-1] < threshold) & (values[1:] >= threshold)
    else:
        raise ValueError(f'不支持的穿越模式: {mode}')

    cross_positions = np.where(condition)[0]
    if len(cross_positions) == 0:
        return None

    if mode.startswith('First'):
        return int(cross_positions[0])
    return int(cross_positions[-1])
