from pathlib import Path

import pytest

from signalforge.config import DATA_DIR_ENV, ConfigError, load_config

EXAMPLE = Path(__file__).resolve().parents[2] / "configs" / "project.example.yaml"


def test_example_config_loads(monkeypatch):
    monkeypatch.delenv(DATA_DIR_ENV, raising=False)
    config = load_config(EXAMPLE)
    assert config.project_name == "signalforge"
    assert config.raw_dir == Path("data") / "raw"
    assert config.processed_dir == Path("data") / "processed"


def test_env_overrides_data_dir(monkeypatch, tmp_path):
    monkeypatch.setenv(DATA_DIR_ENV, str(tmp_path))
    assert load_config(EXAMPLE).data_dir == tmp_path


def test_missing_keys_are_reported(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("project_name: x\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="dataset"):
        load_config(bad)


def test_missing_file_is_reported(tmp_path):
    with pytest.raises(ConfigError, match="not found"):
        load_config(tmp_path / "nope.yaml")


def test_non_mapping_is_rejected(tmp_path):
    bad = tmp_path / "list.yaml"
    bad.write_text("- a\n- b\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="mapping"):
        load_config(bad)
