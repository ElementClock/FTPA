"""
文件路径工具函数模块
提供项目文件路径搜索和解析功能
"""

import logging
import os
import sys
from pathlib import Path
from ..config import MAPPING_FILENAME  # P1-ARCH-2: 从顶层 config 导入，避免 utils 反向依赖 data

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[3]  # src/ftpa/utils/ → 项目根目录


def resolve_path(path_value: str | os.PathLike[str] | None, default_path: Path | None = None) -> str:
    """Resolve an input path relative to the project root when needed.

    行为（M10 修订）：
      - **用户传入具体路径**：依次按 ``绝对路径 → PROJECT_ROOT → CWD`` 解析；
        路径不存在时记录 warning 并原样返回（由调用方报错），**不再偷换文件**。
      - ``path_value is None`` 且提供 ``default_path``：直接使用默认文件，
        存在才返回解析结果，否则原样返回并告警。
      - ``path_value is None`` 且未提供 ``default_path``：在
        ``testdata / data / data/raw / data/processed / 项目根`` 下惰性发现首个
        数据文件（``*.txt``/``*.tsv``/``*.dat``），找不到返回空字符串。
    """
    # 用户显式传入的路径
    if path_value is not None:
        candidate = Path(path_value)
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

        logger.warning("resolve_path: 路径不存在，原样返回供调用方报错: %s", path_value)
        return str(path_value)

    # 显式请求默认文件
    if default_path is not None:
        candidate = Path(default_path)
        if candidate.exists():
            return str(candidate.resolve())
        logger.warning("resolve_path: 默认文件不存在: %s", default_path)
        return str(candidate)

    # 惰性发现首个数据文件（不再硬编码架次文件名）
    fallback_dirs = [PROJECT_ROOT / "testdata", PROJECT_ROOT / "data", PROJECT_ROOT / "data" / "raw", PROJECT_ROOT / "data" / "processed", PROJECT_ROOT]
    for folder in fallback_dirs:
        if not folder.exists():
            continue
        for pattern in ("*.txt", "*.tsv", "*.dat"):
            matches = sorted(folder.glob(pattern))
            for match in matches:
                if match.name.lower() in {"requirements.txt", "pyproject.toml", "readme.md"}:
                    continue
                return str(match.resolve())

    logger.warning("resolve_path: 未找到任何数据文件")
    return ""


def resolve_mapping_path(csv_path: str | None = None) -> str:
    """自动发现参数映射文件（参数名.csv，唯一输入）。

    查找顺序：
      1. 显式传入路径（已存在则返回）
      2. 打包版（frozen）：
         a. exe 同目录 参数名.csv（操作员可编辑，改映射无需重新打包）
         b. 内置于 ``sys._MEIPASS`` 的默认 参数名.csv
      3. 开发/源码环境：cwd → src/ftpa/data → testdata → data
      4. 兜底返回 src/ftpa/data/参数名.csv（不存在时由调用方降级）
    """
    project_root = Path(__file__).resolve().parents[3]  # src/ftpa/utils/ → 项目根目录

    # 1. 显式路径
    if csv_path:
        p = Path(csv_path)
        if p.is_absolute():
            if p.exists():
                return str(p.resolve())
        else:
            for base in (project_root, Path.cwd()):
                candidate = (base / p).resolve()
                if candidate.exists():
                    return str(candidate)

    search_dirs: list[Path] = []

    # 2. 打包版：exe 同目录外部覆盖优先，内置默认兜底
    if getattr(sys, "frozen", False):
        exe_parent = Path(sys.executable).resolve().parent
        search_dirs.append(exe_parent / MAPPING_FILENAME)
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            search_dirs.append(Path(meipass) / MAPPING_FILENAME)

    # 3. 开发/源码环境
    search_dirs += [
        Path.cwd() / MAPPING_FILENAME,
        project_root / "src" / "ftpa" / "data" / MAPPING_FILENAME,
        project_root / "testdata" / MAPPING_FILENAME,
        project_root / "data" / MAPPING_FILENAME,
    ]
    for d in search_dirs:
        candidate = d.resolve()
        if candidate.is_file():
            return str(candidate)

    # 4. 兜底（文件不存在，调用方据此降级）
    return str((project_root / "src" / "ftpa" / "data" / MAPPING_FILENAME).resolve())