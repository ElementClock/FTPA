"""
数据导出模块
支持多种格式的数据导出：CSV、Parquet、HDF5
"""

import os
import numpy as np
import pandas as pd
from typing import Dict, Union, Optional
from datetime import datetime
from .time_utils import format_duration_chinese
from .statistics import generate_data_summary  # noqa: F401 — re-exports


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
        format: 导出格式，可选 'csv', 'parquet', 'hdf5', 'excel'
        time_format: 时间格式，'string' 或 'timedelta'
        compression: 压缩方式，如 'gzip', 'snappy'（仅对 parquet 和 csv 有效）

    返回:
        实际保存的文件路径

    示例:
        >>> export_data(data, 'output/result', format='parquet')
        'output/result.parquet'
    """
    # 确保输出目录存在
    output_dir = os.path.dirname(output_path)
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

    else:
        raise ValueError(f"不支持的导出格式: {output_format}。支持: csv, parquet, hdf5, excel")

    print(f"数据已导出到: {file_path}")
    print(f"  格式: {output_format.upper()}")
    print(f"  行数: {len(df)}")
    print(f"  列数: {len(df.columns)}")
    if compression:
        print(f"  压缩: {compression}")

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
    将 timedelta64 数组转换为字符串数组

    参数:
        time_array: timedelta64 数组

    返回:
        字符串数组，格式为 HH:MM:SS.mmm
    """
    result = []
    for td in time_array:
        # 转换为秒
        total_seconds = td / np.timedelta64(1, 's')

        # 计算时、分、秒、毫秒
        hours = int(total_seconds // 3600)
        minutes = int((total_seconds % 3600) // 60)
        seconds = int(total_seconds % 60)
        milliseconds = int((total_seconds % 1) * 1000)

        # 格式化为字符串
        time_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}.{milliseconds:03d}"
        result.append(time_str)

    return np.array(result)


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
    output_dir = os.path.dirname(output_path)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)

    output_format = output_format.lower()

    if output_format == 'csv':
        file_path = f"{output_path}_stats.csv"
        df = pd.DataFrame(stats)
        df.to_csv(file_path, index=False, encoding='utf-8-sig')

    elif output_format == 'json':
        file_path = f"{output_path}_stats.json"
        import json
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(stats, f, ensure_ascii=False, indent=2)

    else:
        raise ValueError(f"不支持的格式: {output_format}。支持: csv, json")

    print(f"统计结果已导出到: {file_path}")
    return file_path


def print_data_summary(data: Dict[str, np.ndarray]):
    """
    打印数据统计摘要

    参数:
        data: 数据字典
    """
    summary = generate_data_summary(data)

    print("=" * 70)
    print("数据统计摘要")
    print("=" * 70)
    print(f"总记录数: {summary['total_records']:,}")
    print(f"通道数量: {summary['total_channels']}")
    print()

    if summary['time_range']:
        print("时间范围:")
        print(f"  起始: {summary['time_range']['start']}")
        print(f"  结束: {summary['time_range']['end']}")
        print(f"  时长: {summary['time_range']['duration_formatted']}")
        print(f"       ({summary['time_range']['duration_seconds']:.2f} 秒)")
        print()

    print("通道统计:")
    print(f"  {'通道名':<30} {'最小值':>12} {'最大值':>12} {'平均值':>12} {'标准差':>12}")
    print("  " + "-" * 80)

    # 按通道名排序
    sorted_channels = sorted(summary['channels'].items())

    for channel_name, stats in sorted_channels[:20]:  # 只显示前20个
        print(f"  {channel_name:<30} {stats['min']:>12.4f} {stats['max']:>12.4f} "
              f"{stats['mean']:>12.4f} {stats['std']:>12.4f}")

    if len(sorted_channels) > 20:
        print(f"  ... 还有 {len(sorted_channels) - 20} 个通道")

    print("=" * 70)
