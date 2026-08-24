"""
数据统计摘要函数

从 statistics/multi.py 迁移至此，消除 data 与 statistics 之间的循环依赖。
generate_data_summary / print_data_summary 仅依赖 numpy 与 utils.time_utils，
不依赖 statistics 模块的任何函数，因此可安全下沉到 data 层。

向后兼容：
- ``from ftpa.data import generate_data_summary, print_data_summary``
- ``from ftpa.data.summary import generate_data_summary, print_data_summary``
- ``from ftpa.data.exporter import generate_data_summary, print_data_summary``
- ``from ftpa.statistics import generate_data_summary, print_data_summary``
  以上路径在迁移后均保持可用（exporter / statistics.multi 重新导出）。
"""

from __future__ import annotations

import numpy as np
from typing import Dict

from . import META_KEYS  # D3：元数据键单一来源
from ..utils.time_utils import format_duration_chinese


def generate_data_summary(data: Dict[str, np.ndarray]) -> Dict:
    """
    生成数据统计摘要

    参数:
        data: 数据字典

    返回:
        统计摘要字典
    """
    # 元数据键不计入通道数（META_KEYS：TIME / filename / _name_mapping 等，D3 单一来源）
    summary = {
        'total_records': len(data.get('TIME', [])),
        'total_channels': sum(1 for k in data if k not in META_KEYS),
        'time_range': {},
        'channels': {}
    }

    if 'TIME' in data:
        time_array = data['TIME']
        if len(time_array) > 0:
            start_time = time_array[0]
            end_time = time_array[-1]
            duration = (end_time - start_time) / np.timedelta64(1, 's')

            summary['time_range'] = {
                'start': str(start_time),
                'end': str(end_time),
                'duration_seconds': float(duration),
                'duration_formatted': format_duration_chinese(duration)
            }

    for key, value in data.items():
        if key == 'TIME':
            continue

        if isinstance(value, np.ndarray) and np.issubdtype(value.dtype, np.number):
            valid_data = value[~np.isnan(value)]

            if len(valid_data) > 0:
                summary['channels'][key] = {
                    'min': float(np.min(valid_data)),
                    'max': float(np.max(valid_data)),
                    'mean': float(np.mean(valid_data)),
                    'std': float(np.std(valid_data, ddof=1)),
                    'valid_count': int(len(valid_data)),
                    'invalid_count': int(len(value) - len(valid_data))
                }

    return summary


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

    sorted_channels = sorted(summary['channels'].items())

    for channel_name, stats in sorted_channels[:20]:
        print(f"  {channel_name:<30} {stats['min']:>12.4f} {stats['max']:>12.4f} "
              f"{stats['mean']:>12.4f} {stats['std']:>12.4f}")

    if len(sorted_channels) > 20:
        print(f"  ... 还有 {len(sorted_channels) - 20} 个通道")

    print("=" * 70)
