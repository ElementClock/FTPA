"""
底层文件 I/O 操作（私有模块，不直接对外暴露）

提供 ZIP 解压和数据文件读取功能。
"""

import os
import logging
import zipfile
import tempfile
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def resolve_zip_file(filepath: str) -> tuple[str, bool]:
    """
    解析 ZIP 文件，返回实际可读的文件路径

    参数:
        filepath: 文件路径（可能是 .zip）

    返回:
        (readable_file, is_temp): 可读文件路径，是否为临时文件
    """
    if not filepath.lower().endswith('.zip'):
        return filepath, False

    # 解压到临时目录（取绝对路径，便于后续做路径逃逸校验）
    temp_dir = os.path.abspath(tempfile.mkdtemp())
    with zipfile.ZipFile(filepath, 'r') as zip_ref:
        non_dir = [info for info in zip_ref.infolist() if not info.is_dir()]
        if not non_dir:
            raise FileNotFoundError("ZIP 压缩包中未找到任何文件。")

        # ZIP 仅支持单文件数据包：记录被忽略的其余成员（L10）
        if len(non_dir) > 1:
            logger.info(
                "ZIP 含 %d 个数据成员，仅解压首个（%s），其余 %d 个被忽略",
                len(non_dir), non_dir[0].filename, len(non_dir) - 1,
            )

        info = non_dir[0]

        # 安全校验：防止 Zip Slip 路径遍历漏洞
        # ZIP 规范使用正斜杠，这里统一反斜杠后按组件精确判断
        member_name = info.filename.replace('\\', '/')
        parts = member_name.split('/')
        # 拒绝包含 ".." 上跳组件的文件名（精确匹配组件，避免误伤 my..file.txt）
        if any(part == '..' for part in parts):
            raise ValueError(
                f"ZIP 内文件名包含路径遍历序列 '..': {info.filename!r}"
            )
        # 拒绝绝对路径：Unix 风格 "/etc/passwd" 或 Windows 盘符 "C:\\evil"
        if member_name.startswith('/') or (
            len(member_name) >= 2 and member_name[1] == ':'
        ):
            raise ValueError(
                f"ZIP 内文件名为绝对路径: {info.filename!r}"
            )
        # 二次防御：拼接后的绝对路径必须落在 temp_dir 之内
        target_path = os.path.abspath(os.path.join(temp_dir, *parts))
        if target_path != temp_dir and not target_path.startswith(
            temp_dir + os.sep
        ):
            raise ValueError(
                f"ZIP 内文件名试图逃逸出解压目录: {info.filename!r}"
            )
        zip_ref.extract(info, temp_dir)
        return os.path.join(temp_dir, info.filename), True


def read_data_file(filepath: str) -> pd.DataFrame:
    """
    读取数据文件（支持 ZIP 和普通文本文件）

    优化策略：
    - 先读表头获取列名，为 TIME 列保留 str 类型，其余列声明 float64
    - 跳过 pandas 类型推断，减少 30-50% 解析时间
    - 若 dtype 声明失败（存在非数值列），自动回退到默认推断

    参数:
        filepath: 文件路径

    返回:
        DataFrame，列名为原始列名
    """
    readable_file, is_temp = resolve_zip_file(filepath)

    try:
        # 先读表头获取列名，构建 dtype 映射；编码 utf-8 失败后回退 gbk（L10）
        encoding = "utf-8"
        header: list[str] | None = None
        try:
            with open(readable_file, 'r', encoding='utf-8') as f:
                header_line = f.readline()
            header = header_line.strip().split('\t')
        except (UnicodeDecodeError, OSError):
            try:
                with open(readable_file, 'r', encoding='gbk') as f:
                    header_line = f.readline()
                header = header_line.strip().split('\t')
                encoding = "gbk"
            except (UnicodeDecodeError, OSError):
                logger.debug("表头编码探测失败（utf-8/gbk），使用默认类型推断", exc_info=True)

        dtype_map = {col: np.float64 for col in header if col != 'TIME'} if header else None

        try:
            if dtype_map is not None:
                df = pd.read_csv(readable_file, sep='\t', dtype=dtype_map, encoding=encoding)
            else:
                df = pd.read_csv(readable_file, sep='\t', encoding=encoding)
        except (ValueError, TypeError):
            # dtype 声明失败（存在非数值列），回退到默认推断
            logger.debug("dtype=float64 声明失败，回退到默认类型推断")
            df = pd.read_csv(readable_file, sep='\t', encoding=encoding)

        return df
    finally:
        # 清理临时文件
        if is_temp:
            import shutil
            temp_dir = os.path.dirname(readable_file)
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir, ignore_errors=True)
