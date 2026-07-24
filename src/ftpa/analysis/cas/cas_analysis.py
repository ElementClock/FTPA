"""
CAS 告警分析
============

分析显示告警系统（CAS）的告警事件和告警等级。
"""

from __future__ import annotations

import logging
from typing import Callable, Optional

import numpy as np
import pandas as pd

from ..interface import AnalysisInterface
from ..config import CAS_CONFIG
from ..utils import merge_continuous_time_periods

logger = logging.getLogger(__name__)


class CasAnalysis(AnalysisInterface):
    """CAS 告警分析插件。

    依赖发动机分析结果以确定分析时间范围。
    """

    def analyze(self, df: pd.DataFrame,
                progress_callback: Optional[Callable[[int, str], None]] = None) -> dict:
        """执行 CAS 告警分析。"""
        if progress_callback:
            progress_callback(10, "正在分析 CAS 告警数据...")

        result: dict = {"cas_found": False}

        # 查找 CAS 告警列
        cas_cols = [col for col in df.columns
                    if "CAS" in str(col) or "告警" in str(col) or "警告" in str(col)]
        if not cas_cols:
            logger.info("未找到 CAS 告警数据列，跳过 CAS 分析")
            return result

        result["cas_found"] = True
        result["cas_columns"] = cas_cols

        # 统计各告警列
        cas_stats = {}
        for col in cas_cols:
            values = df[col]
            if values.dtype == object:
                # 文本列：统计非空值
                non_null = values.dropna()
                non_null = non_null[non_null.astype(str).str.strip() != '']
                cas_stats[col] = {"alert_count": len(non_null)}
            else:
                numeric_vals = pd.to_numeric(values, errors='coerce').dropna().values
                cas_stats[col] = {"alert_count": len(numeric_vals)}
        result["cas_stats"] = cas_stats

        if progress_callback:
            progress_callback(100, "CAS 分析完成")

        return result

    def generate_text(self, analysis_result: dict) -> str:
        """生成 CAS 分析文本报告。"""
        if not analysis_result.get("cas_found"):
            return "未检测到 CAS 告警数据"

        lines = ["═" * 40, "CAS 告警分析报告", "═" * 40]

        cas_stats = analysis_result.get("cas_stats", {})
        if cas_stats:
            lines.append("\n【告警统计】")
            for col, stats in cas_stats.items():
                lines.append(f"  {col}: 告警次数 {stats.get('alert_count', 0)}")

        return "\n".join(lines)
