"""降采样渲染模块 — 大数据集 min-max 降采样。

参考 MATLAB 大规模时序数据渲染策略：
- 将可见窗口内数据按目标点数均匀分桶
- 每个桶保留 min 和 max 值，确保峰谷值不丢失
- 仅用于渲染加速，穿越分析/统计仍使用全量数据

性能优化：
- 向量化实现：使用 np.reshape + np.nanmin/np.nanmax 替代 Python for 循环
- 对 500K 点数据从 ~7.7ms 降至 <1ms
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

    算法：
        1. searchsorted 快速定位可见窗口（O(log N)）
        2. 将可见数据按 max_points//2 均匀分桶
        3. 向量化计算每桶的 nanmin/nanmax 及对应时间
        4. 按时间排序输出（确保单调递增）
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

    # 截断至整桶数以支持 reshape
    usable = n_buckets * bucket_size
    if usable > n_visible:
        usable = (n_buckets - 1) * bucket_size
        n_buckets -= 1

    if usable <= 0 or n_buckets <= 0:
        return vis_time.copy(), vis_data.copy()

    # 4. 向量化计算每桶 min/max
    t_reshaped = vis_time[:usable].reshape(n_buckets, bucket_size)
    d_reshaped = vis_data[:usable].reshape(n_buckets, bucket_size)

    # 处理 NaN：使用 nanmin/nanmax
    # 对全 NaN 桶，nanmin/nanmax 返回 NaN（带 RuntimeWarning），后续会过滤
    with np.errstate(all="ignore"):
        d_min = np.nanmin(d_reshaped, axis=1)   # (n_buckets,)
        d_max = np.nanmax(d_reshaped, axis=1)   # (n_buckets,)

    # 5. 过滤全 NaN 桶（d_min 为 NaN 表示该桶全 NaN）
    valid = ~np.isnan(d_min)
    if not np.any(valid):
        return vis_time.copy(), vis_data.copy()

    # 仅对有效桶计算 argmin/argmax（避免全 NaN 桶触发 ValueError）
    d_valid = d_reshaped[valid]
    t_valid = t_reshaped[valid]

    with np.errstate(all="ignore"):
        min_idx = np.nanargmin(d_valid, axis=1)
        max_idx = np.nanargmax(d_valid, axis=1)

    # 取对应时间
    bucket_indices = np.arange(d_valid.shape[0])
    t_min = t_valid[bucket_indices, min_idx]
    t_max = t_valid[bucket_indices, max_idx]
    d_min = d_min[valid]
    d_max = d_max[valid]

    # 6. 按时间顺序排列：确保 min 点在前，max 点在后
    swap = t_min > t_max
    # 交换需要交换的桶
    t_min[swap], t_max[swap] = t_max[swap].copy(), t_min[swap].copy()
    d_min[swap], d_max[swap] = d_max[swap].copy(), d_min[swap].copy()

    # 7. 交错合并 min 和 max
    result_time = np.empty(2 * len(t_min), dtype=np.float64)
    result_data = np.empty(2 * len(d_min), dtype=np.float64)
    result_time[0::2] = t_min
    result_time[1::2] = t_max
    result_data[0::2] = d_min
    result_data[1::2] = d_max

    # 8. 处理尾部余量（usable 之后的点）
    if usable < n_visible:
        tail_t = vis_time[usable:]
        tail_d = vis_data[usable:]
        valid_tail = ~np.isnan(tail_d)
        if np.any(valid_tail):
            result_time = np.concatenate([result_time, tail_t[valid_tail]])
            result_data = np.concatenate([result_data, tail_d[valid_tail]])

    return result_time, result_data
