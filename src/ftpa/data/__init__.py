"""
数据加载子包
负责从数据文件提取所有列数据，支持 ZIP 压缩和缓存机制。
"""

from .loader import param_extract, extract_time, extract_column_efficient, clear_cache, _trim_data
from .io import read_data_file, resolve_zip_file
from .cache import FileCache, _file_cache

__all__ = [
    'param_extract',
    'extract_time',
    'extract_column_efficient',
    'clear_cache',
]
