"""绘图数据提取服务 —— 封装 get_plot_data + fallback 逻辑。

从 DataContext 的 get_plot_data() 方法提取，使 DataContext 不再
包含绘图数据组装逻辑。
"""

from __future__ import annotations

import logging

import numpy as np

from .query import DataQueryService

logger = logging.getLogger(__name__)


class PlotDataService:
    """绘图数据提取服务。"""

    def __init__(self, query_svc: DataQueryService):
        self._query_svc = query_svc

    def update(self, query_svc: DataQueryService) -> None:
        """数据加载后更新引用。"""
        self._query_svc = query_svc

    def clear(self) -> None:
        """卸载时清空引用。"""
        pass  # 无状态，仅持有引用

    def get_plot_data(self, signal_ids: list[str]) -> tuple[np.ndarray, np.ndarray, list[str]]:
        """返回 (time_sec, NxM signals_matrix, labels)。

        逻辑：
        1. 对每个 signal_id 通过 query_svc 解析字段名
        2. 如全部解析失败，取前 3 个数值信号作为 fallback
        3. 组装为 (N, M) 矩阵返回
        """
        time_sec = self._query_svc.get_time_sec()
        if time_sec is None:
            return np.array([], dtype=float), np.empty((0, 0)), []

        fields: list[str] = []
        labels: list[str] = []
        for sid in signal_ids:
            f = self._query_svc.resolve_field(sid)
            if f is not None:
                fields.append(f)
                labels.append(self._query_svc.get_label(f))

        if not fields:
            # fallback: 取前 3 个数值信号
            for f in self._query_svc.get_field_names():
                col = self._query_svc.get_signal_data(f)
                if isinstance(col, np.ndarray) and np.issubdtype(col.dtype, np.number):
                    fields.append(f)
                    labels.append(self._query_svc.get_label(f))
                    if len(fields) >= 3:
                        break

        n = len(time_sec)
        m = len(fields)
        signals = np.zeros((n, m), dtype=float)
        for i, f in enumerate(fields):
            col = self._query_svc.get_signal_data(f)
            if col is not None:
                try:
                    if isinstance(col, np.ndarray):
                        signals[:, i] = col
                    else:
                        signals[:, i] = np.asarray(col, dtype=np.float64)
                except (ValueError, TypeError):
                    logger.debug("非数值列跳过: field=%s", f)
        return time_sec, signals, labels
