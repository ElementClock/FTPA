"""
综合验证测试套件
验证 MATLAB 到 Python 迁移的所有模块功能
"""

import numpy as np
import pandas as pd
import sys
import tempfile
import os
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from ftpa.utils import make_valid_name, column_to_field_name
from ftpa.data.label_map import LabelMap
from ftpa.data import param_extract, extract_time
from ftpa.utils.time_utils import select_time_window, format_time_seconds
from ftpa.computing import compute_total_weight_rel_cg, compute_fitted_circle_radius
from ftpa.statistics import (
    compute_stat, compute_var_stats, show_group_stats,
    compute_takeoff_landing_stats, statistics_params, crossing_analysis
)
# CLI plotting 模块已归档到 references/cli/，不再在源码树中
# from ftpa.plotting import plot_time_signals, plot_track


def test_utils():
    """测试工具函数模块"""
    print("\n" + "="*70)
    print("测试 M1-T1: utils.py")
    print("="*70)
    
    # 测试 make_valid_name
    assert make_valid_name("valid_name") == "valid_name"
    assert make_valid_name("123invalid") == "x123invalid"
    assert make_valid_name("invalid-name") == "invalid_name"
    assert make_valid_name("") == "x"
    print("[PASS] make_valid_name 测试通过")
    
    # 测试 column_to_field_name
    assert column_to_field_name("TIME") == "TIME"
    assert column_to_field_name("GNSU1001-L-076") == "GNSU1001_L_076"
    assert column_to_field_name("123-abc") == "x123_abc"
    print("[PASS] column_to_field_name 测试通过")
    
    print("[PASS][PASS][PASS] utils.py 所有测试通过")


def test_label_map():
    """测试标签映射模块"""
    print("\n" + "="*70)
    print("测试 M1-T4: label_map.py")
    print("="*70)
    
    # 创建测试映射 CSV 文件
    test_data = {
        '原始名称': ['TIME', 'AirSpeed', 'Altitude'],
        '中文名称': ['时间', '空速', '高度']
    }
    df = pd.DataFrame(test_data)
    tmp_dir = tempfile.mkdtemp()
    test_excel = os.path.join(tmp_dir, 'test_label_map.csv')
    df.to_csv(test_excel, index=False, encoding='utf-8-sig')
    
    try:
        # 测试 LabelMap
        lm = LabelMap(test_excel)
        
        # 测试 get_label
        assert lm.get_label('TIME') == '时间'
        assert lm.get_label('AirSpeed') == '空速'
        print("[PASS] get_label 测试通过")
        
        # 测试 get_var_name
        assert lm.get_var_name('时间') == 'TIME'
        assert lm.get_var_name('空速') == 'AirSpeed'
        print("[PASS] get_var_name 测试通过")
        
        # 测试 list_all
        all_mappings = lm.list_all()
        assert len(all_mappings) == 3
        print("[PASS] list_all 测试通过")
        
        print("[PASS][PASS][PASS] label_map.py 所有测试通过")
    finally:
        # 清理测试文件
        import shutil
        if Path(test_excel).exists():
            Path(test_excel).unlink()
        shutil.rmtree(tmp_dir, ignore_errors=True)


def test_time_utils():
    """测试时间工具模块"""
    print("\n" + "="*70)
    print("测试 M3-T7: time_utils.py")
    print("="*70)
    
    # 创建测试时间数据
    time_data = np.array([
        np.timedelta64(0, 's'),
        np.timedelta64(1, 's'),
        np.timedelta64(2, 's'),
        np.timedelta64(3, 's'),
        np.timedelta64(4, 's')
    ])
    
    # 测试 select_time_window
    i_start, i_end, start, end = select_time_window(time_data, 1, 3)
    assert i_end - i_start + 1 == 3  # 包含 1, 2, 3 秒
    assert start == 1.0
    assert end == 3.0
    print("[PASS] select_time_window 测试通过")
    
    # 测试 format_time_seconds
    assert format_time_seconds(3661.5) == "01:01:01.500"
    assert format_time_seconds(0) == "00:00:00.000"
    print("[PASS] format_time_seconds 测试通过")
    
    print("[PASS][PASS][PASS] time_utils.py 所有测试通过")


def test_computing():
    """测试计算模块"""
    print("\n" + "="*70)
    print("测试 M2: computing.py")
    print("="*70)
    
    # 测试 compute_total_weight_rel_cg
    # 使用简化的测试数据
    oil_lout = np.array([1000.0, 1100.0, 1200.0])
    oil_lin = np.array([1000.0, 1100.0, 1200.0])
    oil_rin = np.array([1000.0, 1100.0, 1200.0])
    oil_rout = np.array([1000.0, 1100.0, 1200.0])
    
    base_weight = 50000.0
    base_rel_cg = 25.0
    base_oil = 4000.0
    
    total_weight, rel_cg = compute_total_weight_rel_cg(
        oil_lout, oil_lin, oil_rin, oil_rout,
        base_weight, base_rel_cg, base_oil
    )
    
    assert len(total_weight) == 3
    assert len(rel_cg) == 3
    assert all(total_weight > 0)
    assert all((rel_cg >= 0) & (rel_cg <= 100))
    print("[PASS] compute_total_weight_rel_cg 测试通过")
    
    # 测试 compute_fitted_circle_radius
    # 创建一个圆形轨迹
    n_points = 100
    theta = np.linspace(0, 2*np.pi, n_points)
    radius = 1000.0  # 1000米
    center_lat = 30.0
    center_lon = 120.0
    
    # 转换为经纬度（简化）
    lat = center_lat + (radius / 111320) * np.sin(theta)
    lon = center_lon + (radius / (111320 * np.cos(np.radians(center_lat)))) * np.cos(theta)
    
    time_vec = np.arange(n_points) * np.timedelta64(1, 's')
    
    R = compute_fitted_circle_radius(time_vec, 0, n_points-1, lon, lat)
    
    assert not np.isnan(R)
    assert abs(R - radius) < 50  # 允许 50 米误差
    print(f"[PASS] compute_fitted_circle_radius 测试通过 (R={R:.2f}m, 期望≈{radius}m)")
    
    print("[PASS][PASS][PASS] computing.py 所有测试通过")


