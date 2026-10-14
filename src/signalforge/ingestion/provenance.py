"""Verify a raw directory holds the genuine dataset files and record their provenance.

This proves the files are present, non-empty, have the expected columns, and records their
SHA-256 hashes. It cannot prove the files came from Kaggle; that rests on how you obtained them.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import duckdb

from signalforge.errors import PipelineError
from signalforge.ingestion.bronze import _sha256, validate_inputs
from signalforge.schema import SYNTHETIC_MARKER, TABLES

SOURCE = {
    "dataset": "Brazilian E-Commerce Public Dataset by Olist",
    "url": "https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce",
    "license": "CC BY-NC-SA 4.0 (non-commercial, share-alike, attribution required)",
}


def verify_raw(raw_dir: Path, out_path: Path) -> dict:
    """Raise unless ``raw_dir`` has every required file, non-empty and with expected columns."""
    if (raw_dir / SYNTHETIC_MARKER).exists():
        raise PipelineError(
            f"{raw_dir} contains the synthetic-data marker; it is not the real dataset. "
            "Use a separate data directory for real files (SIGNALFORGE_DATA_DIR)."
        )
    validate_inputs(raw_dir)
    empty = [s.file for s in TABLES if s.required and (raw_dir / s.file).stat().st_size == 0]
    if empty:
        raise PipelineError(f"empty file(s): {', '.join(empty)}")
    con = duckdb.connect(":memory:")
    files = {}
    for spec in TABLES:
        path = raw_dir / spec.file
        rows = con.execute(
            "SELECT count(*) FROM read_csv(?, header=true, all_varchar=true)", [str(path)]
        ).fetchone()[0]
        files[spec.file] = {"bytes": path.stat().st_size, "rows": rows, "sha256": _sha256(path)}
    record = {
        **SOURCE,
        "verified_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "files": files,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(record, indent=2), encoding="utf-8")
    return record
