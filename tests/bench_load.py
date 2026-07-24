"""数据加载性能基准测试"""
import time
import os
import tempfile
import shutil

import numpy as np
import pandas as pd

from ftpa.data.loader import param_extract, extract_time, clear_cache, _file_cache


def main():
    # 创建模拟数据文件（与实际格式一致：Tab分隔, TIME列, 多列数值）
    tmp_dir = tempfile.mkdtemp()
    test_file = os.path.join(tmp_dir, 'bench_data.txt')

    print('创建测试数据文件...')
    n_cols = 300
    n_rows = 20000  # 比实际文件小，但足以测量差异

    header = 'TIME\t' + '\t'.join([f'Col{i:03d}' for i in range(n_cols - 1)])
    with open(test_file, 'w', encoding='utf-8') as f:
        f.write(header + '\n')
        for i in range(n_rows):
            time_str = f'10:{i // 60:02d}:{i % 60:02d}:000'
            vals = '\t'.join([f'{np.random.randn():.7f}'] * (n_cols - 1))
            f.write(f'{time_str}\t{vals}\n')

    file_size_mb = os.path.getsize(test_file) / 1024 / 1024
    print(f'测试文件大小: {file_size_mb:.1f}MB, {n_rows}行 x {n_cols}列')
    print()

    # --- 冷启动测试 ---
    clear_cache()
    t0 = time.perf_counter()
    data = param_extract(test_file)
    t1 = time.perf_counter()
    cold_time = t1 - t0
    time_len = len(data.get('TIME', []))
    col_count = len(data)
    print(f'[冷启动] param_extract(): {cold_time:.3f}s')
    print(f'  行数: {time_len}, 列数: {col_count}')

    # --- 缓存命中测试 ---
    t0 = time.perf_counter()
    data2 = param_extract(test_file)
    t1 = time.perf_counter()
    warm_time = t1 - t0
    print(f'[热缓存] param_extract(): {warm_time:.6f}s')

    # --- extract_time 委托测试（应从缓存取，不重新读文件） ---
    t0 = time.perf_counter()
    time_arr = extract_time(test_file)
    t1 = time.perf_counter()
    et_time = t1 - t0
    print(f'[委托]   extract_time(): {et_time:.6f}s (应接近0，从缓存取)')

    # --- 验证数据正确性 ---
    assert 'TIME' in data, 'TIME 键缺失'
    assert data['TIME'].dtype.kind == 'm', \
        f'TIME dtype 错误: {data["TIME"].dtype} (期望 timedelta)'
    expected_rows = n_rows - 100  # TRIM_HEAD=50 + TRIM_TAIL=50
    assert len(data['TIME']) == expected_rows, \
        f'行数错误: {len(data["TIME"])} (期望 {expected_rows})'
    # 验证 float64 内联转换
    for k in list(data.keys())[:5]:
        if k not in ('TIME', 'filename'):
            assert data[k].dtype == np.float64, f'{k} dtype 错误: {data[k].dtype}'
    print()
    print('✓ 数据正确性验证通过')
    print()

    # --- 缓存统计 ---
    stats = _file_cache.stats()
    print(f'缓存统计: size={stats["size"]}, hits={stats["hits"]}, misses={stats["misses"]}')
    print()

    # --- 清理 ---
    shutil.rmtree(tmp_dir, ignore_errors=True)

    print('=== 性能摘要 ===')
    print(f'冷启动加载: {cold_time:.3f}s')
    print(f'热缓存命中: {warm_time:.6f}s (加速 {cold_time / warm_time:.0f}x)')
    print(f'extract_time 委托: {et_time:.6f}s (零额外 I/O)')


if __name__ == '__main__':
    main()
