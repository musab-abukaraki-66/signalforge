import json

import pytest

from signalforge import cli
from signalforge.demo.synthetic import generate
from signalforge.errors import MissingInputError, PipelineError
from signalforge.ingestion.provenance import verify_raw
from signalforge.schema import SYNTHETIC_MARKER


def _real_looking(tmp_path):
    generate(tmp_path, n_orders=100, seed=3)
    (tmp_path / SYNTHETIC_MARKER).unlink()  # stands in for genuine files in structure tests only


def test_synthetic_directory_is_rejected(tmp_path):
    generate(tmp_path, n_orders=100, seed=3)
    with pytest.raises(PipelineError, match="synthetic-data marker"):
        verify_raw(tmp_path, tmp_path / "p.json")


def test_missing_and_empty_files_fail(tmp_path):
    _real_looking(tmp_path)
    (tmp_path / "olist_orders_dataset.csv").write_text("")
    with pytest.raises(PipelineError):
        verify_raw(tmp_path, tmp_path / "p.json")
    (tmp_path / "olist_orders_dataset.csv").unlink()
    with pytest.raises(MissingInputError):
        verify_raw(tmp_path, tmp_path / "p.json")


def test_provenance_records_hashes_and_rows(tmp_path):
    _real_looking(tmp_path)
    rec = verify_raw(tmp_path, tmp_path / "out" / "p.json")
    assert rec["files"]["olist_orders_dataset.csv"]["rows"] == 100
    assert len(rec["files"]["olist_orders_dataset.csv"]["sha256"]) == 64
    assert json.loads((tmp_path / "out" / "p.json").read_text())["license"].startswith(
        "CC BY-NC-SA"
    )


def test_demo_data_refuses_to_overwrite_real_files(tmp_path, monkeypatch):
    raw = tmp_path / "raw"
    raw.mkdir()
    _real_looking(raw)
    cfg = tmp_path / "c.yaml"
    cfg.write_text(
        f"project_name: x\ndataset: y\ndata_dir: {tmp_path}\ndatabase_path: {tmp_path}/d.duckdb\n"
    )
    monkeypatch.delenv("SIGNALFORGE_DATA_DIR", raising=False)
    assert cli.main(["--config", str(cfg), "demo-data"]) == 1
