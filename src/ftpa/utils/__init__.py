"""
工具函数子包
提供字符串处理、列名转换、文件路径发现、编码检测等功能。
"""

from .log_utils import setup_logging
from .time_utils import (
    parse_time_to_seconds,
    time_to_seconds_array,
    select_time_window,
    format_time_seconds,
    format_duration_chinese,
)
from .strings import make_valid_name, column_to_field_name
from .paths import resolve_mapping_path
from .file_utils import detect_encoding, is_safe_path, sanitize_filename

__all__ = [
    'setup_logging',
    'parse_time_to_seconds',
    'time_to_seconds_array',
    'select_time_window',
    'format_time_seconds',
    'format_duration_chinese',
    'make_valid_name',
    'column_to_field_name',
    'resolve_mapping_path',
    'detect_encoding',
    'is_safe_path',
    'sanitize_filename',
]
