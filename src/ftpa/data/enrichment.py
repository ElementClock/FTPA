"""数据富化模块

提供在数据加载后向数据字典注入派生量的操作。该模块属于 data 层，
依赖 computing 层的纯计算函数，但不被 computing 反向依赖（P1-ARCH-3）。

历史：``add_weight_cg_to_data`` 原位于 ``computing/weight_cg.py``，因其需要
``LabelMap``（data 层概念）并原地修改数据字典，本质是数据富化而非纯计算，
故迁移至 data 层。纯计算函数 ``compute_total_weight_rel_cg`` 仍保留在 computing。
"""

from __future__ import annotations

import logging

import numpy as np

from ..computing.aircraft import BASE_OIL, BASE_REL_CG, BASE_WEIGHT
from ..computing.weight_cg import compute_total_weight_rel_cg
from .label_map import LabelMap

logger = logging.getLogger(__name__)


def add_weight_cg_to_data(data: dict[str, np.ndarray], lm: LabelMap) -> None:
    """为数据字典添加重量和重心计算结果（原地修改）。

    Args:
        data: 数据字典。
        lm: LabelMap 对象，用于通过中文标签查找油箱油量字段。
    """
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

            # 幂等性：字段已存在时跳过 add，避免二次注入产生 '总重_2'（L4）
            if 'totalWeight' not in lm.list_fields():
                lm.add('totalWeight', '总重')
            if 'relCg' not in lm.list_fields():
                lm.add('relCg', '相对重心')
    except (ValueError, TypeError, KeyError, ZeroDivisionError):
        logger.warning("重量重心计算失败，跳过富化", exc_info=True)
