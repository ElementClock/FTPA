"""
批量处理模块
支持多文件批量处理和分析
"""

import os
import glob
from typing import List, Dict, Callable, Optional
from datetime import datetime
import pandas as pd
import numpy as np

from .data_loader import param_extract, extract_time
from .label_map import LabelMap
from .computing import compute_total_weight_rel_cg
from .exporter import export_data, generate_data_summary


def batch_process_files(file_pattern: str,
                       output_dir: str,
                       excel_file: str,
                       process_func: Optional[Callable] = None,
                       export_format: str = 'csv',
                       verbose: bool = True) -> Dict:
    """
    批量处理多个数据文件
    
    参数:
        file_pattern: 文件匹配模式，如 'data/*.txt' 或 'data/file_*.txt'
        output_dir: 输出目录
        excel_file: 标签映射 Excel 文件路径
        process_func: 自定义处理函数，签名为 func(data, lm, file_info) -> Dict
        export_format: 导出格式，'csv', 'parquet', 'hdf5'
        verbose: 是否打印详细信息
    
    返回:
        处理结果字典，包含成功/失败文件列表和统计信息
    
    示例:
        >>> results = batch_process_files('data/*.txt', 'output/', '参数名.xlsx')
        >>> print(f"成功处理 {results['success_count']} 个文件")
    """
    # 查找所有匹配的文件
    files = glob.glob(file_pattern)
    
    if not files:
        print(f"警告: 未找到匹配的文件: {file_pattern}")
        return {'success_count': 0, 'failed_count': 0, 'results': []}
    
    if verbose:
        print(f"找到 {len(files)} 个文件待处理")
    
    # 创建输出目录
    os.makedirs(output_dir, exist_ok=True)
    
    # 加载标签映射（只加载一次）
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
            # 加载数据
            data = param_extract(file_path)
            data['TIME'] = extract_time(file_path)
            
            # 计算重量重心
            _add_weight_cg(data, lm)
            
            # 生成输出路径
            output_path = os.path.join(output_dir, file_base)
            
            # 执行自定义处理
            custom_result = None
            if process_func:
                file_info = {
                    'file_path': file_path,
                    'file_name': file_name,
                    'output_path': output_path
                }
                custom_result = process_func(data, lm, file_info)
            
            # 导出数据
            actual_path = export_data(data, output_path, format=export_format)
            
            # 记录结果
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
    
    # 打印汇总
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
                            time_window: tuple = None,
                            signals: List[str] = None) -> pd.DataFrame:
    """
    批量分析多个文件的统计信息
    
    参数:
        file_pattern: 文件匹配模式
        excel_file: 标签映射 Excel 文件路径
        time_window: 时间窗口 (start_time, end_time)，None 表示全时段
        signals: 要分析的信号列表（中文标签），None 表示所有信号
    
    返回:
        统计结果 DataFrame，每行一个文件，列包含各信号的统计值
    
    示例:
        >>> df = batch_analyze_statistics('data/*.txt', '参数名.xlsx',
        ...                               time_window=('00:00:00', '00:10:00'),
        ...                               signals=['指示空速表决值', '俯仰角表决值'])
        >>> df.to_csv('batch_stats.csv')
    """
    from .statistics import compute_stat
    
    files = glob.glob(file_pattern)
    
    if not files:
        print(f"警告: 未找到匹配的文件: {file_pattern}")
        return pd.DataFrame()
    
    lm = LabelMap(excel_file)
    
    all_stats = []
    
    for file_path in files:
        file_name = os.path.basename(file_path)
        
        try:
            # 加载数据
            data = param_extract(file_path)
            data['TIME'] = extract_time(file_path)
            
            # 计算重量重心
            _add_weight_cg(data, lm)
            
            # 确定时间索引
            if time_window:
                from .time_utils import select_time_window
                idx, _, _ = select_time_window(data['TIME'], time_window[0], time_window[1])
            else:
                idx = slice(None)
            
            # 确定要分析的信号
            if signals is None:
                # 默认分析一些关键信号
                analysis_signals = ['总重', '相对重心', '指示空速表决值', '俯仰角表决值']
            else:
                analysis_signals = signals
            
            # 计算每个信号的统计
            file_stats = {'file': file_name}
            
            for signal_label in analysis_signals:
                try:
                    field_name = lm.get_var_name(signal_label)
                    if field_name and field_name in data:
                        signal_data = data[field_name][idx]
                        
                        # 计算基本统计
                        mean_val = np.nanmean(signal_data)
                        std_val = np.nanstd(signal_data)
                        min_val = np.nanmin(signal_data)
                        max_val = np.nanmax(signal_data)
                        
                        file_stats[f'{signal_label}_mean'] = mean_val
                        file_stats[f'{signal_label}_std'] = std_val
                        file_stats[f'{signal_label}_min'] = min_val
                        file_stats[f'{signal_label}_max'] = max_val
                except Exception as e:
                    # 信号不存在或计算失败，跳过
                    pass
            
            all_stats.append(file_stats)
        
        except Exception as e:
            print(f"处理 {file_name} 失败: {e}")
    
    # 转换为 DataFrame
    df = pd.DataFrame(all_stats)
    
    return df


