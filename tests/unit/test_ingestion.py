import shutil

import pytest

from signalforge.demo.synthetic import generate
from signalforge.errors import MissingInputError, SchemaError
from signalforge.ingestion.bronze import data_source, validate_inputs


@pytest.fixture()
def raw(tmp_path):
    generate(tmp_path, n_orders=200, seed=1)
    return tmp_path


def test_valid_inputs_pass(raw):
    validate_inputs(raw)
    assert data_source(raw) == "synthetic-demo"


def test_missing_file_fails_clearly(raw):
    (raw / "olist_orders_dataset.csv").unlink()
    with pytest.raises(MissingInputError, match="olist_orders_dataset.csv"):
        validate_inputs(raw)


def test_missing_column_fails_clearly(raw):
    path = raw / "olist_order_items_dataset.csv"
    path.write_text(path.read_text().replace("freight_value", "freight", 1))
    with pytest.raises(SchemaError, match="freight_value"):
        validate_inputs(raw)


def test_real_data_has_no_synthetic_marker(raw):
    (raw / "_SYNTHETIC_DEMO.txt").unlink()
    assert data_source(raw) == "olist"
    shutil.rmtree(raw)
