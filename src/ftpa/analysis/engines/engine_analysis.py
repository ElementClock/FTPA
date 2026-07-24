"""
发动机分析
==========

检测发动机启停时间、转速/温度/滑油参数统计。
"""

from __future__ import annotations

import logging
import re
from typing import Callable, Optional

import numpy as np
import pandas as pd

from ..interface import AnalysisInterface
from ..config import ENGINE_CONFIG
from ..utils import compute_statistics, find_threshold_crossings

logger = logging.getLogger(__name__)


class EngineAnalysis(AnalysisInterface):
    """发动机分析插件。"""

    def analyze(self, df: pd.DataFrame,
                progress_callback: Optional[Callable[[int, str], None]] = None) -> dict:
        """执行发动机分析。

        Args:
            df: 飞行数据 DataFrame。
            progress_callback: 进度回调。

        Returns:
            分析结果字典，包含启停时间、各参数统计等。
        """
        if progress_callback:
            progress_callback(10, "正在分析发动机数据...")

        result: dict = {"engine_found": False}

        # 查找发动机转速列
        rpm_cols = _find_columns(df, ["发动机转速", "1发发动机转速", "2发发动机转速"])
        if not rpm_cols:
            logger.info("未找到发动机转速列，跳过发动机分析")
            return result

        result["engine_found"] = True
        result["rpm_columns"] = rpm_cols

        # 分析各发动机转速
        rpm_stats = {}
        for col in rpm_cols:
            values = pd.to_numeric(df[col], errors='coerce').dropna().values
            if len(values) > 0:
                rpm_stats[col] = compute_statistics(values)
        result["rpm_stats"] = rpm_stats

        # 检测启停时间
        if rpm_cols:
            primary_rpm = rpm_cols[0]
            rpm_values = pd.to_numeric(df[primary_rpm], errors='coerce').fillna(0).values
            threshold = ENGINE_CONFIG["rpm_threshold"]

            start_indices = find_threshold_crossings(rpm_values, threshold, "up")
            end_indices = find_threshold_crossings(rpm_values, threshold, "down")

            result["takeoff_start_time"] = start_indices[0] if start_indices else None
            result["takeoff_end_time"] = end_indices[0] if end_indices else None
            result["start_indices"] = start_indices
            result["end_indices"] = end_indices

        # 查找排气温度列
        egt_cols = _find_columns(df, ["排气温度", "1发排气温度", "2发排气温度"])
        if egt_cols:
            egt_stats = {}
            for col in egt_cols:
                values = pd.to_numeric(df[col], errors='coerce').dropna().values
                if len(values) > 0:
                    egt_stats[col] = compute_statistics(values)
            result["egt_stats"] = egt_stats

        if progress_callback:
            progress_callback(100, "发动机分析完成")

        return result

    def generate_text(self, analysis_result: dict) -> str:
        """生成发动机分析文本报告。"""
        if not analysis_result.get("engine_found"):
            return "未检测到发动机数据"

        lines = ["═" * 40, "发动机分析报告", "═" * 40]

        # 转速统计
        rpm_stats = analysis_result.get("rpm_stats", {})
        if rpm_stats:
            lines.append("\n【发动机转速统计】")
            for col, stats in rpm_stats.items():
                lines.append(f"  {col}:")
                lines.append(f"    平均: {stats['mean']:.1f}%, 标准差: {stats['std']:.1f}%")
                lines.append(f"    范围: {stats['min']:.1f}% ~ {stats['max']:.1f}%")

        # 排气温度
        egt_stats = analysis_result.get("egt_stats", {})
        if egt_stats:
            lines.append("\n【排气温度统计】")
            for col, stats in egt_stats.items():
                lines.append(f"  {col}:")
                lines.append(f"    平均: {stats['mean']:.1f}°C, 最大: {stats['max']:.1f}°C")

        # 启停时间
        start = analysis_result.get("takeoff_start_time")
        end = analysis_result.get("takeoff_end_time")
        if start is not None:
            lines.append(f"\n【启停时间】起始索引: {start}", )
            if end is not None:
                lines.append(f"  结束索引: {end}")

        return "\n".join(lines)


def _find_columns(df: pd.DataFrame, patterns: list[str]) -> list[str]:
    """按关键字查找匹配的列名。"""
    found = []
    for pattern in patterns:
        for col in df.columns:
            if pattern in str(col):
                found.append(col)
                break
    return found
