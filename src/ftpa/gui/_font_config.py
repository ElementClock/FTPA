"""Matplotlib 字体配置 —— 从 plotting.py 提取，供 GUI 使用。

此模块独立于 CLI plotting 模块，消除 GUI 对 CLI 的依赖。
"""

import threading

import matplotlib.pyplot as plt

_FONT_CONFIGURED = False
_FONT_CACHED = None
_FONT_LOCK = threading.Lock()


def configure_display_font():
    """配置 CJK 字体，惰性且线程安全。

    优先使用系统中文字体，否则回退到 DejaVu Sans。
    同时禁用路径简化以防止 matplotlib 自动丢弃数据点。
    """
    global _FONT_CONFIGURED, _FONT_CACHED
    with _FONT_LOCK:
        if _FONT_CONFIGURED:
            return _FONT_CACHED

        preferred_fonts = [
            'Microsoft YaHei Light',
            'Microsoft YaHei',
            'SimHei',
            'Arial Unicode MS',
            'Noto Sans CJK SC',
            'WenQuanYi Zen Hei',
            'DejaVu Sans',
        ]

        available_fonts = set()
        try:
            import matplotlib.font_manager as fm
            available_fonts = {font.name for font in fm.fontManager.ttflist}
        except Exception:
            available_fonts = set()

        selected_font = None
        for font_name in preferred_fonts:
            if font_name in available_fonts:
                selected_font = font_name
                break

        if selected_font is None:
            selected_font = 'DejaVu Sans'

        plt.rcParams['font.family'] = 'sans-serif'
        plt.rcParams['font.sans-serif'] = [selected_font, 'DejaVu Sans', 'Arial']
        plt.rcParams['axes.unicode_minus'] = False
        # 禁用路径简化，防止 matplotlib 自动丢弃数据点导致失真
        plt.rcParams['path.simplify'] = False
        plt.rcParams['path.simplify_threshold'] = 0.0
        _FONT_CACHED = selected_font
        _FONT_CONFIGURED = True
        return selected_font


# 向后兼容别名（plotting.py 原导出名）
_configure_display_font = configure_display_font
