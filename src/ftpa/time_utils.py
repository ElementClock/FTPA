"""
时间工具模块
对应 MATLAB: selectTimeWindow.m
提供时间窗口选择功能，支持多种时间格式
"""

import numpy as np
import pandas as pd
from typing import Union


def parse_time_to_seconds(t) -> float:
    """
    将各种时间格式统一转换为数值秒

    支持：
    - 数值（已经是秒）
    - 字符串 'HH:MM:SS.mmm' 或 'HH:MM:SS:mmm'
    - pd.Timedelta / np.timedelta64
    """
    if isinstance(t, (int, float, np.integer, np.floating)):
        return float(t)
    elif isinstance(t, (pd.Timedelta, np.timedelta64)):
        return pd.Timedelta(t).total_seconds()
    elif isinstance(t, str):
        # 处理 'HH:MM:SS:mmm' 格式（MATLAB 风格）
        # 将 HH:MM:SS:mmm 转换为 HH:MM:SS.mmm
        parts = t.split(':')
        if len(parts) == 4:
            # 格式为 HH:MM:SS:mmm
            t = f"{parts[0]}:{parts[1]}:{parts[2]}.{parts[3]}"
        # 尝试解析为 Timedelta
        try:
            return pd.Timedelta(t).total_seconds()
        except ValueError:
            return float(t)
    else:
        raise TypeError(f"无法将 {type(t)} 转换为数值秒")


def time_to_seconds_array(time_vec) -> np.ndarray:
    """
    将时间向量统一转换为数值秒数组

    支持：
    - numpy array of timedelta64
    - pandas TimedeltaIndex
    - 数值数组（已经是秒）
    """
    if isinstance(time_vec, np.ndarray) and np.issubdtype(time_vec.dtype, np.timedelta64):
        return time_vec.astype('timedelta64[ns]').astype(np.float64) / 1e9
    elif isinstance(time_vec, pd.TimedeltaIndex):
        return time_vec.total_seconds().values
    elif isinstance(time_vec, np.ndarray) and np.issubdtype(time_vec.dtype, np.number):
        return time_vec.astype(np.float64)
    else:
        # 尝试逐元素转换
        return np.array([parse_time_to_seconds(t) for t in time_vec], dtype=np.float64)


def select_time_window(time_vec, t_start, t_end):
    """
    根据时间窗口选择数据索引

    对应 MATLAB 的 selectTimeWindow 函数

    参数:
        time_vec: 时间向量（支持 timedelta64, 数值秒, TimedeltaIndex）
        t_start: 起始时间（支持数值秒、字符串 'HH:MM:SS.mmm'、Timedelta）
        t_end: 结束时间（同上）

    返回:
        (idx, t_start_actual, t_end_actual):
        - idx: 布尔索引数组，指示窗口内的数据点
        - t_start_actual: 实际起始时间（TIME 中离 t_start 最近的点）
        - t_end_actual: 实际结束时间（TIME 中离 t_end 最近的点）
    """
    # 转换为数值秒
    time_sec = time_to_seconds_array(time_vec)
    t_start_sec = parse_time_to_seconds(t_start)
    t_end_sec = parse_time_to_seconds(t_end)

    # 找到最近的索引
    i_start = np.argmin(np.abs(time_sec - t_start_sec))
    i_end = np.argmin(np.abs(time_sec - t_end_sec))

    # 保证起始索引小于等于结束索引
    if i_start > i_end:
        i_start, i_end = i_end, i_start

    # 构建布尔索引
    idx = np.zeros(len(time_vec), dtype=bool)
    idx[i_start:i_end + 1] = True

    # 返回实际起止时间（数值秒）
    t_start_actual = time_sec[i_start]
    t_end_actual = time_sec[i_end]

    return idx, t_start_actual, t_end_actual


def format_time_seconds(t_sec: float) -> str:
    """
    将数值秒格式化为 'HH:MM:SS.mmm' 字符串

    对应 MATLAB 的 datestr(seconds(t), 'HH:MM:SS.FFF')
    """
    if np.isnan(t_sec):
        return 'NaN'

    total_ms = int(round(t_sec * 1000))
    hours = total_ms // 3600000
    total_ms %= 3600000
    minutes = total_ms // 60000
    total_ms %= 60000
    seconds = total_ms // 1000
    ms = total_ms % 1000

    return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{ms:03d}"


def format_duration_chinese(seconds: float) -> str:
    """
    将秒数格式化为中文时长字符串

    参数:
        seconds: 秒数

    返回:
        格式化字符串，如 "1小时23分45秒"
    """
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)

    parts = []
    if hours > 0:
        parts.append(f"{hours}小时")
    if minutes > 0:
        parts.append(f"{minutes}分")
    parts.append(f"{secs}秒")

    return ''.join(parts)
