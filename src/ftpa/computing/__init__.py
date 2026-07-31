"""
计算子包
提供重量重心反解和回转半径计算功能。
"""

from .aircraft import BASE_WEIGHT, BASE_REL_CG, BASE_OIL, X0, L
from .weight_cg import compute_total_weight_rel_cg, add_weight_cg_to_data
from .circle_fit import compute_fitted_circle_radius

# 私有函数仅供子包内部使用，不导出到公共 API
# 如需内部引用，请直接从子模块导入，例如：
#   from ftpa.computing.weight_cg import _interp_clamp
#   from ftpa.computing.circle_fit import _taubin_circle_fit

__all__ = [
    'BASE_WEIGHT',
    'BASE_REL_CG',
    'BASE_OIL',
    'X0',
    'L',
    'compute_total_weight_rel_cg',
    'compute_fitted_circle_radius',
    'add_weight_cg_to_data',
]
