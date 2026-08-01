"""
数据加载子包
负责从数据文件提取所有列数据，支持 TXT、CSV 格式，ZIP 压缩和缓存机制。
"""

# 数据加载与文件参数
# EXCEL_FILENAME 集中定义于 config（顶层），供 utils 与 data 共享，避免 utils 反向依赖 data（P1-ARCH-2）
from ..config import EXCEL_FILENAME  # noqa: E402  标签映射 Excel 文件名
CHUNK_SIZE = 10000                   # 分块读取每块行数

from .column_config import get_replacement_rules, apply_replacement_rules
from .label_map import LabelMap
from .loader import param_extract, extract_time, extract_column_efficient, clear_cache, _trim_data
from .io import read_data_file, resolve_zip_file
from .cache import FileCache, _file_cache
from .csv_loader import csv_param_extract
from .batch import batch_process_files, batch_analyze_statistics, batch_export_summaries
from .enrichment import add_weight_cg_to_data  # P1-ARCH-3: 自 computing 迁入的数据富化函数
from .summary import generate_data_summary, print_data_summary
from .exporter import export_data, export_statistics

__all__ = [
    'EXCEL_FILENAME',
    'CHUNK_SIZE',
    'get_replacement_rules',
    'apply_replacement_rules',
    'LabelMap',
    'param_extract',
    'extract_time',
    'extract_column_efficient',
    'clear_cache',
    'csv_param_extract',
    'batch_process_files',
    'batch_analyze_statistics',
    'batch_export_summaries',
    'add_weight_cg_to_data',
    'export_data',
    'export_statistics',
    'generate_data_summary',
    'print_data_summary',
]
