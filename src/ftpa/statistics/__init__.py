"""
统计子包
提供单变量统计、分组统计、起降统计、参数统计和阈值穿越分析。
"""

from .basic import compute_stat, find_crossing_points, find_all_crossings, StatType
from .multi import (
    VarSpec, GroupSpec,
    compute_var_stats_typed, show_group_stats_typed,
    compute_var_stats, show_group_stats, statistics_params,
    statistics_params_without_labelmap,
    crossing_analysis, crossing_analysis_without_labelmap,
    generate_data_summary, print_data_summary,
    _compute_var_stats_data, _show_group_stats_data, _format_stat_value,
)
from .event_detection import compute_takeoff_landing_stats

__all__ = [
    'StatType',
    'compute_stat',
    'compute_var_stats',
    'compute_var_stats_typed',
    'show_group_stats',
    'show_group_stats_typed',
    'VarSpec',
    'GroupSpec',
    'compute_takeoff_landing_stats',
    'statistics_params',
    'statistics_params_without_labelmap',
    'crossing_analysis',
    'crossing_analysis_without_labelmap',
    'find_crossing_points',
    'find_all_crossings',
    'generate_data_summary',
    'print_data_summary',
]
