"""燃油报告生成器。"""
from __future__ import annotations
from typing import Any


def generate_fuel_report(analysis_result: dict[str, Any]) -> str:
    from .fuel_analysis import FuelAnalysis
    return FuelAnalysis().generate_text(analysis_result)
