"""Project configuration loading.

Configuration lives in a YAML file (see ``configs/project.example.yaml``). The data
directory can be overridden with the ``SIGNALFORGE_DATA_DIR`` environment variable so the
same config works on a laptop and in CI.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import yaml

DATA_DIR_ENV = "SIGNALFORGE_DATA_DIR"
REQUIRED_KEYS = ("project_name", "dataset", "data_dir", "database_path")


class ConfigError(ValueError):
    """Raised when the configuration file is missing keys or malformed."""


@dataclass(frozen=True)
class ProjectConfig:
    project_name: str
    dataset: str
    data_dir: Path
    database_path: Path

    @property
    def raw_dir(self) -> Path:
        return self.data_dir / "raw"

    @property
    def interim_dir(self) -> Path:
        return self.data_dir / "interim"

    @property
    def processed_dir(self) -> Path:
        return self.data_dir / "processed"


def load_config(path: str | Path) -> ProjectConfig:
    """Load and validate a project config file."""
    path = Path(path)
    if not path.is_file():
        raise ConfigError(f"config file not found: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ConfigError(f"config must be a mapping of keys to values: {path}")
    missing = [key for key in REQUIRED_KEYS if key not in data]
    if missing:
        raise ConfigError(f"config is missing required keys: {', '.join(missing)}")

    data_dir = Path(os.environ.get(DATA_DIR_ENV) or data["data_dir"])
    return ProjectConfig(
        project_name=str(data["project_name"]),
        dataset=str(data["dataset"]),
        data_dir=data_dir,
        database_path=Path(data["database_path"]),
    )
