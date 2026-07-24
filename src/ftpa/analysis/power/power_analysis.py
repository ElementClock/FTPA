"""
电源分析
========

分析发电机电压、频率和负载情况。
"""

from __future__ import annotations

import logging
from typing import Callable, Optional

import numpy as np
import pandas as pd

from ..interface import AnalysisInterface
from ..config import POWER_CONFIG
from ..utils import compute_statistics

logger = logging.getLogger(__name__)


class PowerAnalysis(AnalysisInterface):
    """电源分析插件。"""

    def analyze(self, df: pd.DataFrame,
                progress_callback: Optional[Callable[[int, str], None]] = None) -> dict:
        """执行电源分析。"""
        if progress_callback:
            progress_callback(10, "正在分析电源数据...")

        result: dict = {"power_found": False}

        # 查找电压/频率/发电机列
        power_cols = [col for col in df.columns
                      if "电压" in str(col) or "频率" in str(col) or "发电机" in str(col)]
        if not power_cols:
            logger.info("未找到电源数据列，跳过电源分析")
            return result

        result["power_found"] = True
        result["power_columns"] = power_cols

        # 统计
        power_stats = {}
        for col in power_cols:
            values = pd.to_numeric(df[col], errors='coerce').dropna().values
            if len(values) > 0:
                power_stats[col] = compute_statistics(values)
        result["power_stats"] = power_stats

        if progress_callback:
            progress_callback(100, "电源分析完成")

        return result

    def generate_text(self, analysis_result: dict) -> str:
        """生成电源分析文本报告。"""
        if not analysis_result.get("power_found"):
            return "未检测到电源数据"

        lines = ["═" * 40, "电源分析报告", "═" * 40]

        power_stats = analysis_result.get("power_stats", {})
        if power_stats:
            lines.append("\n【电源参数统计】")
            for col, stats in power_stats.items():
                lines.append(f"  {col}:")
                lines.append(f"    平均: {stats['mean']:.2f}, 范围: {stats['min']:.2f} ~ {stats['max']:.2f}")

        return "\n".join(lines)
