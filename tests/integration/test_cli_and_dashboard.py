import os
from pathlib import Path

import pytest

from signalforge import cli
from signalforge.models import late_delivery as ld


def test_cli_missing_database_exits_nonzero(tmp_path, capsys):
    cfg = tmp_path / "c.yaml"
    cfg.write_text(
        f"project_name: x\ndataset: y\ndata_dir: {tmp_path}\ndatabase_path: {tmp_path}/nope.duckdb\n"
    )
    assert cli.main(["--config", str(cfg), "report"]) == 1
    assert "signalforge build" in capsys.readouterr().err


def test_cli_build_fails_clearly_without_data(tmp_path, capsys):
    cfg = tmp_path / "c.yaml"
    cfg.write_text(
        f"project_name: x\ndataset: y\ndata_dir: {tmp_path}\ndatabase_path: {tmp_path}/db.duckdb\n"
    )
    assert cli.main(["--config", str(cfg), "build"]) == 1
    assert "missing required file" in capsys.readouterr().err


def test_dashboard_renders_without_exceptions(warehouse, con, monkeypatch):
    pytest.importorskip("streamlit")
    from streamlit.testing.v1 import AppTest

    config, _ = warehouse
    model, meta, scored = ld.train_and_evaluate(ld.load_dataset(con))
    ld.save_artifacts(model, meta, scored, config.processed_dir / "models", "synthetic-demo")
    monkeypatch.setenv("SIGNALFORGE_DB", str(config.database_path))
    monkeypatch.setenv("SIGNALFORGE_PROCESSED", str(config.processed_dir))
    app = Path(__file__).resolve().parents[2] / "src" / "signalforge" / "dashboard" / "app.py"
    at = AppTest.from_file(str(app), default_timeout=60).run()
    assert not at.exception, [e.value for e in at.exception]
    assert len(at.metric) >= 6
    assert os.environ["SIGNALFORGE_DB"]
