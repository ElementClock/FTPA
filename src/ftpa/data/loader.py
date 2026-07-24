"""
数据加载模块
对应 MATLAB: paramExtract.m, extractTime.m, extractColumnEfficient.m
负责从数据文件提取所有列数据，支持 ZIP 压缩和缓存机制
"""

import logging
import os
import numpy as np
import pandas as pd
from ..utils.strings import column_to_field_name
from ..constants import TRIM_HEAD, TRIM_TAIL
from .io import read_data_file, resolve_zip_file
from .cache import _file_cache

logger = logging.getLogger(__name__)


def _trim_data(arr, trim_head=TRIM_HEAD, trim_tail=TRIM_TAIL):
    """
    截取数组头尾（与 MATLAB extractColumnEfficient 一致）

    参数:
        arr: 输入数组
        trim_head: 头部截取行数
        trim_tail: 尾部截取行数

    返回:
        截取后的数组；若长度不足则返回空数组
    """
    n_total = len(arr)
    n_drop = trim_head + trim_tail

    if n_total >= n_drop:
        return arr[trim_head:n_total - trim_tail]

    logger.warning("数据长度 (%d) 小于需截取的长度 (%d)，返回空数组。", n_total, n_drop)
    return np.array([]) if isinstance(arr, np.ndarray) else type(arr)()


def param_extract(filename: str) -> dict:
    """
    从数据文件提取所有列到字典（带缓存）

    对应 MATLAB 的 paramExtract 函数

    参数:
        filename: 数据文件路径（支持 .zip 和普通文本）

    返回:
        dict，键为字段名（- 替换为 _），值为 numpy 数组
        特殊键 'filename' 存储文件路径
    """
    # 标准化文件路径
    abs_file = os.path.abspath(filename)

    # 检查缓存
    cached = _file_cache.get(abs_file)
    if cached is not None:
        return cached

    # 读取数据文件
    df = read_data_file(abs_file)

    # 获取原始列名
    raw_names = df.columns.tolist()

    if not raw_names:
        raise ValueError("文件中未检测到任何列名。")

    # 转换列名为合法字段名
    field_names = [column_to_field_name(name) for name in raw_names]

    # 构建数据字典
    data = {}
    for raw_name, field_name in zip(raw_names, field_names):
        col_data = df[raw_name].values
        col_data = _trim_data(col_data)
        data[field_name] = col_data

    # 附加文件名
    data['filename'] = abs_file

    # 存入缓存
    _file_cache.set(abs_file, data)

    return data


def extract_time(filename: str) -> np.ndarray:
    """
    提取 TIME 列并转换为 Timedelta 数组

    对应 MATLAB 的 extractTime 函数

    参数:
        filename: 数据文件路径

    返回:
        numpy 数组，dtype=timedelta64[ns]
    """
    # 读取数据文件
    abs_file = os.path.abspath(filename)
    df = read_data_file(abs_file)

    # 提取 TIME 列（字符串格式）
    time_str = df['TIME'].astype(str)

    # 截取头尾
    time_str = _trim_data(time_str)

    if len(time_str) == 0:
        return np.array([], dtype='timedelta64[ns]')

    # 转换格式：MATLAB 的 TIME 格式为 "HH:MM:SS:mmm"
    # 需要转换为 "HH:MM:SS.mmm" 才能被 pandas 解析
    time_str = time_str.str.replace(r':(\d{3})$', r'.\1', regex=True)

    # 转换为 Timedelta
    time_delta = pd.to_timedelta(time_str)

    return time_delta.values


def extract_column_efficient(filename: str, col_name: str,
                             col_type: str = 'auto') -> np.ndarray:
    """
    高效提取单列数据（带缓存）

    对应 MATLAB 的 extractColumnEfficient 函数

    参数:
        filename: 文件路径
        col_name: 列名（原始列名，未转换）
        col_type: 数据类型，'auto'（自动）或 'string'

    返回:
        numpy 数组
    """
    # 构建缓存键
    abs_file = os.path.abspath(filename)
    cache_key = f"{abs_file}|{col_name}|{col_type}"

    df = _file_cache.get(cache_key)
    if df is None:
        df = read_data_file(abs_file)
        _file_cache.set(cache_key, df)

    # 检查列是否存在
    if col_name not in df.columns:
        available = ', '.join(df.columns[:10])
        raise KeyError(f'文件中未找到列 "{col_name}"。可用列（前10个）: {available}')

    # 提取列
    if col_type == 'string':
        data = df[col_name].astype(str).values
    else:
        data = df[col_name].values

    # 截取头尾
    data = _trim_data(data)

    return data


def clear_cache():
    """清除文件缓存"""
    _file_cache.clear()
