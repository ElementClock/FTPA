"""字段名解析与标签映射服务。

从 services.py 迁移，零行为变更。
"""

from __future__ import annotations

import logging

from ...data.label_map import LabelMap
from ...utils.strings import column_to_field_name

logger = logging.getLogger(__name__)


class FieldResolver:
    """字段名解析与标签映射。

    职责：
    - 枚举数据字段名
    - 将字段名映射为中文标签（通过 LabelMap）
    - 将中文标签/别名反解析为字段名
    """

    def __init__(self, data: dict, lm: LabelMap | None = None):
        self._data = data
        self._lm = lm
        self._label_cache: dict[str, str] | None = None

    def update(self, data: dict, lm: LabelMap | None = None) -> None:
        """数据加载后更新引用并清除缓存。"""
        self._data = data
        self._lm = lm
        self._label_cache = None

    def clear(self) -> None:
        """卸载时清空所有状态。"""
        self._data = {}
        self._lm = None
        self._label_cache = None

    def get_field_names(self) -> list[str]:
        """所有字段名（不包括 TIME 和元数据键）。"""
        if not self._data:
            return []
        _meta_keys = {"TIME", "filename", "_name_mapping"}
        return [k for k in self._data if k not in _meta_keys]

    def get_field_labels(self) -> dict[str, str]:
        """字段名 -> 中文标签（惰性缓存）。"""
        if self._label_cache is not None:
            return self._label_cache
        result: dict[str, str] = {}
        for field in self.get_field_names():
            if self._lm is not None:
                try:
                    result[field] = self._lm.get_label(field)
                except Exception:
                    logger.debug("标签获取失败，回退到字段名: field=%s", field, exc_info=True)
                    result[field] = field
            else:
                result[field] = field
        self._label_cache = result
        return result

    def get_label(self, field_name: str) -> str:
        """获取单个字段的中文标签。"""
        return self.get_field_labels().get(field_name, field_name)

    def get_field_labels_with_units(self) -> dict[str, str]:
        """字段名 -> 带单位的中文标签（用于 GUI 参数树显示）。

        例如：``高度_G1 (m)``；无单位时只返回中文标签。
        """
        result: dict[str, str] = {}
        for field, label in self.get_field_labels().items():
            unit = self._lm.get_unit(field) if self._lm is not None else None
            result[field] = f"{label} ({unit})" if unit else label
        return result

    def get_all_field_labels_with_units(self) -> tuple[dict[str, str], set[str]]:
        """返回完整参数库标签和当前数据可用字段。

        返回值：
            (all_labels, available_fields)
            - all_labels: 映射参数库（参数名.csv）+ 当前数据字段的“字段名 -> 带单位标签”
            - available_fields: 当前数据中实际存在的字段名集合
        """
        available_fields = set(self.get_field_names())
        result = self.get_field_labels_with_units()

        # 完整参数库来自已加载的 LabelMap（单一 CSV 输入）；无映射时无库条目
        if self._lm is not None:
            for field in self._lm.list_fields():
                if field in result:
                    continue
                unit = self._lm.get_unit(field)
                label = self._lm.get_label(field)
                result[field] = f"{label} ({unit})" if unit else label

        return result, available_fields

    def resolve_field(self, signal_id: str) -> str | None:
        """将中文标签或字段名解析为 data 中的字段名。"""
        if signal_id in self._data:
            return signal_id
        if self._lm is not None:
            f = self._lm.get_var_name(signal_id)
            if f and f in self._data:
                return f
        cf = column_to_field_name(signal_id)
        if cf != signal_id and cf in self._data:
            return cf
        return None
