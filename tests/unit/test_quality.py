import duckdb
import pytest

from signalforge.config import ProjectConfig
from signalforge.demo.synthetic import generate
from signalforge.errors import DataQualityError
from signalforge.quality.checks import Check, run_checks
from signalforge.transformations.build import build_warehouse


def test_failing_error_check_raises():
    con = duckdb.connect(":memory:")
    con.execute("CREATE TABLE t AS SELECT 1 AS a UNION ALL SELECT 1")
    bad = Check(
        "unique:t(a)", "SELECT count(*) FROM (SELECT a FROM t GROUP BY a HAVING count(*) > 1)"
    )
    with pytest.raises(DataQualityError, match="unique:t"):
        run_checks(con, (bad,))


def test_warn_check_does_not_raise():
    con = duckdb.connect(":memory:")
    warn = Check("warn:x", "SELECT 3", severity="warn")
    results = run_checks(con, (warn,))
    assert results[0].violations == 3 and not results[0].passed


def test_build_fails_and_keeps_previous_db_when_data_is_corrupt(tmp_path):
    generate(tmp_path / "raw", n_orders=300, seed=2)
    config = ProjectConfig("t", "olist", tmp_path, tmp_path / "processed" / "sf.duckdb")
    build_warehouse(config)
    before = config.database_path.stat().st_mtime_ns
    items = tmp_path / "raw" / "olist_order_items_dataset.csv"
    lines = items.read_text().splitlines()
    cols = lines[1].split(",")
    cols[5] = "-5"  # negative price
    lines[1] = ",".join(cols)
    items.write_text("\n".join(lines) + "\n")
    with pytest.raises(DataQualityError, match="non_negative_money"):
        build_warehouse(config)
    assert config.database_path.stat().st_mtime_ns == before  # old warehouse untouched
