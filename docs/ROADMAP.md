# Roadmap

Each milestone has exit criteria that can be verified. A milestone is marked done only when all of them are met.

| # | Milestone | Status | Exit criteria |
|---|---|---|---|
| 1 | Repository and development foundation | **Done** | Package installs; unit and integration smoke tests pass; Ruff lint and format pass; CI workflow defined; docs written |
| 2 | Data ingestion and quality validation | Planned | Raw files load reproducibly with recorded hashes and row counts; schema, null, key and referential checks run and report; failing data fails the run |
| 3 | Staging models and analytical warehouse | Planned | Staging, intermediate and mart SQL build a DuckDB database from raw; keys and grain tested; one command rebuilds everything |
| 4 | Business analysis and KPI validation | Planned | Each KPI in BUSINESS_METRICS.md computed and reconciled against an independent calculation; written findings in `reports/` |
| 5 | Power BI dashboard | Planned | Report built on the marts; every number traceable to a metric definition; screenshots committed only from the real report |
| 6 | Predictive modelling and evaluation | Planned | Target and features defined without leakage; baseline and model compared on a later time window; limits documented |
| 7 | Decision intelligence and scenario analysis | Planned | Recommendation records with evidence and assumptions; scenarios labelled as what-ifs |
| 8 | Integrated demo, documentation and release | Planned | End-to-end run from raw data in documented steps; tagged release; README updated with real results only |

## Implemented today

- Package skeleton `datascope` and config loader.
- Tests, lint, formatting, CI.
- Documentation of scope, architecture, model, metrics, methodology and dataset setup.

## Next

Milestone 2: ingestion and data-quality validation.
