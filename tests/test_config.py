"""FTPA 配置系统测试。"""
from __future__ import annotations

import dataclasses
import tempfile
from pathlib import Path

import pytest

from ftpa.config import (
    Config,
    ZoomConfig,
    PlotConfig,
    DataConfig,
    GuiConfig,
    load_config,
    _merge_toml_into_config,
    CONFIG,
)


# ── TestConfigDefaults ──


class TestConfigDefaults:
    """验证所有默认值与原始硬编码值一致。"""

    def test_zoom_defaults(self):
        z = ZoomConfig()
        assert z.min_span == 1.0
        assert z.factor_in == 0.92
        assert z.factor_out == 1.087

    def test_plot_defaults(self):
        p = PlotConfig()
        assert p.y_margin_ratio == 0.05
        assert p.downsample_threshold == 3000
        assert p.downsample_target == 1500

    def test_data_defaults(self):
        d = DataConfig()
        assert d.trim_head == 50
        assert d.trim_tail == 50
        assert d.cache_max_size == 5

    def test_gui_defaults(self):
        g = GuiConfig()
        assert g.window_width == 1400
        assert g.window_height == 860

    def test_config_defaults(self):
        c = Config()
        assert c.zoom == ZoomConfig()
        assert c.plot == PlotConfig()
        assert c.data == DataConfig()
        assert c.gui == GuiConfig()


# ── TestConfigFrozen ──


class TestConfigFrozen:
    """验证 frozen=True 防止修改。"""

    def test_zoom_frozen(self):
        z = ZoomConfig()
        with pytest.raises(dataclasses.FrozenInstanceError):
            z.min_span = 2.0

    def test_plot_frozen(self):
        p = PlotConfig()
        with pytest.raises(dataclasses.FrozenInstanceError):
            p.y_margin_ratio = 0.1

    def test_data_frozen(self):
        d = DataConfig()
        with pytest.raises(dataclasses.FrozenInstanceError):
            d.trim_head = 100

    def test_gui_frozen(self):
        g = GuiConfig()
        with pytest.raises(dataclasses.FrozenInstanceError):
            g.window_width = 1920

    def test_config_frozen(self):
        c = Config()
        with pytest.raises(dataclasses.FrozenInstanceError):
            c.zoom = ZoomConfig(min_span=5.0)


# ── TestConfigLoading ──


class TestConfigLoading:
    """测试配置加载各种场景。"""

    def test_no_file_returns_defaults(self):
        """无配置文件时返回全默认值。"""
        config = load_config(path=Path("/nonexistent/ftpa_config.toml"))
        assert config == Config()

    def test_valid_toml(self):
        """有效 TOML 文件正确覆盖默认值。"""
        with tempfile.NamedTemporaryFile(mode="wb", suffix=".toml", delete=False) as f:
            f.write(b'[zoom]\nmin_span = 2.0\n[plot]\ny_margin_ratio = 0.1\n')
            f.flush()
            config = load_config(path=Path(f.name))
        assert config.zoom.min_span == 2.0
        assert config.plot.y_margin_ratio == 0.1
        # 未覆盖的值保持默认
        assert config.zoom.factor_in == 0.92
        assert config.data.trim_head == 50

    def test_invalid_toml(self):
        """无效 TOML 文件时回退到默认值。"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
            f.write("this is not valid toml [[[")
            f.flush()
            config = load_config(path=Path(f.name))
        assert config == Config()

    def test_partial_config(self):
        """部分配置只覆盖指定字段。"""
        with tempfile.NamedTemporaryFile(mode="wb", suffix=".toml", delete=False) as f:
            f.write(b'[data]\ntrim_head = 100\n')
            f.flush()
            config = load_config(path=Path(f.name))
        assert config.data.trim_head == 100
        assert config.data.trim_tail == 50  # 未指定，保持默认
        assert config.zoom == ZoomConfig()  # 完全未覆盖

    def test_empty_toml(self):
        """空 TOML 文件返回全默认值。"""
        with tempfile.NamedTemporaryFile(mode="wb", suffix=".toml", delete=False) as f:
            f.write(b"")
            f.flush()
            config = load_config(path=Path(f.name))
        assert config == Config()

    def test_full_config(self):
        """完整配置覆盖所有值。"""
        with tempfile.NamedTemporaryFile(mode="wb", suffix=".toml", delete=False) as f:
            f.write(
                b'[zoom]\nmin_span = 2.0\nfactor_in = 0.8\nfactor_out = 1.25\n'
                b'[plot]\ny_margin_ratio = 0.1\ndownsample_threshold = 5000\ndownsample_target = 2500\n'
                b'[data]\ntrim_head = 100\ntrim_tail = 200\ncache_max_size = 10\n'
                b'[gui]\nwindow_width = 1920\nwindow_height = 1080\n'
            )
            f.flush()
            config = load_config(path=Path(f.name))
        assert config.zoom == ZoomConfig(min_span=2.0, factor_in=0.8, factor_out=1.25)
        assert config.plot == PlotConfig(y_margin_ratio=0.1, downsample_threshold=5000, downsample_target=2500)
        assert config.data == DataConfig(trim_head=100, trim_tail=200, cache_max_size=10)
        assert config.gui == GuiConfig(window_width=1920, window_height=1080)


    def test_unknown_key_ignored_not_crash(self):
        """TOML 中拼写错误的键应被忽略而非导致整个配置回退。"""
        with tempfile.NamedTemporaryFile(mode="wb", suffix=".toml", delete=False) as f:
            # typo: min_spam instead of min_span; unknown_key is invalid
            f.write(b'[zoom]\nmin_spam = 9.0\nfactor_in = 0.5\n[plot]\nunknown_key = 99\n')
            f.flush()
            config = load_config(path=Path(f.name))
        # 有效的 factor_in 应被正确读取
        assert config.zoom.factor_in == 0.5
        # 无效的键应被忽略，使用默认值
        assert config.zoom.min_span == 1.0  # 默认值
        assert config.plot.y_margin_ratio == 0.05  # 默认值，unknown_key 被忽略


# ── TestModuleSingleton ──


class TestModuleSingleton:
    """验证模块级单例。"""

    def test_config_exists(self):
        """CONFIG 模块级单例存在。"""
        assert CONFIG is not None

    def test_config_is_config_instance(self):
        """CONFIG 是 Config 实例。"""
        assert isinstance(CONFIG, Config)

    def test_config_has_all_sub_configs(self):
        """CONFIG 包含所有子配置。"""
        assert isinstance(CONFIG.zoom, ZoomConfig)
        assert isinstance(CONFIG.plot, PlotConfig)
        assert isinstance(CONFIG.data, DataConfig)
        assert isinstance(CONFIG.gui, GuiConfig)
