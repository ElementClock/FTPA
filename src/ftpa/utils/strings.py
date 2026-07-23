"""
字符串工具函数模块
对应 MATLAB: matlab.lang.makeValidName 等内置功能
"""

import re


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
