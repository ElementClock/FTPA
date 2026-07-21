"""
计算模块
对应 MATLAB: PrivateComputing/computeTotalWeightRelCg.m, computeFittedCircleRadius.m
提供重量重心反解和回转半径计算功能
"""

import numpy as np
from scipy.linalg import eig
from .time_utils import select_time_window


def compute_total_weight_rel_cg(oil_lout, oil_lin, oil_rin, oil_rout,
                                 base_weight, base_rel_cg, base_oli):
    """
    计算总重量和相对重心
    
    对应 MATLAB: computeTotalWeightRelCg.m
    
    参数:
        oil_lout: 左外油箱油量 (kg)，numpy 数组或标量
        oil_lin: 左内油箱油量 (kg)，numpy 数组或标量
        oil_rin: 右内油箱油量 (kg)，numpy 数组或标量
        oil_rout: 右外油箱油量 (kg)，numpy 数组或标量
        base_weight: 任务重量 (kg)，标量
        base_rel_cg: 任务相对重心 (%)，标量
        base_oli: 任务油量 (kg)，标量
    
    返回:
        (total_weight, rel_cg): 总重量 (kg) 和相对重心 (%) 的 numpy 数组
    """
    # 基础配置
    X0 = 15.902  # 参考点绝对重心 (m)
    L = 4.453    # 参考长度 (m)
    
    # 1007架机燃油质量特性基础数据
    # 右内（及左内）燃油质量特性
    fuel_rin_oil = np.array([0, 100, 200, 300, 400, 500, 600, 700, 800, 900, 1000, 1100, 
                             1200, 1300, 1400, 1500, 1600, 1700, 1800, 1900, 2000, 2100, 
                             2200, 2300, 2400, 2500, 2600, 2700, 2800, 2900, 3000, 3100, 
                             3200, 3300, 3400, 3500, 3600, 3700, 3800, 3900, 4000, 4100, 
                             4200, 4300, 4400, 4500, 4600, 4700, 4800, 4900, 5000, 5100, 
                             5200, 5275], dtype=np.float64)
    
    fuel_rin_cg_x = np.array([17.543, 17.397, 17.350, 17.336, 17.330, 17.328, 17.328, 17.328, 
                              17.328, 17.322, 17.337, 17.348, 17.356, 17.362, 17.365, 17.367, 
                              17.368, 17.369, 17.369, 17.370, 17.370, 17.371, 17.371, 17.371, 
                              17.372, 17.372, 17.373, 17.373, 17.373, 17.374, 17.374, 17.375, 
                              17.375, 17.376, 17.376, 17.376, 17.377, 17.377, 17.378, 17.378, 
                              17.378, 17.379, 17.379, 17.380, 17.380, 17.381, 17.381, 17.381, 
                              17.382, 17.382, 17.383, 17.383, 17.383, 17.384], dtype=np.float64)
    
    # 右外（及左外）燃油质量特性
    fuel_rout_oil = np.array([0, 100, 200, 300, 400, 500, 600, 700, 800, 900, 1000, 1100, 
                              1200, 1300, 1400, 1500, 1600, 1700, 1800, 1900, 2000, 2100, 
                              2200, 2300, 2400, 2500, 2600, 2700, 2800, 2900, 3000, 3100, 
                              3200, 3300, 3400, 3500, 3600, 3700, 3800, 3900, 4000, 4100, 
                              4200, 4300, 4400, 4500, 4600, 4700, 4800, 4900, 5000, 5100, 
                              5200, 5275], dtype=np.float64)
    
    fuel_rout_cg_x = np.array([17.667, 17.523, 17.486, 17.476, 17.472, 17.471, 17.471, 17.459, 
                               17.467, 17.479, 17.487, 17.492, 17.496, 17.500, 17.503, 17.506, 
                               17.508, 17.511, 17.513, 17.515, 17.517, 17.518, 17.520, 17.521, 
                               17.523, 17.524, 17.525, 17.526, 17.527, 17.528, 17.529, 17.530, 
                               17.531, 17.532, 17.533, 17.534, 17.535, 17.535, 17.536, 17.537, 
                               17.538, 17.538, 17.539, 17.540, 17.540, 17.541, 17.541, 17.542, 
                               17.543, 17.543, 17.544, 17.544, 17.544, 17.544], dtype=np.float64)
    
    # 任务状态反解零油重量重心
    oil_each_ref = base_oli / 4.0
    cg_lout_ref = _interp_clamp(fuel_rout_oil, fuel_rout_cg_x, oil_each_ref)
    cg_lin_ref = _interp_clamp(fuel_rin_oil, fuel_rin_cg_x, oil_each_ref)
    cg_rin_ref = _interp_clamp(fuel_rin_oil, fuel_rin_cg_x, oil_each_ref)
    cg_rout_ref = _interp_clamp(fuel_rout_oil, fuel_rout_cg_x, oil_each_ref)
    
    # 任务油量力矩
    M_fuel_ref = oil_each_ref * (cg_lout_ref + cg_lin_ref + cg_rin_ref + cg_rout_ref)
    
    # 任务状态绝对重心 (m)
    base_cg_x_abs = X0 + L * (base_rel_cg / 100.0)
    
    # 零油重
    W_empty = base_weight - base_oli
    
    # 检查零油重量是否为正数
    if W_empty <= 0:
        raise ValueError(f"零油重量必须为正数，当前: {W_empty}")
    
    # 零油绝对重心
    X_empty = (base_weight * base_cg_x_abs - M_fuel_ref) / W_empty
    
    # 实际状态插值计算
    cg_lout = _interp_clamp(fuel_rout_oil, fuel_rout_cg_x, oil_lout)
    cg_lin = _interp_clamp(fuel_rin_oil, fuel_rin_cg_x, oil_lin)
    cg_rin = _interp_clamp(fuel_rin_oil, fuel_rin_cg_x, oil_rin)
    cg_rout = _interp_clamp(fuel_rout_oil, fuel_rout_cg_x, oil_rout)
    
    # 计算总重与相对重心
    total_fuel_weight = oil_lout + oil_lin + oil_rin + oil_rout
    total_moment = (oil_lout * cg_lout + oil_lin * cg_lin + 
                    oil_rin * cg_rin + oil_rout * cg_rout)
    
    total_weight = W_empty + total_fuel_weight
    total_cg_x = (W_empty * X_empty + total_moment) / total_weight
    rel_cg = (total_cg_x - X0) / L * 100.0
    
    return total_weight, rel_cg


