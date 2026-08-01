"""
重量重心计算模块

对应 MATLAB: PrivateComputing/computeTotalWeightRelCg.m
提供基于燃油插值的总重量和相对重心反解计算。
"""

from __future__ import annotations

import numpy as np
from .aircraft import X0, L
from .fuel_data import fuel_rin_oil, fuel_rin_cg_x, fuel_rout_oil, fuel_rout_cg_x
# P1-ARCH-3: add_weight_cg_to_data 已迁移至 data/enrichment.py，
# 本模块不再依赖 data 层（LabelMap 等），保持纯计算职责。


def _interp_clamp(oil_arr: np.ndarray, cg_arr: np.ndarray,
                  oil_val: np.ndarray | float) -> np.ndarray | float:
    """
    线性插值并钳位到边界

    对应 MATLAB: interp_clamp 内部函数
    使用 np.interp()，它自动处理边界钳位

    参数:
        oil_arr: 油量数组 (kg)
        cg_arr: 重心数组 (m)
        oil_val: 待插值的油量（numpy 数组或标量）

    返回:
        插值后的重心值（numpy 数组或标量）
    """
    return np.interp(oil_val, oil_arr, cg_arr)


def compute_total_weight_rel_cg(
    oil_lout: np.ndarray,
    oil_lin: np.ndarray,
    oil_rin: np.ndarray,
    oil_rout: np.ndarray,
    base_weight: float,
    base_rel_cg: float,
    base_oil: float,
) -> tuple[np.ndarray, np.ndarray]:
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
        base_oil: 任务油量 (kg)，标量

    返回:
        (total_weight, rel_cg): 总重量 (kg) 和相对重心 (%) 的 numpy 数组
    """
    # 任务状态反解零油重量重心
    oil_each_ref = base_oil / 4.0
    cg_lout_ref = _interp_clamp(fuel_rout_oil, fuel_rout_cg_x, oil_each_ref)
    cg_lin_ref = _interp_clamp(fuel_rin_oil, fuel_rin_cg_x, oil_each_ref)
    cg_rin_ref = _interp_clamp(fuel_rin_oil, fuel_rin_cg_x, oil_each_ref)
    cg_rout_ref = _interp_clamp(fuel_rout_oil, fuel_rout_cg_x, oil_each_ref)

    # 任务油量力矩
    M_fuel_ref = oil_each_ref * (cg_lout_ref + cg_lin_ref + cg_rin_ref + cg_rout_ref)

    # 任务状态绝对重心 (m)
    base_cg_x_abs = X0 + L * (base_rel_cg / 100.0)

    # 零油重
    W_empty = base_weight - base_oil

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
