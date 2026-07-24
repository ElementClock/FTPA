"""
文件工具模块
============

提供编码检测、路径安全校验和文件名清理功能。
"""

from __future__ import annotations

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)


def detect_encoding(
    file_path: str,
    sample_size: int = 32_768,
    fallback: str = "utf-8",
) -> str:
    """检测文件编码。

    优先使用 chardet 库自动检测，失败时回退到逐编码尝试。
    对中文编码（GBK/GB18030）有特殊优化，确保中文字符正确解码。

    Args:
        file_path: 文件路径。
        sample_size: 用于检测的样本字节数（默认 32KB，大样本提高准确性）。
        fallback: 检测失败时的默认编码。

    Returns:
        检测到的编码名称（如 'utf-8', 'gbk' 等）。
    """
    try:
        import chardet
    except ImportError:
        logger.debug("chardet 未安装，使用逐编码尝试方式")
        return _try_encodings(file_path, fallback)

    try:
        with open(file_path, "rb") as f:
            raw = f.read(sample_size)
        if not raw:
            return fallback
        result = chardet.detect(raw)
        encoding = result.get("encoding")
        confidence = result.get("confidence", 0)

        # chardet 有时返回 'ascii'，实际兼容 utf-8
        if encoding and encoding.lower() in ("ascii", "iso-8859-1"):
            encoding = "utf-8"

        # 高置信度直接返回，但需验证中文解码是否正确
        if encoding and confidence >= 0.7:
            if _validate_encoding(file_path, encoding):
                return encoding
            logger.debug(
                "chardet 返回 %s (置信度 %.2f) 但验证失败，回退到逐编码尝试",
                encoding, confidence,
            )
            return _try_encodings(file_path, fallback)

        # 置信度不足：优先尝试中文编码
        logger.debug("chardet 置信度 %.2f 过低，使用中文编码优先策略", confidence)
        return _try_encodings_chinese_first(file_path, fallback)
    except OSError as e:
        logger.warning("编码检测失败: %s，回退到 %s", e, fallback)
        return fallback


def _validate_encoding(file_path: str, encoding: str, check_size: int = 4096) -> bool:
    """验证编码是否能正确解码文件中的中文字符。

    如果文件包含 CJK 字符且用该编码能正确解码，返回 True；
    如果文件不包含 CJK 字符，仅验证不抛异常即返回 True。

    Args:
        file_path: 文件路径。
        encoding: 待验证的编码。
        check_size: 验证时读取的字符数。

    Returns:
        编码验证是否通过。
    """
    try:
        with open(file_path, "r", encoding=encoding) as f:
            content = f.read(check_size)
    except (UnicodeDecodeError, UnicodeError):
        return False

    # 检测是否包含乱码特征（连续替换字符 U+FFFD 或无效代理区字符）
    garbled_count = content.count("\ufffd")
    if garbled_count > 5:
        logger.debug("编码 %s 产生 %d 个替换字符，可能不正确", encoding, garbled_count)
        return False

    return True


def _try_encodings_chinese_first(
    file_path: str,
    fallback: str = "utf-8",
) -> str:
    """中文编码优先的逐编码尝试。

    对中文 CSV 文件，优先尝试 GBK/GB18030 等中文编码，
    并验证解码后是否包含有效的 CJK 字符。

    Args:
        file_path: 文件路径。
        fallback: 全部失败时的默认编码。

    Returns:
        检测到的编码名称。
    """
    # 中文编码优先列表
    chinese_encodings = ["gb18030", "gbk", "gb2312", "utf-8", "utf-8-sig", "big5"]
    # 通用编码列表
    general_encodings = ["latin1", "cp1252"]

    # 第一轮：寻找能产生有效 CJK 字符的编码
    best_encoding = None
    best_cjk_count = 0

    for enc in chinese_encodings:
        try:
            with open(file_path, "r", encoding=enc) as f:
                sample = f.read(4096)
            # 统计 CJK 字符数
            cjk_count = sum(
                1 for c in sample
                if ("\u4e00" <= c <= "\u9fff"      # CJK Unified Ideographs
                    or "\u3400" <= c <= "\u4dbf"    # CJK Extension A
                    or "\uf900" <= c <= "\ufaff"    # CJK Compatibility Ideographs
                    or "\u3000" <= c <= "\u303f"    # CJK Symbols and Punctuation
                    or "\uff00" <= c <= "\uffef")   # Fullwidth Forms
            )
            # 无替换字符（乱码）
            if "\ufffd" not in sample:
                if cjk_count > best_cjk_count:
                    best_cjk_count = cjk_count
                    best_encoding = enc
                elif cjk_count == 0 and best_encoding is None:
                    # 没有 CJK 但也没乱码，可能是纯 ASCII/英文文件
                    best_encoding = enc
        except (UnicodeDecodeError, UnicodeError):
            continue

    if best_encoding is not None:
        return best_encoding

    # 第二轮：回退到通用编码
    for enc in general_encodings:
        try:
            with open(file_path, "r", encoding=enc) as f:
                f.read(1024)
            return enc
        except (UnicodeDecodeError, UnicodeError):
            continue

    return fallback


def _try_encodings(
    file_path: str,
    fallback: str = "utf-8",
    encodings: Optional[list[str]] = None,
) -> str:
    """逐编码尝试读取文件头部来检测编码。"""
    if encodings is None:
        encodings = ["utf-8", "gbk", "gb2312", "gb18030", "latin1"]
    for enc in encodings:
        try:
            with open(file_path, "r", encoding=enc) as f:
                f.read(1024)
            return enc
        except (UnicodeDecodeError, UnicodeError):
            continue
    return fallback


def is_safe_path(base_path: str, user_path: str) -> bool:
    """检查用户路径是否在基础路径内，防止路径遍历攻击。

    Args:
        base_path: 基础目录的绝对路径。
        user_path: 用户提供的路径。

    Returns:
        True 表示路径安全（在基础路径内）。
    """
    try:
        abs_user = os.path.abspath(os.path.normpath(user_path))
        abs_base = os.path.abspath(base_path)
        return abs_user.startswith(abs_base + os.sep) or abs_user == abs_base
    except (TypeError, ValueError):
        return False


def sanitize_filename(filename: str) -> str:
    """清理文件名中的非法字符。

    Args:
        filename: 原始文件名。

    Returns:
        清理后的安全文件名。
    """
    illegal_chars = '<>:"/\\|?*'
    for ch in illegal_chars:
        filename = filename.replace(ch, "_")
    # 去除首尾空白和点号
    filename = filename.strip(" .")
    if not filename:
        filename = "unnamed"
    return filename
