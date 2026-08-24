"""
多变量统计和穿越分析函数
"""

from __future__ import annotations

import numpy as np
from dataclasses import dataclass
from typing import Optional, Dict, List, Union
from ..utils.time_utils import select_time_window, format_time_seconds
from .basic import compute_stat, find_crossing_points
from ..data.label_map import LabelMap
from ..data import META_KEYS
from ..data.summary import generate_data_summary, print_data_summary  # noqa: F401 — re-exports for backward compatibility


@dataclass
class VarSpec:
    """变量统计规格。"""
    data: np.ndarray
    name: str
    stat_type: str


def _format_stat_value(val: Union[int, float, np.number, str, tuple]) -> str:
    """格式化统计值，数值用 g 格式，其他转为字符串

    对于 range 类型的 (min_val, max_val) 元组，格式化为 'min ~ max'。
    """
    if isinstance(val, tuple):
        # range 类型: (min_val, max_val)
        return f'{val[0]:.4g} ~ {val[1]:.4g}'
    if isinstance(val, (int, float, np.number)):
        return f'{val:.6g}'
    return str(val)


def compute_var_stats_typed(time_vec: np.ndarray, start_t: Union[float, str],
                            end_t: Union[float, str], specs: list[VarSpec]) -> tuple:
    """
    对多个变量在指定时间区间内计算统计值，返回结构化数据（不打印）

    参数:
        time_vec: 时间向量
        start_t: 起始时间
        end_t: 结束时间
        specs: VarSpec 列表，每个元素包含 data, name, stat_type

    返回:
        (var_names, descs, vals, actual_start, actual_end)
    """
    i_start, i_end, actual_start, actual_end = select_time_window(time_vec, start_t, end_t)

    var_names = []
    descs = []
    vals = []

    for spec in specs:
        if len(time_vec) != len(spec.data):
            raise ValueError(f'TIME 与变量 "{spec.name}" 的长度必须相同。')

        segment = spec.data[i_start:i_end + 1]
        val, desc = compute_stat(segment, spec.stat_type)

        var_names.append(spec.name)
        descs.append(desc)
        vals.append(val)

    return var_names, descs, vals, actual_start, actual_end


