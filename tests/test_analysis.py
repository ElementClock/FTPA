"""
测试 analysis 子包
"""

import numpy as np
import pandas as pd
import pytest

from ftpa.analysis.interface import AnalysisInterface, AnalysisResult
from ftpa.analysis.plugin_manager import PluginManager, PluginConfig
from ftpa.analysis.utils import (
    merge_continuous_time_periods,
    find_threshold_crossings,
    compute_statistics,
)


class TestAnalysisResult:
    """AnalysisResult 数据类测试。"""

    def test_default_values(self):
        r = AnalysisResult()
        assert r.text_engine == ""
        assert r.errors == []
        assert r.df is None

    def test_with_values(self):
        r = AnalysisResult(text_engine="report", errors=["err1"])
        assert r.text_engine == "report"
        assert len(r.errors) == 1


class TestPluginManager:
    """PluginManager 测试。"""

    def _make_plugin(self, name):
        """创建简单测试插件。"""
        class SimplePlugin(AnalysisInterface):
            def analyze(self, df, progress_callback=None):
                return {"name": name, "rows": len(df)}

            def generate_text(self, analysis_result):
                return f"[{name}] rows={analysis_result['rows']}"
        return SimplePlugin()

    def test_register_and_execute(self):
        pm = PluginManager()
        pm.register("a", self._make_plugin("a"), PluginConfig("a", priority=10))
        df = pd.DataFrame({"x": [1, 2, 3]})
        results = pm.execute_analysis(df)
        assert "a" in results
        assert results["a"]["rows"] == 3

    def test_dependency_order(self):
        pm = PluginManager()
        pm.register("a", self._make_plugin("a"), PluginConfig("a", priority=10, dependencies=["b"]))
        pm.register("b", self._make_plugin("b"), PluginConfig("b", priority=5))
        order = pm._execution_order()
        assert order.index("b") < order.index("a")

    def test_generate_reports(self):
        pm = PluginManager()
        pm.register("a", self._make_plugin("a"), PluginConfig("a", priority=10))
        df = pd.DataFrame({"x": [1]})
        results = pm.execute_analysis(df)
        reports = pm.generate_reports(results)
        assert "a" in reports
        assert "rows=1" in reports["a"]

    def test_unregister(self):
        pm = PluginManager()
        pm.register("a", self._make_plugin("a"), PluginConfig("a"))
        assert pm.unregister("a")
        assert not pm.unregister("a")


class TestAnalysisUtils:
    """分析辅助函数测试。"""

    def test_merge_periods_empty(self):
        assert merge_continuous_time_periods([]) == []

    def test_merge_periods_continuous(self):
        periods = [(0.0, 1.0), (1.5, 2.0)]
        merged = merge_continuous_time_periods(periods, gap_threshold=1.0)
        assert len(merged) == 1
        assert merged[0] == (0.0, 2.0)

    def test_merge_periods_separate(self):
        periods = [(0.0, 1.0), (5.0, 6.0)]
        merged = merge_continuous_time_periods(periods, gap_threshold=1.0)
        assert len(merged) == 2

    def test_find_crossings_up(self):
        values = np.array([0.0, 0.5, 1.0, 0.5, 1.5])
        crossings = find_threshold_crossings(values, 0.8, "up")
        assert 1 in crossings  # 0.5 → 1.0 上穿 0.8

    def test_find_crossings_down(self):
        values = np.array([2.0, 1.0, 0.5, 1.0, 0.0])
        crossings = find_threshold_crossings(values, 0.8, "down")
        assert 1 in crossings

    def test_compute_statistics(self):
        values = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        stats = compute_statistics(values)
        assert stats["mean"] == 3.0
        assert stats["min"] == 1.0
        assert stats["max"] == 5.0
        assert stats["count"] == 5

    def test_compute_statistics_empty(self):
        stats = compute_statistics(np.array([]))
        assert stats["count"] == 0


class TestSystemAnalyzer:
    """SystemAnalyzer 端到端测试。"""

    def test_analyze_with_dict(self):
        from ftpa.analysis import SystemAnalyzer
        analyzer = SystemAnalyzer()
        data = {"发动机转速": np.array([0.0, 50.0, 70.0, 80.0, 60.0, 30.0])}
        results = analyzer.analyze(data)
        # 至少有 engine 插件的结果
        assert "engine" in results

    def test_analyze_empty_data(self):
        from ftpa.analysis import SystemAnalyzer
        analyzer = SystemAnalyzer()
        results = analyzer.analyze({})
        assert results == {}

    def test_analyze_with_dataframe(self):
        from ftpa.analysis import SystemAnalyzer
        analyzer = SystemAnalyzer()
        df = pd.DataFrame({"发动机转速": [0.0, 50.0, 70.0]})
        results = analyzer.analyze(df)
        assert "engine" in results
