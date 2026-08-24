"""数据加载策略 —— Strategy 模式。

将 DataContext 的 _load_txt / _load_csv 提取为独立的 Loader 类，
新增数据格式只需实现 DataLoader Protocol 并注册到 LOADERS 即可。
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

import numpy as np
import pandas as pd

from ...data import param_extract
from ...errors import (
    FileNotFoundLoadError,
    FormatLoadError,
    ResourceLoadError,
)
from ...data.label_map import LabelMap
from ...utils.time_utils import time_to_seconds_array

logger = logging.getLogger(__name__)


@dataclass
class LoadResult:
    """数据加载结果。加载成功时由 Loader 返回，失败时抛出自定义异常。"""

    data: dict = field(default_factory=dict)
    time_vec: np.ndarray | None = None
    time_sec: np.ndarray | None = None
    lm: LabelMap | None = None
    source_type: str = ""
    data_path: str = ""
    excel_path: str = ""


@runtime_checkable
class DataLoader(Protocol):
    """数据加载策略接口。"""

    def load(self, data_path: str, excel_path: str) -> LoadResult:
        ...


class TxtLoader:
    """TXT 格式数据加载器（从 DataContext._load_txt 迁移，零行为变更）。"""

    def load(self, data_path: str, excel_path: str) -> LoadResult:
        if not os.path.exists(data_path):
            raise FileNotFoundLoadError(f"数据文件不存在: {data_path}", path=data_path)

        try:
            raw = param_extract(data_path)
            time_vec = raw["TIME"]
            time_sec = time_to_seconds_array(time_vec)

            # searchsorted 依赖 time_sec 单调递增，一次性验证
            if len(time_sec) > 1 and not np.all(np.diff(time_sec) >= 0):
                logger.warning("时间列非单调递增，缩放/统计可能不准确")

            lm: LabelMap | None = None
            try:
                from ...data.enrichment import add_weight_cg_to_data  # P1-ARCH-3: 迁移至 data 层
                # 优先使用 Excel 覆盖，缺失时 LabelMap 内部回退到静态映射
                lm = LabelMap(excel_path if excel_path else None)
                add_weight_cg_to_data(raw, lm)
            except Exception as e:
                logger.warning("映射表加载失败，回退到静态映射: %s", e)
                try:
                    lm = LabelMap()
                    add_weight_cg_to_data(raw, lm)
                except Exception:
                    logger.warning("静态映射加载失败，将使用无标签模式")
                    lm = None

            return LoadResult(
                data=raw,
                time_vec=time_vec,
                time_sec=time_sec,
                lm=lm,
                source_type="txt",
                data_path=data_path,
                excel_path=excel_path,
            )
        except FileNotFoundLoadError:
            raise
        except FormatLoadError:
            raise
        except ResourceLoadError:
            raise
        except FileNotFoundError as e:
            raise FileNotFoundLoadError(f"文件不存在: {e}", path=data_path) from e
        except (pd.errors.ParserError, ValueError) as e:
            raise FormatLoadError(f"文件格式错误: {e}", path=data_path) from e
        except MemoryError as e:
            raise ResourceLoadError(f"内存不足，文件过大: {e}", path=data_path) from e
        except OSError as e:
            raise ResourceLoadError(f"文件读取失败: {e}", path=data_path) from e
        except Exception as e:
            logger.exception("数据加载未知错误")
            raise ResourceLoadError(f"加载失败: {e}", path=data_path) from e


# Strategy 注册表：新增格式只需在此添加映射（当前构型仅支持 TXT）
LOADERS: dict[str, type[DataLoader]] = {
    ".txt": TxtLoader,
}
