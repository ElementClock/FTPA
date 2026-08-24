"""
针对代码审阅修复的回归测试。

覆盖：
- select_time_window 支持 None / 空字符串表示全时段
- DataContext.compute_fitted_circle 经纬度参数顺序正确
- generate_data_summary 不把 filename 计入通道数
"""

from __future__ import annotations

import numpy as np

from ftpa.data.summary import generate_data_summary
from ftpa.gui._data_context.data_context import DataContext
from ftpa.utils.time_utils import select_time_window


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