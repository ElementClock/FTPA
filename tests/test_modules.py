"""
单元测试：验证 computing.py 和 statistics.py 模块
"""

import sys
import numpy as np
import pytest
import matplotlib
matplotlib.use('Agg')  # 非交互式后端，防止 plt.show() 阻塞
import matplotlib.pyplot as plt
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from ftpa.computing import compute_total_weight_rel_cg, compute_fitted_circle_radius
from ftpa.computing.circle_fit import _taubin_circle_fit
from ftpa.statistics import (
    compute_stat,
    compute_var_stats,
    show_group_stats,
    crossing_analysis,
    find_crossing_points,
)
from ftpa.utils.time_utils import select_time_window
# CLI plotting 模块已归档，_build_stats_lines/_plot_core_interactive 不再可用
from ftpa.gui._font_config import configure_display_font


def test_find_crossing_points():
    """测试 MATLAB 风格的阈值穿越检测。"""
    values = np.array([2.0, 1.5, 0.2, -1.0, -0.5, 0.8, 0.2])

    first_down = find_crossing_points(values, 0.5, 'FirstDown')
    assert first_down == 1, f'首次下降穿越位置应为 1，实际为 {first_down}'

    first_up = find_crossing_points(values, 0.0, 'FirstUp')
    assert first_up == 4, f'首次上升穿越位置应为 4，实际为 {first_up}'

    last_down = find_crossing_points(values, 0.5, 'LastDown')
    assert last_down == 5, f'末次下降穿越位置应为 5，实际为 {last_down}'

    print('[OK] find_crossing_points 测试通过\n')


def test_build_stats_lines():
    """测试交互绘图窗口统计摘要构造 — CLI plotting 模块已归档，跳过。"""
    pytest.skip("CLI plotting 模块已归档到 references/cli/，_build_stats_lines 不再可用")


def test_configure_display_font():
    """测试中文显示字体配置能生效。"""
    font_family = configure_display_font()
    assert font_family is not None
    assert font_family in plt.rcParams['font.sans-serif']
    print('[OK] _configure_display_font 测试通过\n')


def test_plot_core_interactive_smoke():
    """测试交互绘图函数 — CLI plotting 模块已归档，跳过。"""
    pytest.skip("CLI plotting 模块已归档到 references/cli/，_plot_core_interactive 不再可用")


def test_compute_stat():
    """测试 compute_stat 函数"""
    print('=' * 60)
    print('测试 compute_stat 函数')
    print('=' * 60)
    
    data = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
    
    # 测试各种统计类型
    val, desc = compute_stat(data, 'start')
    assert val == 1.0 and desc == '起始值', f'start 失败: {val}, {desc}'
    print(f'[OK] start: {val} ({desc})')
    
    val, desc = compute_stat(data, 'end')
    assert val == 5.0 and desc == '结束值', f'end 失败: {val}, {desc}'
    print(f'[OK] end: {val} ({desc})')
    
    val, desc = compute_stat(data, 'min')
    assert val == 1.0 and desc == '最小值', f'min 失败: {val}, {desc}'
    print(f'[OK] min: {val} ({desc})')
    
    val, desc = compute_stat(data, 'max')
    assert val == 5.0 and desc == '最大值', f'max 失败: {val}, {desc}'
    print(f'[OK] max: {val} ({desc})')
    
    result = compute_stat(data, 'range')
    assert result == (1.0, 5.0, '范围'), f'range 失败: {result}'
    print(f'[OK] range: {result[0]:.4g} ~ {result[1]:.4g} ({result[2]})')
    
    val, desc = compute_stat(data, 'mean')
    assert val == 3.0 and desc == '平均值', f'mean 失败: {val}, {desc}'
    print(f'[OK] mean: {val} ({desc})')
    
    val, desc = compute_stat(data, 'std')
    expected_std = np.std(data, ddof=1)
    assert np.isclose(val, expected_std) and desc == '标准差', f'std 失败: {val}, {desc}'
    print(f'[OK] std: {val:.6g} ({desc})')
    
    val, desc = compute_stat(data, 'points')
    assert val == 5 and desc == '数据点数', f'points 失败: {val}, {desc}'
    print(f'[OK] points: {val} ({desc})')
    
    print('[OK] compute_stat 所有测试通过\n')


