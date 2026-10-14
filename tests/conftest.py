"""Shared fixtures: a small synthetic warehouse built once per test session."""

import duckdb
import pytest

from signalforge.config import ProjectConfig
from signalforge.demo.synthetic import generate
from signalforge.transformations.build import build_warehouse


@pytest.fixture(scope="session")
def warehouse(tmp_path_factory):
    data_dir = tmp_path_factory.mktemp("data")
    generate(data_dir / "raw", n_orders=2500, seed=11)
    config = ProjectConfig("test", "olist", data_dir, data_dir / "processed" / "sf.duckdb")
    summary = build_warehouse(config)
    return config, summary


@pytest.fixture()
def con(warehouse):
    config, _ = warehouse
    connection = duckdb.connect(str(config.database_path), read_only=True)
    yield connection
    connection.close()
