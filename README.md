# SIGNALFORGE

**From Raw Data to Better Decisions.**

SIGNALFORGE is an end-to-end e-commerce intelligence platform: Data Engineering, Business Analysis, BI, Data Science and decision support in one reproducible, local-first system (Python, SQL, DuckDB, Parquet, scikit-learn, Streamlit).

![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white) ![License: MIT (code only)](https://img.shields.io/badge/license-MIT%20(code)-green) ![Status: working vertical slice](https://img.shields.io/badge/status-working%20slice-teal)

> **Honest status.** The full pipeline runs end to end, but **only on a seeded synthetic dataset** that mimics the Olist table layout. The real Olist files could not be downloaded when this was built (see [docs/DATASET_SETUP.md](docs/DATASET_SETUP.md)). Every number produced from synthetic data describes the generator, not a real business, and the warehouse, report and dashboard label it as such. The GitHub repository is still named `DATASCOPE`; renaming it is a manual step (Settings > General > Repository name).

## Public web app (try it, no install)

`web/` is a Next.js + TypeScript app: a labelled synthetic demo (KPIs, filters, data quality, forecast, decision room) and an **in-browser CSV analyzer** (profile, quality flags, guided charts and findings, baselines, JSON/CSV export). Your CSV never leaves the browser: no upload endpoint, no analytics, nothing stored. See [web/README.md](web/README.md). Run locally with `cd web && npm ci && npm run dev`.

**Live deployment: not yet.** The Vercel connector in the build environment could not create a project (HTTP 403), so no production URL exists. To deploy: Vercel dashboard > Add New Project > import `musab-abukaraki-66/DATASCOPE`, set Root Directory to `web`, and choose the branch that contains `web/` as the Production Branch (or merge it to `main`). No environment variables are needed.

![Web landing](docs/screenshots/web-landing.png)
![CSV analyzer](docs/screenshots/web-analyze.png)

## See it (Streamlit analyst dashboard)

Screenshots captured from the running app on **synthetic demo data** (not real findings):

| Overview | Trends & forecast |
|---|---|
| ![Overview](docs/screenshots/overview-synthetic.png) | ![Forecast](docs/screenshots/forecast-synthetic.png) |
| **Decision Room** | **Data & quality** |
| ![Decision Room](docs/screenshots/decision-room-synthetic.png) | ![Data and quality](docs/screenshots/data-quality-synthetic.png) |

Mobile (390 px): ![Mobile overview](docs/screenshots/mobile-overview-synthetic.png)

## The problem

Marketplace teams hold orders, payments, deliveries and reviews in separate tables. Headline numbers (revenue, order value, delivery performance) are often computed from inconsistent definitions, and dashboards rarely connect a finding to a defensible decision. SIGNALFORGE aims to show the full path: ingest raw data, validate it, model it, analyse it, visualise it, predict with it, and turn the result into decisions whose evidence and assumptions are explicit.

**Intended users:** marketplace and e-commerce analysts, operations and category managers, and data teams who need a reproducible reference for definitions, models and decision support.

## Five disciplines, one system

| Discipline | What exists today | Status |
|---|---|---|
| **Data Engineering** | Bronze (raw text + hash manifest) -> Silver (typed) -> Gold (star schema) in DuckDB, Parquet export, 37 quality checks, atomic builds | Implemented |
| **Business Analytics** | Single-definition KPIs, breakdowns, cohorts, weekly demand forecast (backtest vs naive and moving-average baselines), findings report with definition / period / n / limitation, independent reconciliation | Implemented |
| **Business Intelligence** | Streamlit dashboard, 8 views: Overview, Products, Delivery, Customers, Trends & forecast, Decision Room, Data & quality, Definitions & methods; Power BI handoff docs | Implemented; no `.pbix` |
| **Machine Learning** | Late-delivery risk model: purchase-time features, chronological split, baselines, calibration, segment errors | Implemented (synthetic data only) |
| **Decision Intelligence** | Decision Room: held-out evidence vs assumption-based what-ifs, no invented costs | Implemented |

## Architecture

```mermaid
flowchart LR
    A[Raw CSVs<br/>data/raw] --> B[Bronze<br/>text, hashed manifest]
    B --> C[Silver<br/>typed, de-duplicated]
    C --> D[(Gold<br/>facts, dims, marts)]
    C -. checks .-> Q{37 quality checks}
    D --> Q
    D --> E[KPIs and findings]
    D --> F[Streamlit dashboard]
    D --> G[Late-delivery model]
    G --> H[Decision Room]
    E --> H
    D --> I[Parquet for Power BI]
```

Details: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md), [docs/DATA_MODEL.md](docs/DATA_MODEL.md), [docs/BUSINESS_METRICS.md](docs/BUSINESS_METRICS.md), [docs/DECISION_METHODOLOGY.md](docs/DECISION_METHODOLOGY.md).

