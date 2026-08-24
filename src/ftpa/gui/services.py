"""
DataContext —— 核心数据模型，桥接所有 CLI 模块到 GUI 面板。
单一实例，所有 Tab 共享。

所有实现已迁移到 _data_context/ 子包。
本文件仅保留重导出，确保外部模块 `from .services import DataContext` 仍可用。
"""

from ._data_context import (
    DataContext,
    FieldResolver,
    StatisticsService,
    DataQueryService,
    DataExportService,
    PlotDataService,
    DataLoader,
    TxtLoader,
    LoadResult,
)
from ._data_context.data_context import DATA_DIRS

__all__ = [
    "DataContext",
    "FieldResolver",
    "StatisticsService",
    "DataQueryService",
    "DataExportService",
    "PlotDataService",
    "DataLoader",
    "TxtLoader",
    "LoadResult",
    "DATA_DIRS",
]
