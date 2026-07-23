"""
统计子包
提供单变量统计、分组统计、起降统计、参数统计和阈值穿越分析。
"""

from .basic import compute_stat, find_crossing_points
from .multi import (
    compute_var_stats, show_group_stats, statistics_params,
    crossing_analysis, generate_data_summary, print_data_summary,
    _compute_var_stats_data, _show_group_stats_data, _format_stat_value,
)
from .event_detection import compute_takeoff_landing_stats

__all__ = [
    'compute_stat',
    'compute_var_stats',
    'show_group_stats',
    'compute_takeoff_landing_stats',
    'statistics_params',
    'crossing_analysis',
    'find_crossing_points',
    'generate_data_summary',
    'print_data_summary',
]