def batch_export_summaries(file_pattern: str,
                          excel_file: str,
                          output_file: str = 'batch_summary.csv'):
    """
    批量导出多个文件的数据摘要
    
    参数:
        file_pattern: 文件匹配模式
        excel_file: 标签映射 Excel 文件路径
        output_file: 输出文件路径
    
    示例:
        >>> batch_export_summaries('data/*.txt', '参数名.xlsx', 'summary.csv')
    """
    files = glob.glob(file_pattern)
    
    if not files:
        print(f"警告: 未找到匹配的文件: {file_pattern}")
        return
    
    lm = LabelMap(excel_file)
    
    summaries = []
    
    for file_path in files:
        file_name = os.path.basename(file_path)
        
        try:
            # 加载数据
            data = param_extract(file_path)
            data['TIME'] = extract_time(file_path)
            
            # 计算重量重心
            _add_weight_cg(data, lm)
            
            # 生成摘要
            summary = generate_data_summary(data)
            
            # 提取关键信息
            summary_row = {
                'file': file_name,
                'records': summary['total_records'],
                'channels': summary['total_channels'],
                'duration_seconds': summary['time_range']['duration_seconds']
            }
            
            # 添加一些关键通道的统计
            key_channels = ['总重', '相对重心', '指示空速表决值']
            for channel in key_channels:
                if channel in summary['channels']:
                    stats = summary['channels'][channel]
                    summary_row[f'{channel}_mean'] = stats['mean']
                    summary_row[f'{channel}_std'] = stats['std']
            
            summaries.append(summary_row)
        
        except Exception as e:
            print(f"处理 {file_name} 失败: {e}")
    
    # 导出到 CSV
    df = pd.DataFrame(summaries)
    df.to_csv(output_file, index=False, encoding='utf-8-sig')
    
    print(f"批量摘要已导出到: {output_file}")
    print(f"共处理 {len(summaries)} 个文件")


def _add_weight_cg(data: Dict, lm: LabelMap):
    """
    为数据添加重量和重心计算结果
    
    参数:
        data: 数据字典
        lm: 标签映射对象
    """
    # 默认配置（可根据实际情况调整）
    base_weight = 48487.0
    base_rel_cg = 25.28
    base_oli = 6000.0
    
    try:
        # 获取油箱油量
        oil_lout = data.get(lm.get_var_name('Ⅰ号油箱油量'))
        oil_lin = data.get(lm.get_var_name('Ⅱ号油箱油量'))
        oil_rin = data.get(lm.get_var_name('Ⅲ号油箱油量'))
        oil_rout = data.get(lm.get_var_name('Ⅳ号油箱油量'))
        
        if all(v is not None for v in [oil_lout, oil_lin, oil_rin, oil_rout]):
            total_weight, rel_cg = compute_total_weight_rel_cg(
                oil_lout, oil_lin, oil_rin, oil_rout,
                base_weight, base_rel_cg, base_oli
            )
            
            data['totalWeight'] = total_weight
            data['relCg'] = rel_cg
            
            # 添加标签映射
            lm.add('totalWeight', '总重')
            lm.add('relCg', '相对重心')
    except Exception as e:
        # 如果计算失败，静默跳过
        pass
