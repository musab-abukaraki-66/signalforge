import json

import pytest

from signalforge.models import late_delivery as ld
from signalforge.web_export import ORDER_COLUMNS, export_web


@pytest.fixture()
def bundle(warehouse, con, tmp_path):
    config, _ = warehouse
    model, meta, scored = ld.train_and_evaluate(ld.load_dataset(con))
    ld.save_artifacts(model, meta, scored, config.processed_dir / "models", "synthetic-demo")
    out = export_web(con, config.processed_dir, tmp_path / "b.json")
    return json.loads(out.read_text())


def test_bundle_is_labelled_and_consistent(bundle):
    assert bundle["meta"]["data_source"] == "synthetic-demo"
    assert len(bundle["orders"]) == bundle["meta"]["gold_rows"]["fact_order"]
    assert all(len(r) == len(ORDER_COLUMNS) for r in bundle["orders"][:50])
    assert bundle["expected"]["overview_all"]["orders"] > 0
    assert {"orders", "gmv"} <= set(bundle["forecast"])
    assert len(bundle["model"]["scored"]) == bundle["model"]["split"]["test"]["n"]
    assert all(q["passed"] or q["severity"] == "warn" for q in bundle["quality"])
