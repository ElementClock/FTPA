"""CAS 数据处理器。"""
from __future__ import annotations
import logging
import pandas as pd
logger = logging.getLogger(__name__)


def extract_cas_data(df: pd.DataFrame) -> dict:
    cas_cols = [col for col in df.columns if "CAS" in str(col) or "告警" in str(col)]
    return {col: df[col].values for col in cas_cols}
