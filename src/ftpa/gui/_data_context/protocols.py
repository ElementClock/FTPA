"""DataContext 拆分后的接口协议定义。

面板按需依赖窄接口，不依赖不需要的方法。
使用 Protocol（结构化子类型）而非 ABC，支持运行时 duck typing 且无需继承。
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

import numpy as np


@runtime_checkable
class DataQueryable(Protocol):
    """数据查询接口 —— 面板获取字段/标签/元信息。"""

    def get_field_names(self) -> list[str]: ...
    def get_field_labels(self) -> dict[str, str]: ...
    def get_label(self, field_name: str) -> str: ...
    def resolve_field(self, signal_id: str) -> str | None: ...
    def get_row_count(self) -> int: ...
    def get_column_count(self) -> int: ...
    def get_time_range_sec(self) -> tuple[float, float]: ...


@runtime_checkable
class DataLoadable(Protocol):
    """数据加载接口 —— MainWindow/Worker 使用。"""

    def load(self, data_path: str, excel_path: str) -> tuple[bool, str]: ...
    def unload(self) -> None: ...

    @property
    def is_loaded(self) -> bool: ...


@runtime_checkable
class DataExportable(Protocol):
    """数据导出接口 —— ExportPanel 使用。"""

    def export_data(self, output_path: str, fmt: str, compression: str | None = None) -> str: ...
    def export_statistics(self, stats: list, output_path: str, fmt: str = "csv") -> str: ...
    def generate_summary(self) -> dict: ...


@runtime_checkable
class PlotDataQueryable(Protocol):
    """绘图数据查询接口 —— PlotCanvasWidget/控制器 使用。"""

    def get_plot_data(self, signal_ids: list[str]) -> tuple[np.ndarray, np.ndarray, list[str]]: ...


@runtime_checkable
class StatisticsComputable(Protocol):
    """统计计算接口 —— StatisticsPanel/CrossingAnalyzer 使用。"""

    def compute_parameter_stats(self, t_start, t_end, signal_ids: list[str]) -> list[str]: ...
    def compute_crossing_analysis(self, signal_ids: list[str], mode: str, threshold: float, t_start, t_end) -> list[str]: ...
    def compute_takeoff_landing_stats(self, t_start, t_end) -> str: ...
    def compute_fitted_circle(self, lon_field: str, lat_field: str, t_start, t_end) -> float: ...
