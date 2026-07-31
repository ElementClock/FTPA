"""
FTPA - 飞机性能操稳数据分析工具

AG600试飞数据处理系统
"""

__version__ = "1.0.1"
__author__ = "FTPA Team"

from .data import param_extract, extract_time
from .data.label_map import LabelMap
from .computing import compute_total_weight_rel_cg, compute_fitted_circle_radius
from .statistics import (
    compute_stat,
    compute_var_stats,
    show_group_stats,
    compute_takeoff_landing_stats,
    statistics_params,
    crossing_analysis
)
from .utils.time_utils import select_time_window, format_time_seconds, parse_time_to_seconds, time_to_seconds_array
from .utils import make_valid_name, column_to_field_name
from .data.exporter import (
    export_data,
    export_statistics,
    generate_data_summary,
    print_data_summary
)
from .data.batch import (
    batch_process_files,
    batch_analyze_statistics,
    batch_export_summaries
)
from .config import Config, CONFIG
from .errors import FtpaError, LoadError, FileNotFoundLoadError, FormatLoadError, ResourceLoadError, LabelMapLoadError

__all__ = [
    # Data loading
    'param_extract',
    'extract_time',
    # Label mapping
    'LabelMap',
    # Computing
    'compute_total_weight_rel_cg',
    'compute_fitted_circle_radius',
    # Statistics
    'compute_stat',
    'compute_var_stats',
    'show_group_stats',
    'compute_takeoff_landing_stats',
    'statistics_params',
    'crossing_analysis',
    # Time utilities
    'select_time_window',
    'format_time_seconds',
    # Utils
    'make_valid_name',
    'column_to_field_name',
    # Exporter
    'export_data',
    'export_statistics',
    'generate_data_summary',
    'print_data_summary',
    # Batch processor (moved from batch_processor.py to data/batch.py)
    'batch_process_files',
    'batch_analyze_statistics',
    'batch_export_summaries',
    # Config
    'Config',
    'CONFIG',
    # Errors
    'FtpaError',
    'LoadError',
    'FileNotFoundLoadError',
    'FormatLoadError',
    'ResourceLoadError',
    'LabelMapLoadError',
]
