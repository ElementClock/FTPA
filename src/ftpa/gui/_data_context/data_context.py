"""DataContext Facade —— 统一数据上下文，持有加载的数据和标签映射。

对外提供统一入口，内部委托给子服务：
- DataLoader: 数据加载策略（loading.py）
- DataQueryService: 只读数据查询（query.py）
- StatisticsService: 统计计算（statistics_service.py）
- DataExportService: 数据导出（export_service.py）
- PlotDataService: 绘图数据提取（plot_data_service.py）
"""

from __future__ import annotations

import logging
import os
import warnings
from pathlib import Path

import numpy as np

from ...data.label_map import LabelMap
from .export_service import DataExportService
from .field_resolver import FieldResolver
from .loading import LOADERS, LoadResult
from .plot_data_service import PlotDataService
from .query import DataQueryService
from .statistics_service import StatisticsService

logger = logging.getLogger(__name__)


def _warn_deprecated(prop_name: str, replacement: str, *, kind: str = "access") -> None:
    """发出 DeprecationWarning，提示外部代码迁移到 query 服务。

    Args:
        prop_name: 被弃用的属性名（如 ``"data"``）。
        replacement: 推荐的替代调用（如 ``"ctx.query.get_raw_data()"``）。
        kind: ``"access"`` 或 ``"setter"``，用于区分读写场景。
    """
    action = "写入" if kind == "setter" else "访问"
    warnings.warn(
        f"DataContext.{prop_name} 的{action}已弃用，请改用 {replacement}；"
        f"该属性仅保留向后兼容，未来版本可能移除。",
        DeprecationWarning,
        stacklevel=3,
    )

DATA_DIRS = [
    Path(__file__).resolve().parents[2] / "data",
    Path(__file__).resolve().parents[2] / "data" / "raw",
    Path(__file__).resolve().parents[2] / "testdata",
]


