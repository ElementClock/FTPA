import subprocess
import sys
from pathlib import Path

import pytest


def test_main_entrypoint_dry_run():
    """测试通过 python -m ftpa.main --dry-run 入口运行（GUI 模式 dry-run）。

    CLI 模式（verify/chunked/analysis 等）已归档到 references/cli/，
    当前入口仅支持 GUI 模式，--dry-run 可在无头环境下验证入口可用。
    """
    repo_root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [sys.executable, "-m", "ftpa.main", "--dry-run"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    assert "dry run" in result.stdout.lower() or "ready" in result.stdout.lower()
