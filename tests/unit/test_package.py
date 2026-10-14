import importlib

import pytest

import signalforge

SUBPACKAGES = ["ingestion", "quality", "transformations", "analytics", "models", "decision_engine"]


def test_version_is_semver_like():
    parts = signalforge.__version__.split(".")
    assert len(parts) == 3
    assert all(part.isdigit() for part in parts)


@pytest.mark.parametrize("name", SUBPACKAGES)
def test_subpackages_are_importable(name):
    assert importlib.import_module(f"signalforge.{name}")
