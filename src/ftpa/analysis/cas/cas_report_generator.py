"""CAS 报告生成器。"""
from __future__ import annotations
from typing import Any


def generate_cas_report(analysis_result: dict[str, Any]) -> str:
    from .cas_analysis import CasAnalysis
    return CasAnalysis().generate_text(analysis_result)
