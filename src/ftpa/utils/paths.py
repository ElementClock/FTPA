"""
文件路径工具函数模块
提供项目文件路径搜索和解析功能
"""

import os
from pathlib import Path
from ..constants import EXCEL_FILENAME


PROJECT_ROOT = Path(__file__).resolve().parents[3]  # src/ftpa/utils/ → 项目根目录
DEFAULT_TXT_FILE = PROJECT_ROOT / "FTPD-AG600-007-QD-260509-G-1-飞机性能操稳-32.txt"


def resolve_path(path_value: str | os.PathLike[str] | None, default_path: Path | None = None) -> str:
    """Resolve an input path relative to the project root when needed.

    搜索优先级：
      1. 如果 path_value 为 None，使用 default_path 或 DEFAULT_TXT_FILE
      2. 绝对路径直接使用
      3. 相对路径先按项目根目录解析，再按 CWD 解析
      4. 兜底搜索 data/ 子目录中的数据文件
    """
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

    fallback_dirs = [PROJECT_ROOT / "testdata", PROJECT_ROOT / "data", PROJECT_ROOT / "data" / "raw", PROJECT_ROOT / "data" / "processed", PROJECT_ROOT]
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


def resolve_excel_path(excel_path: str | None = None) -> str:
    """自动发现标签映射 Excel 文件（参数名.xlsx）。

    优先级：
      1. 如果用户提供了显式路径，优先使用（已存在则返回）
      2. 搜索 data/ 目录
      3. 搜索项目根目录
      4. 兜底返回 data/参数名.xlsx（即使文件不存在，让调用方报错）

    matlab/ 是迁移参考文件夹，不列入搜索路径。
    """
    project_root = Path(__file__).resolve().parents[3]  # src/ftpa/utils/ → 项目根目录

    # 1. 显式路径
    if excel_path:
        p = Path(excel_path)
        if p.is_absolute():
            if p.exists():
                return str(p.resolve())
        else:
            for base in (project_root, Path.cwd()):
                candidate = (base / p).resolve()
                if candidate.exists():
                    return str(candidate)

    # 2. 已知位置搜索
    search_dirs = [
        project_root / "data",
        project_root / "testdata",
        project_root / "src" / "ftpa" / "data",
        project_root,
    ]
    for d in search_dirs:
        candidate = (d / EXCEL_FILENAME).resolve()
        if candidate.exists():
            return str(candidate)

    # 3. 也搜一下 cwd（IDE 终端直接运行场景）
    for d in (Path.cwd() / "data", Path.cwd()):
        candidate = (d / EXCEL_FILENAME).resolve()
        if candidate.exists():
            return str(candidate)

    # 4. 兜底
    return str((project_root / "data" / EXCEL_FILENAME).resolve())
