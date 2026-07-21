"""
可视化模块
对应 MATLAB: PlotFigure/ 目录下的所有函数
提供时间序列绘图、交互绘图和航线轨迹绘图功能
"""

import os
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.widgets import Button, RadioButtons, TextBox
from .time_utils import select_time_window, format_time_seconds
from .statistics import find_crossing_points
from typing import Optional, Callable


def _configure_display_font():
    """配置中文字体，优先使用系统可用字体，并提供回退。"""
    preferred_fonts = [
        'Microsoft YaHei',
        'SimHei',
        'Arial Unicode MS',
        'Noto Sans CJK SC',
        'WenQuanYi Zen Hei',
        'DejaVu Sans',
    ]

    available_fonts = set()
    try:
        import matplotlib.font_manager as fm
        available_fonts = {font.name for font in fm.fontManager.ttflist}
    except Exception:
        available_fonts = set()

    selected_font = None
    for font_name in preferred_fonts:
        if font_name in available_fonts:
            selected_font = font_name
            break

    if selected_font is None:
        selected_font = 'DejaVu Sans'

    plt.rcParams['font.family'] = 'sans-serif'
    plt.rcParams['font.sans-serif'] = [selected_font, 'DejaVu Sans', 'Arial']
    plt.rcParams['axes.unicode_minus'] = False
    return selected_font


_configure_display_font()


def plot_time_signals(time_vec, signals, labels, time_range=None):
    """
    绘制多个时间序列信号，支持手动指定Y轴标签
    
    对应 MATLAB: plot_time_signals.m
    
    参数:
        time_vec: 时间向量（numpy 数组）
        signals: 信号数据，可以是：
            - numpy 数组（N x M）：每列作为一个信号
            - list of numpy arrays：每个元素为一个信号
        labels: Y轴标签列表，长度与信号个数相同
        time_range: 可选，[tStart, tEnd] 设置 X 轴范围
    
    示例:
        plot_time_signals(TIME, [sig1, sig2], ['信号1', '信号2'])
        plot_time_signals(TIME, signal_matrix, ['信号1', '信号2'], time_range=[10, 50])
    """
    # 解析信号数据
    if isinstance(signals, np.ndarray) and signals.ndim == 2:
        # 矩阵形式，按列拆分
        if signals.shape[0] != len(time_vec):
            raise ValueError('信号矩阵的行数必须等于 TIME 的长度。')
        n_signals = signals.shape[1]
        all_signals = [signals[:, i] for i in range(n_signals)]
    elif isinstance(signals, list):
        # 列表形式
        n_signals = len(signals)
        all_signals = []
        for i, sig in enumerate(signals):
            if len(sig) != len(time_vec):
                raise ValueError(f'第 {i + 1} 个信号的长度必须与 TIME 一致。')
            all_signals.append(sig)
    else:
        raise ValueError('signals 必须是矩阵或列表。')
    
    # 解析标签
    if not isinstance(labels, list) or len(labels) != n_signals:
        raise ValueError(f'labels 的长度（{len(labels)}）与信号个数（{n_signals}）不匹配。')
    
    # 绘制
    fig, axes = plt.subplots(n_signals, 1, figsize=(12, 7), sharex=True)
    if n_signals == 1:
        axes = [axes]
    
    for i in range(n_signals):
        axes[i].plot(time_vec, all_signals[i], linewidth=0.8)
        axes[i].set_ylabel(labels[i])
        axes[i].grid(True)
        if time_range is not None:
            axes[i].set_xlim(time_range)
        
        if i == n_signals - 1:
            axes[i].set_xlabel('时间 (s)')
    
    plt.tight_layout()
    plt.show()


def plot_time_signals_interactive(data: dict, lm, signal_ids: list, 
                                   stats_func: Optional[Callable] = None):
    """
    交互信号绘图（基于 data 字典 + lm 映射对象）
    
    对应 MATLAB: plot_time_signals_interactive.m
    
    参数:
        data: 数据字典，必须包含 'TIME' 键
        lm: LabelMap 对象
        signal_ids: 信号标识符列表，可以是中文标签或字段名
        stats_func: 可选，自定义统计函数，输入 (t_start, t_end, data, lm)，输出字符串
    
    示例:
        plot_time_signals_interactive(data, lm, 
            ['无线电高度表决值', '指示空速表决值', '俯仰角表决值'],
            stats_func=my_stats_func)
    """
    # 从 data 和 lm 中提取 TIME, signals, labels
    if 'TIME' not in data:
        raise ValueError('数据字典中必须包含 TIME 字段')
    
    TIME = data['TIME']
    n_signals = len(signal_ids)
    
    signals = np.zeros((len(TIME), n_signals))
    labels = []
    
    for i in range(n_signals):
        sig_id = signal_ids[i]
        
        # 获取字段名：优先判断 sig_id 是否直接是 data 的字段名
        if sig_id in data:
            field = sig_id
        else:
            # 否则通过 lm 将中文标签转换为字段名
            field = lm.get_var_name(sig_id)
            if not field or field not in data:
                raise ValueError(f'无法识别信号标识 "{sig_id}"，既不是数据字段名，也无法通过标签映射找到。')
        
        # 提取数据
        col = data[field]
        if len(col) != len(TIME):
            raise ValueError(f'字段 {field} 的数据长度与 TIME 不一致。')
        signals[:, i] = col
        
        # 获取中文标签
        try:
            label = lm.get_label(field)
        except:
            label = field  # 回退到字段名
        labels.append(label)
    
    # 调用绘图核心
    _plot_core_interactive(TIME, signals, labels, stats_func)


