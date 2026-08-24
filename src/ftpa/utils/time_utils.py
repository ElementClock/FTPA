"""
时间工具模块
对应 MATLAB: selectTimeWindow.m
提供时间窗口选择功能，支持多种时间格式
"""

import numpy as np
import pandas as pd


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
        t_start: 起始时间（支持数值秒、字符串 'HH:MM:SS.mmm'、Timedelta；
                 None 或空字符串表示从最早时间开始）
        t_end: 结束时间（同上；None 或空字符串表示到最晚时间结束）

    返回:
        (i_start, i_end, t_start_actual, t_end_actual):
        - i_start: 窗口起始索引（含），用于 data[i_start:i_end+1] 切片
        - i_end: 窗口结束索引（含），用于 data[i_start:i_end+1] 切片
        - t_start_actual: 实际起始时间（TIME 中离 t_start 最近的点）
        - t_end_actual: 实际结束时间（TIME 中离 t_end 最近的点）

    边界语义（MATLAB 兼容，勿与其他"无数据即报错"的调用方混淆）：
        - 空数组：返回 (0, 0, 0.0, 0.0)；
        - 起止倒置（t_start > t_end）：自动交换，返回较小区间；
        - 超出数据范围：钳位到最近数据点（非报错）；
        - None / 空字符串：对应侧取全时段。
        需要"窗口完全无数据即返回"语义的调用方（如 event_detection），
        应自行前置校验，见 event_detection.py 的说明。
    """
    # 转换为数值秒
    time_sec = time_to_seconds_array(time_vec)

    n = len(time_sec)

    # 空数组防御：searchsorted 对空数组返回 0，后续索引会越界
    if n == 0:
        return 0, 0, 0.0, 0.0

    # 开放边界：None / 空字符串表示“全时段”
    if t_start is None or t_start == "":
        i_start = 0
        t_start_actual = float(time_sec[0])
    else:
        t_start_sec = parse_time_to_seconds(t_start)
        # O(log N) 查找：先用 searchsorted 定位插入点，再调整到最近点
        i_start = int(np.searchsorted(time_sec, t_start_sec, side="left"))
        if i_start >= n:
            i_start = n - 1
        elif i_start > 0 and (t_start_sec - time_sec[i_start - 1]) <= (time_sec[i_start] - t_start_sec):
            i_start -= 1
        t_start_actual = float(time_sec[i_start])

    if t_end is None or t_end == "":
        i_end = n - 1
        t_end_actual = float(time_sec[-1])
    else:
        t_end_sec = parse_time_to_seconds(t_end)
        i_end = int(np.searchsorted(time_sec, t_end_sec, side="left"))
        if i_end >= n:
            i_end = n - 1
        elif i_end > 0 and (t_end_sec - time_sec[i_end - 1]) <= (time_sec[i_end] - t_end_sec):
            i_end -= 1
        t_end_actual = float(time_sec[i_end])

    # 保证起始索引小于等于结束索引
    if i_start > i_end:
        i_start, i_end = i_end, i_start
        t_start_actual, t_end_actual = t_end_actual, t_start_actual

    return i_start, i_end, t_start_actual, t_end_actual


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