def test_compute_total_weight_rel_cg():
    """测试 compute_total_weight_rel_cg 函数"""
    print('=' * 60)
    print('测试 compute_total_weight_rel_cg 函数')
    print('=' * 60)
    
    # 测试用例：标量输入
    oil_lout = np.array([1000.0])
    oil_lin = np.array([1200.0])
    oil_rin = np.array([1200.0])
    oil_rout = np.array([1000.0])
    base_weight = 45000.0  # kg
    base_rel_cg = 25.0     # %
    base_oil = 4400.0      # kg
    
    total_weight, rel_cg = compute_total_weight_rel_cg(
        oil_lout, oil_lin, oil_rin, oil_rout,
        base_weight, base_rel_cg, base_oil
    )
    
    print(f'输入参数:')
    print(f'  左外油量: {oil_lout[0]} kg')
    print(f'  左内油量: {oil_lin[0]} kg')
    print(f'  右内油量: {oil_rin[0]} kg')
    print(f'  右外油量: {oil_rout[0]} kg')
    print(f'  任务重量: {base_weight} kg')
    print(f'  任务重心: {base_rel_cg} %')
    print(f'  任务油量: {base_oil} kg')
    print(f'\n输出结果:')
    print(f'  总重量: {total_weight[0]:.2f} kg')
    print(f'  相对重心: {rel_cg[0]:.2f} %')
    
    # 验证合理性
    assert total_weight[0] > 0, '总重量应为正数'
    assert 0 < rel_cg[0] < 100, '相对重心应在 0-100% 之间'
    print('[OK] compute_total_weight_rel_cg 测试通过\n')


def test_compute_fitted_circle_radius():
    """测试 compute_fitted_circle_radius 函数"""
    print('=' * 60)
    print('测试 compute_fitted_circle_radius 函数')
    print('=' * 60)
    
    # 直接测试 _taubin_circle_fit 函数
    from ftpa.computing.circle_fit import _taubin_circle_fit
    
    # 生成一个标准圆（单位：米）
    n_points = 100
    theta = np.linspace(0, 2 * np.pi, n_points, endpoint=False)
    center_x = 1000.0  # 米
    center_y = 2000.0  # 米
    radius = 500.0     # 米
    
    x = center_x + radius * np.cos(theta)
    y = center_y + radius * np.sin(theta)
    
    # 调用圆拟合
    R, a, b = _taubin_circle_fit(x, y)
    
    print(f'标准圆参数:')
    print(f'  圆心: ({center_x}, {center_y}) 米')
    print(f'  半径: {radius} 米')
    print(f'  数据点: {n_points}')
    print(f'\n拟合结果:')
    print(f'  圆心: ({a:.2f}, {b:.2f}) 米')
    print(f'  半径: {R:.2f} 米')
    
    # 验证拟合精度
    assert not np.isnan(R), '回转半径不应为 NaN'
    assert abs(R - radius) < 1.0, f'半径偏差过大: {R} vs {radius}'
    assert abs(a - center_x) < 1.0, f'圆心X偏差过大: {a} vs {center_x}'
    assert abs(b - center_y) < 1.0, f'圆心Y偏差过大: {b} vs {center_y}'
    print(f'[OK] _taubin_circle_fit 测试通过')
    
    # 测试完整的 compute_fitted_circle_radius 函数
    # 使用简单的数值秒时间向量
    TIME_sec = np.linspace(0, 100, n_points)
    # 经纬度转换需要考虑 cos(latitude) 修正
    meters_per_deg_lat = 111320.0
    meters_per_deg_lon = 111320.0 * np.cos(39.5 * np.pi / 180.0)
    lon = 116.5 + (x / meters_per_deg_lon)  # 经度转换
    lat = 39.5 + (y / meters_per_deg_lat)   # 纬度转换
    
    R_full = compute_fitted_circle_radius(TIME_sec, 0, 100, lon, lat)
    
    print(f'\n完整函数测试结果:')
    print(f'  回转半径: {R_full:.2f} 米')
    
    # 验证合理性（由于 mean(lat) 与固定 lat 的近似差异，允许一定误差）
    assert not np.isnan(R_full), '回转半径不应为 NaN'
    assert R_full > 0, '回转半径应为正数'
    # 算法使用 mean(lat) 而非固定 lat 做经度缩放，存在系统偏差
    assert abs(R_full - radius) / radius < 0.15, f'回转半径相对偏差过大: {R_full} vs {radius}'
    print(f'  相对偏差: {abs(R_full - radius) / radius * 100:.1f}%')
    print(f'[OK] compute_fitted_circle_radius 测试通过\n')


