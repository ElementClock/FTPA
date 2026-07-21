import subprocess
import sys
from pathlib import Path


def test_main_entrypoint_runs_via_script_path():
    repo_root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [sys.executable, str(repo_root / "src" / "ftpa" / "main.py"), "--mode", "verify", "--nrows", "1"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr or result.stdout
    assert "快速验证" in result.stdout or "列数:" in result.stdout
