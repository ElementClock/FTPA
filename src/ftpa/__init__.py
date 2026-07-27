"""
FTPA - 飞机性能操稳数据分析工具

AG600试飞数据处理系统
"""

__version__ = "1.0.1"
__author__ = "FTPA Team"

from .data import param_extract, extract_time
from .label_map import LabelMap
from .computing import compute_total_weight_rel_cg, compute_fitted_circle_radius
from .statistics import (
    compute_stat,
    compute_var_stats,
    show_group_stats,
    compute_takeoff_landing_stats,
    statistics_params,
    crossing_analysis
)
from .plotting import plot_time_signals, plot_time_signals_interactive, plot_track
from .time_utils import select_time_window, format_time_seconds, parse_time_to_seconds, time_to_seconds_array
from .utils import make_valid_name, column_to_field_name
from .exporter import (
    export_data,
    export_statistics,
    generate_data_summary,
    print_data_summary
)
from .batch_processor import (
    batch_process_files,
    batch_analyze_statistics,
    batch_export_summaries
)
from .pipeline import (
    load_and_prepare,
    full_analysis,
    interactive_view,
    stats_analysis,
    DEFAULT_SIGNAL_IDS,
)
from .config import Config, CONFIG

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
    # Plotting
    'plot_time_signals',
    'plot_time_signals_interactive',
    'plot_track',
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
    # Batch processor
    'batch_process_files',
    'batch_analyze_statistics',
    'batch_export_summaries',
    # Pipeline
    'load_and_prepare',
    'full_analysis',
    'interactive_view',
    'stats_analysis',
    'DEFAULT_SIGNAL_IDS',
    # Config
    'Config',
    'CONFIG',
]
