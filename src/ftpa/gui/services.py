"""
DataContext —— 核心数据模型，桥接所有 CLI 模块到 GUI 面板。
单一实例，所有 Tab 共享。
"""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np

from ..batch_processor import _add_weight_cg
from ..computing import compute_fitted_circle_radius
from ..constants import BASE_OIL, BASE_REL_CG, BASE_WEIGHT
from ..data_loader import extract_time, param_extract
from ..exporter import (
    export_data,
    export_statistics,
    generate_data_summary,
    print_data_summary,
)
from ..label_map import LabelMap
from ..statistics import (
    compute_takeoff_landing_stats,
    crossing_analysis,
    statistics_params,
)
from ..time_utils import time_to_seconds_array
from ..utils import column_to_field_name

DATA_DIRS = [
    Path(__file__).resolve().parents[2],  # project root
    Path(__file__).resolve().parents[2] / "data",
    Path(__file__).resolve().parents[2] / "data" / "raw",
    Path(__file__).resolve().parents[2] / "matlab",
]


class DataContext:
    """统一数据上下文，持有加载的数据和标签映射。"""

    def __init__(self):
        self.data_path: str = ""
        self.excel_path: str = ""
        self.data: dict = {}
        self.lm: LabelMap | None = None
        self.time_vec: np.ndarray | None = None
        self.time_sec: np.ndarray | None = None
        self._loaded = False

    @staticmethod
    def resolve_path(path_value: str | os.PathLike[str] | None, default: str = "") -> str:
        """解析文件路径，相对路径自动搜寻已知目录。"""
        if not path_value:
            return default
        p = Path(path_value)
        if p.is_absolute() and p.exists():
            return str(p.resolve())
        for base in DATA_DIRS:
            candidate = (base / p).resolve()
            if candidate.exists():
                return str(candidate)
        return str(p.resolve())

    def load(self, data_path: str, excel_path: str) -> bool:
        """加载数据和标签映射。返回 True 表示成功。"""
        self.data_path = data_path
        self.excel_path = excel_path

        if not os.path.exists(data_path):
            self._loaded = False
            return False

        try:
            raw = param_extract(data_path)
            raw["TIME"] = extract_time(data_path)
            self.data = raw
            self.time_vec = raw["TIME"]
            self.time_sec = time_to_seconds_array(self.time_vec)

            if os.path.exists(excel_path):
                try:
                    self.lm = LabelMap(excel_path)
                    _add_weight_cg(self.data, self.lm)
                except Exception:
                    self.lm = None
            else:
                self.lm = None

            self._loaded = True
            return True
        except Exception:
            self._loaded = False
            return False

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    # -- 字段管理 --

    def get_field_names(self) -> list[str]:
        """所有字段名（不包括 TIME）。"""
        if not self.data:
            return []
        return [k for k in self.data if k != "TIME"]

    def get_field_labels(self) -> dict[str, str]:
        """字段名 → 中文标签。"""
        result: dict[str, str] = {}
        for field in self.get_field_names():
            if self.lm is not None:
                try:
                    result[field] = self.lm.get_label(field)
                except Exception:
                    result[field] = field
            else:
                result[field] = field
        return result

    def get_label(self, field_name: str) -> str:
        return self.get_field_labels().get(field_name, field_name)

    def resolve_field(self, signal_id: str) -> str | None:
        """将中文标签或字段名解析为 data 中的字段名。"""
        if signal_id in self.data:
            return signal_id
        if self.lm is not None:
            f = self.lm.get_var_name(signal_id)
            if f and f in self.data:
                return f
        cf = column_to_field_name(signal_id)
        if cf in self.data:
            return cf
        return None

    # -- 绘图数据 --

    def get_plot_data(self, signal_ids: list[str]) -> tuple[np.ndarray, np.ndarray, list[str]]:
        """返回 (time_sec, NxM signals_matrix, labels)。"""
        if not self._loaded or self.time_sec is None:
            return np.array([], dtype=float), np.empty((0, 0)), []

        fields: list[str] = []
        labels: list[str] = []
        for sid in signal_ids:
            f = self.resolve_field(sid)
            if f is not None:
                fields.append(f)
                labels.append(self.get_label(f))

        if not fields:
            # fallback: 取前 3 个信号
            names = self.get_field_names()[:3]
            for f in names:
                fields.append(f)
                labels.append(self.get_label(f))

        n = len(self.time_sec)
        m = len(fields)
        signals = np.zeros((n, m), dtype=float)
        for i, f in enumerate(fields):
            col = self.data.get(f)
            if col is not None:
                signals[:, i] = np.asarray(col, dtype=float)
        return self.time_sec, signals, labels

    # -- 统计 --

    def compute_parameter_stats(self, t_start, t_end, signal_ids: list[str]) -> list[str]:
        if not self._loaded or self.lm is None:
            return ["数据未加载"]
        return statistics_params(t_start, t_end, self.data, self.lm, signal_ids)

    def compute_crossing_analysis(
        self, signal_ids: list[str], mode: str, threshold: float, t_start, t_end
    ) -> list[str]:
        if not self._loaded or self.lm is None:
            return ["数据未加载"]
        return crossing_analysis(self.data, self.lm, signal_ids, mode, threshold, t_start, t_end)

    def compute_takeoff_landing_stats(self, t_start, t_end) -> str:
        if not self._loaded:
            return "数据未加载"
        return compute_takeoff_landing_stats(t_start, t_end, self.data, self.lm)

    # -- 拟合 --

    def compute_fitted_circle(self, lon_field: str, lat_field: str, t_start, t_end) -> float:
        if not self._loaded or self.time_vec is None:
            return float("nan")
        return compute_fitted_circle_radius(self.time_vec, t_start, t_end, self.data[lat_field], self.data[lon_field])

    # -- 导出 --

    def export_data(self, output_path: str, fmt: str, compression: str | None = None) -> str:
        if not self._loaded:
            raise RuntimeError("无数据可导出")
        return export_data(self.data, output_path, fmt, compression=compression)

    def export_statistics(self, stats: list, output_path: str, fmt: str = "csv") -> str:
        return export_statistics(stats, output_path, fmt)

    def generate_summary(self) -> dict:
        if not self._loaded:
            return {}
        return generate_data_summary(self.data)

    # -- 信息 --

    def get_row_count(self) -> int:
        return len(self.time_vec) if self.time_vec is not None else 0

    def get_column_count(self) -> int:
        return len(self.data) if self.data else 0

    def get_time_range_sec(self) -> tuple[float, float]:
        if self.time_sec is None or len(self.time_sec) < 2:
            return 0.0, 0.0
        return float(self.time_sec[0]), float(self.time_sec[-1])
