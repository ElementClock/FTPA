"""
数据加载子包
负责从数据文件提取所有列数据，支持 TXT 格式（含 ZIP 压缩），带缓存机制。
CSV 飞参格式不开发，相关加载代码已移除。
"""

# 数据加载与文件参数
# MAPPING_FILENAME 集中定义于 config（顶层），供 utils 与 data 共享，避免 utils 反向依赖 data（P1-ARCH-2）
from ..config import MAPPING_FILENAME  # noqa: E402  标签映射文件名（参数名.csv）
CHUNK_SIZE = 10000                   # 分块读取每块行数

# 数据字典中的元数据键（非测量通道，统计/枚举时跳过）（D3：单一来源）
META_KEYS = frozenset({"TIME", "filename", "_name_mapping"})

from .label_map import LabelMap
from .loader import param_extract, extract_time, extract_column_efficient, clear_cache, _trim_data
from .io import read_data_file, resolve_zip_file
from .cache import FileCache, _file_cache
from .batch import batch_process_files, batch_analyze_statistics, batch_export_summaries
from .enrichment import add_weight_cg_to_data  # P1-ARCH-3: 自 computing 迁入的数据富化函数
from .summary import generate_data_summary, print_data_summary
from .exporter import export_data, export_statistics

__all__ = [
    'MAPPING_FILENAME',
    'CHUNK_SIZE',
    'META_KEYS',
    'LabelMap',
    'param_extract',
    'extract_time',
    'extract_column_efficient',
    'clear_cache',
    'batch_process_files',
    'batch_analyze_statistics',
    'batch_export_summaries',
    'add_weight_cg_to_data',
    'export_data',
    'export_statistics',
    'generate_data_summary',
    'print_data_summary',
]
