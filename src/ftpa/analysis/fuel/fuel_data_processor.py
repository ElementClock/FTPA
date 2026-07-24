"""燃油数据处理器。"""
from __future__ import annotations
import logging
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def extract_fuel_data(df: pd.DataFrame) -> dict:
    """提取燃油相关数据列。"""
    fuel_cols = [col for col in df.columns if "燃油" in str(col) or "油量" in str(col)]
    return {col: pd.to_numeric(df[col], errors='coerce').values for col in fuel_cols}
