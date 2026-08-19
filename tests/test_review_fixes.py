"""
针对代码审阅修复的回归测试。

覆盖：
- 小 CSV 文件不再因 _trim_data 崩溃
- select_time_window 支持 None / 空字符串表示全时段
- DataContext.compute_fitted_circle 经纬度参数顺序正确
- generate_data_summary 不把 filename 计入通道数
- 发动机列查找去重
- 插件进度回调透传
"""

from __future__ import annotations

import os
import tempfile

import numpy as np
import pandas as pd
import pytest

from ftpa.data.csv_loader import csv_param_extract
from ftpa.data.summary import generate_data_summary
from ftpa.gui._data_context.data_context import DataContext
from ftpa.utils.time_utils import select_time_window


def _write_csv(content: str) -> str:
    fd, path = tempfile.mkstemp(suffix=".csv", prefix="ftpa_fix_")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(content)
    return path


def test_small_csv_does_not_crash():
    """小于 trim_head+trim_tail 的 CSV 不应因 _trim_data 崩溃。"""
    lines = ["飞参内部时间,col1,col2,日期,标识符,时间,温度"]
    lines += [
        f"0:00:{i:02d}.000,{i},{i * 2},2025/10/13,1,0:00:{i:02d},{20.0 + i}"
        for i in range(5)
    ]
    path = _write_csv("\n".join(lines) + "\n")
    try:
        data = csv_param_extract(path)
        assert "TIME" in data
        assert len(data["TIME"]) == 0
    finally:
        os.unlink(path)


def test_select_time_window_none_is_full_range():
    time_vec = np.arange(10.0)
    i_start, i_end, t_start, t_end = select_time_window(time_vec, None, None)
    assert i_start == 0
    assert i_end == 9
    assert t_start == 0.0
    assert t_end == 9.0


def test_select_time_window_empty_string_is_full_range():
    time_vec = np.arange(10.0)
    i_start, i_end, t_start, t_end = select_time_window(time_vec, "", "")
    assert i_start == 0
    assert i_end == 9
    assert t_start == 0.0
    assert t_end == 9.0


def test_data_context_circle_fit_uses_lon_lat_order():
    """DataContext.compute_fitted_circle 应先经度后纬度。"""
    n_points = 100
    theta = np.linspace(0, 2 * np.pi, n_points, endpoint=False)
    radius = 500.0
    lat0 = 39.5
    lon0 = 116.5
    meters_per_deg_lat = 111320.0
    meters_per_deg_lon = 111320.0 * np.cos(np.radians(lat0))

    lon = lon0 + (radius * np.cos(theta)) / meters_per_deg_lon
    lat = lat0 + (radius * np.sin(theta)) / meters_per_deg_lat
    time_vec = np.linspace(0, 100, n_points)

    ctx = DataContext()
    ctx._loaded = True
    ctx._time_vec = time_vec
    ctx._data = {"lon": lon, "lat": lat}

    r = ctx.compute_fitted_circle("lon", "lat", 0, 100)
    assert not np.isnan(r)
    assert abs(r - radius) < 1.0


def test_summary_total_channels_excludes_filename():
    data = {
        "TIME": np.array([0, 1, 2], dtype="timedelta64[s]"),
        "signal1": np.array([1.0, 2.0, 3.0]),
        "filename": "/tmp/foo.txt",
    }
    summary = generate_data_summary(data)
    assert summary["total_channels"] == 1


def test_engine_find_columns_dedup():
    from ftpa.analysis.engines.engine_analysis import _find_columns

    df = pd.DataFrame(
        {
            "1发发动机转速": [1.0],
            "2发发动机转速": [2.0],
        }
    )
    cols = _find_columns(df, ["发动机转速", "1发发动机转速", "2发发动机转速"])
    assert cols == ["1发发动机转速", "2发发动机转速"]


def test_plugin_manager_passes_progress_callback():
    from ftpa.analysis.interface import AnalysisInterface
    from ftpa.analysis.plugin_manager import PluginConfig, PluginManager

    received: list[tuple[int, str]] = []

    class ProgressPlugin(AnalysisInterface):
        def analyze(self, df, progress_callback=None):
            if progress_callback:
                progress_callback(42, "progress")
            return {"ok": True}

        def generate_text(self, analysis_result):
            return "ok"

    pm = PluginManager()
    pm.register("p", ProgressPlugin(), PluginConfig("p", priority=1))

    def cb(value, message):
        received.append((value, message))

    pm.execute_analysis(pd.DataFrame({"x": [1]}), progress_callback=cb)
    assert any(value == 42 and message == "progress" for value, message in received)
