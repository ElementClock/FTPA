"""统计计算服务。

从 services.py 迁移，零行为变更。
"""

from __future__ import annotations

import logging

from ...data.label_map import LabelMap
from ...statistics import (
    compute_takeoff_landing_stats,
    crossing_analysis,
    crossing_analysis_without_labelmap,
    statistics_params,
    statistics_params_without_labelmap,
)
from .field_resolver import FieldResolver

logger = logging.getLogger(__name__)


class StatisticsService:
    """统计计算服务。

    职责：
    - 参数统计（compute_parameter_stats）
    - 穿越分析（compute_crossing_analysis）
    - 起降统计（compute_takeoff_landing_stats）
    """

    def __init__(self, data: dict, lm: LabelMap | None = None,
                 is_loaded: bool = False, field_resolver: FieldResolver | None = None):
        self._data = data
        self._lm = lm
        self._is_loaded = is_loaded
        self._field_resolver = field_resolver

    def update(self, data: dict, lm: LabelMap | None = None,
               is_loaded: bool = False, field_resolver: FieldResolver | None = None) -> None:
        """数据加载后更新引用。"""
        self._data = data
        self._lm = lm
        self._is_loaded = is_loaded
        self._field_resolver = field_resolver

    def clear(self) -> None:
        """卸载时清空所有状态。"""
        self._data = {}
        self._lm = None
        self._is_loaded = False
        self._field_resolver = None

    def compute_parameter_stats(self, t_start, t_end, signal_ids: list[str]) -> list[str]:
        if not self._is_loaded:
            return ["数据未加载"]
        if self._lm is None:
            return self._stats_without_labelmap(t_start, t_end, signal_ids)
        return statistics_params(t_start, t_end, self._data, self._lm, signal_ids)

    def compute_crossing_analysis(
        self, signal_ids: list[str], mode: str, threshold: float, t_start, t_end
    ) -> list[str]:
        if not self._is_loaded:
            return ["数据未加载"]
        if self._lm is None:
            return self._crossing_without_labelmap(signal_ids, mode, threshold, t_start, t_end)
        return crossing_analysis(self._data, self._lm, signal_ids, mode, threshold, t_start, t_end)

    def compute_takeoff_landing_stats(self, t_start, t_end) -> str:
        if not self._is_loaded:
            return "数据未加载"
        if self._lm is None:
            return "CSV 模式不支持起降统计（需要映射表定位关键参数）"
        return compute_takeoff_landing_stats(t_start, t_end, self._data, self._lm)

    def _stats_without_labelmap(self, t_start, t_end, signal_ids: list[str] | None) -> list[str]:
        """CSV 模式参数统计：列名即为标签，无需 LabelMap。"""
        return statistics_params_without_labelmap(
            self._data, t_start, t_end, signal_ids, self._field_resolver
        )

    def _crossing_without_labelmap(
        self, signal_ids: list[str], mode: str, threshold: float, t_start, t_end
    ) -> list[str]:
        """CSV 模式穿越分析：列名即为标签，无需 LabelMap。"""
        return crossing_analysis_without_labelmap(
            self._data, signal_ids, mode, threshold, t_start, t_end
        )