def _build_stats_lines(time_sec, signals, labels, t_start, t_end,
                       main_series=None, crossing_threshold=0.0,
                       crossing_mode='FirstUp'):
    """构造交互绘图中的窗口统计文本。"""
    idx = (time_sec >= t_start) & (time_sec <= t_end)
    info_lines = [f'时间窗口: {format_time_seconds(t_start)} - {format_time_seconds(t_end)}']

    for i in range(len(labels)):
        seg = signals[idx, i]
        if len(seg) > 0:
            info_lines.append(
                f'{labels[i]}: min={np.min(seg):.4g}, max={np.max(seg):.4g}, mean={np.mean(seg):.4g}'
            )

    if main_series is not None:
        try:
            pos = find_crossing_points(main_series, crossing_threshold, crossing_mode)
            if pos is not None:
                info_lines.append(f'穿越提示: {crossing_mode} -> {pos}')
            else:
                info_lines.append(f'穿越提示: {crossing_mode} -> 无')
        except Exception:
            info_lines.append(f'穿越提示: {crossing_mode} -> 无')

    return info_lines


def _plot_core_interactive(time_vec, signals, labels, stats_func=None):
    """
    核心交互绘图函数
    
    对应 MATLAB: plotCoreInteractive.m
    
    参数:
        time_vec: 时间向量
        signals: 信号矩阵（N x M）
        labels: 标签列表
        stats_func: 可选统计函数
    """
    from .time_utils import _time_to_seconds_array
    
    # 转换为数值秒用于交互
    time_sec = _time_to_seconds_array(time_vec)
    n_signals = len(labels)
    
    # 创建图形
    fig, axes = plt.subplots(n_signals, 1, figsize=(12, 7), sharex=True)
    if n_signals == 1:
        axes = [axes]
    
    # 绘制所有信号
    lines = []
    for i in range(n_signals):
        line, = axes[i].plot(time_sec, signals[:, i], linewidth=0.8)
        axes[i].set_ylabel(labels[i])
        axes[i].grid(True)
        lines.append(line)
        
        if i == n_signals - 1:
            axes[i].set_xlabel('时间 (s)')
    
    fig.subplots_adjust(bottom=0.31, top=0.94, left=0.08, right=0.98)
    
    # 添加统计信息显示框
    stats_text = fig.text(0.02, 0.98, '', verticalalignment='top', 
                          fontsize=9, family='monospace',
                          bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))

    # 控制面板
    threshold_box = None
    mode_buttons = None
    signal_buttons = None
    apply_button = None
    reset_button = None
    crossing_lines = []
    current_threshold = 0.0
    current_mode = 'FirstUp'
    current_signal_idx = 0

    def clear_crossing_lines():
        for line in crossing_lines:
            try:
                line.remove()
            except Exception:
                pass
        crossing_lines.clear()

    def refresh_crossing_overlay():
        clear_crossing_lines()
        nonlocal current_threshold, current_mode, current_signal_idx
        try:
            threshold_value = float(threshold_box.text)
            current_threshold = threshold_value
        except Exception:
            current_threshold = 0.0

        current_mode = mode_buttons.value_selected
        current_signal_idx = signal_buttons.value_selected
        main_series = signals[:, current_signal_idx]
        pos = find_crossing_points(main_series, current_threshold, current_mode)
        if pos is None:
            return

        x_pos = time_sec[pos - 1]
        for ax in axes:
            line = ax.axvline(x_pos, color='red', linewidth=1.0, alpha=0.7)
            crossing_lines.append(line)

    def update_stats(event=None):
        """根据当前 X 轴范围更新统计信息"""
        xlim = axes[0].get_xlim()
        t_start, t_end = xlim[0], xlim[1]
        
        info_lines = _build_stats_lines(
            time_sec,
            signals,
            labels,
            t_start,
            t_end,
            main_series=signals[:, current_signal_idx],
            crossing_threshold=current_threshold,
            crossing_mode=current_mode,
        )
        
        if stats_func is not None:
            try:
                custom_stats = stats_func(t_start, t_end, time_vec, signals, labels)
                if custom_stats:
                    info_lines.append('---')
                    info_lines.extend(custom_stats)
            except Exception as e:
                info_lines.append(f'统计函数错误: {e}')
        
        stats_text.set_text('\n'.join(info_lines))
        fig.canvas.draw_idle()

    # 控制面板
    panel_ax = fig.add_axes([0.06, 0.02, 0.88, 0.24])
    panel_ax.axis('off')

    threshold_ax = fig.add_axes([0.08, 0.12, 0.18, 0.05])
    threshold_box = TextBox(threshold_ax, '阈值', initial='0.0')

    mode_ax = fig.add_axes([0.30, 0.12, 0.28, 0.08])
    mode_buttons = RadioButtons(mode_ax, ['FirstDown', 'LastDown', 'FirstUp', 'LastUp'])
    mode_buttons.set_active(2)

    signal_ax = fig.add_axes([0.60, 0.12, 0.22, 0.08])
    signal_buttons = RadioButtons(signal_ax, labels)
    signal_buttons.set_active(0)

    apply_ax = fig.add_axes([0.84, 0.12, 0.08, 0.05])
    apply_button = Button(apply_ax, '应用')

    reset_ax = fig.add_axes([0.84, 0.06, 0.08, 0.05])
    reset_button = Button(reset_ax, '重置')

    def on_apply(event=None):
        refresh_crossing_overlay()
        update_stats()

    def on_reset(event=None):
        clear_crossing_lines()
        if len(time_vec) > 0:
            xlim = [float(np.min(time_sec)), float(np.max(time_sec))]
            for ax in axes:
                ax.set_xlim(xlim)
        update_stats()

    apply_button.on_clicked(on_apply)
    reset_button.on_clicked(on_reset)
    mode_buttons.on_clicked(lambda _: update_stats())
    signal_buttons.on_clicked(lambda _: update_stats())
    threshold_box.on_submit(lambda _: on_apply())

    # 连接事件
    fig.canvas.mpl_connect('button_release_event', lambda event: update_stats())
    fig.canvas.mpl_connect('scroll_event', lambda event: update_stats())
    
    # 初始更新
    current_signal_idx = 0
    current_threshold = 0.0
    current_mode = 'FirstUp'
    update_stats()
    
    plt.show()


