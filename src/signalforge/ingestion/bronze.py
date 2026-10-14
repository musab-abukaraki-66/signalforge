"""Bronze layer: load raw CSVs into DuckDB as text, unchanged, with a hash manifest.

Raw files are only read. Every column is loaded as VARCHAR so that no value is altered or
rejected at this stage; typing happens in silver, where failures are counted.
"""

from __future__ import annotations

import csv
import hashlib
import json
import logging
from pathlib import Path

import duckdb

from signalforge.errors import MissingInputError, SchemaError
from signalforge.schema import SYNTHETIC_MARKER, TABLES, TableSpec

log = logging.getLogger(__name__)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _header(path: Path) -> list[str]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return next(csv.reader(handle), [])


def validate_inputs(raw_dir: Path, specs: tuple[TableSpec, ...] = TABLES) -> None:
    """Fail clearly if a required file is missing or lacks an expected column."""
    missing = [s.file for s in specs if s.required and not (raw_dir / s.file).is_file()]
    if missing:
        raise MissingInputError(
            f"missing required file(s) in {raw_dir}: {', '.join(missing)}. "
            "See docs/DATASET_SETUP.md, or run `signalforge demo-data` for synthetic data."
        )
    for spec in specs:
        path = raw_dir / spec.file
        if not path.is_file():
            continue
        absent = [c for c in spec.columns if c not in _header(path)]
        if absent:
            raise SchemaError(f"{spec.file} is missing column(s): {', '.join(absent)}")


def data_source(raw_dir: Path) -> str:
    """'synthetic-demo' when the generator marker is present, else 'olist'."""
    return "synthetic-demo" if (raw_dir / SYNTHETIC_MARKER).exists() else "olist"


def load_bronze(
    con: duckdb.DuckDBPyConnection, raw_dir: Path, manifest_path: Path | None = None
) -> dict[str, dict]:
    """Load every present source file into ``bronze.<table>``; return the manifest."""
    validate_inputs(raw_dir)
    con.execute("CREATE SCHEMA IF NOT EXISTS bronze")
    manifest: dict[str, dict] = {}
    for spec in TABLES:
        path = raw_dir / spec.file
        if not path.is_file():
            continue
        cols = ", ".join(f'"{c}"' for c in spec.columns)
        con.execute(
            f"CREATE OR REPLACE TABLE bronze.{spec.name} AS SELECT {cols} FROM read_csv(?, "
            "header=true, all_varchar=true, sample_size=-1)",
            [str(path)],
        )
        rows = con.execute(f"SELECT count(*) FROM bronze.{spec.name}").fetchone()[0]
        manifest[spec.name] = {
            "file": spec.file,
            "bytes": path.stat().st_size,
            "sha256": _sha256(path),
            "rows": rows,
        }
        log.info("bronze.%s loaded: %d rows from %s", spec.name, rows, spec.file)
    if manifest_path is not None:
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest
