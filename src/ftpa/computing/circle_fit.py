"""
圆拟合模块（Taubin 最小二乘圆拟合）

对应 MATLAB: PrivateComputing/computeFittedCircleRadius.m
提供基于经纬度轨迹的最小二乘拟合圆半径计算。
"""

from __future__ import annotations

import logging
import numpy as np
from scipy.linalg import eig
from ..time_utils import select_time_window

logger = logging.getLogger(__name__)


def compute_fitted_circle_radius(
    time_vec: np.ndarray,
    start_t: float | str,
    end_t: float | str,
    longitude: np.ndarray,
    latitude: np.ndarray,
) -> float:
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
    i_start, i_end, actual_start, actual_end = select_time_window(time_vec, start_t, end_t)

    # 检查长度一致性
    if len(longitude) != len(time_vec) or len(latitude) != len(time_vec):
        raise ValueError('经纬度向量长度必须与 TIME 一致。')

    # 截取数据
    lon = longitude[i_start:i_end + 1]
    lat = latitude[i_start:i_end + 1]
    n = len(lon)

    # 检查数据点数
    if n < 3:
        logger.warning('时间窗口内有效数据点不足3个，无法拟合圆。')
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

    logger.info('回转半径\t%.2f 米', R)
    return R


def _taubin_circle_fit(x: np.ndarray, y: np.ndarray) -> tuple[float, float, float]:
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
    eigenvalues, eigenvectors = eig(A, M)

    # 取最小 |lambda| 对应的特征向量
    idx = np.argmin(np.abs(eigenvalues))
    u = eigenvectors[:, idx]

    # 取实部（MATLAB 的 eig 返回实数，但 scipy 可能返回复数）
    u = np.real(u)

    # 防范共线点: u[0] ≈ 0 时圆不存在
    if abs(u[0]) < 1e-12:
        return np.nan, np.nan, np.nan

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