## Getting started

```bash
git clone https://github.com/musab-abukaraki-66/DATASCOPE.git && cd DATASCOPE
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
python -m pip install -e ".[dev]"
cp configs/project.example.yaml configs/project.yaml  # optional; the example works as-is
```

### Data

No data is committed. For the real Olist dataset follow [docs/DATASET_SETUP.md](docs/DATASET_SETUP.md) (check its licence yourself). To try the platform now, generate **synthetic** data:

```bash
signalforge demo-data      # writes invented Olist-style CSVs to data/raw
```

### Run the pipeline

```bash
signalforge verify-raw     # real data only: check files, record SHA-256 provenance
signalforge build          # raw -> bronze/silver/gold + quality checks (fails loudly on bad input)
signalforge reconcile      # gold KPIs vs an independent pandas calculation
signalforge report         # data/processed/reports/findings.md
signalforge train          # late-delivery model, metrics, metadata
signalforge dashboard      # Streamlit app
```

### Tests and quality checks

```bash
pytest
ruff check . && ruff format --check .
```

## The model and its limits

Target: delivered later than the estimated date. Prediction time: order placement; delivery timestamps, review data and approval time are excluded as post-outcome. Train/validation/test are chronological (60/20/20), preprocessing is fitted on train only, the threshold is chosen on validation, and results are compared with a base-rate baseline and a cross-state rule. On the synthetic holdout the model is only modestly better than the baseline (PR-AUC 0.134 vs 0.116); this is reported as is. Only delivered orders have a label, which biases the latest period.

## Repository structure

| Path | Purpose |
|---|---|
| `src/signalforge/` | `ingestion`, `quality`, `transformations`, `analytics`, `models`, `decision_engine`, `dashboard`, `demo`, `cli.py` |
| `sql/silver`, `sql/gold` | All transformation logic in SQL; grain stated per table |
| `data/` | `raw`, `interim`, `processed` (git-ignored) |
| `dashboards/power-bi/` | Power BI handoff (model, DAX measures, page plan) |
| `docs/` | Architecture, model, metrics, methodology, dataset setup, roadmap, execution status |
| `tests/` | Unit and integration tests (synthetic fixtures, no download needed) |

## Real data status

Real Olist data has **not** been loaded: every official route attempted (Kaggle, and four UCI hosts or tools) was denied by this environment's network policy. The real-data path (`verify-raw`, hashes, provenance in the app's Data & quality tab) exists and is tested on structure only. CI runs on every push (Python lint/tests/smoke run, plus a web job: lint, typecheck, unit tests, build).

## Limitations

- Not yet run on real data; schema assumptions are unconfirmed until then.
- GMV is item price only. Revenue, profit and costs are absent, so no ROI is computed anywhere.
- Findings are associations, never causal claims.
- No `.pbix`; no screenshots are committed.

## Roadmap and contributing

Milestones are tracked in [docs/ROADMAP.md](docs/ROADMAP.md); handoff state is in [docs/EXECUTION_STATUS.md](docs/EXECUTION_STATUS.md). Contribution guidance is in [CONTRIBUTING.md](CONTRIBUTING.md).

## License

[MIT](LICENSE). The licence of any dataset used is separate; see [docs/DATASET_SETUP.md](docs/DATASET_SETUP.md).