def test_compute_var_stats():
    """测试 compute_var_stats 函数"""
    print('=' * 60)
    print('测试 compute_var_stats 函数')
    print('=' * 60)
    
    # 生成测试数据
    n = 100
    TIME = np.linspace(0, 100, n)
    data1 = np.sin(TIME / 10)
    data2 = np.cos(TIME / 10)
    
    print('调用 compute_var_stats:')
    compute_var_stats(TIME, 20, 80,
                      data1, '正弦信号', 'mean',
                      data2, '余弦信号', 'max')
    print('[OK] compute_var_stats 测试通过\n')


def test_show_group_stats():
    """测试 show_group_stats 函数"""
    print('=' * 60)
    print('测试 show_group_stats 函数')
    print('=' * 60)
    
    # 生成测试数据
    n = 100
    TIME = np.linspace(0, 100, n)
    data1 = np.sin(TIME / 10)
    data2 = np.cos(TIME / 10)
    data3 = np.tan(TIME / 10)
    
    print('调用 show_group_stats:')
    show_group_stats(TIME, 20, 80,
                     'max', [data1, data2], ['正弦', '余弦'],
                     'min', [data1, data3], ['正弦', '正切'])
    print('[OK] show_group_stats 测试通过\n')


def test_crossing_analysis():
    """测试 crossing_analysis 函数"""
    print('=' * 60)
    print('测试 crossing_analysis 函数')
    print('=' * 60)
    
    # 生成测试数据
    n = 100
    TIME = np.linspace(0, 100, n)
    main_sig = np.sin(TIME / 10)  # 正弦波
    other_sig = np.cos(TIME / 10)  # 余弦波
    
    data = {
        'TIME': TIME,
        'main': main_sig,
        'other': other_sig
    }
    
    # 模拟 LabelMap
    class MockLabelMap:
        def get_var_name(self, label):
            return label
        def get_label(self, field):
            return field
    
    lm = MockLabelMap()
    
    print('调用 crossing_analysis (FirstDown):')
    lines = crossing_analysis(data, lm, ['main', 'other'], 'FirstDown', 0.0, 0, 100)
    for line in lines:
        print(f'  {line}')
    
    print('\n调用 crossing_analysis (FirstUp):')
    lines = crossing_analysis(data, lm, ['main', 'other'], 'FirstUp', 0.0, 0, 100)
    for line in lines:
        print(f'  {line}')
    
    print('[OK] crossing_analysis 测试通过\n')


if __name__ == '__main__':
    print('\n' + '=' * 60)
    print('开始单元测试：computing.py 和 statistics.py')
    print('=' * 60 + '\n')
    
    try:
        test_compute_stat()
        test_compute_total_weight_rel_cg()
        test_compute_fitted_circle_radius()
        test_compute_var_stats()
        test_show_group_stats()
        test_crossing_analysis()
        
        print('=' * 60)
        print('[OK] 所有测试通过！')
        print('=' * 60)
    except Exception as e:
        print(f'\n[FAIL] 测试失败: {e}')
        import traceback
        traceback.print_exc()
