"""
全面单元测试套件
覆盖所有关键功能模块、边界条件及异常场景
"""

import pytest
import numpy as np
import pandas as pd
import os
import tempfile
from pathlib import Path
import sys

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from ftpa.utils import make_valid_name
from ftpa.data.label_map import LabelMap
from ftpa.data import (
    extract_column_efficient,
    param_extract,
    extract_time,
)
from ftpa.data.io import read_data_file, resolve_zip_file
from ftpa.utils.time_utils import (
    select_time_window,
    format_time_seconds,
    time_to_seconds_array,
    parse_time_to_seconds
)
from ftpa.computing import compute_total_weight_rel_cg, compute_fitted_circle_radius
from ftpa.statistics import compute_stat, compute_var_stats, show_group_stats


# ============================================================================
# utils.py 测试
# ============================================================================

class TestUtils:
    """工具函数测试"""
    
    def test_make_valid_name_normal(self):
        """测试正常名称"""
        assert make_valid_name("valid_name") == "valid_name"
        assert make_valid_name("Test123") == "Test123"
    
    def test_make_valid_name_start_with_number(self):
        """测试以数字开头的名称"""
        assert make_valid_name("123test") == "x123test"
        assert make_valid_name("1") == "x1"
    
    def test_make_valid_name_special_chars(self):
        """测试包含特殊字符的名称"""
        assert make_valid_name("test-name") == "test_name"
        assert make_valid_name("test.name") == "test_name"
        assert make_valid_name("test name") == "test_name"
    
    def test_make_valid_name_empty(self):
        """测试空字符串"""
        assert make_valid_name("") == "x"
    
    def test_make_valid_name_chinese(self):
        """测试中文字符"""
        result = make_valid_name("测试")
        assert result == "__"  # 中文字符被替换为下划线


# ============================================================================
# label_map.py 测试
# ============================================================================

class TestLabelMap:
    """标签映射测试"""
    
    @pytest.fixture
    def temp_excel_file(self):
        """创建临时映射 CSV 文件（参数名.csv 同构：原始名称,中文名称,单位）"""
        # 使用临时目录避免 Windows 文件锁定问题
        temp_dir = tempfile.mkdtemp()
        temp_path = os.path.join(temp_dir, 'test_labels.csv')
        df = pd.DataFrame({
            '原始名称': ['TIME', 'AirSpeed', 'Altitude'],
            '中文名称': ['时间', '空速', '高度']
        })
        df.to_csv(temp_path, index=False, encoding='utf-8-sig')
        yield temp_path
        # 清理临时目录
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    def test_label_map_init(self, temp_excel_file):
        """测试初始化"""
        lm = LabelMap(temp_excel_file)
        assert lm is not None
    
    def test_label_map_get_label(self, temp_excel_file):
        """测试获取中文标签"""
        lm = LabelMap(temp_excel_file)
        assert lm.get_label('TIME') == '时间'
        assert lm.get_label('AirSpeed') == '空速'
    
    def test_label_map_get_var_name(self, temp_excel_file):
        """测试获取变量名"""
        lm = LabelMap(temp_excel_file)
        assert lm.get_var_name('时间') == 'TIME'
        assert lm.get_var_name('空速') == 'AirSpeed'
    
    def test_label_map_not_found(self, temp_excel_file):
        """测试未找到的标签"""
        lm = LabelMap(temp_excel_file)
        assert lm.get_label('NOTEXIST') == 'NOTEXIST'
        # get_var_name 返回空字符串表示未找到
        assert lm.get_var_name('不存在的标签') == ''


# ============================================================================
# data_loader.py 测试
# ============================================================================

