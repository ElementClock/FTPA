"""
DataContext —— 核心数据模型，桥接所有 CLI 模块到 GUI 面板。
单一实例，所有 Tab 共享。
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

import numpy as np
import pandas as pd

from ..computing.weight_cg import add_weight_cg_to_data
from ..computing import compute_fitted_circle_radius
from ..constants import BASE_OIL, BASE_REL_CG, BASE_WEIGHT
from ..data import param_extract
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
from ..utils.strings import column_to_field_name

logger = logging.getLogger(__name__)

DATA_DIRS = [
    Path(__file__).resolve().parents[2] / "data",
    Path(__file__).resolve().parents[2] / "data" / "raw",
    Path(__file__).resolve().parents[2] / "testdata",
]


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


class StatisticsService:
    """统计计算服务。

    职责：
    - 参数统计（compute_parameter_stats）
    - 穿越分析（compute_crossing_analysis）
    - 起降统计（compute_takeoff_landing_stats）
    """

    def __init__(self, data: dict, lm: LabelMap | None = None,
                 is_loaded: bool = False, field_resolver: FieldResolver | None = None):
        self._data = data
        self._lm = lm
        self._is_loaded = is_loaded
        self._field_resolver = field_resolver

    def update(self, data: dict, lm: LabelMap | None = None,
               is_loaded: bool = False, field_resolver: FieldResolver | None = None) -> None:
        """数据加载后更新引用。"""
        self._data = data
        self._lm = lm
        self._is_loaded = is_loaded
        self._field_resolver = field_resolver

    def clear(self) -> None:
        """卸载时清空所有状态。"""
        self._data = {}
        self._lm = None
        self._is_loaded = False
        self._field_resolver = None

    def compute_parameter_stats(self, t_start, t_end, signal_ids: list[str]) -> list[str]:
        if not self._is_loaded:
            return ["数据未加载"]
        if self._lm is None:
            return self._stats_without_labelmap(t_start, t_end, signal_ids)
        return statistics_params(t_start, t_end, self._data, self._lm, signal_ids)

    def compute_crossing_analysis(
        self, signal_ids: list[str], mode: str, threshold: float, t_start, t_end
    ) -> list[str]:
        if not self._is_loaded:
            return ["数据未加载"]
        if self._lm is None:
            return self._crossing_without_labelmap(signal_ids, mode, threshold, t_start, t_end)
        return crossing_analysis(self._data, self._lm, signal_ids, mode, threshold, t_start, t_end)

    def compute_takeoff_landing_stats(self, t_start, t_end) -> str:
        if not self._is_loaded:
            return "数据未加载"
        if self._lm is None:
            return "CSV 模式不支持起降统计（需要映射表定位关键参数）"
        return compute_takeoff_landing_stats(t_start, t_end, self._data, self._lm)

    def _stats_without_labelmap(self, t_start, t_end, signal_ids: list[str] | None) -> list[str]:
        """CSV 模式参数统计：列名即为标签，无需 LabelMap。"""
        from ..time_utils import select_time_window
        from ..statistics.basic import compute_stat

        if 'TIME' not in self._data:
            return ['数据中无 TIME 字段']

        TIME = self._data['TIME']
        i_start, i_end, t_start_actual, t_end_actual = select_time_window(TIME, t_start, t_end)
        lines = []

        # 确定要处理的字段
        if not signal_ids:
            fields_to_process = self._field_resolver.get_field_names() if self._field_resolver else []
        else:
            fields_to_process = [s for s in signal_ids if s in self._data]

        if not fields_to_process:
            return ['未找到可统计的变量。']

        for field_name in fields_to_process:
            signal = self._data[field_name]
            if not isinstance(signal, np.ndarray) or len(signal) != len(TIME):
                continue
            if not np.issubdtype(signal.dtype, np.number) and signal.dtype != bool:
                continue

            segment = signal[i_start:i_end + 1]
            label = field_name  # CSV 列名即为标签

            if len(segment) == 0:
                lines.append(f'{label}: 窗口内无数据')
                continue

            stat_types = ['start', 'end', 'min', 'max', 'mean', 'std', 'points']
            values = []
            for st in stat_types:
                val, _ = compute_stat(segment, st)
                values.append(f'{val:.6g}' if isinstance(val, (int, float, np.number)) else str(val))

            line = (f'{label}  起始={values[0]}, 结束={values[1]}, 最小={values[2]}, '
                    f'最大={values[3]}, 平均={values[4]}, 标准差={values[5]}, 点数={values[6]}')
            lines.append(line)

        if not lines:
            lines.append('未找到可统计的变量。')
        return lines

    def _crossing_without_labelmap(
        self, signal_ids: list[str], mode: str, threshold: float, t_start, t_end
    ) -> list[str]:
        """CSV 模式穿越分析：列名即为标签，无需 LabelMap。"""
        from ..time_utils import select_time_window
        from ..statistics.basic import find_crossing_points

        if not signal_ids:
            return ['signal_ids 不能为空']

        TIME = self._data.get('TIME')
        if TIME is None:
            return ['数据中无 TIME 字段']

        i_start, i_end, _, _ = select_time_window(TIME, t_start, t_end)

        fields = [s if s in self._data else '' for s in signal_ids]
        labels = signal_ids  # CSV 列名即为标签

        main_field = fields[0]
        main_label = labels[0]

        if not main_field:
            return [f'主信号 "{signal_ids[0]}" 未找到']

        main_sig = self._data[main_field]
        if len(main_sig) != len(TIME):
            return [f'主信号 "{main_label}" 与时间向量长度不一致']

        main_sig = main_sig[i_start:i_end + 1]
        cross_idx_local = find_crossing_points(main_sig, threshold, mode)

        if cross_idx_local is None:
            return [f'在窗口内未检测到 {main_label} 的 {mode} 穿越（阈值 {threshold:.2f}）']

        mode_text = mode.replace('First', '首次').replace('Last', '末次')
        mode_text = mode_text.replace('Down', '下降').replace('Up', '上升')

        lines = [f'{main_label} {mode_text}穿越阈值 {threshold:.2f} 时：']

        for i in range(1, len(signal_ids)):
            other_field = fields[i]
            display_name = labels[i]

            if not other_field or other_field not in self._data:
                lines.append(f'    {signal_ids[i]} = (无数据)')
                continue

            other_sig = self._data[other_field]
            if len(other_sig) != len(TIME):
                lines.append(f'    {display_name} = (长度不一致)')
                continue

            val = other_sig[i_start:i_end + 1]
            cross_idx = cross_idx_local - 1
            lines.append(f'    {display_name} = {val[cross_idx]:.2f}')

        return lines


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
        # 数据源类型与系统级分析
        self.source_type: str = ""       # "txt" | "csv"
        self.analysis_result: dict = {}  # 系统级分析结果（engine/fuel/power/cas）
        # 组合对象
        self.field_resolver = FieldResolver(self.data)
        self.stats_service = StatisticsService(self.data)

    @staticmethod
    def resolve_path(path_value: str | os.PathLike[str] | None, default: str = "") -> str:
        """解析文件路径，相对路径自动搜寻已知目录。

        安全措施：
        - 拒绝包含路径遍历（..）的输入
        - 搜索范围限制为 DATA_DIRS 中的安全目录
        """
        if not path_value:
            return default

        # 安全检查：拒绝路径遍历
        if ".." in Path(path_value).parts:
            logger.warning("路径包含遍历组件（..），已拒绝: %s", path_value)
            return default

        p = Path(path_value)
        if p.is_absolute() and p.exists():
            return str(p.resolve())
        for base in DATA_DIRS:
            candidate = (base / p).resolve()
            if candidate.exists():
                return str(candidate)
        return str(p.resolve())

    def load(self, data_path: str, excel_path: str) -> tuple[bool, str]:
        """加载数据和标签映射。返回 (ok, error_msg)。

        根据文件扩展名自动分发到 TXT 或 CSV 加载路径。
        """
        ext = os.path.splitext(data_path)[1].lower()
        if ext == '.csv':
            return self._load_csv(data_path, excel_path)
        else:
            return self._load_txt(data_path, excel_path)

    def _load_txt(self, data_path: str, excel_path: str) -> tuple[bool, str]:
        """TXT 格式数据加载（原有逻辑，零行为变更）。"""
        self.data_path = data_path
        self.excel_path = excel_path

        if not os.path.exists(data_path):
            self._loaded = False
            return False, f"数据文件不存在: {data_path}"

        try:
            raw = param_extract(data_path)
            self.data = raw
            self.time_vec = raw["TIME"]
            self.time_sec = time_to_seconds_array(self.time_vec)
            self.source_type = "txt"

            # searchsorted 依赖 time_sec 单调递增，一次性验证
            if len(self.time_sec) > 1 and not np.all(np.diff(self.time_sec) >= 0):
                logger.warning("时间列非单调递增，缩放/统计可能不准确")

            if os.path.exists(excel_path):
                try:
                    self.lm = LabelMap(excel_path)
                    add_weight_cg_to_data(self.data, self.lm)
                except Exception as e:
                    logger.warning("映射表加载失败，将使用无标签模式: %s", e)
                    self.lm = None
            else:
                self.lm = None

            # 重置缓存
            self.analysis_result = {}

            self.field_resolver.update(self.data, self.lm)
            self.stats_service.update(self.data, self.lm, True, self.field_resolver)
            self._loaded = True
            return True, ""
        except FileNotFoundError as e:
            self._loaded = False
            return False, f"文件不存在: {e}"
        except (pd.errors.ParserError, ValueError) as e:
            self._loaded = False
            return False, f"文件格式错误: {e}"
        except MemoryError as e:
            self._loaded = False
            return False, f"内存不足，文件过大: {e}"
        except OSError as e:
            self._loaded = False
            return False, f"文件读取失败: {e}"
        except Exception as e:
            self._loaded = False
            logger.exception("数据加载未知错误")
            return False, f"加载失败: {e}"

    def _load_csv(self, data_path: str, excel_path: str) -> tuple[bool, str]:
        """CSV 格式飞参数据加载。

        CSV 数据自带中文列名，不需要映射表（LabelMap/Excel），
        列名即为标签，数据保持原始状态。
        """
        from ..data.csv_loader import csv_param_extract

        self.data_path = data_path
        self.excel_path = ""  # CSV 不使用映射表

        if not os.path.exists(data_path):
            self._loaded = False
            return False, f"数据文件不存在: {data_path}"

        try:
            raw = csv_param_extract(data_path)
            self.data = raw
            self.time_vec = raw.get("TIME", np.array([], dtype='timedelta64[ns]'))
            self.time_sec = time_to_seconds_array(self.time_vec)
            self.source_type = "csv"

            # searchsorted 依赖 time_sec 单调递增，一次性验证
            if len(self.time_sec) > 1 and not np.all(np.diff(self.time_sec) >= 0):
                logger.warning("时间列非单调递增，缩放/统计可能不准确")

            # CSV 不使用映射表：列名即为标签，无需 LabelMap
            self.lm = None

            # 重置缓存
            self.analysis_result = {}

            self.field_resolver.update(self.data, self.lm)
            self.stats_service.update(self.data, self.lm, True, self.field_resolver)
            self._loaded = True
            return True, ""
        except FileNotFoundError as e:
            self._loaded = False
            return False, f"文件不存在: {e}"
        except (pd.errors.ParserError, ValueError) as e:
            self._loaded = False
            return False, f"文件格式错误: {e}"
        except MemoryError as e:
            self._loaded = False
            return False, f"内存不足，文件过大: {e}"
        except OSError as e:
            self._loaded = False
            return False, f"文件读取失败: {e}"
        except Exception as e:
            self._loaded = False
            logger.exception("数据加载未知错误")
            return False, f"加载失败: {e}"

    def unload(self) -> None:
        """卸载当前数据，释放内存，重置所有状态。

        调用后 is_loaded 为 False，data/time_vec/time_sec 均清空。
        """
        self.data_path = ""
        self.excel_path = ""
        self.data = {}
        self.lm = None
        self.time_vec = None
        self.time_sec = None
        self.field_resolver.clear()
        self.stats_service.clear()
        self._loaded = False
        self.source_type = ""
        self.analysis_result = {}

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    # -- 字段管理 --

    def get_field_names(self) -> list[str]:
        """所有字段名（不包括 TIME 和元数据键）。"""
        return self.field_resolver.get_field_names()

    def get_field_labels(self) -> dict[str, str]:
        """字段名 → 中文标签（惰性缓存）。"""
        return self.field_resolver.get_field_labels()

    def get_label(self, field_name: str) -> str:
        return self.field_resolver.get_label(field_name)

    def resolve_field(self, signal_id: str) -> str | None:
        """将中文标签或字段名解析为 data 中的字段名。

        优先级：
        1. 直接匹配 data 中的键（支持中文列名）
        2. 通过 LabelMap 反查
        3. column_to_field_name 转换后匹配（仅对 ASCII 列名有效）
        """
        return self.field_resolver.resolve_field(signal_id)

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
            # fallback: 取前 3 个数值信号
            for f in self.get_field_names():
                col = self.data.get(f)
                if isinstance(col, np.ndarray) and np.issubdtype(col.dtype, np.number):
                    fields.append(f)
                    labels.append(self.get_label(f))
                    if len(fields) >= 3:
                        break

        n = len(self.time_sec)
        m = len(fields)
        signals = np.zeros((n, m), dtype=float)
        for i, f in enumerate(fields):
            col = self.data.get(f)
            if col is not None:
                try:
                    if isinstance(col, np.ndarray):
                        signals[:, i] = col
                    else:
                        signals[:, i] = np.asarray(col, dtype=np.float64)
                except (ValueError, TypeError):
                    logger.debug("非数值列跳过: field=%s", f)
        return self.time_sec, signals, labels

    # -- 统计 --

    def compute_parameter_stats(self, t_start, t_end, signal_ids: list[str]) -> list[str]:
        return self.stats_service.compute_parameter_stats(t_start, t_end, signal_ids)

    def compute_crossing_analysis(
        self, signal_ids: list[str], mode: str, threshold: float, t_start, t_end
    ) -> list[str]:
        return self.stats_service.compute_crossing_analysis(signal_ids, mode, threshold, t_start, t_end)

    def compute_takeoff_landing_stats(self, t_start, t_end) -> str:
        return self.stats_service.compute_takeoff_landing_stats(t_start, t_end)

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
        """返回信号列数（排除 TIME/filename 等元数据键）。"""
        if self.field_resolver is not None:
            return len(self.field_resolver.get_field_names())
        return len(self.data) if self.data else 0

    def get_time_range_sec(self) -> tuple[float, float]:
        if self.time_sec is None or len(self.time_sec) < 2:
            return 0.0, 0.0
        return float(self.time_sec[0]), float(self.time_sec[-1])
