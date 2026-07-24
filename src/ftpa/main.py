"""
主程序：飞机性能操稳数据分析工具
CLI 入口 — 命令行参数解析与模式分发。

业务逻辑已提取到 pipeline.py，本模块仅保留 CLI 特有功能
（quick_verify、read_chunked）和 argparse 分发。
"""

import argparse
import logging
import os
import sys
import time
from pathlib import Path

import pandas as pd

from .utils.paths import resolve_path, DEFAULT_TXT_FILE, PROJECT_ROOT
from .pipeline import full_analysis, interactive_view, stats_analysis
from .constants import CHUNK_SIZE

logger = logging.getLogger(__name__)


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


def launch_gui(dry_run: bool = False) -> int:
    """启动 PySide6 Qt GUI。"""
    try:
        from PySide6 import QtWidgets  # noqa: F401
    except Exception as exc:
        print(f"PySide6 未可用: {exc}")
        print("请先安装 PySide6，例如：pip install PySide6")
        return 0

    from .gui.app import main as gui_main
    return gui_main(dry_run=dry_run)


def main() -> int:
    from .log_utils import setup_logging
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
        default=None,
        help="标签映射 Excel 文件路径（默认：自动发现 data/参数名.xlsx）"
    )
    parser.add_argument(
        "--gui",
        action="store_true",
        help="启动 PySide6 图形界面"
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
