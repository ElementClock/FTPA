"""
主程序：飞机性能操稳数据分析工具
支持多种运行模式：数据验证、分块读取、完整分析、统计分析
"""

import argparse
import logging
import os
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from ftpa.data_loader import param_extract, extract_time
    from ftpa.label_map import LabelMap
    from ftpa.batch_processor import _add_weight_cg
    from ftpa.statistics import compute_var_stats, show_group_stats, compute_takeoff_landing_stats
    from ftpa.plotting import plot_time_signals_interactive
    from ftpa.time_utils import select_time_window
    from ftpa.constants import CHUNK_SIZE
else:
    from .data_loader import param_extract, extract_time
    from .label_map import LabelMap
    from .statistics import compute_var_stats, show_group_stats, compute_takeoff_landing_stats
    from .plotting import plot_time_signals_interactive
    from .batch_processor import _add_weight_cg
    from .time_utils import select_time_window
    from .constants import CHUNK_SIZE


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_TXT_FILE = PROJECT_ROOT / "FTPD-AG600-007-QD-260509-G-1-飞机性能操稳-32.txt"
DEFAULT_EXCEL_FILE = PROJECT_ROOT / "matlab看飞测数据" / "参数名.xlsx"


def resolve_path(path_value: str | os.PathLike[str] | None, default_path: Path | None = None) -> str:
    """Resolve an input path relative to the project root when needed."""
    candidate = path_value
    if candidate is None:
        candidate = default_path or DEFAULT_TXT_FILE
    else:
        candidate = Path(candidate)
        if not candidate.is_absolute():
            for base in (PROJECT_ROOT, Path.cwd()):
                resolved = (base / candidate).resolve()
                if resolved.exists():
                    return str(resolved)
            candidate = (PROJECT_ROOT / candidate).resolve()
        else:
            candidate = candidate.resolve()

    if candidate.exists():
        return str(candidate)

    fallback_dirs = [PROJECT_ROOT / "data", PROJECT_ROOT / "data" / "raw", PROJECT_ROOT / "data" / "processed", PROJECT_ROOT]
    for folder in fallback_dirs:
        if not folder.exists():
            continue
        for pattern in ("*.txt", "*.csv", "*.tsv", "*.dat"):
            matches = sorted(folder.glob(pattern))
            for match in matches:
                if match.name.lower() in {"requirements.txt", "pyproject.toml", "readme.md"}:
                    continue
                return str(match.resolve())

    return str(candidate)


def _load_and_prepare(data_file, excel_file):
    """加载数据、标签映射、计算重量重心。返回 (data, lm)。"""
    txt_path = resolve_path(data_file, DEFAULT_TXT_FILE)
    excel_path = resolve_path(excel_file, DEFAULT_EXCEL_FILE)
    if not os.path.exists(excel_path):
        raise FileNotFoundError(f"标签映射文件不存在: {excel_path}")

    data = param_extract(txt_path)
    data['TIME'] = extract_time(txt_path)
    lm = LabelMap(excel_path)
    _add_weight_cg(data, lm)
    return data, lm, txt_path


def quick_verify(nrows=5, data_file: str | os.PathLike[str] | None = None):
    """
    快速验证模式：读取表头 + 前 nrows 行数据
    - 验证文件能否正常打开
    - 验证列数、分隔符是否正确
    - 查看数据样例
    """
    txt_path = resolve_path(data_file, DEFAULT_TXT_FILE)
    print(f"[快速验证] 读取文件前 {nrows} 行...")
    print(f"文件: {txt_path}")
    print("-" * 60)

    if not os.path.exists(txt_path):
        print("未找到数据文件，已启用友好占位模式。")
        print("请提供有效的数据文件路径，或将数据文件放在项目根目录或 data/ 目录下。")
        return pd.DataFrame({"TIME": ["00:00:00:000"], "VALUE": [0.0]})

    # 读取表头
    with open(txt_path, "r", encoding="utf-8") as f:
        header_line = f.readline().strip()
    columns = header_line.split("\t")
    print(f"列数: {len(columns)}")
    print(f"前10列: {columns[:10]}")
    print(f"后10列: {columns[-10:]}")
    print()

    # 读取前 nrows 行数据
    df = pd.read_csv(
        txt_path,
        sep="\t",
        nrows=nrows,
        dtype={0: str},  # TIME列作为字符串读入
    )

    print(f"数据形状: {df.shape}")
    print(f"TIME列样例: {df.iloc[:, 0].tolist()}")
    print()
    print("前3行数据（前5列）:")
    print(df.iloc[:3, :5].to_string())
    print()
    print("数据类型:")
    print(df.dtypes.head(10).to_string())

    return df