def plot_track(latitude, longitude, title='航线轨迹'):
    """
    绘制航线轨迹地理图
    
    对应 MATLAB: plotTrack.m
    使用 matplotlib 绘制简单的经纬度轨迹图（不依赖地图服务）
    
    参数:
        latitude: 纬度数组（度）
        longitude: 经度数组（度）
        title: 图标题
    
    示例:
        plot_track(data['Latitude_I1'], data['Longitude_I1'])
    """
    fig, ax = plt.subplots(figsize=(10, 8))
    
    ax.plot(longitude, latitude, linewidth=1, color='blue')
    ax.set_xlabel('经度 (°)')
    ax.set_ylabel('纬度 (°)')
    ax.set_title(title)
    ax.grid(True)
    ax.set_aspect('equal')
    
    # 标注起点和终点
    ax.plot(longitude[0], latitude[0], 'go', markersize=8, label='起点')
    ax.plot(longitude[-1], latitude[-1], 'ro', markersize=8, label='终点')
    ax.legend()
    
    plt.tight_layout()
    plt.show()


def compute_window_stats(time_vec, signals, labels, t_start, t_end):
    """
    计算时间窗口内各信号的统计信息
    
    对应 MATLAB: computeWindowStats.m
    
    参数:
        time_vec: 时间向量
        signals: 信号列表或矩阵
        labels: 标签列表
        t_start: 起始时间
        t_end: 结束时间
    
    返回:
        stats: 统计信息字典列表
    """
    from .time_utils import _time_to_seconds_array, _parse_time_to_seconds
    
    time_sec = _time_to_seconds_array(time_vec)
    t_start_sec = _parse_time_to_seconds(t_start)
    t_end_sec = _parse_time_to_seconds(t_end)
    
    idx = (time_sec >= t_start_sec) & (time_sec <= t_end_sec)
    
    # 解析信号
    if isinstance(signals, np.ndarray) and signals.ndim == 2:
        sig_list = [signals[:, i] for i in range(signals.shape[1])]
    else:
        sig_list = signals
    
    stats = []
    for i, sig in enumerate(sig_list):
        seg = sig[idx]
        if len(seg) > 0:
            stats.append({
                'label': labels[i],
                'min': np.min(seg),
                'max': np.max(seg),
                'mean': np.mean(seg),
                'std': np.std(seg, ddof=1) if len(seg) > 1 else 0.0,
                'points': len(seg)
            })
    
    return stats
