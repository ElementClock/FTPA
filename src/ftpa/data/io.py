"""
底层文件 I/O 操作（私有模块，不直接对外暴露）

提供 ZIP 解压和数据文件读取功能。
"""

import os
import logging
import zipfile
import tempfile
import pandas as pd

logger = logging.getLogger(__name__)


def resolve_zip_file(filepath: str) -> tuple[str, bool]:
    """
    解析 ZIP 文件，返回实际可读的文件路径

    参数:
        filepath: 文件路径（可能是 .zip）

    返回:
        (readable_file, is_temp): 可读文件路径，是否为临时文件
    """
    if not filepath.lower().endswith('.zip'):
        return filepath, False

    # 解压到临时目录
    temp_dir = tempfile.mkdtemp()
    with zipfile.ZipFile(filepath, 'r') as zip_ref:
        # 获取第一个非目录文件
        for info in zip_ref.infolist():
            if not info.is_dir():
                zip_ref.extract(info, temp_dir)
                return os.path.join(temp_dir, info.filename), True

    raise FileNotFoundError("ZIP 压缩包中未找到任何文件。")


def read_data_file(filepath: str) -> pd.DataFrame:
    """
    读取数据文件（支持 ZIP 和普通文本文件）

    参数:
        filepath: 文件路径

    返回:
        DataFrame，列名为原始列名
    """
    readable_file, is_temp = resolve_zip_file(filepath)

    try:
        df = pd.read_csv(readable_file, sep='\t')
        return df
    finally:
        # 清理临时文件
        if is_temp:
            import shutil
            temp_dir = os.path.dirname(readable_file)
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir, ignore_errors=True)
