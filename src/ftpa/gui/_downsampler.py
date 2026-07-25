"""降采样渲染模块 — 大数据集 min-max 降采样。

参考 MATLAB 大规模时序数据渲染策略：
- 将可见窗口内数据按目标点数均匀分桶
- 每个桶保留 min 和 max 值，确保峰谷值不丢失
- 仅用于渲染加速，穿越分析/统计仍使用全量数据
"""

from __future__ import annotations

import numpy as np

DOWNSAMPLE_THRESHOLD: int = 10000  # 可见点数超过此值时触发降采样
DOWNSAMPLE_TARGET: int = 2000  # 降采样目标点数


def min_max_downsample(
    time_sec: np.ndarray,
    data_arr: np.ndarray,
    t_start: float,
    t_end: float,
    max_points: int = DOWNSAMPLE_TARGET,
) -> tuple[np.ndarray, np.ndarray]:
    """对可见时间窗口内的数据执行 min-max 降采样。

    Args:
        time_sec: 全量时间数组（已排序，float64）
        data_arr: 全量数据数组（float64，与 time_sec 等长）
        t_start: 可见窗口起始时间
        t_end: 可见窗口结束时间
        max_points: 降采样目标点数

    Returns:
        (downsampled_time, downsampled_data) 降采样后的时间/数据数组。
        若可见点数 ≤ max_points，直接返回原始数据切片。
    """
    # 1. 用 searchsorted 快速定位可见窗口索引范围（O(log N)）
    i_start = np.searchsorted(time_sec, t_start, side="left")
    i_end = np.searchsorted(time_sec, t_end, side="right")

    n_visible = i_end - i_start
    if n_visible <= max_points:
        # 小数据集不需要降采样
        return time_sec[i_start:i_end].copy(), data_arr[i_start:i_end].copy()

    # 2. 提取可见段
    vis_time = time_sec[i_start:i_end]
    vis_data = data_arr[i_start:i_end]

    # 3. 均匀分桶（每桶贡献 2 个点：min 和 max）
    n_buckets = max(1, max_points // 2)
    bucket_size = max(1, n_visible // n_buckets)

    result_time: list[np.ndarray] = []
    result_data: list[np.ndarray] = []

    for b in range(n_buckets):
        b_start = b * bucket_size
        b_end = min(b_start + bucket_size, n_visible)
        if b_start >= n_visible:
            break

        bucket_t = vis_time[b_start:b_end]
        bucket_d = vis_data[b_start:b_end]

        # 排除 NaN
        valid_mask = ~np.isnan(bucket_d)
        if not np.any(valid_mask):
            continue

        valid_d = bucket_d[valid_mask]
        valid_t = bucket_t[valid_mask]

        if len(valid_d) == 0:
            continue

        # 找 min 和 max 的索引
        min_idx = np.argmin(valid_d)
        max_idx = np.argmax(valid_d)

        min_t = valid_t[min_idx]
        max_t = valid_t[max_idx]
        min_v = valid_d[min_idx]
        max_v = valid_d[max_idx]

        # 按时间顺序排列，确保单调递增
        if min_t <= max_t:
            result_time.append(np.array([min_t, max_t]))
            result_data.append(np.array([min_v, max_v]))
        else:
            result_time.append(np.array([max_t, min_t]))
            result_data.append(np.array([max_v, min_v]))

    if not result_time:
        return vis_time.copy(), vis_data.copy()

    return np.concatenate(result_time), np.concatenate(result_data)
