"""数据查询服务 —— 封装 DataContext 内部属性的只读访问。

将 ctx.data / ctx.time_sec 等直接属性访问替换为方法调用，
遵循迪米特法则（LoD），降低模块间的属性耦合。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np

from ...data.label_map import LabelMap
from .field_resolver import FieldResolver

if TYPE_CHECKING:
    pass


class DataQueryService:
    """数据查询服务 —— 将对 DataContext 内部属性的直接访问封装为方法。

    所有只读数据访问均通过此服务，避免外部模块直接读取 ctx.data / ctx.time_sec 等。
    """

    def __init__(
        self,
        data: dict,
        time_vec: np.ndarray | None,
        time_sec: np.ndarray | None,
        lm: LabelMap | None,
        field_resolver: FieldResolver,
        data_path: str = "",
        excel_path: str = "",
        source_type: str = "",
    ):
        self._data = data
        self._time_vec = time_vec
        self._time_sec = time_sec
        self._lm = lm
        self._field_resolver = field_resolver
        self._data_path = data_path
        self._excel_path = excel_path
        self._source_type = source_type

    def update(
        self,
        data: dict,
        time_vec: np.ndarray | None,
        time_sec: np.ndarray | None,
        lm: LabelMap | None,
        field_resolver: FieldResolver,
        data_path: str = "",
        excel_path: str = "",
        source_type: str = "",
    ) -> None:
        """数据加载后更新所有引用。"""
        self._data = data
        self._time_vec = time_vec
        self._time_sec = time_sec
        self._lm = lm
        self._field_resolver = field_resolver
        self._data_path = data_path
        self._excel_path = excel_path
        self._source_type = source_type

    def clear(self) -> None:
        """卸载时清空所有状态。"""
        self._data = {}
        self._time_vec = None
        self._time_sec = None
        self._lm = None
        self._data_path = ""
        self._excel_path = ""
        self._source_type = ""

    # -- 字段管理（委托给 FieldResolver）--

    def get_field_names(self) -> list[str]:
        """所有字段名（不包括 TIME 和元数据键）。"""
        return self._field_resolver.get_field_names()

    def get_field_labels(self) -> dict[str, str]:
        """字段名 → 中文标签（惰性缓存）。"""
        return self._field_resolver.get_field_labels()

    def get_label(self, field_name: str) -> str:
        """获取单个字段的中文标签。"""
        return self._field_resolver.get_label(field_name)

    def resolve_field(self, signal_id: str) -> str | None:
        """将中文标签或字段名解析为 data 中的字段名。"""
        return self._field_resolver.resolve_field(signal_id)

    # -- 元信息查询 --

    def get_row_count(self) -> int:
        """数据行数。"""
        return len(self._time_vec) if self._time_vec is not None else 0

    def get_column_count(self) -> int:
        """信号列数（排除 TIME/filename 等元数据键）。"""
        return len(self._field_resolver.get_field_names())

    def get_time_range_sec(self) -> tuple[float, float]:
        """时间范围（秒）。"""
        if self._time_sec is None or len(self._time_sec) < 2:
            return 0.0, 0.0
        return float(self._time_sec[0]), float(self._time_sec[-1])

    # -- 安全数据访问（替代直接属性访问）--

    def get_signal_data(self, field_name: str) -> np.ndarray | None:
        """获取指定字段的信号数据，不存在时返回 None。"""
        return self._data.get(field_name)

    def get_time_sec(self) -> np.ndarray | None:
        """获取时间秒数组。"""
        return self._time_sec

    def get_time_vec(self) -> np.ndarray | None:
        """获取原始时间向量（timedelta64）。"""
        return self._time_vec

    def get_data_path(self) -> str:
        """获取当前加载的数据文件路径。"""
        return self._data_path

    def get_excel_path(self) -> str:
        """获取当前加载的映射表文件路径。"""
        return self._excel_path

    def get_source_type(self) -> str:
        """获取数据源类型（"txt" | "csv" | ""）。"""
        return self._source_type

    def get_label_map(self) -> LabelMap | None:
        """获取当前 LabelMap。"""
        return self._lm

    def has_data(self) -> bool:
        """是否有已加载的数据。"""
        return bool(self._data) and self._time_sec is not None
