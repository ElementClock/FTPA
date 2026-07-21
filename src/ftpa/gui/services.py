import os
from pathlib import Path

import numpy as np
import pandas as pd

from ..main import DEFAULT_EXCEL_FILE, DEFAULT_TXT_FILE, resolve_path
from ..data_loader import param_extract, extract_time
from ..label_map import LabelMap
from ..computing import compute_total_weight_rel_cg
from ..constants import BASE_WEIGHT, BASE_REL_CG, BASE_OIL
from ..utils import column_to_field_name


def build_analysis_preview(data_path=None, excel_path=None, selected_signals=None):
    """Build a lightweight preview structure for the GUI to display."""
    data_path = resolve_path(data_path, DEFAULT_TXT_FILE)
    excel_path = resolve_path(excel_path, DEFAULT_EXCEL_FILE)

    preview_df = pd.DataFrame({
        "TIME": ["00:00:00:000", "00:00:01:000", "00:00:02:000"],
        "signal_a": [0.0, 1.0, 2.0],
        "signal_b": [1.0, 2.0, 3.0],
        "signal_c": [0.5, 1.5, 2.5],
    })

    if os.path.exists(data_path) and data_path.lower().endswith((".txt", ".csv", ".tsv", ".dat")):
        if data_path.lower().endswith(".txt"):
            preview_df = pd.read_csv(data_path, sep="\t", nrows=20, dtype={0: str}, low_memory=False)
        else:
            preview_df = pd.read_csv(data_path, sep=",", nrows=20, dtype={0: str}, low_memory=False)
        if preview_df.empty:
            preview_df = pd.DataFrame({
                "TIME": ["00:00:00:000"],
                "signal_a": [0.0],
                "signal_b": [1.0],
                "signal_c": [0.5],
            })

    selected = selected_signals or list(preview_df.columns[:3])
    available = [col for col in selected if col in preview_df.columns]
    if not available:
        available = list(preview_df.columns[:2])

    summary_lines = [
        f"数据文件：{data_path}",
        f"样本行数：{len(preview_df)}",
        f"样本列数：{len(preview_df.columns)}",
        f"已选择信号：{', '.join(available)}",
    ]

    plot_series = []
    plot_labels = []
    for name in available:
        try:
            series = pd.to_numeric(preview_df[name], errors="coerce").fillna(0.0).to_numpy()
        except Exception:
            series = np.zeros(len(preview_df), dtype=float)
        plot_series.append(series)
        plot_labels.append(name)

    return {
        "row_count": len(preview_df),
        "column_count": len(preview_df.columns),
        "summary_lines": summary_lines,
        "plot_series": plot_series,
        "plot_labels": plot_labels,
        "data_frame": preview_df,
    }


def get_data_fields(data_path=None):
    data_path = resolve_path(data_path, DEFAULT_TXT_FILE)
    if os.path.exists(data_path):
        try:
            with open(data_path, "r", encoding="utf-8") as fh:
                header = fh.readline().strip()
            fields = [item for item in header.split("\t") if item]
            return fields
        except Exception:
            pass

    return [
        "TIME",
        "无线电高度表决值",
        "指示空速表决值",
        "俯仰角表决值",
        "法向过载_I1",
        "总重",
        "相对重心",
    ]


def run_analysis(data_path=None, excel_path=None, selected_signals=None):
    data_path = resolve_path(data_path, DEFAULT_TXT_FILE)
    excel_path = resolve_path(excel_path, DEFAULT_EXCEL_FILE)

    if not os.path.exists(data_path):
        preview = build_analysis_preview(
            data_path=data_path,
            excel_path=excel_path,
            selected_signals=selected_signals,
        )
        preview["summary_lines"].insert(0, f"数据文件不存在: {data_path}")
        return preview

    data = param_extract(data_path)
    data["TIME"] = extract_time(data_path)

    lm = None
    if os.path.exists(excel_path):
        try:
            lm = LabelMap(excel_path)
        except Exception:
            lm = None

    try:
        if lm is not None:
            oil_lout = data[lm.get_var_name("Ⅰ号油箱油量")]
            oil_lin = data[lm.get_var_name("Ⅱ号油箱油量")]
            oil_rin = data[lm.get_var_name("Ⅲ号油箱油量")]
            oil_rout = data[lm.get_var_name("Ⅳ号油箱油量")]
            total_weight, rel_cg = compute_total_weight_rel_cg(
                oil_lout,
                oil_lin,
                oil_rin,
                oil_rout,
                BASE_WEIGHT,
                BASE_REL_CG,
                BASE_OIL,
            )
            data["totalWeight"] = total_weight
            data["relCg"] = rel_cg
            lm.add("totalWeight", "总重")
            lm.add("relCg", "相对重心")
    except Exception as e:
        print(f"GUI: 重量重心计算跳过: {e}")

    selected_signals = selected_signals or []
    chosen = []
    for signal in selected_signals:
        field_name = None
        if signal in data:
            field_name = signal
        elif lm is not None:
            field_name = lm.get_var_name(signal)
        if field_name is None or field_name not in data:
            field_name = column_to_field_name(signal)
        if field_name in data:
            label = lm.get_label(field_name) if lm is not None else signal
            chosen.append((field_name, label))

    if not chosen:
        default_choices = [
            "无线电高度表决值",
            "指示空速表决值",
            "俯仰角表决值",
            "法向过载_I1",
        ]
        for choice in default_choices:
            if lm is not None:
                field_name = lm.get_var_name(choice)
                if field_name in data:
                    chosen.append((field_name, choice))
        if not chosen:
            for key in data.keys():
                if key != "TIME":
                    chosen.append((key, key))
                if len(chosen) >= 3:
                    break

    plot_series = []
    plot_labels = []
    for field_name, label in chosen:
        series = data[field_name]
        if not isinstance(series, np.ndarray):
            series = np.asarray(series)
        plot_series.append(series)
        plot_labels.append(label)

    summary_lines = [
        f"数据文件：{data_path}",
        f"标签文件：{excel_path if os.path.exists(excel_path) else '未找到'}",
        f"样本行数：{len(data['TIME'])}",
        f"样本列数：{len(data)}",
        f"分析信号：{', '.join(plot_labels)}",
    ]

    return {
        "row_count": len(data["TIME"]),
        "column_count": len(data),
        "summary_lines": summary_lines,
        "plot_series": plot_series,
        "plot_labels": plot_labels,
        "data_frame": None,
    }
