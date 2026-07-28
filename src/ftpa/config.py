"""FTPA 全局配置管理。

提供 TOML 配置文件支持，无配置文件时使用默认值。
配置对象不可变（frozen dataclass），确保运行时一致性。
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ── TOML 解析兼容层 ──
try:
    import tomllib  # Python 3.11+
except ModuleNotFoundError:
    try:
        import tomli as tomllib  # pip install tomli (Python 3.10 fallback)
    except ModuleNotFoundError:
        tomllib = None  # type: ignore[assignment]


@dataclass(frozen=True)
class ZoomConfig:
    """缩放相关配置。"""
    min_span: float = 1.0
    factor_in: float = 0.92
    factor_out: float = 1.087


@dataclass(frozen=True)
class PlotConfig:
    """绘图相关配置。"""
    y_margin_ratio: float = 0.05
    downsample_threshold: int = 3000
    downsample_target: int = 1500


@dataclass(frozen=True)
class DataConfig:
    """数据加载相关配置。"""
    trim_head: int = 50
    trim_tail: int = 50
    cache_max_size: int = 5


@dataclass(frozen=True)
class GuiConfig:
    """GUI 界面相关配置。"""
    window_width: int = 1400
    window_height: int = 860


@dataclass(frozen=True)
class Config:
    """FTPA 全局配置（不可变）。"""
    zoom: ZoomConfig = field(default_factory=ZoomConfig)
    plot: PlotConfig = field(default_factory=PlotConfig)
    data: DataConfig = field(default_factory=DataConfig)
    gui: GuiConfig = field(default_factory=GuiConfig)


def _find_config_file() -> Path | None:
    """按优先级搜索配置文件。"""
    # 1. 用户级: ~/.ftpa/ftpa_config.toml
    user_config = Path.home() / ".ftpa" / "ftpa_config.toml"
    if user_config.is_file():
        return user_config
    # 2. 项目级: {PROJECT_ROOT}/ftpa_config.toml
    project_root = Path(__file__).resolve().parents[2]  # src/ftpa/ → 项目根
    project_config = project_root / "ftpa_config.toml"
    if project_config.is_file():
        return project_config
    return None


def _filter_known_fields(data: dict[str, Any], cls: type) -> dict[str, Any]:
    """过滤 TOML 子字典，仅保留目标 dataclass 的已知字段。

    防止拼写错误的键导致 TypeError 使整个配置回退为默认值。
    """
    from dataclasses import fields
    known = {f.name for f in fields(cls)}
    unknown = set(data.keys()) - known
    if unknown:
        logger.warning("配置文件中存在未知键 %s，已忽略", unknown)
    return {k: v for k, v in data.items() if k in known}


def _merge_toml_into_config(toml_data: dict[str, Any], config: Config) -> Config:
    """将 TOML 字典合并到 Config 默认值上，返回新的 Config 实例。"""
    zoom_kw = _filter_known_fields(toml_data.get("zoom", {}), ZoomConfig)
    plot_kw = _filter_known_fields(toml_data.get("plot", {}), PlotConfig)
    data_kw = _filter_known_fields(toml_data.get("data", {}), DataConfig)
    gui_kw = _filter_known_fields(toml_data.get("gui", {}), GuiConfig)

    return Config(
        zoom=ZoomConfig(**zoom_kw),
        plot=PlotConfig(**plot_kw),
        data=DataConfig(**data_kw),
        gui=GuiConfig(**gui_kw),
    )


def load_config(path: Path | None = None) -> Config:
    """加载配置。无配置文件时返回全默认值。"""
    config_path = path or _find_config_file()
    if config_path is None:
        logger.debug("未找到配置文件，使用默认值")
        return Config()

    if tomllib is None:
        logger.warning(
            "配置文件 %s 存在，但缺少 TOML 解析库（需 Python 3.11+ 或 pip install tomli），使用默认值",
            config_path,
        )
        return Config()

    try:
        with open(config_path, "rb") as f:
            toml_data = tomllib.load(f)
        config = _merge_toml_into_config(toml_data, Config())
        logger.info("已加载配置: %s", config_path)
        return config
    except Exception:
        logger.exception("加载配置文件 %s 失败，使用默认值", config_path)
        return Config()


# ── 模块级单例 ──
CONFIG = load_config()
