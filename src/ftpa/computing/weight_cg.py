"""
重量重心计算模块

对应 MATLAB: PrivateComputing/computeTotalWeightRelCg.m
提供基于燃油插值的总重量和相对重心反解计算。
"""

import logging
import numpy as np
from ..constants import X0, L
from .fuel_data import fuel_rin_oil, fuel_rin_cg_x, fuel_rout_oil, fuel_rout_cg_x

logger = logging.getLogger(__name__)


def _interp_clamp(oil_arr, cg_arr, oil_val):
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


def add_weight_cg_to_data(data: dict, lm) -> None:
    """
    为数据字典添加重量和重心计算结果（原地修改）

    参数:
        data: 数据字典
        lm: LabelMap 对象，用于通过中文标签查找油箱油量字段
    """
    from .constants import BASE_WEIGHT, BASE_REL_CG, BASE_OIL

    try:
        oil_lout = data.get(lm.get_var_name('Ⅰ号油箱油量'))
        oil_lin = data.get(lm.get_var_name('Ⅱ号油箱油量'))
        oil_rin = data.get(lm.get_var_name('Ⅲ号油箱油量'))
        oil_rout = data.get(lm.get_var_name('Ⅳ号油箱油量'))

        if all(v is not None for v in [oil_lout, oil_lin, oil_rin, oil_rout]):
            total_weight, rel_cg = compute_total_weight_rel_cg(
                oil_lout, oil_lin, oil_rin, oil_rout,
                BASE_WEIGHT, BASE_REL_CG, BASE_OIL
            )

            data['totalWeight'] = total_weight
            data['relCg'] = rel_cg

            lm.add('totalWeight', '总重')
            lm.add('relCg', '相对重心')
    except Exception as e:
        logger.warning("重量重心计算失败: %s", e)
