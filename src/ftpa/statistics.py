"""
统计计算模块
对应 MATLAB: PrivateStatistics/ 目录下的所有函数
提供单变量统计、多变量统计、分组统计、起降统计、参数统计和阈值穿越分析
"""

import numpy as np
from .time_utils import select_time_window, format_time_seconds
from typing import Optional


def find_crossing_points(values: np.ndarray, threshold: float, mode: str):
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
    # 检查数据是否为空
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
        return np.std(data, ddof=1), '标准差'  # ddof=1 对应 MATLAB 的 std（无偏估计）
    elif stat_type == 'points':
        return len(data), '数据点数'
    else:
        raise ValueError(f'不支持的统计类型: {stat_type}。可用: start/end/min/max/range/mean/std/points')


def compute_var_stats(time_vec, start_t, end_t, *var_args):
    """
    对多个变量在指定时间区间内计算统计值并打印
    
    对应 MATLAB: computeVarStats.m
    
    参数:
        time_vec: 时间向量（支持 timedelta64, 数值秒, TimedeltaIndex）
        start_t: 起始时间
        end_t: 结束时间
        *var_args: 可变参数，格式为 (data, name, stat_type) 三元组的重复
            - data: 数据数组
            - name: 变量名（字符串）
            - stat_type: 统计类型（字符串）
    
    示例:
        compute_var_stats(TIME, 0, 100,
            data1, '变量1', 'mean',
            data2, '变量2', 'max')
    """
    # 参数解析
    n_var_args = len(var_args)
    if n_var_args % 3 != 0:
        raise ValueError(f'变量参数必须为 (data, name, stat_type) 三元组，当前额外参数个数为 {n_var_args}。')
    
    num_vars = n_var_args // 3
    
    # 统一时间窗口
    idx, actual_start, actual_end = select_time_window(time_vec, start_t, end_t)
    
    # 依次处理各变量
    var_names = []
    descs = []
    vals = []
    
    for i in range(num_vars):
        data = var_args[3 * i]
        name = var_args[3 * i + 1]
        stat_type = var_args[3 * i + 2]
        
        if len(time_vec) != len(data):
            raise ValueError(f'TIME 与变量 "{name}" 的长度必须相同。')
        
        segment = data[idx]
        val, desc = compute_stat(segment, stat_type)
        
        var_names.append(name)
        descs.append(desc)
        vals.append(val)
    
    # 格式化输出
    print(f'统计时间区间: {format_time_seconds(actual_start)} - {format_time_seconds(actual_end)}')
    print('变量名\t统计类型\t数值')
    for i in range(num_vars):
        if isinstance(vals[i], (int, float, np.number)):
            print(f'{var_names[i]}\t{descs[i]}\t{vals[i]:.6g}')
        else:
            print(f'{var_names[i]}\t{descs[i]}\t{vals[i]}')


def show_group_stats(time_vec, start_t, end_t, *group_args):
    """
    对多组同类变量计算统计量，并以紧凑的"名/值"格式输出
    
    对应 MATLAB: showGroupStats.m
    
    参数:
        time_vec: 时间向量
        start_t: 起始时间
        end_t: 结束时间
        *group_args: 可变参数，格式为 (stat_type, data_list, name_list) 三元组的重复
            - stat_type: 统计类型（字符串）
            - data_list: 数据列表（list of numpy arrays）
            - name_list: 名称列表（list of strings）
    
    示例:
        show_group_stats(TIME, 0, 100,
            'max', [data1, data2], ['变量1', '变量2'],
            'min', [data3, data4], ['变量3', '变量4'])
    """
    # 时间区间处理
    idx, actual_start, actual_end = select_time_window(time_vec, start_t, end_t)
    
    # 检查输入组数
    n_args = len(group_args)
    if n_args % 3 != 0:
        raise ValueError('输入必须为三元组：(stat_type, data_list, name_list) 的重复。')
    
    n_groups = n_args // 3
    
    # 逐组处理
    for g in range(n_groups):
        stat_type = group_args[3 * g]
        data_list = group_args[3 * g + 1]
        name_list = group_args[3 * g + 2]
        
        if not isinstance(data_list, list) or not isinstance(name_list, list):
            raise ValueError(f'第 {g + 1} 组的 data_list 和 name_list 必须是列表。')
        
        n_vars = len(data_list)
        if len(name_list) != n_vars:
            raise ValueError(f'第 {g + 1} 组中 data_list 与 name_list 长度必须相等。')
        
        # 检查每个变量的长度
        for k in range(n_vars):
            if len(time_vec) != len(data_list[k]):
                raise ValueError(f'TIME 与变量 "{name_list[k]}" 的长度必须相同。')
        
        # 计算每个变量的统计值
        vals = []
        for k in range(n_vars):
            segment = data_list[k][idx]
            val, desc = compute_stat(segment, stat_type)
            vals.append(val)
        
        # 组装名称和值的字符串
        name_str = '/'.join(name_list)
        
        # 格式化值
        val_strs = []
        for v in vals:
            if isinstance(v, (int, float, np.number)):
                val_strs.append(f'{v:.6g}')
            else:
                val_strs.append(str(v))
        
        val_str = '/'.join(val_strs)
        
        print(f'{name_str}\t{desc}\t{val_str}')


