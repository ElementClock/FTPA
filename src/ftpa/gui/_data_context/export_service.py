"""数据导出服务 —— 从 DataContext 导出职责提取。

封装 export_data / export_statistics / generate_summary，
使 DataContext 不再直接依赖 exporter 模块。
"""

from __future__ import annotations

from ...data.exporter import (
    export_data,
    export_statistics,
    generate_data_summary,
)


class DataExportService:
    """数据导出服务。"""

    def __init__(self, data: dict):
        self._data = data

    def update(self, data: dict) -> None:
        """数据加载后更新引用。"""
        self._data = data

    def clear(self) -> None:
        """卸载时清空引用。"""
        self._data = {}

    def export_data(self, output_path: str, fmt: str, compression: str | None = None) -> str:
        """导出数据到指定格式。"""
        return export_data(self._data, output_path, fmt, compression=compression)

    def export_statistics(self, stats: list, output_path: str, fmt: str = "csv") -> str:
        """导出统计结果。"""
        return export_statistics(stats, output_path, fmt)

    def generate_summary(self) -> dict:
        """生成数据摘要。"""
        return generate_data_summary(self._data)
