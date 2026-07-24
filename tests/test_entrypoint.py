import subprocess
import sys
from pathlib import Path


def test_main_entrypoint_via_module_flag():
    """测试通过 python -m ftpa.main 入口运行。"""
    repo_root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [sys.executable, "-m", "ftpa.main", "--mode", "verify", "--nrows", "1"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    assert "快速验证" in result.stdout or "列数:" in result.stdout
