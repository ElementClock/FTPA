"""
工具函数子包
提供字符串处理、列名转换、文件路径发现、编码检测等功能。
"""

from .strings import make_valid_name, column_to_field_name
from .paths import resolve_excel_path
from .file_utils import detect_encoding, is_safe_path, sanitize_filename

__all__ = [
    'make_valid_name',
    'column_to_field_name',
    'resolve_excel_path',
    'detect_encoding',
    'is_safe_path',
    'sanitize_filename',
]
