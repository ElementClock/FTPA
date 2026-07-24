"""
分析管道 — 业务逻辑编排层。

将数据加载、重量重心计算、统计分析和交互绘图等流程
从 CLI 入口 (main.py) 中解耦，提供可复用的分析管道函数。
"""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path
from typing import Callable

import numpy as np

from .data import param_extract, extract_time
from .label_map import LabelMap
from .computing.weight_cg import add_weight_cg_to_data
from .statistics import compute_var_stats, show_group_stats, compute_takeoff_landing_stats
from .plotting import plot_time_signals_interactive
from .utils.paths import resolve_path, DEFAULT_TXT_FILE
from .utils import resolve_excel_path

logger = logging.getLogger(__name__)


# 默认信号 ID（可配置）
DEFAULT_SIGNAL_IDS = [
    '无线电高度表决值',
    '指示空速表决值',
    '俯仰角表决值',
    '法向过载_I1',
]


def load_and_prepare(
    data_file: str | os.PathLike[str] | None = None,
    excel_file: str | os.PathLike[str] | None = None,
) -> tuple[dict, LabelMap, str]:
    """
    加载数据、标签映射、计算重量重心。

    这是所有分析管道的共享第一步。

    参数:
        data_file: 数据文件路径（None 则自动发现）
        excel_file: 标签 Excel 文件路径（None 则自动发现）

    返回:
        (data, lm, txt_path) 元组：
        - data: 数据字典，含 TIME、各信号和 totalWeight/relCg
        - lm: LabelMap 实例
        - txt_path: 实际使用的数据文件路径

    异常:
        FileNotFoundError: 标签映射文件不存在
    """
    txt_path = resolve_path(data_file, DEFAULT_TXT_FILE)
    excel_path = resolve_excel_path(excel_file)
    if not os.path.exists(excel_path):
        raise FileNotFoundError(f"标签映射文件不存在: {excel_path}")

    data = param_extract(txt_path)
    data['TIME'] = extract_time(txt_path)
    lm = LabelMap(excel_path)
    add_weight_cg_to_data(data, lm)
    return data, lm, txt_path


def build_takeoff_landing_stats_func(data: dict, lm: LabelMap) -> Callable:
    """
    构造起降统计回调函数（供交互绘图使用）。

    参数:
        data: 数据字典
        lm: LabelMap 实例

    返回:
        stats_func(t_start, t_end, time_vec, signals, labels) -> list[str]
    """
    def stats_func(t_start, t_end, time_vec, signals, labels):
        try:
            return [compute_takeoff_landing_stats(t_start, t_end, data, lm)]
        except Exception as e:
            return [f'起降统计错误: {e}']
    return stats_func


def full_analysis(
    data_file: str | os.PathLike[str] | None = None,
    excel_file: str | os.PathLike[str] | None = None,
) -> None:
    """
    完整分析流程：
    1. 加载数据和标签映射
    2. 计算重量重心
    3. 绘制交互图表
    """
    print("=" * 70)
    print("完整分析流程")
    print("=" * 70)

    print("\n[1/3] 加载数据、标签映射、计算重量重心...")
    start = time.time()
    data, lm, txt_path = load_and_prepare(data_file, excel_file)
    print(f"  数据加载完成: {len(data['TIME'])} 行, {len(data)} 列")
    avg_w = np.mean(data.get('totalWeight', [0]))
    avg_cg = np.mean(data.get('relCg', [0]))
    print(f"  平均总重: {avg_w:.2f} kg | 平均重心: {avg_cg:.2f} %")
    print(f"  耗时: {time.time() - start:.2f}s")

    stats_func = build_takeoff_landing_stats_func(data, lm)
    plot_time_signals_interactive(data, lm, DEFAULT_SIGNAL_IDS, stats_func=stats_func)


def interactive_view(
    data_file: str | os.PathLike[str] | None = None,
    excel_file: str | os.PathLike[str] | None = None,
) -> None:
    """启动可交互查看模式，展示多信号时间序列并支持窗口统计与穿越分析。"""
    print("=" * 70)
    print("交互式查看模式")
    print("=" * 70)

    data, lm, _ = load_and_prepare(data_file, excel_file)
    stats_func = build_takeoff_landing_stats_func(data, lm)
    plot_time_signals_interactive(data, lm, DEFAULT_SIGNAL_IDS, stats_func=stats_func)


def stats_analysis(
    data_file: str | os.PathLike[str] | None = None,
    excel_file: str | os.PathLike[str] | None = None,
) -> None:
    """
    统计分析流程：
    1. 加载数据
    2. 加载标签映射
    3. 计算重量重心
    4. 输出统计结果
    """
    data, lm, _ = load_and_prepare(data_file, excel_file)

    print("=" * 70)
    print("统计分析流程")
    print("=" * 70)
    print(f"  数据加载完成: {len(data['TIME'])} 行, {len(data)} 列")
    print(f"  重量重心计算完成")

    # 输出统计结果
    start_t = '10:01:00.000'
    end_t = '10:02:00.000'

    print(f"\n统计时间区间: {start_t} - {end_t}")

    # 多变量统计
    compute_var_stats(
        data['TIME'], start_t, end_t,
        data['totalWeight'], '总重', 'start',
        data['relCg'], '重心', 'start',
        data['AirSpeed_vote'], '空速表决值', 'start',
        data['Theta_vote'], '俯仰角表决值', 'range'
    )