def test_statistics():
    """测试统计模块"""
    print("\n" + "="*70)
    print("测试 M3: statistics.py")
    print("="*70)
    
    # 测试 compute_stat
    data = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
    
    val, desc = compute_stat(data, 'start')
    assert val == 1.0
    print("[PASS] compute_stat (start) 测试通过")
    
    val, desc = compute_stat(data, 'end')
    assert val == 5.0
    print("[PASS] compute_stat (end) 测试通过")
    
    val, desc = compute_stat(data, 'min')
    assert val == 1.0
    print("[PASS] compute_stat (min) 测试通过")
    
    val, desc = compute_stat(data, 'max')
    assert val == 5.0
    print("[PASS] compute_stat (max) 测试通过")
    
    val, desc = compute_stat(data, 'mean')
    assert val == 3.0
    print("[PASS] compute_stat (mean) 测试通过")
    
    val, desc = compute_stat(data, 'std')
    assert abs(val - np.std(data, ddof=1)) < 1e-10
    print("[PASS] compute_stat (std) 测试通过")
    
    val, desc = compute_stat(data, 'range')
    assert val == (1.0, 5.0) and desc == '范围'
    print("[PASS] compute_stat (range) 测试通过")
    
    val, desc = compute_stat(data, 'points')
    assert val == 5
    print("[PASS] compute_stat (points) 测试通过")
    
    # 测试 compute_var_stats（仅验证不报错）
    time_vec = np.arange(5) * np.timedelta64(1, 's')
    data1 = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
    data2 = np.array([10.0, 20.0, 30.0, 40.0, 50.0])
    
    print("  测试 compute_var_stats 输出:")
    compute_var_stats(time_vec, 0, 4,
                     data1, '变量1', 'mean',
                     data2, '变量2', 'max')
    print("[PASS] compute_var_stats 测试通过")
    
    # 测试 show_group_stats（仅验证不报错）
    print("  测试 show_group_stats 输出:")
    show_group_stats(time_vec, 0, 4,
                    'max', [data1, data2], ['变量1', '变量2'])
    print("[PASS] show_group_stats 测试通过")
    
    print("[PASS][PASS][PASS] statistics.py 所有测试通过")


def test_data_loader():
    """测试数据加载模块"""
    print("\n" + "="*70)
    print("测试 M1-T2+T3: data_loader.py")
    print("="*70)
    
    # 创建测试数据文件（需要至少 100 行以避免被截取）
    tmp_dir2 = tempfile.mkdtemp()
    test_file = os.path.join(tmp_dir2, 'test_data.txt')
    with open(test_file, 'w', encoding='utf-8') as f:
        f.write("TIME\tCol1\tCol2\n")
        for i in range(150):
            f.write(f"00:00:{i:02d}:000\t{i}.0\t{i*10}.0\n")
    
    try:
        # 测试 param_extract
        data = param_extract(test_file)
        assert 'TIME' in data
        assert 'Col1' in data
        assert 'Col2' in data
        # 150 行 - 50 头 - 50 尾 = 50 行
        assert len(data['TIME']) == 50
        print("[PASS] param_extract 测试通过")
        
        # 测试 extract_time
        time_vec = extract_time(test_file)
        assert len(time_vec) == 50
        # 验证是时间类型（timedelta64 或 datetime64）
        assert np.issubdtype(time_vec.dtype, np.timedelta64) or np.issubdtype(time_vec.dtype, np.datetime64)
        print("[PASS] extract_time 测试通过")
        
        print("[PASS][PASS][PASS] data_loader.py 所有测试通过")
    finally:
        # 清理测试文件
        import shutil
        if Path(test_file).exists():
            Path(test_file).unlink()
        shutil.rmtree(tmp_dir2, ignore_errors=True)


def test_plotting():
    """测试绘图模块 — CLI plotting.py 已归档，跳过。"""
    print("\n" + "="*70)
    print("测试 M4: plotting.py (已归档到 references/cli/)")
    print("="*70)
    print("[SKIP] CLI plotting 模块已归档，测试跳过")


def run_all_tests():
    """运行所有测试"""
    print("\n" + "="*70)
    print("MATLAB 到 Python 迁移 - 综合验证测试")
    print("="*70)
    
    tests = [
        ("M1-T1: utils.py", test_utils),
        ("M1-T4: label_map.py", test_label_map),
        ("M3-T7: time_utils.py", test_time_utils),
        ("M2: computing.py", test_computing),
        ("M3: statistics.py", test_statistics),
        ("M1-T2+T3: data_loader.py", test_data_loader),
        ("M4: plotting.py", test_plotting),
    ]
    
    passed = 0
    failed = 0
    
    for name, test_func in tests:
        try:
            test_func()
            passed += 1
        except Exception as e:
            print(f"\n[FAIL][FAIL][FAIL] {name} 测试失败: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
    
    print("\n" + "="*70)
    print(f"测试总结: {passed} 通过, {failed} 失败")
    print("="*70)
    
    if failed == 0:
        print("\n[PASS][PASS][PASS] 所有模块验证通过！MATLAB 迁移成功！")
        return 0
    else:
        print(f"\n[FAIL][FAIL][FAIL] {failed} 个模块测试失败，请检查错误信息")
        return 1


if __name__ == "__main__":
    sys.exit(run_all_tests())