def _compute_var_stats_data(time_vec: np.ndarray, start_t: Union[float, str],
                            end_t: Union[float, str], *var_args) -> tuple:
    """
    对多个变量在指定时间区间内计算统计值，返回结构化数据（不打印）

    .. deprecated::
        请使用 compute_var_stats_typed，传入 list[VarSpec] 替代 *var_args。

    参数:
        time_vec: 时间向量
        start_t: 起始时间
        end_t: 结束时间
        *var_args: (data, name, stat_type) 三元组的重复

    返回:
        (var_names, descs, vals, actual_start, actual_end)
    """
    n_var_args = len(var_args)
    if n_var_args % 3 != 0:
        raise ValueError(f'变量参数必须为 (data, name, stat_type) 三元组，当前额外参数个数为 {n_var_args}。')

    specs = [
        VarSpec(data=var_args[3 * i], name=var_args[3 * i + 1], stat_type=var_args[3 * i + 2])
        for i in range(n_var_args // 3)
    ]
    return compute_var_stats_typed(time_vec, start_t, end_t, specs)


def compute_var_stats(time_vec: np.ndarray, start_t: Union[float, str],
                      end_t: Union[float, str], *var_args) -> None:
    """
    对多个变量在指定时间区间内计算统计值并打印

    对应 MATLAB: computeVarStats.m

    参数:
        time_vec: 时间向量（支持 timedelta64, 数值秒, TimedeltaIndex）
        start_t: 起始时间
        end_t: 结束时间
        *var_args: 可变参数，格式为 (data, name, stat_type) 三元组的重复

    示例:
        compute_var_stats(TIME, 0, 100,
            data1, '变量1', 'mean',
            data2, '变量2', 'max')
    """
    var_names, descs, vals, actual_start, actual_end = _compute_var_stats_data(
        time_vec, start_t, end_t, *var_args
    )

    print(f'统计时间区间: {format_time_seconds(actual_start)} - {format_time_seconds(actual_end)}')
    print('变量名\t统计类型\t数值')
    for i in range(len(var_names)):
        print(f'{var_names[i]}\t{descs[i]}\t{_format_stat_value(vals[i])}')


@dataclass
class GroupSpec:
    """分组统计规格。"""
    stat_type: str
    data_list: list
    name_list: list


def show_group_stats_typed(time_vec: np.ndarray, start_t: Union[float, str],
                           end_t: Union[float, str], specs: list[GroupSpec]) -> None:
    """
    对多组同类变量计算统计量，并以紧凑的"名/值"格式输出

    参数:
        time_vec: 时间向量
        start_t: 起始时间
        end_t: 结束时间
        specs: GroupSpec 列表，每个元素包含 stat_type, data_list, name_list

    示例:
        show_group_stats_typed(TIME, 0, 100, [
            GroupSpec('max', [data1, data2], ['变量1', '变量2']),
            GroupSpec('min', [data3, data4], ['变量3', '变量4']),
        ])
    """
    results = _compute_group_stats_typed_data(time_vec, start_t, end_t, specs)
    for name_str, desc, val_str in results:
        print(f'{name_str}\t{desc}\t{val_str}')


def _compute_group_stats_typed_data(time_vec: np.ndarray, start_t: Union[float, str],
                                    end_t: Union[float, str], specs: list[GroupSpec]) -> list:
    """对多组同类变量计算统计量，返回结构化数据（不打印）— typed 版本。"""
    i_start, i_end, actual_start, actual_end = select_time_window(time_vec, start_t, end_t)
    results = []

    for g, spec in enumerate(specs):
        stat_type = spec.stat_type
        data_list = spec.data_list
        name_list = spec.name_list

        if not isinstance(data_list, list) or not isinstance(name_list, list):
            raise ValueError(f'第 {g + 1} 组的 data_list 和 name_list 必须是列表。')

        n_vars = len(data_list)
        if len(name_list) != n_vars:
            raise ValueError(f'第 {g + 1} 组中 data_list 与 name_list 长度必须相等。')

        for k in range(n_vars):
            if len(time_vec) != len(data_list[k]):
                raise ValueError(f'TIME 与变量 "{name_list[k]}" 的长度必须相同。')

        vals = []
        for k in range(n_vars):
            segment = data_list[k][i_start:i_end + 1]
            val, desc = compute_stat(segment, stat_type)
            vals.append(val)

        name_str = '/'.join(name_list)
        val_str = '/'.join(_format_stat_value(v) for v in vals)
        results.append((name_str, desc, val_str))

    return results


def _show_group_stats_data(time_vec: np.ndarray, start_t: Union[float, str],
                           end_t: Union[float, str], *group_args) -> list:
    """
    对多组同类变量计算统计量，返回结构化数据（不打印）

    .. deprecated::
        请使用 show_group_stats_typed，传入 list[GroupSpec] 替代 *group_args。

    参数:
        time_vec: 时间向量
        start_t: 起始时间
        end_t: 结束时间
        *group_args: (stat_type, data_list, name_list) 三元组的重复

    返回:
        results: 列表，每项为 (name_str, desc, val_str) 元组
    """
    n_args = len(group_args)
    if n_args % 3 != 0:
        raise ValueError('输入必须为三元组：(stat_type, data_list, name_list) 的重复。')

    specs = [
        GroupSpec(stat_type=group_args[3 * g], data_list=group_args[3 * g + 1], name_list=group_args[3 * g + 2])
        for g in range(n_args // 3)
    ]
    return _compute_group_stats_typed_data(time_vec, start_t, end_t, specs)


def show_group_stats(time_vec: np.ndarray, start_t: Union[float, str],
                      end_t: Union[float, str], *group_args) -> None:
    """
    对多组同类变量计算统计量，并以紧凑的"名/值"格式输出

    对应 MATLAB: showGroupStats.m

    参数:
        time_vec: 时间向量
        start_t: 起始时间
        end_t: 结束时间
        *group_args: 可变参数，格式为 (stat_type, data_list, name_list) 三元组的重复

    示例:
        show_group_stats(TIME, 0, 100,
            'max', [data1, data2], ['变量1', '变量2'],
            'min', [data3, data4], ['变量3', '变量4'])
    """
    results = _show_group_stats_data(time_vec, start_t, end_t, *group_args)
    for name_str, desc, val_str in results:
        print(f'{name_str}\t{desc}\t{val_str}')


def _statistics_params_impl(
    data: Dict[str, np.ndarray],
    t_start: Union[float, str],
    t_end: Union[float, str],
    signal_ids: Optional[List[str]] = None,
    lm: Optional[LabelMap] = None,
    field_resolver=None,
) -> List[str]:
    """statistics_params 的统一实现，同时支撑带/不带 LabelMap 两种模式。

    参数:
        data: 数据字典，必须包含 'TIME' 键
        t_start: 起始时间
        t_end: 结束时间
        signal_ids: 可选，指定要统计的信号字段名或中文标签列表
        lm: 可选 LabelMap 对象；提供时按 LabelMap 模式解析字段与标签
        field_resolver: 可选，提供 get_field_names() 方法的对象，
                        当 signal_ids 为空且不使用 LabelMap 时用于枚举字段

    返回:
        lines: 统计结果字符串列表
    """
    use_labelmap = lm is not None

    # TIME 字段检查：带 LabelMap 模式抛异常，CSV 模式返回提示
    if 'TIME' not in data:
        if use_labelmap:
            raise ValueError('data 必须包含 TIME 字段。')
        return ['数据中无 TIME 字段']

    TIME = data['TIME']
    i_start, i_end, _, _ = select_time_window(TIME, t_start, t_end)

    lines = []

    # 确定要处理的字段
    if use_labelmap:
        if signal_ids is None or len(signal_ids) == 0:
            fields_to_process = list(data.keys())
        else:
            fields_to_process = []
            for sig_id in signal_ids:
                if sig_id in data:
                    field = sig_id
                else:
                    field = lm.get_var_name(sig_id)

                if not field or field not in data:
                    lines.append(f'信号 "{sig_id}" 未找到或不在 data 中')
                    continue

                if field not in fields_to_process:
                    fields_to_process.append(field)
    else:
        if not signal_ids:
            fields_to_process = field_resolver.get_field_names() if field_resolver else []
        else:
            fields_to_process = [s for s in signal_ids if s in data]

    if not fields_to_process:
        lines.append('未找到可统计的变量。')
        return lines

    for field_name in fields_to_process:
        # 仅在 LabelMap 模式下需要跳过元数据键（因为可能来自 data.keys()）
        if use_labelmap and field_name in META_KEYS:
            continue

        signal = data[field_name]

        if not isinstance(signal, np.ndarray) or len(signal) != len(TIME):
            continue

        if not np.issubdtype(signal.dtype, np.number) and signal.dtype != bool:
            continue

        segment = signal[i_start:i_end + 1]
        label = lm.get_label(field_name) if use_labelmap else field_name

        if len(segment) == 0:
            lines.append(f'{label}: 窗口内无数据')
            continue

        stat_types = ['start', 'end', 'min', 'max', 'mean', 'std', 'points']
        values = []
        for st in stat_types:
            val, _ = compute_stat(segment, st)
            values.append(_format_stat_value(val))

        line = (f'{label}  起始={values[0]}, 结束={values[1]}, 最小={values[2]}, '
                f'最大={values[3]}, 平均={values[4]}, 标准差={values[5]}, 点数={values[6]}')
        lines.append(line)

    if not lines:
        lines.append('未找到可统计的变量。')

    return lines


def statistics_params(t_start: Union[float, str], t_end: Union[float, str],
                      data: Dict[str, np.ndarray], lm: LabelMap,
                      signal_ids: Optional[List[str]] = None) -> List[str]:
    """
    计算指定时间窗口内 data 中信号的统计摘要

    对应 MATLAB: statisticsParams.m

    参数:
        t_start: 起始时间
        t_end: 结束时间
        data: 数据字典，必须包含 'TIME' 键
        lm: LabelMap 对象
        signal_ids: 可选，指定要统计的信号字段名或中文标签列表

    返回:
        lines: 统计结果字符串列表
    """
    return _statistics_params_impl(data, t_start, t_end,
                                   signal_ids=signal_ids, lm=lm, field_resolver=None)


def statistics_params_without_labelmap(
    data: Dict[str, np.ndarray],
    t_start: Union[float, str],
    t_end: Union[float, str],
    signal_ids: Optional[List[str]] = None,
    field_resolver=None,
) -> List[str]:
    """CSV 模式参数统计：列名即为标签，无需 LabelMap。

    参数:
        data: 数据字典，必须包含 'TIME' 键
        t_start: 起始时间
        t_end: 结束时间
        signal_ids: 可选，指定要统计的信号字段名列表
        field_resolver: 可选，提供 get_field_names() 方法的对象，
                        当 signal_ids 为空时用于枚举字段

    返回:
        lines: 统计结果字符串列表
    """
    return _statistics_params_impl(data, t_start, t_end,
                                   signal_ids=signal_ids, lm=None,
                                   field_resolver=field_resolver)


def _crossing_analysis_impl(
    data: Dict[str, np.ndarray],
    signal_ids: List[str],
    mode: str,
    threshold: float,
    t_start: Union[float, str],
    t_end: Union[float, str],
    lm: Optional[LabelMap] = None,
) -> List[str]:
    """crossing_analysis 的统一实现，同时支撑带/不带 LabelMap 两种模式。

    参数:
        data: 数据字典，必须包含 'TIME' 键
        signal_ids: 信号标识符列表，第一项为主信号，其余为关联信号
        mode: 穿越模式
        threshold: 阈值（数值）
        t_start: 起始时间
        t_end: 结束时间
        lm: 可选 LabelMap 对象；提供时按 LabelMap 模式解析字段与标签

    返回:
        lines: 分析结果字符串列表
    """
    use_labelmap = lm is not None

    # 前置校验：带 LabelMap 模式抛异常并兼容 TIME_sec；CSV 模式返回提示
    if use_labelmap:
        if 'TIME' not in data and 'TIME_sec' not in data:
            raise ValueError('data 必须包含 TIME 或 TIME_sec 字段。')
        if not signal_ids or not isinstance(signal_ids, list):
            raise ValueError('signal_ids 必须为非空列表。')
        TIME = data.get('TIME', data.get('TIME_sec'))
    else:
        if not signal_ids:
            return ['signal_ids 不能为空']
        TIME = data.get('TIME')
        if TIME is None:
            return ['数据中无 TIME 字段']

    i_start, i_end, _, _ = select_time_window(TIME, t_start, t_end)

    n_signals = len(signal_ids)
    fields = []
    labels = []

    if use_labelmap:
        for i in range(n_signals):
            sig_id = signal_ids[i]
            if sig_id in data:
                fields.append(sig_id)
                labels.append(lm.get_label(sig_id))
            else:
                field = lm.get_var_name(sig_id)
                if not field or field not in data:
                    fields.append('')
                    labels.append(sig_id)
                else:
                    fields.append(field)
                    labels.append(lm.get_label(field))
    else:
        fields = [s if s in data else '' for s in signal_ids]
        labels = signal_ids  # CSV 列名即为标签

    main_field = fields[0]
    main_label = labels[0]

    if not main_field or main_field not in data:
        return [f'主信号 "{signal_ids[0]}" 未找到']

    main_sig = data[main_field]
    if len(main_sig) != len(TIME):
        return [f'主信号 "{main_label}" 与时间向量长度不一致']

    main_sig = main_sig[i_start:i_end + 1]

    cross_idx_local = find_crossing_points(main_sig, threshold, mode)
    if cross_idx_local is None:
        return [f'在窗口内未检测到 {main_label} 的 {mode} 穿越（阈值 {threshold:.2f}）']

    mode_text = mode.replace('First', '首次').replace('Last', '末次')
    mode_text = mode_text.replace('Down', '下降').replace('Up', '上升')

    lines = [f'{main_label} {mode_text}穿越阈值 {threshold:.2f} 时：']

    for i in range(1, n_signals):
        other_field = fields[i]
        display_name = labels[i]

        if not other_field or other_field not in data:
            lines.append(f'    {signal_ids[i]} = (无数据)')
            continue

        other_sig = data[other_field]
        if len(other_sig) != len(TIME):
            lines.append(f'    {display_name} = (长度不一致)')
            continue

        val = other_sig[i_start:i_end + 1]
        cross_idx = cross_idx_local
        lines.append(f'    {display_name} = {val[cross_idx]:.2f}')

    return lines


def crossing_analysis_without_labelmap(
    data: Dict[str, np.ndarray],
    signal_ids: List[str],
    mode: str,
    threshold: float,
    t_start: Union[float, str],
    t_end: Union[float, str],
) -> List[str]:
    """CSV 模式穿越分析：列名即为标签，无需 LabelMap。

    参数:
        data: 数据字典，必须包含 'TIME' 键
        signal_ids: 信号标识符列表，第一项为主信号，其余为关联信号
        mode: 穿越模式
        threshold: 阈值（数值）
        t_start: 起始时间
        t_end: 结束时间

    返回:
        lines: 分析结果字符串列表
    """
    return _crossing_analysis_impl(data, signal_ids, mode, threshold, t_start, t_end, lm=None)


def crossing_analysis(data: Dict[str, np.ndarray], lm: LabelMap,
                      signal_ids: List[str], mode: str,
                      threshold: float, t_start: Union[float, str],
                      t_end: Union[float, str]) -> List[str]:
    """
    统计主信号在指定窗口内穿越阈值时，其他信号的值

    对应 MATLAB: crossingAnalysis.m

    参数:
        data: 数据字典，必须包含 'TIME' 键
        lm: LabelMap 对象
        signal_ids: 信号标识符列表，第一项为主信号，其余为关联信号
        mode: 穿越模式
        threshold: 阈值（数值）
        t_start: 起始时间
        t_end: 结束时间

    返回:
        lines: 分析结果字符串列表
    """
    return _crossing_analysis_impl(data, signal_ids, mode, threshold, t_start, t_end, lm=lm)