class TestDataLoader:
    """数据加载测试"""
    
    @pytest.fixture
    def temp_data_file(self):
        """创建临时数据文件"""
        # 使用临时目录避免 Windows 文件锁定问题
        temp_dir = tempfile.mkdtemp()
        temp_path = os.path.join(temp_dir, 'test_data.txt')
        with open(temp_path, 'w', encoding='utf-8') as f:
            # 写入表头
            f.write("TIME\tCol1\tCol2\n")
            # 写入 200 行数据（避免被截取）
            for i in range(200):
                f.write(f"00:00:{i:02d}:000\t{i}.0\t{i*2}.0\n")
        yield temp_path
        # 清理临时目录
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    def test_read_data_file(self, temp_data_file):
        """测试读取数据文件"""
        df = read_data_file(temp_data_file)
        assert df is not None
        assert len(df) == 200
        assert 'TIME' in df.columns
        assert 'Col1' in df.columns
        assert 'Col2' in df.columns
    
    def test_extract_column_efficient(self, temp_data_file):
        """测试高效提取单列"""
        col = extract_column_efficient(temp_data_file, 'Col1')
        assert col is not None
        assert len(col) == 100  # 200 - 50 - 50
        assert col[0] == 50.0  # 第 50 行（截取后）
    
    def test_extract_column_cache(self, temp_data_file):
        """测试缓存机制"""
        # 第一次提取
        col1 = extract_column_efficient(temp_data_file, 'Col1')
        # 第二次提取（应该使用缓存）
        col2 = extract_column_efficient(temp_data_file, 'Col1')
        assert np.array_equal(col1, col2)
    
    def test_extract_column_different_cols(self, temp_data_file):
        """测试提取不同列（修复后的缓存键）"""
        col1 = extract_column_efficient(temp_data_file, 'Col1')
        col2 = extract_column_efficient(temp_data_file, 'Col2')
        assert not np.array_equal(col1, col2)
        assert col2[0] == 100.0  # Col2 的值是 Col1 的两倍
    
    def test_param_extract(self, temp_data_file):
        """测试参数提取"""
        data = param_extract(temp_data_file)
        assert 'TIME' in data
        assert 'Col1' in data
        assert 'Col2' in data
        assert len(data['Col1']) == 100
    
    def test_extract_time(self, temp_data_file):
        """测试时间提取"""
        time_vec = extract_time(temp_data_file)
        assert time_vec is not None
        assert len(time_vec) == 100
        # 时间数据类型可能是 timedelta64[ns] 或 timedelta64[us]
        assert str(time_vec.dtype).startswith('timedelta64')


# ============================================================================
# time_utils.py 测试
# ============================================================================

class TestTimeUtils:
    """时间工具测试"""
    
    def test_time_to_seconds_array(self):
        """测试时间数组转秒数"""
        time_vec = np.array([0, 1, 2, 3], dtype='timedelta64[s]')
        seconds = time_to_seconds_array(time_vec)
        assert np.array_equal(seconds, [0, 1, 2, 3])
    
    def test_parse_time_to_seconds(self):
        """测试时间字符串转秒数"""
        assert parse_time_to_seconds("00:00:00") == 0
        assert parse_time_to_seconds("00:01:00") == 60
        assert parse_time_to_seconds("01:00:00") == 3600
        assert parse_time_to_seconds("01:01:01.500") == 3661.5

    def test_parse_time_to_seconds_numeric(self):
        """测试数值时间转秒数"""
        assert parse_time_to_seconds(100) == 100
        assert parse_time_to_seconds(3661.5) == 3661.5
    
    def test_format_time_seconds(self):
        """测试秒数转时间字符串"""
        assert format_time_seconds(0) == "00:00:00.000"
        assert format_time_seconds(61.5) == "00:01:01.500"
        assert format_time_seconds(3661) == "01:01:01.000"
    
    def test_select_time_window(self):
        """测试时间窗口选择"""
        time_vec = np.arange(100, dtype='timedelta64[s]')
        i_start, i_end, start, end = select_time_window(time_vec, 10, 20)
        assert start == 10
        assert end == 20
        assert i_start == 10
        assert i_end == 20
        assert i_end - i_start + 1 == 11  # 包含 10 到 20

    def test_select_time_window_searchsorted_equivalence(self):
        """验证 searchsorted 实现与 argmin(abs(...)) 完全等价"""
        from ftpa.utils.time_utils import select_time_window
        time_vec = np.arange(200) * np.timedelta64(500, 'ms')

        # 精确匹配
        i_start, i_end, start, end = select_time_window(time_vec, 10, 50)
        assert i_start == 20
        assert i_end == 100

        # 非精确匹配 — 选最近点
        i_start, i_end, start, end = select_time_window(time_vec, 10.3, 50.7)
        assert i_start == 21

        # 超出左边界
        i_start, i_end, start, end = select_time_window(time_vec, -5, 10)
        assert i_start == 0

        # 超出右边界
        i_start, i_end, start, end = select_time_window(time_vec, 90, 200)
        assert i_end == 199

        # 逆序输入
        i_start, i_end, start, end = select_time_window(time_vec, 50, 10)
        assert i_start <= i_end
        assert start == 10.0
        assert end == 50.0