def read_chunked(chunksize=CHUNK_SIZE, max_chunks=None, data_file: str | os.PathLike[str] | None = None):
    """
    分块读取模式：逐块读取文件，避免内存爆炸
    - chunksize: 每块行数
    - max_chunks: 最大块数（None=全部）
    """
    txt_path = resolve_path(data_file, DEFAULT_TXT_FILE)
    print(f"[分块读取] chunksize={chunksize}, max_chunks={max_chunks}")
    print("-" * 60)

    # 先读取表头获取列名
    with open(txt_path, "r", encoding="utf-8") as f:
        columns = f.readline().strip().split("\t")

    total_rows = 0
    chunk_count = 0
    start_time = time.time()

    reader = pd.read_csv(
        txt_path,
        sep="\t",
        chunksize=chunksize,
        names=columns,
        skiprows=1,  # 跳过文件中的表头行（因为 names 已指定）
        dtype={0: str},  # TIME列作为字符串
        low_memory=False,  # 避免混合类型警告
    )

    for chunk in reader:
        chunk_count += 1
        total_rows += len(chunk)
        elapsed = time.time() - start_time
        rate = total_rows / elapsed if elapsed > 0 else 0
        print(f"  块 {chunk_count}: {len(chunk)} 行 | 累计 {total_rows} 行 | "
              f"耗时 {elapsed:.1f}s | 速率 {rate:.0f} 行/s")

        if max_chunks and chunk_count >= max_chunks:
            print(f"  达到最大块数限制 {max_chunks}，停止读取")
            break

    total_time = time.time() - start_time
    print(f"\n读取完成: 共 {total_rows} 行, {chunk_count} 块, 耗时 {total_time:.1f}s")
    print(f"平均速率: {total_rows / total_time:.0f} 行/s")

    return total_rows


def full_analysis(data_file: str | os.PathLike[str] | None = None, excel_file: str | os.PathLike[str] | None = None):
    """
    完整分析流程：
    1. 加载数据和标签映射
    2. 计算重量重心
    3. 绘制交互图表
    """
    print("=" * 70)
    print("完整分析流程")
    print("=" * 70)

    # 1-3. 加载数据、标签映射、计算重量重心
    print("\n[1/3] 加载数据、标签映射、计算重量重心...")
    start = time.time()
    data, lm, txt_path = _load_and_prepare(data_file, excel_file)
    print(f"  数据加载完成: {len(data['TIME'])} 行, {len(data)} 列")
    avg_w = np.mean(data.get('totalWeight', [0]))
    avg_cg = np.mean(data.get('relCg', [0]))
    print(f"  平均总重: {avg_w:.2f} kg | 平均重心: {avg_cg:.2f} %")
    print(f"  耗时: {time.time() - start:.2f}s")
    
    # 定义自定义统计函数
    def stats_func(t_start, t_end, time_vec, signals, labels):
        """自定义统计函数，对应 MATLAB myCustomAnalysis"""
        # 调用起降统计
        try:
            stats_str = compute_takeoff_landing_stats(t_start, t_end, data, lm)
            return [stats_str]
        except Exception as e:
            return [f"起降统计错误: {e}"]
    
    # 绘制信号
    signal_ids = [
        '无线电高度表决值',
        '指示空速表决值',
        '俯仰角表决值',
        '法向过载_I1'
    ]
    
    plot_time_signals_interactive(data, lm, signal_ids, stats_func=stats_func)


def interactive_view(data_file: str | os.PathLike[str] | None = None, excel_file: str | os.PathLike[str] | None = None):
    """启动可交互查看模式，展示多信号时间序列并支持窗口统计与穿越分析。"""
    print("=" * 70)
    print("交互式查看模式")
    print("=" * 70)

    data, lm, _ = _load_and_prepare(data_file, excel_file)

    def stats_func(t_start, t_end, time_vec, signals, labels):
        try:
            return [compute_takeoff_landing_stats(t_start, t_end, data, lm)]
        except Exception as e:
            return [f'起降统计错误: {e}']

    signal_ids = [
        '无线电高度表决值',
        '指示空速表决值',
        '俯仰角表决值',
        '法向过载_I1',
    ]

    plot_time_signals_interactive(data, lm, signal_ids, stats_func=stats_func)