def compute_takeoff_landing_stats(t_start, t_end, data: dict, lm) -> str:
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
    # 获取 time 向量并转为数值秒
    from .time_utils import _time_to_seconds_array, _parse_time_to_seconds
    
    t_vec = data['TIME']
    t_vec_sec = _time_to_seconds_array(t_vec)
    t_start_sec = _parse_time_to_seconds(t_start)
    t_end_sec = _parse_time_to_seconds(t_end)
    
    # 窗口索引
    idx = np.where((t_vec_sec >= t_start_sec) & (t_vec_sec <= t_end_sec))[0]
    if len(idx) == 0:
        return '（窗口内无数据）'
    
    # 通过中文标签取数据
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
    
    # 触水时刻
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
    
    # 输出
    stats_str = (f'触水时( RH=0 )：空速={Vc0:.2f}  总重={W0:.2f}  重心={CG0:.2f} '
                 f'最大俯仰角={np.max(Theta):.2f}  最大法向过载={np.max(Nz):.2f}')
    
    return stats_str


def statistics_params(t_start, t_end, data: dict, lm, 
                      signal_ids: Optional[list] = None) -> list:
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
    # 时间窗口
    if 'TIME' not in data:
        raise ValueError('data 必须包含 TIME 字段。')
    
    TIME = data['TIME']
    idx, t_start_actual, t_end_actual = select_time_window(TIME, t_start, t_end)
    
    lines = []
    
    # 确定要处理的字段
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
    
    if not fields_to_process:
        lines.append('未找到可统计的变量。')
        return lines
    
    for field_name in fields_to_process:
        if field_name == 'TIME' or field_name == 'filename':
            continue
        
        signal = data[field_name]
        
        # 检查是否为向量且长度匹配
        if not isinstance(signal, np.ndarray) or len(signal) != len(TIME):
            continue
        
        # 检查是否为数值类型
        if not np.issubdtype(signal.dtype, np.number) and signal.dtype != bool:
            continue
        
        segment = signal[idx]
        label = lm.get_label(field_name)
        
        if len(segment) == 0:
            lines.append(f'{label}: 窗口内无数据')
            continue
        
        stat_types = ['start', 'end', 'min', 'max', 'mean', 'std', 'points']
        values = []
        for st in stat_types:
            val, _ = compute_stat(segment, st)
            if isinstance(val, (int, float, np.number)):
                values.append(f'{val:.6g}')
            else:
                values.append(str(val))
        
        line = (f'{label}  起始={values[0]}, 结束={values[1]}, 最小={values[2]}, '
                f'最大={values[3]}, 平均={values[4]}, 标准差={values[5]}, 点数={values[6]}')
        lines.append(line)
    
    if len(lines) == 0:
        lines.append('未找到可统计的变量。')
    
    return lines


def crossing_analysis(data: dict, lm, signal_ids: list, mode: str, 
                      threshold: float, t_start, t_end) -> list:
    """
    统计主信号在指定窗口内穿越阈值时，其他信号的值
    
    对应 MATLAB: crossingAnalysis.m
    
    参数:
        data: 数据字典，必须包含 'TIME' 键
        lm: LabelMap 对象
        signal_ids: 信号标识符列表，第一项为主信号，其余为关联信号
        mode: 穿越模式，可选值：
            - 'FirstDown': 首次下降穿越
            - 'LastDown': 末次下降穿越
            - 'FirstUp': 首次上升穿越
            - 'LastUp': 末次上升穿越
        threshold: 阈值（数值）
        t_start: 起始时间
        t_end: 结束时间
    
    返回:
        lines: 分析结果字符串列表
    """
    if 'TIME' not in data and 'TIME_sec' not in data:
        raise ValueError('data 必须包含 TIME 或 TIME_sec 字段。')
    
    if not signal_ids or not isinstance(signal_ids, list):
        raise ValueError('signal_ids 必须为非空列表。')
    
    TIME = data.get('TIME', data.get('TIME_sec'))
    idx, t_start_actual, t_end_actual = select_time_window(TIME, t_start, t_end)
    
    n_signals = len(signal_ids)
    fields = []
    labels = []
    
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
    
    main_field = fields[0]
    main_label = labels[0]
    
    if not main_field or main_field not in data:
        return [f'主信号 "{signal_ids[0]}" 未找到']
    
    main_sig = data[main_field]
    if len(main_sig) != len(TIME):
        return [f'主信号 "{main_label}" 与时间向量长度不一致']
    
    main_sig = main_sig[idx]
    
    cross_idx_local = find_crossing_points(main_sig, threshold, mode)
    if cross_idx_local is None:
        return [f'在窗口内未检测到 {main_label} 的 {mode} 穿越（阈值 {threshold:.2f}）']
    
    # 模式文本转换
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
        
        val = other_sig[idx]
        lines.append(f'    {display_name} = {val[cross_idx_local]:.2f}')
    
    return lines
