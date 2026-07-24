"""发动机数据处理器 — 提取和清洗发动机相关数据列。"""

from __future__ import annotations

import logging
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def extract_engine_data(df: pd.DataFrame) -> dict:
    """从 DataFrame 中提取发动机相关数据。

    Args:
        df: 飞行数据 DataFrame。

    Returns:
        发动机数据字典 {"rpm": {...}, "egt": {...}, "oil": {...}}。
    """
    result: dict = {}

    # 转速
    rpm_cols = [col for col in df.columns if "发动机转速" in str(col)]
    if rpm_cols:
        result["rpm"] = {col: pd.to_numeric(df[col], errors='coerce').values for col in rpm_cols}

    # 排气温度
    egt_cols = [col for col in df.columns if "排气温度" in str(col)]
    if egt_cols:
        result["egt"] = {col: pd.to_numeric(df[col], errors='coerce').values for col in egt_cols}

    # 滑油
    oil_cols = [col for col in df.columns if "滑油" in str(col)]
    if oil_cols:
        result["oil"] = {col: pd.to_numeric(df[col], errors='coerce').values for col in oil_cols}

    return result
