"""
文件路径工具函数模块
提供项目文件路径搜索和解析功能
"""

from pathlib import Path
from ..constants import EXCEL_FILENAME


def resolve_excel_path(excel_path: str | None = None) -> str:
    """自动发现标签映射 Excel 文件（参数名.xlsx）。

    优先级：
      1. 如果用户提供了显式路径，优先使用（已存在则返回）
      2. 搜索 data/ 目录
      3. 搜索项目根目录
      4. 兜底返回 data/参数名.xlsx（即使文件不存在，让调用方报错）

    matlab/ 是迁移参考文件夹，不列入搜索路径。
    """
    project_root = Path(__file__).resolve().parents[2]

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
