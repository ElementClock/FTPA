"""使用真实数据文件的基准测试"""
import time
import os
from pathlib import Path

from ftpa.data.loader import param_extract, extract_time, clear_cache, _file_cache

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def main():
    data_path = PROJECT_ROOT / 'testdata' / 'FTPD-AG600-007-QD-260509-G-1-飞机性能操稳-32.txt'
    excel_path = PROJECT_ROOT / 'testdata' / '参数名.xlsx'

    if not os.path.exists(data_path):
        print('实际数据文件不存在，跳过真实文件基准测试')
        return

    print(f'文件大小: {os.path.getsize(data_path) / 1024 / 1024:.1f}MB')
    print()

    # --- 冷启动 ---
    clear_cache()
    t0 = time.perf_counter()
    data = param_extract(data_path)
    t1 = time.perf_counter()
    cold = t1 - t0
    time_len = len(data.get('TIME', []))
    col_count = len(data)
    print(f'[冷启动] param_extract(): {cold:.3f}s')
    print(f'  行数: {time_len}, 列数: {col_count}')

    # --- 热缓存 ---
    t0 = time.perf_counter()
    data2 = param_extract(data_path)
    t1 = time.perf_counter()
    warm = t1 - t0
    print(f'[热缓存] param_extract(): {warm:.6f}s')

    # --- extract_time 委托 ---
    t0 = time.perf_counter()
    time_arr = extract_time(data_path)
    t1 = time.perf_counter()
    et = t1 - t0
    print(f'[委托]   extract_time(): {et:.6f}s')

    # --- DataContext 完整加载 ---
    from ftpa.gui.services import DataContext
    clear_cache()
    ctx = DataContext()
    t0 = time.perf_counter()
    try:
        ctx.load(data_path, excel_path)
        ok = True
    except Exception:
        ok = False
    t1 = time.perf_counter()
    full = t1 - t0
    print(f'[完整]   DataContext.load(): {full:.3f}s (ok={ok})')
    print(f'  行数: {ctx.get_row_count()}, 列数: {ctx.get_column_count()}')

    # --- 缓存统计 ---
    stats = _file_cache.stats()
    print(f'缓存统计: size={stats["size"]}, hits={stats["hits"]}, misses={stats["misses"]}')
    print()
    print('=== 性能摘要 ===')
    print(f'冷启动 param_extract: {cold:.3f}s')
    print(f'完整 DataContext.load: {full:.3f}s')
    print(f'热缓存命中: {warm:.6f}s ({cold / warm:.0f}x 加速)')
    print(f'extract_time 委托: {et:.6f}s (零额外 I/O)')


if __name__ == '__main__':
    main()
