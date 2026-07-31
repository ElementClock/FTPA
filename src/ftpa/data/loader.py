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
from ..config import CONFIG
from .io import read_data_file, resolve_zip_file
from .cache import _file_cache

logger = logging.getLogger(__name__)


def _trim_data(arr, trim_head=None, trim_tail=None):
    """
    截取数组头尾（与 MATLAB extractColumnEfficient 一致）

    参数:
        arr: 输入数组
        trim_head: 头部截取行数（默认取 CONFIG.data.trim_head）
        trim_tail: 尾部截取行数（默认取 CONFIG.data.trim_tail）

    返回:
        截取后的数组；若长度不足则返回空数组
    """
    if trim_head is None:
        trim_head = CONFIG.data.trim_head
    if trim_tail is None:
        trim_tail = CONFIG.data.trim_tail
    n_total = len(arr)
    n_drop = trim_head + trim_tail

    if n_total >= n_drop:
        return arr[trim_head:n_total - trim_tail]

    logger.warning("数据长度 (%d) 小于需截取的长度 (%d)，返回空数组。", n_total, n_drop)
    return np.array([]) if isinstance(arr, np.ndarray) else type(arr)()


def param_extract(filename: str) -> dict:
    """
    从数据文件提取所有列到字典（带缓存）

    对应 MATLAB 的 paramExtract 函数。

    本函数是数据加载的唯一入口，内部同时完成：
    - 文件读取（仅一次 pd.read_csv）
    - TIME 列解析为 timedelta64
    - 数值列内联转换为 float64
    - 头尾裁剪 (trim)

    参数:
        filename: 数据文件路径（支持 .zip 和普通文本）

    返回:
        dict，键为字段名（- 替换为 _），值为 numpy 数组。
        TIME 键为 timedelta64 数组，数值列已转为 float64。
        特殊键 'filename' 存储文件路径。
    """
    # 标准化文件路径
    abs_file = os.path.abspath(filename)

    # 检查缓存
    cached = _file_cache.get(abs_file)
    if cached is not None:
        return cached

    # 读取数据文件（唯一一次 I/O）
    df = read_data_file(abs_file)

    # 获取原始列名
    raw_names = df.columns.tolist()

    if not raw_names:
        raise ValueError("文件中未检测到任何列名。")

    # 转换列名为合法字段名
    field_names = [column_to_field_name(name) for name in raw_names]

    # TIME 列：内联解析（不再依赖独立的 extract_time 读取）
    data: dict = {}
    if 'TIME' in df.columns:
        time_str = df['TIME'].astype(str)
        time_str = _trim_data(time_str)
        if len(time_str) > 0:
            # MATLAB TIME 格式 "HH:MM:SS:mmm" → "HH:MM:SS.mmm"
            time_str = time_str.str.replace(r':(\d{3})$', r'.\1', regex=True)
            data['TIME'] = pd.to_timedelta(time_str).values
        else:
            data['TIME'] = np.array([], dtype='timedelta64[ns]')

    # 构建数据字典，数值列直接 float64（内联转换，避免下游重复转换）
    for raw_name, field_name in zip(raw_names, field_names):
        if raw_name == 'TIME':
            continue
        col_data = _trim_data(df[raw_name].values)
        try:
            data[field_name] = np.asarray(col_data, dtype=np.float64)
        except (ValueError, TypeError):
            # 非数值列保持原样
            data[field_name] = col_data

    # 附加文件名
    data['filename'] = abs_file

    # 存入缓存
    _file_cache.set(abs_file, data)

    return data


def extract_time(filename: str) -> np.ndarray:
    """
    提取 TIME 列并转换为 Timedelta 数组（向后兼容委托）

    对应 MATLAB 的 extractTime 函数。
    内部委托给 param_extract()，不再独立读取文件。

    参数:
        filename: 数据文件路径

    返回:
        numpy 数组，dtype=timedelta64[ns]
    """
    data = param_extract(filename)
    return data.get('TIME', np.array([], dtype='timedelta64[ns]'))


def extract_column_efficient(filename: str, col_name: str,
                             col_type: str = 'auto') -> np.ndarray:
    """
    高效提取单列数据（带缓存）

    对应 MATLAB 的 extractColumnEfficient 函数。
    内部委托给 param_extract()，复用其 dict 缓存，避免重复读取文件。

    参数:
        filename: 文件路径
        col_name: 列名（原始列名，未转换）
        col_type: 数据类型，'auto'（自动）或 'string'

    返回:
        numpy 数组
    """
    # 复用 param_extract 的缓存 dict
    data = param_extract(filename)
    field_name = column_to_field_name(col_name)

    if field_name not in data:
        available = ', '.join(list(data.keys())[:10])
        raise KeyError(f'文件中未找到列 "{col_name}"。可用列（前10个）: {available}')

    result = data[field_name]
    if col_type == 'string':
        return result.astype(str)
    return result


def clear_cache():
    """清除文件缓存"""
    _file_cache.clear()