class DataContext:
    """统一数据上下文 Facade。

    单一实例，所有 Tab 共享。对外提供数据查询、统计计算、导出等功能，
    内部委托给子服务。本类仅负责生命周期管理和请求分发。
    """

    def __init__(self):
        # 内部状态
        self._data: dict = {}
        self._lm: LabelMap | None = None
        self._time_vec: np.ndarray | None = None
        self._time_sec: np.ndarray | None = None
        self._loaded = False
        self._data_path: str = ""
        self._excel_path: str = ""
        self._source_type: str = ""
        self.analysis_result: dict = {}

        # 组合对象
        self._field_resolver = FieldResolver(self._data)
        self._query_svc = DataQueryService(
            self._data, None, None, None, self._field_resolver,
        )
        self._export_svc = DataExportService(self._data)
        self._plot_svc = PlotDataService(self._query_svc)
        self._stats_service = StatisticsService(self._data)

    # -- 子服务访问 --

    @property
    def query(self) -> DataQueryService:
        """数据查询服务 —— 只读数据访问入口。"""
        return self._query_svc

    @property
    def stats(self) -> StatisticsService:
        """统计计算服务。"""
        return self._stats_service

    @property
    def stats_service(self) -> StatisticsService:
        """统计计算服务（向后兼容别名，推荐使用 ctx.stats）。"""
        return self._stats_service

    @property
    def field_resolver(self) -> FieldResolver:
        """字段解析器（向后兼容属性）。"""
        return self._field_resolver

    # -- 向后兼容属性（已弃用，请使用 ctx.query 下的方法）--

    @property
    def data(self) -> dict:
        """已加载数据字典。

        .. deprecated:: 1.1.0
            请改用 ``ctx.query.get_raw_data()`` 获取全部数据，
            或 ``ctx.query.get_signal_data(field)`` 获取单个信号。
        """
        _warn_deprecated("data", "ctx.query.get_raw_data() / ctx.query.get_signal_data(field)")
        return self._data

    @data.setter
    def data(self, value: dict) -> None:
        _warn_deprecated("data", "ctx.load() / ctx.unload()", kind="setter")
        self._data = value

    @property
    def time_sec(self) -> np.ndarray | None:
        """时间秒数组。

        .. deprecated:: 1.1.0
            请改用 ``ctx.query.get_time_sec()``。
        """
        _warn_deprecated("time_sec", "ctx.query.get_time_sec()")
        return self._time_sec

    @time_sec.setter
    def time_sec(self, value: np.ndarray | None) -> None:
        _warn_deprecated("time_sec", "ctx.load() / ctx.unload()", kind="setter")
        self._time_sec = value

    @property
    def time_vec(self) -> np.ndarray | None:
        """原始时间向量。

        .. deprecated:: 1.1.0
            请改用 ``ctx.query.get_time_vec()``。
        """
        _warn_deprecated("time_vec", "ctx.query.get_time_vec()")
        return self._time_vec

    @time_vec.setter
    def time_vec(self, value: np.ndarray | None) -> None:
        _warn_deprecated("time_vec", "ctx.load() / ctx.unload()", kind="setter")
        self._time_vec = value

    @property
    def lm(self) -> LabelMap | None:
        """标签映射。

        .. deprecated:: 1.1.0
            请改用 ``ctx.query.get_label_map()``，或通过 ``ctx.field_resolver``
            间接访问标签映射。
        """
        _warn_deprecated("lm", "ctx.query.get_label_map() / ctx.field_resolver")
        return self._lm

    @lm.setter
    def lm(self, value: LabelMap | None) -> None:
        _warn_deprecated("lm", "ctx.load() / ctx.unload()", kind="setter")
        self._lm = value

    @property
    def data_path(self) -> str:
        """数据文件路径。

        .. deprecated:: 1.1.0
            请改用 ``ctx.query.get_data_path()``。
        """
        _warn_deprecated("data_path", "ctx.query.get_data_path()")
        return self._data_path

    @data_path.setter
    def data_path(self, value: str) -> None:
        _warn_deprecated("data_path", "ctx.load() / ctx.unload()", kind="setter")
        self._data_path = value

    @property
    def excel_path(self) -> str:
        """映射表文件路径。

        .. deprecated:: 1.1.0
            请改用 ``ctx.query.get_excel_path()``。
        """
        _warn_deprecated("excel_path", "ctx.query.get_excel_path()")
        return self._excel_path

    @excel_path.setter
    def excel_path(self, value: str) -> None:
        _warn_deprecated("excel_path", "ctx.load() / ctx.unload()", kind="setter")
        self._excel_path = value

    @property
    def source_type(self) -> str:
        """数据源类型。

        .. deprecated:: 1.1.0
            请改用 ``ctx.query.get_source_type()``。
        """
        _warn_deprecated("source_type", "ctx.query.get_source_type()")
        return self._source_type

    @source_type.setter
    def source_type(self, value: str) -> None:
        _warn_deprecated("source_type", "ctx.load() / ctx.unload()", kind="setter")
        self._source_type = value

    # -- 静态方法 --

    @staticmethod
    def resolve_path(path_value: str | os.PathLike[str] | None, default: str = "") -> str:
        """解析文件路径，相对路径自动搜寻已知目录。"""
        if not path_value:
            return default

        path_str = str(path_value)
        try:
            from urllib.parse import unquote
            decoded = unquote(path_str)
        except Exception:
            logger.debug("URL 解码失败，使用原始路径: %s", path_str, exc_info=True)
            decoded = path_str
        if ".." in Path(decoded).parts:
            logger.warning("路径包含遍历组件（..），已拒绝: %s", path_value)
            return default

        p = Path(decoded)
        if p.is_absolute() and p.exists():
            return str(p.resolve())
        for base in DATA_DIRS:
            candidate = (base / p).resolve()
            if candidate.exists():
                try:
                    candidate.relative_to(base.resolve())
                except ValueError:
                    logger.warning("解析路径逃逸安全目录，已拒绝: %s", candidate)
                    continue
                return str(candidate)
        return str(p.resolve())

    # -- 生命周期管理 --

    def load(self, data_path: str, excel_path: str) -> None:
        """加载数据和标签映射。

        成功时设置 _loaded = True；失败时抛出 FtpaError 子类异常，
        由调用方捕获并处理。
        """
        ext = os.path.splitext(data_path)[1].lower()
        loader_cls = LOADERS.get(ext)
        if loader_cls is None:
            loader_cls = LOADERS[".txt"]
        # Loader 在失败时抛出自定义异常（FileNotFoundLoadError 等），
        # 由调用方捕获；成功时返回 LoadResult。
        result = loader_cls().load(data_path, excel_path)

        self._data_path = result.data_path
        self._excel_path = result.excel_path
        self._data = result.data
        self._time_vec = result.time_vec
        self._time_sec = result.time_sec
        self._lm = result.lm
        self._source_type = result.source_type
        self.analysis_result = {}

        self._field_resolver.update(self._data, self._lm)
        self._query_svc.update(
            self._data, self._time_vec, self._time_sec, self._lm,
            self._field_resolver, self._data_path, self._excel_path, self._source_type,
        )
        self._export_svc.update(self._data)
        self._plot_svc.update(self._query_svc)
        self._stats_service.update(self._data, self._lm, True, self._field_resolver)
        self._loaded = True

    def unload(self) -> None:
        """卸载当前数据，释放内存，重置所有状态。"""
        self._data_path = ""
        self._excel_path = ""
        self._data = {}
        self._lm = None
        self._time_vec = None
        self._time_sec = None
        self._field_resolver.clear()
        self._query_svc.clear()
        self._export_svc.clear()
        self._plot_svc.clear()
        self._stats_service.clear()
        self._loaded = False
        self._source_type = ""
        self.analysis_result = {}

    @property
    def is_loaded(self) -> bool:
        return self._loaded

    # -- 字段管理（委托给 query）--

    def get_field_names(self) -> list[str]:
        return self._query_svc.get_field_names()

    def get_field_labels(self) -> dict[str, str]:
        return self._query_svc.get_field_labels()

    def get_label(self, field_name: str) -> str:
        return self._query_svc.get_label(field_name)

    def resolve_field(self, signal_id: str) -> str | None:
        return self._query_svc.resolve_field(signal_id)

    # -- 绘图数据（委托给 plot_svc）--

    def get_plot_data(self, signal_ids: list[str]) -> tuple[np.ndarray, np.ndarray, list[str]]:
        """返回 (time_sec, NxM signals_matrix, labels)。"""
        if not self._loaded or self._time_sec is None:
            return np.array([], dtype=float), np.empty((0, 0)), []
        return self._plot_svc.get_plot_data(signal_ids)

    # -- 统计（委托给 stats_service）--

    def compute_parameter_stats(self, t_start, t_end, signal_ids: list[str]) -> list[str]:
        return self._stats_service.compute_parameter_stats(t_start, t_end, signal_ids)

    def compute_crossing_analysis(
        self, signal_ids: list[str], mode: str, threshold: float, t_start, t_end
    ) -> list[str]:
        return self._stats_service.compute_crossing_analysis(signal_ids, mode, threshold, t_start, t_end)

    def compute_takeoff_landing_stats(self, t_start, t_end) -> str:
        return self._stats_service.compute_takeoff_landing_stats(t_start, t_end)

    # -- 拟合 --

    def compute_fitted_circle(self, lon_field: str, lat_field: str, t_start, t_end) -> float:
        from ...computing import compute_fitted_circle_radius
        if not self._loaded or self._time_vec is None:
            return float("nan")
        return compute_fitted_circle_radius(self._time_vec, t_start, t_end, self._data[lat_field], self._data[lon_field])

    # -- 导出（委托给 export_svc）--

    def export_data(self, output_path: str, fmt: str, compression: str | None = None) -> str:
        if not self._loaded:
            raise RuntimeError("无数据可导出")
        return self._export_svc.export_data(output_path, fmt, compression)

    def export_statistics(self, stats: list, output_path: str, fmt: str = "csv") -> str:
        return self._export_svc.export_statistics(stats, output_path, fmt)

    def generate_summary(self) -> dict:
        if not self._loaded:
            return {}
        return self._export_svc.generate_summary()

    # -- 信息（委托给 query）--

    def get_row_count(self) -> int:
        return self._query_svc.get_row_count()

    def get_column_count(self) -> int:
        return self._query_svc.get_column_count()

    def get_time_range_sec(self) -> tuple[float, float]:
        return self._query_svc.get_time_range_sec()
