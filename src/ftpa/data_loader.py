"""
数据加载模块
对应 MATLAB: paramExtract.m, extractTime.m, extractColumnEfficient.m
负责从数据文件提取所有列数据，支持 ZIP 压缩和缓存机制
"""

import os
import zipfile
import tempfile
import threading
import pandas as pd
import numpy as np
from .utils import column_to_field_name
from .constants import TRIM_HEAD, TRIM_TAIL


# 模块级缓存（替代 MATLAB 的 persistent 变量）
_file_cache = {}
_file_cache_lock = threading.Lock()


def _resolve_zip_file(filepath: str) -> tuple[str, bool]:
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


def _read_data_file(filepath: str) -> pd.DataFrame:
    """
    读取数据文件（支持 ZIP 和普通文本文件）
    
    参数:
        filepath: 文件路径
    
    返回:
        DataFrame，列名为原始列名
    """
    readable_file, is_temp = _resolve_zip_file(filepath)
    
    try:
        # 读取第一行作为列名，Tab 分隔
        # 不指定 dtype，让 pandas 自动推断类型（TIME 列为字符串，其他列为数值）
        df = pd.read_csv(readable_file, sep='\t')
        return df
    finally:
        # 清理临时文件
        if is_temp:
            import shutil
            temp_dir = os.path.dirname(readable_file)
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir, ignore_errors=True)


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
    with _file_cache_lock:
        if abs_file in _file_cache:
            return _file_cache[abs_file]
    
    # 读取数据文件
    df = _read_data_file(abs_file)
    
    # 获取原始列名
    raw_names = df.columns.tolist()
    
    if not raw_names:
        raise ValueError("文件中未检测到任何列名。")
    
    # 转换列名为合法字段名
    field_names = [column_to_field_name(name) for name in raw_names]
    
    # 构建数据字典
    data = {}
    for raw_name, field_name in zip(raw_names, field_names):
        # 提取列数据并截取头尾
        col_data = df[raw_name].values
        
        # 应用截取（与 MATLAB extractColumnEfficient 一致）
        n_total = len(col_data)
        n_drop = TRIM_HEAD + TRIM_TAIL
        
        if n_total >= n_drop:
            col_data = col_data[TRIM_HEAD:n_total - TRIM_TAIL]
        else:
            print(f"警告: 数据长度 ({n_total}) 小于需截取的长度 ({n_drop})，返回空数组。")
            col_data = np.array([])
        
        data[field_name] = col_data
    
    # 附加文件名
    data['filename'] = abs_file
    
    # 存入缓存
    _file_cache[abs_file] = data
    
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
    df = _read_data_file(abs_file)
    
    # 提取 TIME 列（字符串格式）
    time_str = df['TIME'].astype(str)
    
    # 截取头尾
    n_total = len(time_str)
    n_drop = TRIM_HEAD + TRIM_TAIL
    
    if n_total >= n_drop:
        time_str = time_str.iloc[TRIM_HEAD:n_total - TRIM_TAIL]
    else:
        print(f"警告: 数据长度 ({n_total}) 小于需截取的长度 ({n_drop})，返回空数组。")
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

    with _file_cache_lock:
        if cache_key in _file_cache:
            df = _file_cache[cache_key]
        else:
            df = _read_data_file(abs_file)
            _file_cache[cache_key] = df
    
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
    n_total = len(data)
    n_drop = TRIM_HEAD + TRIM_TAIL
    
    if n_total >= n_drop:
        data = data[TRIM_HEAD:n_total - TRIM_TAIL]
    else:
        print(f"警告: 数据长度 ({n_total}) 小于需截取的长度 ({n_drop})，返回空数组。")
        data = np.array([])
    
    return data


def clear_cache():
    """清除文件缓存"""
    global _file_cache
    _file_cache.clear()
