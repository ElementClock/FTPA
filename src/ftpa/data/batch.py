"""批量处理模块 —— 支持多文件批量处理和分析。

从 batch_processor.py 迁移至 data/ 子包，
消除 GUI panel_batch.py 对根目录 CLI 模块的依赖。
"""

import glob
import logging
import os
from datetime import datetime
from typing import Callable, List, Optional

import numpy as np
import pandas as pd

from . import param_extract
from ..computing.weight_cg import add_weight_cg_to_data
from .exporter import export_data, generate_data_summary
from .label_map import LabelMap
from ..utils.time_utils import select_time_window

logger = logging.getLogger(__name__)


def _load_and_prepare(file_path: str, lm: LabelMap) -> dict:
    """公共：加载数据文件并计算重量重心。"""
    data = param_extract(file_path)
    add_weight_cg_to_data(data, lm)
    return data


def batch_process_files(file_pattern: str,
                       output_dir: str,
                       excel_file: str,
                       process_func: Optional[Callable] = None,
                       export_format: str = 'csv',
                       verbose: bool = True) -> dict:
    """批量处理多个数据文件。"""
    files = glob.glob(file_pattern)

    if not files:
        logger.warning("未找到匹配的文件: %s", file_pattern)
        return {'success_count': 0, 'failed_count': 0, 'results': []}

    if verbose:
        print(f"找到 {len(files)} 个文件待处理")

    os.makedirs(output_dir, exist_ok=True)
    lm = LabelMap(excel_file)

    results = {
        'success_count': 0,
        'failed_count': 0,
        'results': [],
        'start_time': datetime.now(),
        'end_time': None
    }

    for idx, file_path in enumerate(files, 1):
        file_name = os.path.basename(file_path)
        file_base = os.path.splitext(file_name)[0]

        if verbose:
            print(f"\n[{idx}/{len(files)}] 处理: {file_name}")

        try:
            data = _load_and_prepare(file_path, lm)
            output_path = os.path.join(output_dir, file_base)

            custom_result = None
            if process_func:
                file_info = {
                    'file_path': file_path,
                    'file_name': file_name,
                    'output_path': output_path
                }
                custom_result = process_func(data, lm, file_info)

            actual_path = export_data(data, output_path, output_format=export_format)

            result_item = {
                'file': file_path,
                'status': 'success',
                'output': actual_path,
                'records': len(data['TIME']),
                'channels': len(data) - 1,
                'custom_result': custom_result
            }

            results['results'].append(result_item)
            results['success_count'] += 1

            if verbose:
                print(f"  ✓ 成功: {len(data['TIME'])} 条记录, {len(data) - 1} 个通道")
                print(f"  ✓ 输出: {actual_path}")

        except Exception as e:
            result_item = {
                'file': file_path,
                'status': 'failed',
                'error': str(e)
            }
            results['results'].append(result_item)
            results['failed_count'] += 1

            if verbose:
                print(f"  ✗ 失败: {e}")

    results['end_time'] = datetime.now()

    if verbose:
        print("\n" + "=" * 70)
        print("批量处理完成")
        print("=" * 70)
        print(f"总文件数: {len(files)}")
        print(f"成功: {results['success_count']}")
        print(f"失败: {results['failed_count']}")
        duration = (results['end_time'] - results['start_time']).total_seconds()
        print(f"总耗时: {duration:.2f} 秒")
        if results['success_count'] > 0:
            avg_time = duration / results['success_count']
            print(f"平均每个文件: {avg_time:.2f} 秒")
        print("=" * 70)

    return results


def batch_analyze_statistics(file_pattern: str,
                            excel_file: str,
                            time_window: Optional[tuple] = None,
                            signals: Optional[List[str]] = None) -> pd.DataFrame:
    """批量分析多个文件的统计信息。"""
    from ..statistics.basic import compute_stat

    files = glob.glob(file_pattern)

    if not files:
        logger.warning("未找到匹配的文件: %s", file_pattern)
        return pd.DataFrame()

    lm = LabelMap(excel_file)

    all_stats = []

    for file_path in files:
        file_name = os.path.basename(file_path)

        try:
            data = _load_and_prepare(file_path, lm)

            if time_window:
                i_start, i_end, _, _ = select_time_window(data['TIME'], time_window[0], time_window[1])
                sl = slice(i_start, i_end + 1)
            else:
                sl = slice(None)

            if signals is None:
                analysis_signals = ['总重', '相对重心', '指示空速表决值', '俯仰角表决值']
            else:
                analysis_signals = signals

            file_stats = {'file': file_name}

            for signal_label in analysis_signals:
                try:
                    field_name = lm.get_var_name(signal_label)
                    if field_name and field_name in data:
                        signal_data = data[field_name][sl]

                        mean_val = np.nanmean(signal_data)
                        std_val = np.nanstd(signal_data)
                        min_val = np.nanmin(signal_data)
                        max_val = np.nanmax(signal_data)

                        file_stats[f'{signal_label}_mean'] = mean_val
                        file_stats[f'{signal_label}_std'] = std_val
                        file_stats[f'{signal_label}_min'] = min_val
                        file_stats[f'{signal_label}_max'] = max_val
                except Exception as e:
                    logger.debug("信号 '%s' 统计计算失败: %s", signal_label, e)

            all_stats.append(file_stats)

        except Exception as e:
            print(f"处理 {file_name} 失败: {e}")

    df = pd.DataFrame(all_stats)
    return df


def batch_export_summaries(file_pattern: str,
                          excel_file: str,
                          output_file: str = 'batch_summary.csv'):
    """批量导出多个文件的数据摘要。"""
    files = glob.glob(file_pattern)

    if not files:
        logger.warning("未找到匹配的文件: %s", file_pattern)
        return

    lm = LabelMap(excel_file)

    summaries = []

    for file_path in files:
        file_name = os.path.basename(file_path)

        try:
            data = _load_and_prepare(file_path, lm)
            summary = generate_data_summary(data)

            summary_row = {
                'file': file_name,
                'records': summary['total_records'],
                'channels': summary['total_channels'],
                'duration_seconds': summary['time_range']['duration_seconds']
            }

            key_channels = ['totalWeight', 'relCg', 'AirSpeed_vote']
            for channel in key_channels:
                if channel in summary['channels']:
                    stats = summary['channels'][channel]
                    summary_row[f'{channel}_mean'] = stats['mean']
                    summary_row[f'{channel}_std'] = stats['std']

            summaries.append(summary_row)

        except Exception as e:
            print(f"处理 {file_name} 失败: {e}")

    df = pd.DataFrame(summaries)
    df.to_csv(output_file, index=False, encoding='utf-8-sig')

    print(f"批量摘要已导出到: {output_file}")
    print(f"共处理 {len(summaries)} 个文件")
