"""发动机报告生成器。"""

from __future__ import annotations

from typing import Any


def generate_engine_report(analysis_result: dict[str, Any]) -> str:
    """生成发动机分析文本报告。

    Args:
        analysis_result: EngineAnalysis.analyze() 的返回值。

    Returns:
        格式化的文本报告。
    """
    from .engine_analysis import EngineAnalysis
    return EngineAnalysis().generate_text(analysis_result)
