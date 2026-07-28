"""
CSV 飞参数据加载模块
====================

从 CSV 格式的飞参数据文件提取所有列到字典，
输出格式与 loader.param_extract 完全一致（dict[str, np.ndarray]）。

CSV 数据特征：
- 逗号分隔，可能有 GBK/GB2312 编码
- 第 4 列为日期（2025/10/13 或 25-10-13）
- 第 5 列为标识符（1=可信，0=不可信）
- 第 6 列为时间（H:MM:SS）
"""

from __future__ import annotations

import logging
import os
from datetime import timedelta
from typing import Optional

import numpy as np
import pandas as pd

from ..column_config import get_replacement_rules
from ..config import CONFIG
from ..constants import TRIM_HEAD, TRIM_TAIL, CHUNK_SIZE
from ..utils.strings import column_to_field_name
from ..utils.file_utils import detect_encoding
from .cache import _file_cache
from .loader import _trim_data

logger = logging.getLogger(__name__)

# 大文件分块读取阈值 (bytes)
_LARGE_FILE_THRESHOLD = 50 * 1024 * 1024  # 50 MB


def csv_param_extract(
    filename: str,
    encoding: Optional[str] = None,
    filter_reliable: bool = True,
    apply_name_rules: bool = False,
) -> dict:
    """从 CSV 飞参数据文件提取所有列到字典。

    输出格式与 param_extract() 完全一致，使下游代码无需区分数据来源。

    CSV 数据保留原始列名，不做任何 label 变换：
    - 列名保持 CSV 文件中的原始名称（中文名保持中文）
    - 不应用 ATA 编号替换规则
    - 不将列名转换为 ASCII 标识符

    Args:
        filename: CSV 文件路径。
        encoding: 文件编码，None 时自动检测。
        filter_reliable: 是否过滤标识符 != 1 的行（默认 True）。
        apply_name_rules: 是否应用 ATA 列名替换规则（默认 False，
            保持原始列名不变）。

    Returns:
        dict，键为字段名，值为 numpy 数组。
        TIME 键为 timedelta64 数组（相对于首个时间点），数值列为 float64。
        特殊键 'filename' 存储文件路径。
    """
    # 标准化文件路径
    abs_file = os.path.abspath(filename)

    # 检查缓存
    cached = _file_cache.get(abs_file)
    if cached is not None:
        return cached

    # 1. 编码检测
    if encoding is None:
        encoding = detect_encoding(abs_file)
    logger.info("CSV 加载: %s (encoding=%s)", os.path.basename(abs_file), encoding)

    # 2. 读取 CSV
    df = _read_csv(abs_file, encoding)

    # 3. 时间处理：合并第 4/5/6 列为北京时间 datetime
    df = _convert_flight_time(df, filter_reliable=filter_reliable)

    # 4. 列名替换规则
    name_mapping: dict[str, str] = {}
    if apply_name_rules:
        df, name_mapping = _convert_flight_name(df)

    # 5. 转换为 dict[str, np.ndarray]（与 param_extract 格式一致）
    #    preserve_names=True: 保留原始列名，不做 label 变换（默认行为）
    data = _dataframe_to_dict(df, preserve_names=not apply_name_rules)

    # 6. 附加元数据
    data['filename'] = abs_file
    if name_mapping:
        data['_name_mapping'] = name_mapping

    # 7. 存入缓存
    _file_cache.set(abs_file, data)

    return data


def _read_csv(filepath: str, encoding: str) -> pd.DataFrame:
    """读取 CSV 文件，大文件自动分块读取。

    Args:
        filepath: 文件路径。
        encoding: 文件编码。

    Returns:
        DataFrame。
    """
    file_size = os.path.getsize(filepath)

    if file_size > _LARGE_FILE_THRESHOLD:
        return _read_csv_chunked(filepath, encoding)

    # 普通文件：指定第 4 列（索引 3）为 str，避免日期被截断
    try:
        df = pd.read_csv(filepath, encoding=encoding, dtype={3: str})
    except (ValueError, TypeError):
        logger.debug("dtype={3: str} 声明失败，回退到默认类型推断")
        df = pd.read_csv(filepath, encoding=encoding)

    max_rows = CONFIG.data.max_rows
    if len(df) > max_rows:
        logger.warning("CSV 行数 %d 超过限制 %d，截断到前 %d 行", len(df), max_rows, max_rows)
        df = df.iloc[:max_rows]

    return df


