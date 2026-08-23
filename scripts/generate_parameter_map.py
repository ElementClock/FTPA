"""根据 参数名.xlsx 生成 src/ftpa/data/参数名.csv（参数映射的唯一输入）。

输入：厂商 参数名.xlsx（第 1 列=原始名称，第 2 列=中文名称，可选第 3 列=单位；可带表头）
输出：src/ftpa/data/参数名.csv（UTF-8+BOM，表头 `原始名称,中文名称,单位`）

单位列规则（按优先级）：
1. xlsx 自带第 3 列 → 直接使用
2. 已存在 参数名.csv → 按字段名结转已有单位（避免重新生成时丢失手工维护的单位）
3. 都没有 → 空

定位：本脚本为 xlsx→csv 合并桥。供应商仍以 xlsx 交付时重跑本脚本即可：
- 厂商 xlsx 行的原始名称/中文标签为权威（按字段名覆盖），单位列按 xlsx 自带 / 结转 / 空。
- 已存在 参数名.csv 中 xlsx 没有的行（手工维护或脚本补录）保持不变，避免丢失。

用法：
    python scripts/generate_parameter_map.py
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXCEL_CANDIDATE_DIRS = [
    PROJECT_ROOT / "data",
    PROJECT_ROOT / "testdata",
    PROJECT_ROOT / "src" / "ftpa" / "data",
]
OUTPUT_PATH = PROJECT_ROOT / "src" / "ftpa" / "data" / "参数名.csv"
CSV_HEADER = ["原始名称", "中文名称", "单位"]


def _resolve_excel_path() -> Path:
    """按候选目录顺序查找 参数名.xlsx，返回第一个存在的路径。"""
    for d in EXCEL_CANDIDATE_DIRS:
        p = d / "参数名.xlsx"
        if p.is_file():
            return p
    searched = "\n  ".join(str(d / "参数名.xlsx") for d in EXCEL_CANDIDATE_DIRS)
    raise FileNotFoundError(f"未找到 参数名.xlsx，已搜索以下位置：\n  {searched}")


def _canonical_field(orig: str) -> str:
    """原始名称归一化为字段名（- → _，保留字母/数字/下划线），用于跨文件单位结转。"""
    cleaned = "".join(c if c.isalnum() or c == "_" else "_" for c in orig.replace("-", "_"))
    if cleaned and cleaned[0].isdigit():
        cleaned = "x" + cleaned
    return cleaned


def _load_existing_units() -> dict[str, str]:
    """从已存在的 参数名.csv 读取「字段名 → 非空单位」，供重新生成时结转。"""
    units: dict[str, str] = {}
    for orig, _, unit in _read_existing_rows():
        if unit and unit.lower() not in ("nan", "none"):
            units[_canonical_field(orig)] = unit
    return units


def _read_existing_rows() -> list[tuple[str, str, str]]:
    """读取已存在 参数名.csv 的全部行（原始名称, 中文名称, 单位）。"""
    if not OUTPUT_PATH.is_file():
        return []
    existing = pd.read_csv(OUTPUT_PATH, encoding="utf-8-sig", dtype=str)
    rows: list[tuple[str, str, str]] = []
    for i in range(len(existing)):
        orig = str(existing.iloc[i, 0]).strip()
        label = str(existing.iloc[i, 1]).strip()
        unit = str(existing.iloc[i, 2]).strip() if existing.shape[1] >= 3 and pd.notna(existing.iloc[i, 2]) else ""
        if not orig or orig.lower() == "nan":
            continue
        rows.append((orig, label, unit))
    return rows


def main() -> None:
    df = pd.read_excel(_resolve_excel_path(), dtype=str)
    if df.shape[1] < 2:
        raise ValueError("Excel 至少需要两列：原始名称、中文名称")

    existing_units = _load_existing_units()
    existing_by_field = {_canonical_field(o): (o, l, u) for o, l, u in _read_existing_rows()}

    # 合并：厂商 xlsx 行为准（按字段名对比），已存在但 xlsx 没有的行保留，避免丢失手工维护
    merged: dict[str, tuple[str, str, str]] = {}
    for i in range(len(df)):
        orig = str(df.iloc[i, 0]).strip()
        label = str(df.iloc[i, 1]).strip()
        if not orig or orig.lower() == "nan":
            continue
        if not label or label.lower() == "nan":
            continue

        # 单位：xlsx 自带第 3 列优先，否则结转已有，否则空
        unit = ""
        if df.shape[1] >= 3 and pd.notna(df.iloc[i, 2]):
            unit = str(df.iloc[i, 2]).strip()
        if not unit or unit.lower() in ("nan", "none"):
            unit = existing_units.get(_canonical_field(orig), "")

        merged[_canonical_field(orig)] = (orig, label, unit)

    for cf, (orig, label, unit) in existing_by_field.items():
        if cf not in merged:
            merged[cf] = (orig, label, unit)

    out_df = pd.DataFrame(sorted(merged.values(), key=lambda r: r[0]), columns=CSV_HEADER)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    out_df.to_csv(OUTPUT_PATH, index=False, encoding="utf-8-sig")
    print(f"已生成: {OUTPUT_PATH}（合并后数据行数: {len(out_df)}）")


if __name__ == "__main__":
    main()