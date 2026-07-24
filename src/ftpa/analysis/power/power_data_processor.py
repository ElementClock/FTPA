"""电源数据处理器。"""
from __future__ import annotations
import logging
import pandas as pd
logger = logging.getLogger(__name__)


def extract_power_data(df: pd.DataFrame) -> dict:
    power_cols = [col for col in df.columns if "电压" in str(col) or "频率" in str(col)]
    return {col: pd.to_numeric(df[col], errors='coerce').values for col in power_cols}