def _read_csv_chunked(filepath: str, encoding: str) -> pd.DataFrame:
    """分块读取大型 CSV 文件。

    Args:
        filepath: 文件路径。
        encoding: 文件编码。

    Returns:
        合并后的 DataFrame。
    """
    logger.info("大文件分块读取: %s (%d MB)", os.path.basename(filepath),
                os.path.getsize(filepath) // (1024 * 1024))

    chunks: list[pd.DataFrame] = []
    for chunk in pd.read_csv(filepath, encoding=encoding, chunksize=CHUNK_SIZE, dtype={3: str}):
        chunks.append(chunk)

    if not chunks:
        raise ValueError(f"CSV 文件为空: {filepath}")

    df = pd.concat(chunks, ignore_index=True, copy=False)
    del chunks  # 释放临时内存

    max_rows = CONFIG.data.max_rows
    if len(df) > max_rows:
        logger.warning("CSV 行数 %d 超过限制 %d，截断到前 %d 行", len(df), max_rows, max_rows)
        df = df.iloc[:max_rows]

    return df


def _convert_flight_time(
    df: pd.DataFrame,
    filter_reliable: bool = True,
) -> pd.DataFrame:
    """将 CSV 飞参数据的时间列合并为北京时间 datetime。

    处理第 4 列（日期）、第 5 列（标识符）、第 6 列（时间），
    合并为完整的 datetime 并转为 UTC+8 北京时间。

    Args:
        df: 原始 DataFrame。
        filter_reliable: 是否过滤标识符 != 1 的行。

    Returns:
        时间列已转换的 DataFrame。
    """
    try:
        date_col, flag_col, time_col = _get_time_column_names(df)
    except ValueError as e:
        logger.warning("无法识别 CSV 时间列结构: %s，跳过时间处理", e)
        return df

    # 过滤不可信数据（就地过滤，避免大文件创建副本导致峰值内存翻倍）
    if filter_reliable and flag_col in df.columns:
        before = len(df)
        unreliable_mask = df[flag_col] != 1
        after = before - int(unreliable_mask.sum())
        if after == 0:
            logger.warning("过滤后无可信数据，保留全部")
            return df
        df.drop(df[unreliable_mask].index, inplace=True)
        df.reset_index(drop=True, inplace=True)
        logger.debug("标识符过滤: %d → %d 行", before, after)

    if df.empty:
        return df

    # 解析日期
    parsed_dates = _parse_date_column(df, date_col)

    # 合并日期和时间
    datetime_combined = parsed_dates.astype(str) + ' ' + df[time_col].astype(str)
    df['_datetime'] = pd.to_datetime(datetime_combined, errors='coerce')

    # 如果全部解析失败，尝试仅解析时间列
    if df['_datetime'].isna().all():
        logger.warning("日期时间合并解析全部失败，尝试仅解析时间列")
        df['_datetime'] = pd.to_datetime(df[time_col], errors='coerce')

    # 转为北京时间 (UTC+8)
    df['_datetime'] = df['_datetime'] + timedelta(hours=8)

    # 构建新的列顺序，避免 insert/drop 多次修改导致碎片化
    drop_cols = set()
    if flag_col in df.columns:
        drop_cols.add(flag_col)
    if time_col in df.columns:
        drop_cols.add(time_col)
    if '_datetime' in df.columns:
        drop_cols.add('_datetime')

    remaining_cols = [c for c in df.columns if c not in drop_cols and c != date_col]
    cols = [date_col] + remaining_cols

    df = df[cols].copy()
    df.columns = ['飞行时间'] + [c for c in df.columns[1:]]

    return df


def _get_time_column_names(df: pd.DataFrame) -> tuple[str, str, str]:
    """获取时间相关列名。

    Args:
        df: DataFrame。

    Returns:
        (date_col, flag_col, time_col) 元组。

    Raises:
        ValueError: 列数不足或无法识别时间列。
    """
    if len(df.columns) >= 6:
        return df.columns[3], df.columns[4], df.columns[5]

    # 尝试按列名查找
    time_cols = [col for col in df.columns if '时间' in col or '日期' in col]
    if len(time_cols) >= 3:
        return time_cols[0], time_cols[1], time_cols[2]

    raise ValueError(f"列数不足 6 且未找到足够的时间相关列（共 {len(df.columns)} 列）")


def _parse_date_column(df: pd.DataFrame, date_column: str) -> pd.Series:
    """解析日期列，支持多种格式。

    Args:
        df: DataFrame。
        date_column: 日期列名。

    Returns:
        解析后的 datetime Series。
    """
    if df.empty:
        return pd.Series(dtype='datetime64[ns]')

    sample = str(df[date_column].iloc[0])

    # 先根据样本长度推测格式
    parsed: Optional[pd.Series] = None

    if len(sample) >= 10:  # "2025/10/13" 格式
        try:
            parsed = pd.to_datetime(df[date_column], format='%Y/%m/%d', errors='coerce')
            if parsed.isna().sum() / len(parsed) > 0.5:
                parsed = None
        except Exception:
            parsed = None
    elif len(sample) >= 8:  # "25-10-13" 格式
        try:
            parsed = pd.to_datetime(df[date_column], format='%y-%m-%d', errors='coerce')
            if parsed.isna().sum() / len(parsed) > 0.5:
                parsed = None
        except Exception:
            parsed = None

    # 自动推断兜底
    if parsed is None:
        parsed = pd.to_datetime(df[date_column], errors='coerce')

    return parsed


def _convert_flight_name(df: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, str]]:
    """应用 ATA 列名替换规则。

    Args:
        df: 原始 DataFrame。

    Returns:
        (转换后的 DataFrame, 旧名→新名映射) 元组。
    """
    rules = get_replacement_rules()
    name_mapping: dict[str, str] = {}

    rename_dict: dict[str, str] = {}
    for old_name in df.columns:
        new_name = old_name
        for pattern, replacement in rules.items():
            if pattern in old_name:
                new_name = old_name.replace(pattern, replacement)
                break
        if new_name != old_name:
            rename_dict[old_name] = new_name
            name_mapping[old_name] = new_name

    if rename_dict:
        df = df.rename(columns=rename_dict)

    return df, name_mapping


