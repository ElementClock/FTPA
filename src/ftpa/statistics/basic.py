"""
基础统计函数
"""

import numpy as np
from typing import Optional


def compute_stat(data: np.ndarray, stat_type: str):
    """
    计算单变量的统计值

    对应 MATLAB: computeStat.m

    参数:
        data: 数据数组（numpy 数组）
        stat_type: 统计类型，可选值：
            - 'start': 起始值
            - 'end': 结束值
            - 'min': 最小值
            - 'max': 最大值
            - 'range': 范围（格式化为 "min ~ max"）
            - 'mean': 平均值
            - 'std': 标准差
            - 'points': 数据点数

    返回:
        (value, description): 统计值和描述字符串的元组
    """
    if len(data) == 0:
        raise ValueError("数据数组不能为空")

    stat_type = stat_type.lower()

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
        return f'{min_val:.4g} ~ {max_val:.4g}', '范围'
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
        穿越位置的索引（基于 1-based 位置，等价 MATLAB 的 find(condition)+1）
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

    cross_positions = np.where(condition)[0] + 1
    if len(cross_positions) == 0:
        return None

    if mode.startswith('First'):
        return int(cross_positions[0])
    return int(cross_positions[-1])