# ============================================================================
    def test_select_time_window_empty_array(self):
        """空时间数组不应崩溃（Critical 修复验证）。"""
        time_vec = np.array([], dtype='timedelta64[s]')
        i_start, i_end, start, end = select_time_window(time_vec, 0, 10)
        assert i_start == 0
        assert i_end == 0
        assert start == 0.0
        assert end == 0.0


# computing.py 测试
# ============================================================================

class TestComputing:
    """计算模块测试"""
    
    def test_compute_total_weight_rel_cg_normal(self):
        """测试正常情况下的重量重心计算"""
        oil_lout = np.array([1000.0])
        oil_lin = np.array([1000.0])
        oil_rin = np.array([1000.0])
        oil_rout = np.array([1000.0])
        base_weight = 50000.0
        base_rel_cg = 25.0
        base_oil = 4000.0
        
        total_weight, rel_cg = compute_total_weight_rel_cg(
            oil_lout, oil_lin, oil_rin, oil_rout,
            base_weight, base_rel_cg, base_oil
        )
        
        assert total_weight is not None
        assert rel_cg is not None
        assert total_weight[0] > 0
        assert 0 <= rel_cg[0] <= 100
    
    def test_compute_total_weight_rel_cg_zero_empty_weight(self):
        """测试零油重量为0的情况（修复后的异常处理）"""
        oil_lout = np.array([1000.0])
        oil_lin = np.array([1000.0])
        oil_rin = np.array([1000.0])
        oil_rout = np.array([1000.0])
        base_weight = 4000.0  # 等于 base_oil
        base_rel_cg = 25.0
        base_oil = 4000.0
        
        with pytest.raises(ValueError, match="零油重量必须为正数"):
            compute_total_weight_rel_cg(
                oil_lout, oil_lin, oil_rin, oil_rout,
                base_weight, base_rel_cg, base_oil
            )
    
    def test_compute_total_weight_rel_cg_negative_empty_weight(self):
        """测试零油重量为负数的情况"""
        oil_lout = np.array([1000.0])
        oil_lin = np.array([1000.0])
        oil_rin = np.array([1000.0])
        oil_rout = np.array([1000.0])
        base_weight = 3000.0  # 小于 base_oil
        base_rel_cg = 25.0
        base_oil = 4000.0
        
        with pytest.raises(ValueError, match="零油重量必须为正数"):
            compute_total_weight_rel_cg(
                oil_lout, oil_lin, oil_rin, oil_rout,
                base_weight, base_rel_cg, base_oil
            )
    
    def test_compute_fitted_circle_radius(self):
        """测试圆拟合"""
        # 创建一个圆形轨迹
        n_points = 100
        theta = np.linspace(0, 2*np.pi, n_points)
        radius = 1000.0
        center_lat = 30.0
        center_lon = 120.0
        
        lat = center_lat + (radius / 111320) * np.sin(theta)
        lon = center_lon + (radius / (111320 * np.cos(np.radians(center_lat)))) * np.cos(theta)
        
        time_vec = np.arange(n_points) * np.timedelta64(1, 's')
        
        R = compute_fitted_circle_radius(time_vec, 0, n_points-1, lon, lat)
        
        assert R is not None
        assert not np.isnan(R)
        assert abs(R - radius) < 50  # 允许 50 米误差


# ============================================================================
# statistics.py 测试
# ============================================================================

