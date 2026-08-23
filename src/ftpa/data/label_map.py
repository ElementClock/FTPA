"""标签映射模块
对应 MATLAB: loadLabelMap.m
从 参数名.csv（唯一输入，可维护数据文件）加载变量名与中文标签的映射关系；
文件缺失或解析失败时降级为空映射（标签回退为原名称）。
"""

from __future__ import annotations

import logging
import os

import pandas as pd

from ..utils.paths import resolve_mapping_path
from ..utils.strings import make_valid_name

logger = logging.getLogger(__name__)


class LabelMap:
    """变量名与中文标签的双向映射管理器。

    唯一输入为 ``参数名.csv``（原始名称, 中文名称, 单位），
    构造时未显式传路径则自动经 ``resolve_mapping_path()`` 发现默认文件。

    重复中文标签会生成编号后缀（如 ``1发油门_1`` / ``1发油门_2``），
    并保留“原始中文标签 -> 字段名列表”的对照表供后续查找。
    """

    def __init__(self, csv_file: str | None = None):
        self._init_tables()

        path = self._resolve_path(csv_file)
        if path is not None:
            self._load_csv(path)
        else:
            logger.warning("映射文件未找到，使用空映射（标签回退原名称）")

    # ── 初始化 ──

    def _resolve_path(self, csv_file: str | None) -> str | None:
        """显式路径存在则用之；否则取默认映射文件，存在才返回。"""
        if csv_file:
            return csv_file if os.path.exists(csv_file) else None
        default = resolve_mapping_path()
        return default if os.path.exists(default) else None

    def _init_tables(self) -> None:
        self._orig2label: dict[str, str] = {}
        self._field2label: dict[str, str] = {}
        self._orig2unit: dict[str, str | None] = {}
        self._field2unit: dict[str, str | None] = {}
        self._label2orig: dict[str, str] = {}
        self._label2field: dict[str, str] = {}
        self._field2orig: dict[str, str] = {}
        self._display_label2fields: dict[str, list[str]] = {}
        self._original_label2fields: dict[str, list[str]] = {}
        self._duplicate_labels: dict[str, list[str]] = {}
        self._orig_list: list[str] = []
        self._field_list: list[str] = []
        self._label_list: list[str] = []
        self._unit_list: list[str | None] = []
        # 实际加载来源的行（list_all* 仅列这些行）
        self._loaded = False
        self._loaded_origs: list[str] = []
        self._loaded_fields: list[str] = []
        self._loaded_labels: list[str] = []
        self._loaded_units: list[str | None] = []

    def _read_csv(self, csv_file: str) -> pd.DataFrame:
        """读取映射 CSV：BOM→utf-8-sig，否则 chardet 检测，GB18030 回退。"""
        with open(csv_file, "rb") as f:
            raw = f.read()
        if raw[:3] == b"\xef\xbb\xbf":
            encoding = "utf-8-sig"
        else:
            import chardet

            guess = chardet.detect(raw[:8192])
            encoding = guess.get("encoding") or "utf-8"
        try:
            return pd.read_csv(csv_file, header=0, dtype=str, encoding=encoding)
        except (UnicodeDecodeError, ValueError):
            return pd.read_csv(csv_file, header=0, dtype=str, encoding="gb18030")

    def _load_csv(self, csv_file: str) -> None:
        """从 参数名.csv 加载映射（唯一输入）。"""
        try:
            df = self._read_csv(csv_file)
        except Exception as e:
            logger.warning("映射文件解析失败，使用空映射: %s — %s", csv_file, e)
            return
        if df.shape[1] < 2:
            raise ValueError("映射 CSV 至少需要两列：原始名称、中文名称")

        orig_raw = df.iloc[:, 0].astype(str).str.strip().tolist()
        label_raw = df.iloc[:, 1].astype(str).str.strip().tolist()
        unit_raw = (
            [self._clean_unit(v) for v in df.iloc[:, 2].tolist()]
            if df.shape[1] >= 3
            else [None] * len(df)
        )

        # 先统计每个中文标签出现次数，用于生成编号后缀
        from collections import Counter

        label_counts = Counter(label for label in label_raw if label and label.lower() != "nan")
        seen: dict[str, int] = {}
        new_duplicates: list[tuple[str, str, str]] = []  # (label, display_label, field)

        loaded_origs: list[str] = []
        loaded_fields: list[str] = []
        loaded_labels: list[str] = []
        loaded_units: list[str | None] = []

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
                    new_duplicates.append((label, display_label, field))
            else:
                display_label = label

            self._upsert_mapping(
                orig=orig,
                field=field,
                display_label=display_label,
                original_label=label,
                unit=unit,
            )
            loaded_origs.append(orig)
            loaded_fields.append(field)
            loaded_labels.append(display_label)
            loaded_units.append(unit)

        self._loaded = True
        self._loaded_origs = loaded_origs
        self._loaded_fields = loaded_fields
        self._loaded_labels = loaded_labels
        self._loaded_units = loaded_units

        if new_duplicates:
            samples = ", ".join(f"'{l}'→'{d}'" for l, d, _ in new_duplicates[:3])
            logger.warning(
                "映射含 %d 个重复中文标签，已生成编号后缀（如 %s …）",
                len(new_duplicates), samples,
            )

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

    def list_fields(self) -> list[str]:
        """返回全部字段名列表（完整参数库用）。"""
        return list(self._field_list)

    def _list_source(self):
        """返回 list_all* 使用的列表元组（加载来源行）。"""
        if self._loaded:
            return (
                self._loaded_origs,
                self._loaded_fields,
                self._loaded_labels,
                self._loaded_units,
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