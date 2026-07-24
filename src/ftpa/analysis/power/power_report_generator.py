"""电源报告生成器。"""
from __future__ import annotations
from typing import Any


def generate_power_report(analysis_result: dict[str, Any]) -> str:
    from .power_analysis import PowerAnalysis
    return PowerAnalysis().generate_text(analysis_result)
