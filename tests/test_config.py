from pathlib import Path

from ftpa.config_utils import load_project_config


def test_load_project_config_reads_expected_values():
    repo_root = Path(__file__).resolve().parents[1]
    config = load_project_config(repo_root / "config" / "config.yaml")

    assert config["data"]["chunk_size"] == 10000
    assert config["data"]["trim_head"] == 50
    assert config["data"]["trim_tail"] == 50
    assert config["output"]["log_dir"] == "logs"
