"""
工具函数模块
对应 MATLAB: matlab.lang.makeValidName 等内置功能
"""

import re
from pathlib import Path


def make_valid_name(name: str) -> str:
    """
    将任意字符串转换为合法的 Python 标识符。
    等效于 MATLAB 的 matlab.lang.makeValidName()

    规则：
    - 将非字母数字字符替换为 '_'
    - 若以数字开头，前缀 'x'
    - 空字符串返回 'x'
    """
    if not name:
        return 'x'
    # 替换非字母数字字符为 '_'
    result = re.sub(r'[^a-zA-Z0-9_]', '_', name)
    # 若以数字开头，加前缀
    if result[0].isdigit():
        result = 'x' + result
    # 若全为空或下划线开头后无内容
    if not result or result == '_':
        result = 'x'
    return result


def column_to_field_name(raw_name: str) -> str:
    """
    将原始列名转换为结构体字段名。
    对应 MATLAB paramExtract.m 中的转换逻辑：
    1. 先将 '-' 替换为 '_'
    2. 再调用 makeValidName
    """
    temp = raw_name.replace('-', '_')
    return make_valid_name(temp)


EXCEL_FILENAME = "参数名.xlsx"


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
