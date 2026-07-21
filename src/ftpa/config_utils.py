"""Project configuration helpers."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml


def load_project_config(config_path: str | os.PathLike[str] | None = None) -> dict[str, Any]:
    """Load YAML configuration from disk.

    The function resolves a path relative to the project root when needed and
    returns a dictionary suitable for runtime settings.
    """
    if config_path is None:
        config_path = Path(__file__).resolve().parents[2] / "config" / "config.yaml"

    config_file = Path(config_path)
    if not config_file.is_absolute():
        config_file = (Path.cwd() / config_file).resolve()

    if not config_file.exists():
        raise FileNotFoundError(f"配置文件不存在: {config_file}")

    with config_file.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}

    return data
