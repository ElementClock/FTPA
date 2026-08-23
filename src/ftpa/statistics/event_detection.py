"""
事件检测函数

对应 MATLAB: PrivateStatistics/computeTakeoffLandingStats.m
"""

from __future__ import annotations

import numpy as np
from ..utils.time_utils import parse_time_to_seconds, select_time_window, time_to_seconds_array
from ..data.label_map import LabelMap


def compute_takeoff_landing_stats(
    t_start: float | str,
    t_end: float | str,
    data: dict[str, np.ndarray],
    lm: LabelMap,
) -> str:
    """
    起降统计（兼容 duration 和数值秒）

    对应 MATLAB: computeTakeoffLandingStats.m

    参数:
        t_start: 起始时间
        t_end: 结束时间
        data: 数据字典，必须包含 'TIME' 键
        lm: LabelMap 对象，用于中文标签→字段名映射

    返回:
        stats_str: 统计结果字符串
    """
    t_vec = data['TIME']
    if len(t_vec) == 0:
        return '（窗口内无数据）'

    # 保留原有“窗口完全超出数据范围/起止倒置时返回无数据”的语义；
    # 仅 None / 空字符串表示全时段。
    t_vec_sec = time_to_seconds_array(t_vec)
    t_start_sec = parse_time_to_seconds(t_start) if t_start is not None and t_start != "" else None
    t_end_sec = parse_time_to_seconds(t_end) if t_end is not None and t_end != "" else None

    if t_start_sec is not None and t_end_sec is not None and t_start_sec > t_end_sec:
        return '（窗口内无数据）'
    if t_start_sec is not None and t_start_sec > t_vec_sec[-1]:
        return '（窗口内无数据）'
    if t_end_sec is not None and t_end_sec < t_vec_sec[0]:
        return '（窗口内无数据）'

    i_start, i_end, _, _ = select_time_window(t_vec, t_start, t_end)
    idx = np.arange(i_start, i_end + 1)
    if len(idx) == 0:
        return '（窗口内无数据）'

    def get_val(label: str) -> np.ndarray:
        field_name = lm.get_var_name(label)
        if not field_name or field_name not in data:
            raise KeyError(f'变量 "{label}" 未找到')
        return data[field_name][idx]

    try:
        RH = get_val('无线电高度表决值')
        Vc = get_val('指示空速表决值')
        W = get_val('总重')
        CG = get_val('相对重心')
        Theta = get_val('俯仰角表决值')
        Nz = get_val('法向过载_I1')
    except KeyError as e:
        return f'变量缺失: {e}'

    rh0_idx = np.where(RH == 0)[0]
    if len(rh0_idx) == 0:
        Vc0 = np.nan
        W0 = np.nan
        CG0 = np.nan
    else:
        rh0 = rh0_idx[0]
        Vc0 = Vc[rh0]
        W0 = W[rh0]
        CG0 = CG[rh0]

    stats_str = (f'触水时( RH=0 )：空速={Vc0:.2f}  总重={W0:.2f}  重心={CG0:.2f} '
                 f'最大俯仰角={np.max(Theta):.2f}  最大法向过载={np.max(Nz):.2f}')

    return stats_str
