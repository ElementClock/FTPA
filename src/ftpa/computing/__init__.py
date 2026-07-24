"""
计算子包
提供重量重心反解和回转半径计算功能。
"""

from .weight_cg import compute_total_weight_rel_cg, add_weight_cg_to_data
from .circle_fit import compute_fitted_circle_radius

# 私有函数仅供子包内部使用，不导出到公共 API
from .weight_cg import _interp_clamp  # noqa: F401
from .circle_fit import _taubin_circle_fit  # noqa: F401

__all__ = [
    'compute_total_weight_rel_cg',
    'compute_fitted_circle_radius',
    'add_weight_cg_to_data',
]
