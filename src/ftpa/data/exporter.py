"""
数据导出模块
支持多种格式的数据导出：CSV、Parquet、HDF5、Excel、JSON
"""

import gzip
import os
import json
import logging
import numpy as np
import pandas as pd
from typing import Dict, Union, Optional
from datetime import datetime
from .summary import generate_data_summary, print_data_summary  # noqa: F401 — re-exports
from ..utils.file_utils import is_safe_path

logger = logging.getLogger(__name__)


def export_data(data: Dict[str, np.ndarray],
                output_path: str,
                output_format: str = 'csv',
                time_format: str = 'string',
                compression: Optional[str] = None) -> str:
    """
    导出数据到指定格式

    参数:
        data: 数据字典，包含 TIME 和其他信号
        output_path: 输出文件路径（不含扩展名）
        format: 导出格式，可选 'csv', 'parquet', 'hdf5', 'excel', 'json'
            (注意: 实际参数名为 output_format)
        time_format: 时间格式，'string' 或 'timedelta'
        compression: 压缩方式，如 'gzip', 'snappy'（json 仅支持 gzip）

    返回:
        实际保存的文件路径

    示例:
        >>> export_data(data, 'output/result', output_format='parquet')
        'output/result.parquet'
    """
    # 安全校验：防止路径遍历攻击（P1-SEC-1）
    output_dir = os.path.dirname(output_path)
    base_dir = output_dir or os.getcwd()
    if not is_safe_path(base_dir, output_path):
        raise ValueError(f"不安全的输出路径: {output_path}")

    # 确保输出目录存在
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # 转换为 DataFrame
    df = _data_to_dataframe(data, time_format)

    # 根据格式导出
    output_format = output_format.lower()

    if output_format == 'csv':
        file_path = f"{output_path}.csv"
        df.to_csv(file_path, index=False, compression=compression)

    elif output_format == 'parquet':
        file_path = f"{output_path}.parquet"
        # parquet 不支持所有压缩方式，使用默认
        df.to_parquet(file_path, compression=compression or 'snappy')

    elif output_format == 'hdf5':
        file_path = f"{output_path}.h5"
        # HDF5 需要指定 key
        df.to_hdf(file_path, key='data', mode='w', complevel=6 if compression else 0)

    elif output_format == 'excel':
        file_path = f"{output_path}.xlsx"
        # Excel 不支持超过 1,048,576 行
        if len(df) > 1048576:
            raise ValueError(f"数据行数 {len(df)} 超过 Excel 限制 1,048,576 行")
        df.to_excel(file_path, index=False)

    elif output_format == 'json':
        file_path = f"{output_path}.json"
        if compression and compression != 'gzip':
            raise ValueError("JSON 导出仅支持 gzip 压缩，请选择“无”或 gzip")
        json_text = df.to_json(orient='records', force_ascii=False, date_format='iso', lines=False)
        if compression == 'gzip':
            file_path = f"{file_path}.gz"
            with gzip.open(file_path, 'wt', encoding='utf-8') as f:
                f.write(json_text)
        else:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(json_text)

    else:
        raise ValueError(f"不支持的导出格式: {output_format}。支持: csv, parquet, hdf5, excel, json")

    logger.info("数据已导出到: %s", file_path)
    logger.info("  格式: %s", output_format.upper())
    logger.info("  行数: %d", len(df))
    logger.info("  列数: %d", len(df.columns))
    if compression:
        logger.info("  压缩: %s", compression)

    return file_path


def _data_to_dataframe(data: Dict[str, np.ndarray],
                       time_format: str = 'string') -> pd.DataFrame:
    """
    将数据字典转换为 DataFrame

    参数:
        data: 数据字典
        time_format: 时间格式，'string' 或 'timedelta'

    返回:
        DataFrame
    """
    df_dict = {}

    for key, value in data.items():
        if key == 'TIME':
            if time_format == 'string':
                # 将 timedelta64 转换为字符串格式 HH:MM:SS.mmm
                df_dict[key] = _timedelta_to_string(value)
            else:
                # 保持 timedelta 格式
                df_dict[key] = value
        else:
            df_dict[key] = value

    return pd.DataFrame(df_dict)


def _timedelta_to_string(time_array: np.ndarray) -> np.ndarray:
    """
    将 timedelta64 数组转换为字符串数组（向量化实现）。

    参数:
        time_array: timedelta64 数组

    返回:
        字符串数组，格式为 HH:MM:SS.mmm
    """
    # 一次性转为浮点秒数
    total_seconds = time_array / np.timedelta64(1, 's')
    total_seconds = np.asarray(total_seconds, dtype=np.float64)

    # 向量化计算时、分、秒、毫秒
    hours = np.floor(total_seconds / 3600).astype(np.int32)
    remainder = total_seconds - hours * 3600
    minutes = np.floor(remainder / 60).astype(np.int32)
    remainder = remainder - minutes * 60
    seconds = np.floor(remainder).astype(np.int32)
    milliseconds = np.round((remainder - seconds) * 1000).astype(np.int32)

    # 向量化格式化
    result = np.char.zfill(hours.astype(str), 2)
    result = np.char.add(result, np.char.zfill(minutes.astype(str), 2).astype(str))
    # 逐元素拼接更可靠（np.char 对长链拼接有兼容性问题）
    return np.array([
        f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"
        for h, m, s, ms in zip(hours, minutes, seconds, milliseconds)
    ])


def export_statistics(stats: Dict, output_path: str, output_format: str = 'csv') -> str:
    """
    导出统计结果

    参数:
        stats: 统计结果字典
        output_path: 输出文件路径（不含扩展名）
        output_format: 导出格式，'csv' 或 'json'

    返回:
        实际保存的文件路径
    """
    # 安全校验：防止路径遍历攻击（P1-SEC-1）
    output_dir = os.path.dirname(output_path)
    base_dir = output_dir or os.getcwd()
    if not is_safe_path(base_dir, output_path):
        raise ValueError(f"不安全的输出路径: {output_path}")

    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)

    output_format = output_format.lower()

    if output_format == 'csv':
        file_path = f"{output_path}_stats.csv"
        df = pd.DataFrame(stats)
        df.to_csv(file_path, index=False, encoding='utf-8-sig')

    elif output_format == 'json':
        file_path = f"{output_path}_stats.json"
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(stats, f, ensure_ascii=False, indent=2)

    else:
        raise ValueError(f"不支持的格式: {output_format}。支持: csv, json")

    logger.info("统计结果已导出到: %s", file_path)
    return file_path
