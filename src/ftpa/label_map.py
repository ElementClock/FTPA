"""
标签映射模块
对应 MATLAB: loadLabelMap.m
从 Excel 加载变量名与中文标签的映射关系
"""

import logging
import pandas as pd
from .utils import make_valid_name

logger = logging.getLogger(__name__)


class LabelMap:
    """
    变量名与中文标签的双向映射管理器
    
    对应 MATLAB 的 loadLabelMap 函数，提供：
    - get_label(var_name): 变量名 → 中文标签
    - get_var_name(label, mode='field'): 中文标签 → 变量名
    - list_all(): 列出所有映射
    - add(orig_name, label): 添加新映射
    """
    
    def __init__(self, excel_file: str):
        """
        从 Excel 文件加载映射表
        
        参数:
            excel_file: Excel 文件路径，前两列为"原始名称"和"中文名称"
        """
        # 读取 Excel
        df = pd.read_excel(excel_file)
        
        if df.shape[1] < 2:
            raise ValueError("Excel 文件至少需要两列：原始名称、中文名称")
        
        # 提取前两列，去除首尾空格，过滤空行
        orig = df.iloc[:, 0].astype(str).str.strip()
        label = df.iloc[:, 1].astype(str).str.strip()
        
        # 过滤空值
        valid_mask = (orig != '') & (orig != 'nan')
        orig = orig[valid_mask].tolist()
        label = label[valid_mask].tolist()
        
        # 生成字段名（与 MATLAB paramExtract 一致）
        field = [make_valid_name(name.replace('-', '_')) for name in orig]
        
        # 构建四个映射表
        self._orig2label = dict(zip(orig, label))
        self._field2label = dict(zip(field, label))
        self._label2orig = dict(zip(label, orig))
        self._label2field = dict(zip(label, field))
        
        # 保存原始列表用于 list_all
        self._orig_list = orig
        self._label_list = label
        self._field_list = field
    
    def get_label(self, var_name: str) -> str:
        """
        变量名 → 中文标签
        
        参数:
            var_name: 变量名（可以是原始名或字段名）
        
        返回:
            中文标签，若未找到则返回原名称
        """
        if var_name in self._field2label:
            return self._field2label[var_name]
        elif var_name in self._orig2label:
            return self._orig2label[var_name]
        else:
            logger.warning('变量 "%s" 未在映射表中找到，返回原名称。', var_name)
            return var_name
    
    def get_var_name(self, label: str, mode: str = 'field') -> str:
        """
        中文标签 → 变量名
        
        参数:
            label: 中文标签
            mode: 'field' 返回字段名（默认），'original' 返回原始名
        
        返回:
            变量名，若未找到则返回空字符串
        """
        if mode == 'original':
            mapping = self._label2orig
        elif mode == 'field':
            mapping = self._label2field
        else:
            raise ValueError("mode 必须为 'original' 或 'field'")
        
        if label in mapping:
            return mapping[label]
        else:
            logger.warning('中文标签 "%s" 未找到，返回空字符串。', label)
            return ''
    
    def list_all(self) -> pd.DataFrame:
        """
        列出所有映射关系
        
        返回:
            DataFrame，包含三列：原始名称、结构体字段名、中文标签
        """
        return pd.DataFrame({
            '原始名称': self._orig_list,
            '结构体字段名': self._field_list,
            '中文标签': self._label_list
        })
    
    def list_all_print(self):
        """打印所有映射关系（格式化输出）"""
        print(f"{'原始名称':<35} {'结构体字段名':<35} {'中文标签'}")
        print('-' * 90)
        for orig, field, label in zip(self._orig_list, self._field_list, self._label_list):
            print(f"{orig:<35} {field:<35} {label}")
    
    def add(self, orig_name: str, label: str):
        """
        添加新的映射关系
        
        参数:
            orig_name: 原始变量名
            label: 中文标签
        """
        field_name = make_valid_name(orig_name.replace('-', '_'))
        
        self._orig2label[orig_name] = label
        self._field2label[field_name] = label
        self._label2orig[label] = orig_name
        self._label2field[label] = field_name
        
        # 更新列表
        self._orig_list.append(orig_name)
        self._field_list.append(field_name)
        self._label_list.append(label)
