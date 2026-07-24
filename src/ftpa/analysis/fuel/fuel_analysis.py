"""
燃油分析
========

分析油箱油量、燃油流量和油箱不平衡情况。
"""

from __future__ import annotations

import logging
from typing import Callable, Optional

import numpy as np
import pandas as pd

from ..interface import AnalysisInterface
from ..config import FUEL_CONFIG
from ..utils import compute_statistics

logger = logging.getLogger(__name__)


class FuelAnalysis(AnalysisInterface):
    """燃油分析插件。"""

    def analyze(self, df: pd.DataFrame,
                progress_callback: Optional[Callable[[int, str], None]] = None) -> dict:
        """执行燃油分析。"""
        if progress_callback:
            progress_callback(10, "正在分析燃油数据...")

        result: dict = {"fuel_found": False}

        # 查找燃油量列
        fuel_cols = [col for col in df.columns
                     if "燃油" in str(col) or "油量" in str(col) or "油箱" in str(col)]
        if not fuel_cols:
            logger.info("未找到燃油数据列，跳过燃油分析")
            return result

        result["fuel_found"] = True
        result["fuel_columns"] = fuel_cols

        # 统计各油箱
        fuel_stats = {}
        for col in fuel_cols:
            values = pd.to_numeric(df[col], errors='coerce').dropna().values
            if len(values) > 0:
                fuel_stats[col] = compute_statistics(values)
        result["fuel_stats"] = fuel_stats

        if progress_callback:
            progress_callback(100, "燃油分析完成")

        return result

    def generate_text(self, analysis_result: dict) -> str:
        """生成燃油分析文本报告。"""
        if not analysis_result.get("fuel_found"):
            return "未检测到燃油数据"

        lines = ["═" * 40, "燃油分析报告", "═" * 40]

        fuel_stats = analysis_result.get("fuel_stats", {})
        if fuel_stats:
            lines.append("\n【燃油量统计】")
            for col, stats in fuel_stats.items():
                lines.append(f"  {col}:")
                lines.append(f"    平均: {stats['mean']:.1f}, 范围: {stats['min']:.1f} ~ {stats['max']:.1f}")

        return "\n".join(lines)
