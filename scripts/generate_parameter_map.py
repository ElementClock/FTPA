"""根据 参数名.xlsx 生成 src/ftpa/data/parameter_map.py。

生成内容：
- PARAMETER_LABELS: 原始名称/字段名 -> 中文显示名（重复标签自动加编号后缀）
- PARAMETER_UNITS: 原始名称/字段名 -> 单位（无单位时为 None）
- DISPLAY_LABEL_TO_FIELDS: 中文显示名 -> 字段名列表
- ORIGINAL_LABEL_TO_FIELDS: Excel 原始中文标签 -> 字段名列表（跨数据源对照表）
- DUPLICATE_LABELS: 原始中文标签 -> 编号后的显示名列表（重复标签对照表）

输入文件按序在以下位置查找，取第一个存在的：
    data/参数名.xlsx → testdata/参数名.xlsx → src/ftpa/data/参数名.xlsx

用法：
    python scripts/generate_parameter_map.py
"""

from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXCEL_CANDIDATE_DIRS = [
    PROJECT_ROOT / "data",
    PROJECT_ROOT / "testdata",
    PROJECT_ROOT / "src" / "ftpa" / "data",
]
OUTPUT_PATH = PROJECT_ROOT / "src" / "ftpa" / "data" / "parameter_map.py"


def _resolve_excel_path() -> Path:
    """按候选目录顺序查找 参数名.xlsx，返回第一个存在的路径。"""
    for d in EXCEL_CANDIDATE_DIRS:
        p = d / "参数名.xlsx"
        if p.is_file():
            return p
    searched = "\n  ".join(str(d / "参数名.xlsx") for d in EXCEL_CANDIDATE_DIRS)
    raise FileNotFoundError(f"未找到 参数名.xlsx，已搜索以下位置：\n  {searched}")


def _clean(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() == "nan":
        return None
    return text


def generate() -> str:
    df = pd.read_excel(_resolve_excel_path())
    if df.shape[1] < 2:
        raise ValueError("Excel 至少需要两列：原始名称、中文名称")

    raw_orig = df.iloc[:, 0].astype(str).str.strip().tolist()
    raw_label = df.iloc[:, 1].astype(str).str.strip().tolist()
    raw_unit = [_clean(v) for v in df.iloc[:, 2].tolist()] if df.shape[1] >= 3 else [None] * len(df)

    rows: list[tuple[str, str, str | None]] = []
    for orig, label, unit in zip(raw_orig, raw_label, raw_unit):
        if not orig or orig.lower() == "nan":
            continue
        if not label or label.lower() == "nan":
            continue
        rows.append((orig, label, unit))

    label_counts = Counter(label for _, label, _ in rows)
    seen: dict[str, int] = defaultdict(int)

    parameter_labels: dict[str, str] = {}
    parameter_units: dict[str, str | None] = {}
    display_label_to_fields: dict[str, list[str]] = defaultdict(list)
    original_label_to_fields: dict[str, list[str]] = defaultdict(list)
    duplicate_labels: dict[str, list[str]] = defaultdict(list)

    for orig, label, unit in rows:
        seen[label] += 1
        if label_counts[label] > 1:
            display_label = f"{label}_{seen[label]}"
            duplicate_labels[label].append(display_label)
        else:
            display_label = label

        parameter_labels[orig] = display_label
        parameter_units[orig] = unit
        display_label_to_fields[display_label].append(orig)
        original_label_to_fields[label].append(orig)

    lines = [
        '"""',
        "FTPA 参数映射静态数据。",
        "",
        "由 scripts/generate_parameter_map.py 根据 参数名.xlsx（按 data/testdata/src 回退查找）自动生成，",
        "请勿手工编辑；如需更新请重新运行生成脚本。",
        '"""',
        "",
        "from __future__ import annotations",
        "",
        "PARAMETER_LABELS: dict[str, str] = {",
    ]
    for orig in parameter_labels:
        lines.append(f"    {orig!r}: {parameter_labels[orig]!r},")
    lines.extend(["}", "", "PARAMETER_UNITS: dict[str, str | None] = {"])
    for orig in parameter_units:
        lines.append(f"    {orig!r}: {parameter_units[orig]!r},")
    lines.extend(["}", "", "DISPLAY_LABEL_TO_FIELDS: dict[str, list[str]] = {"])
    for label in sorted(display_label_to_fields):
        fields = display_label_to_fields[label]
        lines.append(f"    {label!r}: {fields!r},")
    lines.extend(["}", "", "ORIGINAL_LABEL_TO_FIELDS: dict[str, list[str]] = {"])
    for label in sorted(original_label_to_fields):
        fields = original_label_to_fields[label]
        lines.append(f"    {label!r}: {fields!r},")
    lines.extend(["}", "", "DUPLICATE_LABELS: dict[str, list[str]] = {"])
    for label in sorted(duplicate_labels):
        lines.append(f"    {label!r}: {duplicate_labels[label]!r},")
    lines.extend(["}", ""])

    return "\n".join(lines)


def main() -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(generate(), encoding="utf-8")
    print(f"已生成: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