class TestStatistics:
    """统计模块测试"""
    
    def test_compute_stat_start(self):
        """测试起始值统计"""
        data = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        val, desc = compute_stat(data, 'start')
        assert val == 1.0
        assert desc == '起始值'
    
    def test_compute_stat_end(self):
        """测试结束值统计"""
        data = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        val, desc = compute_stat(data, 'end')
        assert val == 5.0
        assert desc == '结束值'
    
    def test_compute_stat_min(self):
        """测试最小值统计"""
        data = np.array([3.0, 1.0, 4.0, 1.0, 5.0])
        val, desc = compute_stat(data, 'min')
        assert val == 1.0
        assert desc == '最小值'
    
    def test_compute_stat_max(self):
        """测试最大值统计"""
        data = np.array([3.0, 1.0, 4.0, 1.0, 5.0])
        val, desc = compute_stat(data, 'max')
        assert val == 5.0
        assert desc == '最大值'
    
    def test_compute_stat_mean(self):
        """测试平均值统计"""
        data = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        val, desc = compute_stat(data, 'mean')
        assert val == 3.0
        assert desc == '平均值'
    
    def test_compute_stat_std(self):
        """测试标准差统计"""
        data = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        val, desc = compute_stat(data, 'std')
        expected = np.std(data, ddof=1)
        assert abs(val - expected) < 1e-10
        assert desc == '标准差'
    
    def test_compute_stat_range(self):
        """测试范围统计"""
        data = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        val, desc = compute_stat(data, 'range')
        assert val == (1.0, 5.0)
        assert desc == '范围'
    
    def test_compute_stat_points(self):
        """测试数据点数统计"""
        data = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        val, desc = compute_stat(data, 'points')
        assert val == 5
        assert desc == '数据点数'
    
    def test_compute_stat_empty_array(self):
        """测试空数组（修复后的异常处理）"""
        data = np.array([])
        with pytest.raises(ValueError, match="数据数组不能为空"):
            compute_stat(data, 'start')
    
    def test_compute_stat_empty_array_end(self):
        """测试空数组的 end 统计"""
        data = np.array([])
        with pytest.raises(ValueError, match="数据数组不能为空"):
            compute_stat(data, 'end')
    
    def test_compute_stat_empty_array_min(self):
        """测试空数组的 min 统计"""
        data = np.array([])
        with pytest.raises(ValueError, match="数据数组不能为空"):
            compute_stat(data, 'min')
    
    def test_compute_stat_invalid_type(self):
        """测试无效的统计类型"""
        data = np.array([1.0, 2.0, 3.0])
        with pytest.raises(ValueError, match="不支持的统计类型"):
            compute_stat(data, 'invalid')


# ============================================================================
# 集成测试
# ============================================================================

class TestIntegration:
    """集成测试"""
    
    @pytest.fixture
    def temp_data_file(self):
        """创建临时数据文件"""
        # 使用临时目录避免 Windows 文件锁定问题
        temp_dir = tempfile.mkdtemp()
        temp_path = os.path.join(temp_dir, 'test_data.txt')
        with open(temp_path, 'w', encoding='utf-8') as f:
            f.write("TIME\tCol1\tCol2\n")
            for i in range(200):
                f.write(f"00:00:{i:02d}:000\t{i}.0\t{i*2}.0\n")
        yield temp_path
        # 清理临时目录
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    def test_full_workflow(self, temp_data_file):
        """测试完整工作流程"""
        # 1. 提取数据
        data = param_extract(temp_data_file)
        assert 'TIME' in data
        assert 'Col1' in data
        
        # 2. 提取时间
        time_vec = extract_time(temp_data_file)
        assert len(time_vec) == len(data['Col1'])
        
        # 3. 计算统计
        val, desc = compute_stat(data['Col1'], 'mean')
        assert val > 0
        
        # 4. 时间窗口选择
        # 注意：param_extract 默认截取前50行和后50行，所以数据从50秒开始
        i_start, i_end, start, end = select_time_window(time_vec, 60, 70)
        assert start == 60
        assert end == 70


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