def stats_analysis(data_file: str | os.PathLike[str] | None = None, excel_file: str | os.PathLike[str] | None = None):
    """
    统计分析流程：
    1. 加载数据
    2. 加载标签映射
    3. 计算重量重心
    4. 输出统计结果
    """
    data, lm, _ = _load_and_prepare(data_file, excel_file)

    print("=" * 70)
    print("统计分析流程")
    print("=" * 70)
    print(f"  数据加载完成: {len(data['TIME'])} 行, {len(data)} 列")
    print(f"  重量重心计算完成")

    # 输出统计结果
    start_t = '10:01:00.000'
    end_t = '10:02:00.000'
    
    print(f"\n统计时间区间: {start_t} - {end_t}")
    
    # 多变量统计
    compute_var_stats(
        data['TIME'], start_t, end_t,
        data['totalWeight'], '总重', 'start',
        data['relCg'], '重心', 'start',
        data['AirSpeed_vote'], '空速表决值', 'start',
        data['Theta_vote'], '俯仰角表决值', 'range'
    )


def launch_gui(dry_run: bool = False) -> int:
    """启动 PySide6 Qt GUI。"""
    try:
        from PySide6 import QtWidgets  # noqa: F401
    except Exception as exc:
        print(f"PySide6 未可用: {exc}")
        print("请先安装 PySide6，例如：pip install PySide6")
        return 0

    if __package__ in {None, ""}:
        from ftpa.gui.app import main as gui_main
    else:
        from .gui.app import main as gui_main
    return gui_main(dry_run=dry_run)


def main() -> int:
    # 日志初始化（兼容无包名直接运行）
    try:
        from .log_utils import setup_logging
    except ImportError:
        from log_utils import setup_logging
    setup_logging(log_file="ftpa.log")

    parser = argparse.ArgumentParser(description="飞机性能操稳数据分析工具")
    parser.add_argument(
        "--mode", "-m",
        choices=["verify", "chunked", "analysis", "stats", "interactive"],
        default=None,
        help="运行模式: verify=快速验证, chunked=分块读取, analysis=完整分析, stats=统计分析, interactive=交互式查看"
    )
    parser.add_argument(
        "--nrows", "-n",
        type=int,
        default=5,
        help="验证模式时读取的行数 (默认5)"
    )
    parser.add_argument(
        "--chunksize", "-c",
        type=int,
        default=CHUNK_SIZE,
        help="分块模式时每块行数 (默认10000)"
    )
    parser.add_argument(
        "--max-chunks", "-mxc",
        type=int,
        default=None,
        help="分块模式时最大块数 (默认全部)"
    )
    parser.add_argument(
        "--data-file",
        default=str(DEFAULT_TXT_FILE),
        help="输入数据文件路径"
    )
    parser.add_argument(
        "--excel-file",
        default=str(DEFAULT_EXCEL_FILE),
        help="标签映射 Excel 文件路径"
    )
    parser.add_argument(
        "--gui",
        action="store_true",
        help="启动 wxPython 图形界面"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="仅验证 GUI 启动路径，不打开窗口"
    )

    args = parser.parse_args()

    # 默认启动 GUI（无参数或仅 --gui）
    if args.gui or args.mode is None:
        return launch_gui(dry_run=args.dry_run)

    if args.mode == "verify":
        quick_verify(nrows=args.nrows, data_file=args.data_file)
    elif args.mode == "chunked":
        read_chunked(chunksize=args.chunksize, max_chunks=args.max_chunks, data_file=args.data_file)
    elif args.mode == "analysis":
        full_analysis(data_file=args.data_file, excel_file=args.excel_file)
    elif args.mode == "stats":
        stats_analysis(data_file=args.data_file, excel_file=args.excel_file)
    elif args.mode == "interactive":
        interactive_view(data_file=args.data_file, excel_file=args.excel_file)

    return 0


if __name__ == "__main__":
    main()
