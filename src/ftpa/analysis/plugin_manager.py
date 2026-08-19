"""
插件管理器
==========

管理系统级分析插件的注册、依赖解析和串行执行。
与参考项目不同，本实现采用串行执行（FTPA 已有 QThread 管理后台）。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Callable, Optional, Any

import pandas as pd

from .interface import AnalysisInterface

logger = logging.getLogger(__name__)


@dataclass
class PluginConfig:
    """插件配置。"""

    name: str
    priority: int = 0
    dependencies: list[str] = field(default_factory=list)


class PluginManager:
    """分析插件管理器。

    管理插件的注册、依赖排序和串行执行。
    """

    def __init__(self) -> None:
        self._plugins: dict[str, tuple[AnalysisInterface, PluginConfig]] = {}

    def register(self, name: str, plugin: AnalysisInterface, config: PluginConfig) -> None:
        """注册分析插件。

        Args:
            name: 插件名称。
            plugin: 分析插件实例。
            config: 插件配置。
        """
        self._plugins[name] = (plugin, config)
        logger.debug("注册分析插件: %s (priority=%d, deps=%s)",
                     name, config.priority, config.dependencies)

    def unregister(self, name: str) -> bool:
        """注销插件。"""
        if name in self._plugins:
            del self._plugins[name]
            return True
        return False

    def _execution_order(self) -> list[str]:
        """按依赖关系和优先级计算执行顺序。"""
        sorted_names = sorted(
            self._plugins.keys(),
            key=lambda n: self._plugins[n][1].priority,
            reverse=True,
        )

        order: list[str] = []
        remaining = set(sorted_names)
        visited: set[str] = set()

        while remaining:
            ready = []
            for name in sorted(remaining, key=lambda n: self._plugins[n][1].priority, reverse=True):
                config = self._plugins[name][1]
                if all(dep in visited for dep in config.dependencies):
                    ready.append(name)

            if not ready:
                name = next(iter(remaining))
                logger.warning("检测到循环依赖，强制执行: %s", name)
                ready = [name]

            for name in ready:
                order.append(name)
                visited.add(name)
                remaining.discard(name)

        return order

    def execute_analysis(
        self,
        df: pd.DataFrame,
        progress_callback: Optional[Callable[[int, str], None]] = None,
    ) -> dict[str, Any]:
        """串行执行所有已注册插件的分析。"""
        order = self._execution_order()
        results: dict[str, Any] = {}
        total = len(order)

        for i, name in enumerate(order):
            plugin, config = self._plugins[name]
            if progress_callback:
                progress_callback(int((i / max(total, 1)) * 90), f"正在分析 {name}...")

            try:
                result = plugin.analyze(df, progress_callback=progress_callback)
                results[name] = result
                logger.debug("插件 %s 分析完成", name)
            except Exception as e:
                logger.error("插件 %s 分析失败: %s", name, e)
                results[name] = {"error": str(e)}

        if progress_callback:
            progress_callback(90, "分析完成")

        return results

    def generate_reports(self, analysis_results: dict) -> dict[str, str]:
        """从分析结果生成各插件的文本报告。"""
        reports: dict[str, str] = {}

        for name, (plugin, _) in self._plugins.items():
            result = analysis_results.get(name)
            if result is not None and "error" not in result:
                try:
                    reports[name] = plugin.generate_text(result)
                except Exception as e:
                    logger.error("插件 %s 报告生成失败: %s", name, e)
                    reports[name] = f"报告生成失败: {e}"

        return reports
