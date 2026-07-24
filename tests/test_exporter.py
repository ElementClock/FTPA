"""
测试数据导出和批量处理模块
"""

import pytest
import numpy as np
import tempfile
import os
from pathlib import Path
from ftpa.exporter import (
    export_data,
    export_statistics,
    generate_data_summary,
    print_data_summary
)


class TestExporter:
    """测试导出模块"""
    
    def test_export_data_csv(self, tmp_path):
        """测试导出 CSV 格式"""
        # 准备测试数据
        data = {
            'TIME': np.array([np.timedelta64(0, 's'), np.timedelta64(1, 's'), np.timedelta64(2, 's')]),
            'signal1': np.array([1.0, 2.0, 3.0]),
            'signal2': np.array([4.0, 5.0, 6.0])
        }
        
        output_path = str(tmp_path / 'test_output')
        result_path = export_data(data, output_path, output_format='csv')
        
        assert os.path.exists(result_path)
        assert result_path.endswith('.csv')
    
    def test_export_data_parquet(self, tmp_path):
        """测试导出 Parquet 格式"""
        pytest.importorskip("pyarrow", reason="pyarrow not installed")
        
        data = {
            'TIME': np.array([np.timedelta64(0, 's'), np.timedelta64(1, 's')]),
            'signal1': np.array([1.0, 2.0])
        }
        
        output_path = str(tmp_path / 'test_output')
        result_path = export_data(data, output_path, output_format='parquet')
        
        assert os.path.exists(result_path)
        assert result_path.endswith('.parquet')
    
    def test_export_data_hdf5(self, tmp_path):
        """测试导出 HDF5 格式"""
        pytest.importorskip("tables", reason="pytables not installed")
        
        data = {
            'TIME': np.array([np.timedelta64(0, 's'), np.timedelta64(1, 's')]),
            'signal1': np.array([1.0, 2.0])
        }
        
        output_path = str(tmp_path / 'test_output')
        result_path = export_data(data, output_path, output_format='hdf5')
        
        assert os.path.exists(result_path)
        assert result_path.endswith('.h5')
    
    def test_export_data_invalid_format(self, tmp_path):
        """测试无效格式"""
        data = {
            'TIME': np.array([np.timedelta64(0, 's')]),
            'signal1': np.array([1.0])
        }
        
        output_path = str(tmp_path / 'test_output')
        with pytest.raises(ValueError, match="不支持的导出格式"):
            export_data(data, output_path, output_format='invalid')
    
    def test_generate_data_summary(self):
        """测试生成数据摘要"""
        data = {
            'TIME': np.array([
                np.timedelta64(0, 's'),
                np.timedelta64(10, 's'),
                np.timedelta64(20, 's')
            ]),
            'signal1': np.array([1.0, 2.0, 3.0]),
            'signal2': np.array([4.0, 5.0, 6.0])
        }
        
        summary = generate_data_summary(data)
        
        assert 'total_records' in summary
        assert 'total_channels' in summary
        assert 'time_range' in summary
        assert 'channels' in summary
        
        assert summary['total_records'] == 3
        assert summary['total_channels'] == 2
        
        # 检查时间范围
        assert 'duration_seconds' in summary['time_range']
        assert summary['time_range']['duration_seconds'] == 20.0
        
        # 检查通道统计
        assert 'signal1' in summary['channels']
        assert summary['channels']['signal1']['min'] == 1.0
        assert summary['channels']['signal1']['max'] == 3.0
        assert summary['channels']['signal1']['mean'] == 2.0
    
    def test_generate_data_summary_with_nan(self):
        """测试包含 NaN 的数据摘要"""
        data = {
            'TIME': np.array([np.timedelta64(0, 's'), np.timedelta64(1, 's')]),
            'signal1': np.array([1.0, np.nan])
        }
        
        summary = generate_data_summary(data)
        
        assert summary['channels']['signal1']['valid_count'] == 1
        assert summary['channels']['signal1']['invalid_count'] == 1
    
    def test_export_statistics_csv(self, tmp_path):
        """测试导出统计结果到 CSV"""
        stats = {
            'file': ['file1.txt', 'file2.txt'],
            'records': [100, 200],
            'mean': [1.5, 2.5]
        }
        
        output_path = str(tmp_path / 'stats_output')
        result_path = export_statistics(stats, output_path, output_format='csv')
        
        assert os.path.exists(result_path)
        assert result_path.endswith('_stats.csv')
    
    def test_export_statistics_json(self, tmp_path):
        """测试导出统计结果到 JSON"""
        stats = {
            'file': 'file1.txt',
            'records': 100
        }
        
        output_path = str(tmp_path / 'stats_output')
        result_path = export_statistics(stats, output_path, output_format='json')
        
        assert os.path.exists(result_path)
        assert result_path.endswith('_stats.json')


class TestBatchProcessor:
    """测试批量处理模块"""
    
    def test_batch_process_files_no_files(self, tmp_path):
        """测试批量处理无文件情况"""
        from ftpa.batch_processor import batch_process_files
        
        pattern = str(tmp_path / 'nonexistent_*.txt')
        output_dir = str(tmp_path / 'output')
        
        result = batch_process_files(pattern, output_dir, 'dummy.xlsx', verbose=False)
        
        assert result['success_count'] == 0
        assert result['failed_count'] == 0
        assert len(result['results']) == 0
    
    def test_batch_analyze_statistics_no_files(self, tmp_path):
        """测试批量统计分析无文件情况"""
        from ftpa.batch_processor import batch_analyze_statistics
        
        pattern = str(tmp_path / 'nonexistent_*.txt')
        
        result = batch_analyze_statistics(pattern, 'dummy.xlsx')
        
        assert len(result) == 0
    
    def test_batch_export_summaries_no_files(self, tmp_path):
        """测试批量导出摘要无文件情况"""
        from ftpa.batch_processor import batch_export_summaries
        
        pattern = str(tmp_path / 'nonexistent_*.txt')
        output_file = str(tmp_path / 'summary.csv')
        
        # 应该不抛出异常
        batch_export_summaries(pattern, 'dummy.xlsx', output_file)
        
        # 文件不应该被创建（因为没有文件）
        assert not os.path.exists(output_file)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