def _dataframe_to_dict(df: pd.DataFrame, preserve_names: bool = True) -> dict:
    """将 DataFrame 转为 dict[str, np.ndarray]，与 param_extract 输出格式一致。

    - TIME/飞行时间 列转为 timedelta64 相对时间数组
    - 其余列转 float64 numpy 数组
    - preserve_names=True 时保留原始列名（中文列名保持不变），
      不执行 column_to_field_name() 变换
    - preserve_names=False 时使用 column_to_field_name() 转换为 ASCII 标识符
    - 应用头尾裁剪

    Args:
        df: 处理后的 DataFrame。
        preserve_names: 是否保留原始列名（默认 True，禁止 label 变换）。

    Returns:
        数据字典。
    """
    data: dict = {}
    raw_names = df.columns.tolist()

    if preserve_names:
        # 保留原始列名，不做任何 label 变换
        field_names = raw_names
    else:
        # 转换为 ASCII 标识符（仅用于兼容旧路径）
        field_names = [column_to_field_name(name) for name in raw_names]

    # 处理时间列
    time_col_name = _find_time_column(df)
    if time_col_name is not None:
        time_values = df[time_col_name]
        time_values = _trim_data(time_values)
        if len(time_values) > 0:
            # 兼容 pandas StringDtype / object / datetime64 等多种 dtype
            try:
                # 如果是 datetime 类型，转为相对 timedelta
                if hasattr(time_values, 'dt'):
                    base_time = time_values.iloc[0]
                    data['TIME'] = (time_values - base_time).values.astype('timedelta64[ns]')
                else:
                    # 字符串或 object：先尝试 to_datetime
                    parsed = pd.to_datetime(time_values, errors='coerce')
                    if parsed.isna().all():
                        # 可能是 timedelta 字符串
                        data['TIME'] = pd.to_timedelta(time_values, errors='coerce').values
                    else:
                        base_time = parsed.iloc[0]
                        data['TIME'] = (parsed - base_time).values.astype('timedelta64[ns]')
            except ValueError as e:
                logger.warning("TIME 列时间解析失败: %s", e)
                data['TIME'] = np.array([], dtype='timedelta64[ns]')
            except Exception as e:
                logger.warning("TIME 列转换失败（未知原因）: %s", e, exc_info=True)
                data['TIME'] = np.array([], dtype='timedelta64[ns]')
        else:
            data['TIME'] = np.array([], dtype='timedelta64[ns]')

    # 数值列
    for raw_name, field_name in zip(raw_names, field_names):
        if raw_name == time_col_name:
            continue
        col_data = _trim_data(df[raw_name].values)
        try:
            data[field_name] = np.asarray(col_data, dtype=np.float64)
        except (ValueError, TypeError):
            data[field_name] = col_data

    return data


def _find_time_column(df: pd.DataFrame) -> Optional[str]:
    """查找时间列。

    优先查找 '飞行时间'，其次 'TIME'，最后按 dtype=datetime64 查找。

    Args:
        df: DataFrame。

    Returns:
        时间列名或 None。
    """
    for candidate in ('飞行时间', 'TIME', 'time', 'Time'):
        if candidate in df.columns:
            return candidate

    # 按 dtype 查找
    for col in df.columns:
        if np.issubdtype(df[col].dtype, np.datetime64):
            return col

    return None
