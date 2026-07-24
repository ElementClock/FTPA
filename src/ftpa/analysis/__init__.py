"""
系统级分析子包
=============

提供发动机、燃油、电源、CAS 告警等系统级分析功能。
分析通过 SystemAnalyzer 入口类触发，按需执行（不在数据加载时自动运行）。
"""

from __future__ import annotations

from typing import Callable, Optional
import pandas as pd
import logging

from .interface import AnalysisInterface, AnalysisResult
from .plugin_manager import PluginManager, PluginConfig

logger = logging.getLogger(__name__)


class SystemAnalyzer:
    """系统级分析入口，协调发动机/燃油/电源/CAS 分析。

    使用示例：
        analyzer = SystemAnalyzer()
        results = analyzer.analyze(data_dict)
    """

    def __init__(self) -> None:
        self._pm = PluginManager()
        self._register_default_plugins()

    def _register_default_plugins(self) -> None:
        """注册默认分析插件。"""
        try:
            from .engines.engine_analysis import EngineAnalysis
            self._pm.register("engine", EngineAnalysis(),
                              PluginConfig("engine", priority=40))
        except ImportError:
            logger.debug("EngineAnalysis 不可用")

        try:
            from .fuel.fuel_analysis import FuelAnalysis
            self._pm.register("fuel", FuelAnalysis(),
                              PluginConfig("fuel", priority=30))
        except ImportError:
            logger.debug("FuelAnalysis 不可用")

        try:
            from .power.power_analysis import PowerAnalysis
            self._pm.register("power", PowerAnalysis(),
                              PluginConfig("power", priority=20))
        except ImportError:
            logger.debug("PowerAnalysis 不可用")

        try:
            from .cas.cas_analysis import CasAnalysis
            self._pm.register("cas", CasAnalysis(),
                              PluginConfig("cas", priority=10, dependencies=["engine"]))
        except ImportError:
            logger.debug("CasAnalysis 不可用")

    def analyze(
        self,
        data: dict | pd.DataFrame,
        source_type: str = "",
        progress_callback: Optional[Callable[[int, str], None]] = None,
    ) -> dict:
        """执行全部分析。

        Args:
            data: 输入数据，可以是 dict[str, np.ndarray] 或 DataFrame。
            source_type: 数据源类型 ("txt" | "csv")。
            progress_callback: 进度回调 (value: 0-100, message: str)。

        Returns:
            分析结果字典 {"engine": {...}, "fuel": {...}, ...}。
        """
        if isinstance(data, dict):
            df = pd.DataFrame(data)
        else:
            df = data

        if df.empty:
            logger.warning("输入数据为空，跳过分析")
            return {}

        return self._pm.execute_analysis(df, progress_callback=progress_callback)

    def generate_reports(self, analysis_results: dict) -> dict[str, str]:
        """从分析结果生成文本报告。"""
        return self._pm.generate_reports(analysis_results)


__all__ = [
    'SystemAnalyzer',
    'AnalysisInterface',
    'AnalysisResult',
    'PluginManager',
    'PluginConfig',
]
