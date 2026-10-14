"""Command line entry point: ``signalforge <command>``."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

import duckdb

from signalforge.config import ConfigError, ProjectConfig, load_config
from signalforge.errors import PipelineError

DEFAULT_CONFIG = Path("configs/project.yaml")
EXAMPLE_CONFIG = Path("configs/project.example.yaml")


def _config(args) -> ProjectConfig:
    path = (
        Path(args.config)
        if args.config
        else (DEFAULT_CONFIG if DEFAULT_CONFIG.exists() else EXAMPLE_CONFIG)
    )
    return load_config(path)


def _connect(config: ProjectConfig) -> duckdb.DuckDBPyConnection:
    if not config.database_path.exists():
        raise PipelineError(
            f"database not found: {config.database_path}. Run `signalforge build` first."
        )
    return duckdb.connect(str(config.database_path), read_only=True)


def cmd_demo_data(args, config: ProjectConfig) -> None:
    from signalforge.demo.synthetic import generate
    from signalforge.schema import SYNTHETIC_MARKER, TABLES

    expected = [t.file for t in TABLES if (config.raw_dir / t.file).exists()]
    if expected and not (config.raw_dir / SYNTHETIC_MARKER).exists() and not args.force:
        raise PipelineError(
            f"{config.raw_dir} already holds non-synthetic dataset files; refusing to overwrite. "
            "Point SIGNALFORGE_DATA_DIR at a different directory, or pass --force."
        )
    counts = generate(config.raw_dir, n_orders=args.orders, seed=args.seed)
    print(f"Wrote SYNTHETIC demo CSVs to {config.raw_dir}: {counts}")


def cmd_verify_raw(args, config: ProjectConfig) -> None:
    from signalforge.ingestion.provenance import verify_raw

    record = verify_raw(config.raw_dir, config.interim_dir / "raw_provenance.json")
    for name, info in record["files"].items():
        print(
            f"{name}: {info['rows']} rows, {info['bytes']} bytes, sha256={info['sha256'][:16]}..."
        )
    print(f"Provenance written to {config.interim_dir / 'raw_provenance.json'}")


def cmd_build(args, config: ProjectConfig) -> None:
    from signalforge.transformations.build import build_warehouse

    print(json.dumps(build_warehouse(config), indent=2))


def cmd_reconcile(args, config: ProjectConfig) -> None:
    from signalforge.analytics.reconcile import reconcile

    con = _connect(config)
    rows = reconcile(con, config.raw_dir)
    for r in rows:
        status = "OK  " if r.ok else "DIFF"
        print(f"{status} {r.kpi}: gold={r.gold:.6f} independent={r.independent:.6f}")
    if not all(r.ok for r in rows):
        raise PipelineError("KPI reconciliation failed")


def cmd_report(args, config: ProjectConfig) -> None:
    from signalforge.analytics.findings import build_findings, render_markdown
    from signalforge.ingestion.bronze import data_source

    con = _connect(config)
    text = render_markdown(build_findings(con), data_source(config.raw_dir))
    out = config.processed_dir / "reports" / "findings.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    print(f"Wrote {out}")


def cmd_train(args, config: ProjectConfig) -> None:
    from signalforge.ingestion.bronze import data_source
    from signalforge.models import late_delivery as ld

    con = _connect(config)
    model, meta, scored = ld.train_and_evaluate(ld.load_dataset(con))
    paths = ld.save_artifacts(
        model, meta, scored, config.processed_dir / "models", data_source(config.raw_dir)
    )
    rep = meta["report"]
    print(f"chosen model: {rep['chosen_model']}  validation PR-AUC: {rep['validation_pr_auc']}")
    print(f"test: {json.dumps(rep['test'][rep['chosen_model']])}")
    print(f"baseline test: {json.dumps(rep['test']['baseline_prior'])}")
    print({k: str(v) for k, v in paths.items()})


def cmd_export_web(args, config: ProjectConfig) -> None:
    from signalforge.web_export import export_web

    out = export_web(_connect(config), config.processed_dir, Path(args.out))
    print(f"Wrote {out} ({out.stat().st_size / 1024:.0f} KB)")


def cmd_dashboard(args, config: ProjectConfig) -> None:
    import os
    import subprocess

    app = Path(__file__).parent / "dashboard" / "app.py"
    env = {
        **os.environ,
        "SIGNALFORGE_DB": str(config.database_path),
        "SIGNALFORGE_PROCESSED": str(config.processed_dir),
    }
    subprocess.run([sys.executable, "-m", "streamlit", "run", str(app)], check=True, env=env)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="signalforge", description="SIGNALFORGE pipeline")
    parser.add_argument("--config", help="path to project YAML (default configs/project.yaml)")
    sub = parser.add_subparsers(dest="command", required=True)
    demo = sub.add_parser("demo-data", help="write SYNTHETIC Olist-style CSVs to data/raw")
    demo.add_argument("--orders", type=int, default=6000)
    demo.add_argument("--seed", type=int, default=7)
    demo.add_argument("--force", action="store_true", help="overwrite non-synthetic files")
    demo.set_defaults(fn=cmd_demo_data)
    export = sub.add_parser("export-web", help="write the demo bundle for the public web app")
    export.add_argument("--out", default="web/public/demo/demo-bundle.json")
    export.set_defaults(fn=cmd_export_web)
    for name, fn, helptext in (
        ("verify-raw", cmd_verify_raw, "check real dataset files and record SHA-256 provenance"),
        ("build", cmd_build, "raw CSVs -> bronze/silver/gold, with quality checks"),
        ("reconcile", cmd_reconcile, "compare gold KPIs with an independent pandas calculation"),
        ("report", cmd_report, "write the findings report"),
        ("train", cmd_train, "train and evaluate the late-delivery model"),
        ("dashboard", cmd_dashboard, "launch the Streamlit dashboard"),
    ):
        sub.add_parser(name, help=helptext).set_defaults(fn=fn)
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    try:
        args.fn(args, _config(args))
    except (PipelineError, ConfigError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