def _interp_clamp(oil_arr, cg_arr, oil_val):
    """
    线性插值并钳位到边界
    
    对应 MATLAB: interp_clamp 内部函数
    使用 np.interp()，它自动处理边界钳位（与 MATLAB interp1 的 'linear' 插值 + 手动钳位等效）
    
    参数:
        oil_arr: 油量数组 (kg)
        cg_arr: 重心数组 (m)
        oil_val: 待插值的油量（numpy 数组或标量）
    
    返回:
        插值后的重心值（numpy 数组或标量）
    """
    # np.interp 自动处理边界钳位：
    # - 当 oil_val < oil_arr[0] 时，返回 cg_arr[0]
    # - 当 oil_val > oil_arr[-1] 时，返回 cg_arr[-1]
    return np.interp(oil_val, oil_arr, cg_arr)


def compute_fitted_circle_radius(time_vec, start_t, end_t, longitude, latitude):
    """
    计算给定时间窗口内经纬度轨迹的最小二乘拟合圆半径（米）
    
    对应 MATLAB: computeFittedCircleRadius.m
    
    参数:
        time_vec: 时间向量（支持 timedelta64, 数值秒, TimedeltaIndex）
        start_t: 起始时间
        end_t: 结束时间
        longitude: 经度数组（度），长度与 time_vec 一致
        latitude: 纬度数组（度），长度与 time_vec 一致
    
    返回:
        R: 拟合圆半径（米），若数据不足或拟合失败则返回 NaN
    """
    # 时间区间对齐
    idx, actual_start, actual_end = select_time_window(time_vec, start_t, end_t)
    
    # 检查长度一致性
    if len(longitude) != len(time_vec) or len(latitude) != len(time_vec):
        raise ValueError('经纬度向量长度必须与 TIME 一致。')
    
    # 截取数据
    lon = longitude[idx]
    lat = latitude[idx]
    n = len(lon)
    
    # 检查数据点数
    if n < 3:
        print('警告: 时间窗口内有效数据点不足3个，无法拟合圆。')
        print('回转半径\tNaN')
        return np.nan
    
    # 经纬度转换为局部平面坐标（米）
    lat0 = lat[0]
    lon0 = lon[0]
    mean_lat = np.mean(lat) * np.pi / 180.0
    meters_per_deg_lat = 111320.0
    meters_per_deg_lon = 111320.0 * np.cos(mean_lat)
    
    y = (lat - lat0) * meters_per_deg_lat
    x = (lon - lon0) * meters_per_deg_lon
    
    # Taubin 圆拟合
    R, a, b = _taubin_circle_fit(x, y)
    
    print(f'回转半径\t{R:.2f} 米')
    return R


def _taubin_circle_fit(x, y):
    """
    Taubin 最小二乘圆拟合算法
    
    对应 MATLAB: taubinCircleFit 内部函数
    
    参数:
        x: X 坐标数组（米）
        y: Y 坐标数组（米）
    
    返回:
        (R, a, b): 半径（米）、圆心 X 坐标、圆心 Y 坐标
    """
    n = len(x)
    xm = np.mean(x)
    ym = np.mean(y)
    xc = x - xm
    yc = y - ym
    
    z = xc**2 + yc**2
    Z = np.column_stack([z, xc, yc, np.ones(n)])
    
    # 构建约束矩阵 M
    M = np.zeros((4, 4))
    M[0, 0] = 4.0 * np.mean(z)
    M[0, 1] = 2.0 * np.mean(xc)
    M[0, 2] = 2.0 * np.mean(yc)
    M[1, 0] = M[0, 1]
    M[1, 1] = 1.0
    M[2, 0] = M[0, 2]
    M[2, 2] = 1.0
    
    # 构建矩阵 A = Z' * Z
    A = Z.T @ Z
    
    # 求解广义特征值问题 A * u = lambda * M * u
    # scipy.linalg.eig 返回 (eigenvalues, eigenvectors)
    eigenvalues, eigenvectors = eig(A, M)
    
    # 取最小 |lambda| 对应的特征向量
    # MATLAB: [~, idx] = min(abs(diag(D)))
    idx = np.argmin(np.abs(eigenvalues))
    u = eigenvectors[:, idx]
    
    # 取实部（MATLAB 的 eig 返回实数，但 scipy 可能返回复数）
    u = np.real(u)
    
    # 计算圆心和半径
    a = -u[1] / (2.0 * u[0]) + xm
    b = -u[2] / (2.0 * u[0]) + ym
    R_squared = (u[1]**2 + u[2]**2 - 4.0 * u[0] * u[3]) / (4.0 * u[0]**2)
    
    # 检查 R 是否为实数且为正
    if R_squared <= 0 or np.isnan(R_squared):
        R = np.nan
        a = np.nan
        b = np.nan
    else:
        R = np.sqrt(R_squared)
    
    return R, a, b
