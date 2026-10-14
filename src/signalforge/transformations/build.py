"""Bronze -> Silver -> Gold build. Business logic lives in ``sql/``; this only orchestrates."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import duckdb

from signalforge.config import ProjectConfig
from signalforge.ingestion.bronze import data_source, load_bronze
from signalforge.quality.checks import CheckResult, run_checks

log = logging.getLogger(__name__)
REPO_ROOT = Path(__file__).resolve().parents[3]
SQL_DIR = REPO_ROOT / "sql"
GOLD_TABLES = (
    "dim_date",
    "dim_customer",
    "dim_seller",
    "dim_product",
    "fact_order_item",
    "fact_payment",
    "fact_review",
    "fact_order",
    "mart_customer_rfm",
)


def run_sql_layer(con: duckdb.DuckDBPyConnection, layer: str, sql_dir: Path = SQL_DIR) -> None:
    con.execute(f"CREATE SCHEMA IF NOT EXISTS {layer}")
    for path in sorted((sql_dir / layer).glob("*.sql")):
        log.info("running %s", path.relative_to(sql_dir.parent))
        con.execute(path.read_text(encoding="utf-8"))


def build_warehouse(config: ProjectConfig, sql_dir: Path = SQL_DIR) -> dict:
    """Rebuild the whole warehouse from raw files. Raises on missing/invalid input or failed checks.

    Returns a run summary (also written to ``<processed>/run_summary.json``).
    """
    db_path = config.database_path
    db_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = db_path.with_suffix(".building")
    tmp_path.unlink(missing_ok=True)
    con = duckdb.connect(str(tmp_path))
    try:
        manifest = load_bronze(con, config.raw_dir, config.interim_dir / "bronze_manifest.json")
        run_sql_layer(con, "silver", sql_dir)
        run_sql_layer(con, "gold", sql_dir)
        results = run_checks(con)  # raises DataQualityError; the previous database stays intact
        source = data_source(config.raw_dir)
        con.execute("CREATE OR REPLACE TABLE gold.meta AS SELECT ? AS data_source", [source])
        gold_counts = {
            t: con.execute(f"SELECT count(*) FROM gold.{t}").fetchone()[0] for t in GOLD_TABLES
        }
        gold_dir = config.processed_dir / "gold"
        gold_dir.mkdir(parents=True, exist_ok=True)
        for table in GOLD_TABLES:
            con.execute(
                f"COPY gold.{table} TO '{gold_dir / (table + '.parquet')}' (FORMAT parquet)"
            )
    finally:
        con.close()
    db_path.unlink(missing_ok=True)
    tmp_path.replace(db_path)
    summary = {
        "data_source": source,
        "bronze_rows": {k: v["rows"] for k, v in manifest.items()},
        "gold_rows": gold_counts,
        "checks_total": len(results),
        "checks_failed_error": sum(
            1 for r in results if not r.passed and r.check.severity == "error"
        ),
        "warnings": {
            r.check.name: r.violations
            for r in results
            if not r.passed and r.check.severity == "warn"
        },
        "database": str(db_path),
        "gold_parquet_dir": str(gold_dir),
    }
    (config.processed_dir / "run_summary.json").write_text(json.dumps(summary, indent=2))
    log.info("build complete: %s", summary["gold_rows"])
    return summary


def format_results(results: list[CheckResult]) -> str:
    return "\n".join(
        f"{'PASS' if r.passed else 'FAIL'} [{r.check.severity}] {r.check.name} ({r.violations})"
        for r in results
    )
