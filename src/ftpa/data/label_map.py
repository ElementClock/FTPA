"""
标签映射模块
对应 MATLAB: loadLabelMap.m
从 Excel 加载变量名与中文标签的映射关系；Excel 缺失时回退到静态映射。
"""

from __future__ import annotations

import logging
import os

import pandas as pd

from ..utils.strings import make_valid_name
from .parameter_map import (
    DISPLAY_LABEL_TO_FIELDS,
    DUPLICATE_LABELS,
    ORIGINAL_LABEL_TO_FIELDS,
    PARAMETER_LABELS,
    PARAMETER_UNITS,
)

logger = logging.getLogger(__name__)


class LabelMap:
    """
    变量名与中文标签的双向映射管理器。

    数据来源优先级：
    1. 静态映射 `parameter_map.py`（由 `data/参数名.xlsx` 生成）；
    2. 运行时传入的 Excel 文件（存在时覆盖/补充静态映射）。

    重复中文标签会生成编号后缀（如 ``1发油门_1`` / ``1发油门_2``），
    并保留“原始中文标签 -> 字段名列表”的对照表供后续查找。
    """

    def __init__(self, excel_file: str | None = None):
        self._load_static()

        if excel_file:
            self._load_excel(excel_file)

    # ── 初始化 ──

    def _load_static(self) -> None:
        """从静态映射模块初始化。"""
        self._orig2label: dict[str, str] = dict(PARAMETER_LABELS)
        self._field2label: dict[str, str] = dict(PARAMETER_LABELS)
        self._orig2unit: dict[str, str | None] = dict(PARAMETER_UNITS)
        self._field2unit: dict[str, str | None] = dict(PARAMETER_UNITS)

        self._label2orig: dict[str, str] = {}
        self._label2field: dict[str, str] = {}
        self._field2orig: dict[str, str] = {}
        self._display_label2fields: dict[str, list[str]] = {
            k: list(v) for k, v in DISPLAY_LABEL_TO_FIELDS.items()
        }
        self._original_label2fields: dict[str, list[str]] = {
            k: list(v) for k, v in ORIGINAL_LABEL_TO_FIELDS.items()
        }
        self._duplicate_labels: dict[str, list[str]] = {
            k: list(v) for k, v in DUPLICATE_LABELS.items()
        }

        for field, label in self._field2label.items():
            self._label2field[label] = field
            self._label2orig[label] = field
            self._field2orig[field] = field

        self._orig_list = list(self._orig2label.keys())
        self._field_list = list(self._field2label.keys())
        self._label_list = list(self._field2label.values())
        self._unit_list = [self._field2unit.get(f) for f in self._field_list]

        # Excel 加载后用于保持 list_all() 的旧语义：仅列出 Excel 中的行
        self._excel_loaded = False
        self._excel_orig_list: list[str] = []
        self._excel_field_list: list[str] = []
        self._excel_label_list: list[str] = []
        self._excel_unit_list: list[str | None] = []

    def _load_excel(self, excel_file: str) -> None:
        """从 Excel 文件加载映射并覆盖/补充静态映射。"""
        if not os.path.exists(excel_file):
            logger.warning("映射表文件不存在，使用静态映射: %s", excel_file)
            return

        df = pd.read_excel(excel_file)
        if df.shape[1] < 2:
            raise ValueError("Excel 文件至少需要两列：原始名称、中文名称")

        orig_raw = df.iloc[:, 0].astype(str).str.strip().tolist()
        label_raw = df.iloc[:, 1].astype(str).str.strip().tolist()
        unit_raw = (
            [self._clean_unit(v) for v in df.iloc[:, 2].tolist()]
            if df.shape[1] >= 3
            else [None] * len(df)
        )

        # 先统计 Excel 内每个中文标签出现次数，用于生成编号后缀
        from collections import Counter

        label_counts = Counter(label for label in label_raw if label and label.lower() != "nan")
        seen: dict[str, int] = {}

        excel_origs: list[str] = []
        excel_fields: list[str] = []
        excel_labels: list[str] = []
        excel_units: list[str | None] = []

        for orig, label, unit in zip(orig_raw, label_raw, unit_raw):
            if not orig or orig.lower() == "nan":
                continue
            if not label or label.lower() == "nan":
                continue

            field = make_valid_name(orig.replace("-", "_"))

            # 重复标签：生成编号后缀
            if label_counts[label] > 1:
                seen[label] = seen.get(label, 0) + 1
                display_label = f"{label}_{seen[label]}"
                if label not in self._duplicate_labels:
                    self._duplicate_labels[label] = []
                if display_label not in self._duplicate_labels[label]:
                    self._duplicate_labels[label].append(display_label)
                logger.warning(
                    "检测到重复中文标签 '%s'，已生成编号标签 '%s'（字段: %s）",
                    label, display_label, field,
                )
            else:
                display_label = label

            self._upsert_mapping(
                orig=orig,
                field=field,
                display_label=display_label,
                original_label=label,
                unit=unit,
            )
            excel_origs.append(orig)
            excel_fields.append(field)
            excel_labels.append(display_label)
            excel_units.append(unit)

        self._excel_loaded = True
        self._excel_orig_list = excel_origs
        self._excel_field_list = excel_fields
        self._excel_label_list = excel_labels
        self._excel_unit_list = excel_units

    @staticmethod
    def _clean_unit(value: object) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        if not text or text.lower() == "nan":
            return None
        return text

    def _upsert_mapping(
        self,
        *,
        orig: str,
        field: str,
        display_label: str,
        original_label: str,
        unit: str | None,
    ) -> None:
        """将一条映射写入所有内部表。"""
        self._orig2label[orig] = display_label
        self._field2label[field] = display_label
        self._orig2unit[orig] = unit
        self._field2unit[field] = unit
        self._field2orig[field] = orig

        self._label2orig[display_label] = orig
        self._label2field[display_label] = field
        self._display_label2fields.setdefault(display_label, [])
        if field not in self._display_label2fields[display_label]:
            self._display_label2fields[display_label].append(field)

        self._original_label2fields.setdefault(original_label, [])
        if field not in self._original_label2fields[original_label]:
            self._original_label2fields[original_label].append(field)

        if field in self._field_list:
            idx = self._field_list.index(field)
            self._label_list[idx] = display_label
            self._unit_list[idx] = unit
        else:
            self._field_list.append(field)
            self._orig_list.append(orig)
            self._label_list.append(display_label)
            self._unit_list.append(unit)

    # ── 查询：字段/原始名 → 标签 ──

    def get_label(self, var_name: str) -> str:
        """
        变量名 → 中文标签（重复标签返回带编号后缀的显示名）。

        参数:
            var_name: 变量名（可以是原始名或字段名）

        返回:
            中文标签，若未找到则返回原名称
        """
        if var_name in self._field2label:
            return self._field2label[var_name]
        if var_name in self._orig2label:
            return self._orig2label[var_name]
        logger.warning('变量 "%s" 未在映射表中找到，返回原名称。', var_name)
        return var_name

    def get_unit(self, field_or_label: str) -> str | None:
        """获取字段或标签对应的单位；未找到时返回 None。"""
        if field_or_label in self._field2unit:
            return self._field2unit[field_or_label]
        if field_or_label in self._label2field:
            return self._field2unit.get(self._label2field[field_or_label])
        if field_or_label in self._original_label2fields:
            fields = self._original_label2fields[field_or_label]
            if fields:
                return self._field2unit.get(fields[-1])
        return None

    # ── 查询：标签 → 字段/原始名 ──

    def get_var_name(self, label: str, mode: str = "field") -> str:
        """
        中文标签 → 变量名。

        - 优先匹配带编号后缀的显示名；
        - 若传入原始重复标签，则发出警告并按原行为返回最后一个字段。

        参数:
            label: 中文标签
            mode: 'field' 返回字段名（默认），'original' 返回原始名

        返回:
            变量名，若未找到则返回空字符串
        """
        if mode not in ("field", "original"):
            raise ValueError("mode 必须为 'original' 或 'field'")

        if mode == "field":
            if label in self._label2field:
                return self._label2field[label]
        else:
            if label in self._label2orig:
                return self._label2orig[label]

        fields = self._original_label2fields.get(label, [])
        if fields:
            if len(fields) > 1:
                logger.warning(
                    "中文标签 '%s' 对应多个数据源 %s，按原行为返回最后一个。"
                    "如需全部字段请使用 get_var_names()",
                    label, fields,
                )
            chosen = fields[-1]
            return chosen if mode == "field" else self._field2orig.get(chosen, chosen)

        logger.warning('中文标签 "%s" 未找到，返回空字符串。', label)
        return ""

    def get_var_names(self, label: str) -> list[str]:
        """返回中文标签对应的全部字段名（含原始重复标签的跨数据源对照）。"""
        if label in self._display_label2fields:
            return list(self._display_label2fields[label])
        if label in self._original_label2fields:
            return list(self._original_label2fields[label])
        return []

    def get_duplicate_labels(self) -> dict[str, list[str]]:
        """返回重复中文标签 -> 编号后显示名列表的对照表。"""
        return {k: list(v) for k, v in self._duplicate_labels.items()}

    # ── 列表输出 ──

    def _list_source(self):
        """返回 list_all* 使用的列表元组。Excel 加载后保持旧语义只列 Excel 行。"""
        if self._excel_loaded:
            return (
                self._excel_orig_list,
                self._excel_field_list,
                self._excel_label_list,
                self._excel_unit_list,
            )
        return self._orig_list, self._field_list, self._label_list, self._unit_list

    def list_all(self) -> pd.DataFrame:
        """
        列出所有映射关系。

        返回:
            DataFrame，包含三列：原始名称、结构体字段名、中文标签（含编号后缀）
        """
        orig_list, field_list, label_list, _ = self._list_source()
        return pd.DataFrame({
            "原始名称": orig_list,
            "结构体字段名": field_list,
            "中文标签": label_list,
        })

    def list_all_with_units(self) -> pd.DataFrame:
        """列出所有映射关系，额外包含单位列。"""
        orig_list, field_list, label_list, unit_list = self._list_source()
        return pd.DataFrame({
            "原始名称": orig_list,
            "结构体字段名": field_list,
            "中文标签": label_list,
            "单位": unit_list,
        })

    def list_all_print(self) -> None:
        """打印所有映射关系（格式化输出）"""
        orig_list, field_list, label_list, unit_list = self._list_source()
        print(f"{'原始名称':<35} {'结构体字段名':<35} {'中文标签':<30} {'单位'}")
        print("-" * 110)
        for orig, field, label, unit in zip(orig_list, field_list, label_list, unit_list):
            print(f"{orig:<35} {field:<35} {label:<30} {unit or ''}")

    # ── 运行时添加 ──

    def add(self, orig_name: str, label: str, unit: str | None = None) -> None:
        """
        添加新的映射关系。

        若中文标签已存在，则自动生成编号后缀并发出警告。
        """
        field_name = make_valid_name(orig_name.replace("-", "_"))
        display_label = self._make_unique_display_label(label)
        self._upsert_mapping(
            orig=orig_name,
            field=field_name,
            display_label=display_label,
            original_label=label,
            unit=unit,
        )

    def add_mapping(
        self, field_name: str, label: str, unit: str | None = None
    ) -> None:
        """运行时添加字段名→标签映射（用于 CSV 列名转换后注入）。"""
        display_label = self._make_unique_display_label(label)
        self._upsert_mapping(
            orig=field_name,
            field=field_name,
            display_label=display_label,
            original_label=label,
            unit=unit,
        )

    def _make_unique_display_label(self, label: str) -> str:
        """当标签已存在时生成带编号后缀的唯一显示名。"""
        existing = self._original_label2fields.get(label, [])
        if not existing:
            return label

        logger.warning(
            "检测到重复中文标签 '%s'，已生成编号标签（字段数: %d）",
            label, len(existing),
        )
        suffix = len(existing) + 1
        display_label = f"{label}_{suffix}"
        self._duplicate_labels.setdefault(label, [])
        if display_label not in self._duplicate_labels[label]:
            self._duplicate_labels[label].append(display_label)
        return display_label
