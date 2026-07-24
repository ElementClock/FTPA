"""
分析接口定义
============

定义分析插件的抽象基类和结果容器。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Optional, List

import pandas as pd


class AnalysisInterface(ABC):
    """分析插件抽象基类。

    所有系统级分析插件必须实现此接口。
    """

    @abstractmethod
    def analyze(self, df: pd.DataFrame,
                progress_callback: Optional[Callable[[int, str], None]] = None) -> dict:
        """执行分析。

        Args:
            df: 飞行数据 DataFrame。
            progress_callback: 进度回调。

        Returns:
            分析结果字典。
        """
        ...

    @abstractmethod
    def generate_text(self, analysis_result: dict) -> str:
        """从分析结果生成文本报告。

        Args:
            analysis_result: analyze() 返回的结果。

        Returns:
            格式化的文本报告。
        """
        ...


@dataclass
class AnalysisResult:
    """分析结果容器，聚合各子模块结果。"""

    text_engine: str = ""
    text_fuel: str = ""
    text_power: str = ""
    text_cas: str = ""
    errors: List[str] = field(default_factory=list)
    df: Any = None
    engine_data: Any = None
    fuel_data: Any = None
    power_data: Any = None
    cas_data: Any = None
    engine_start_time: Any = None
    engine_end_time: Any = None
