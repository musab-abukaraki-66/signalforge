# Contributing to DataScope

## Setup

```bash
python -m venv .venv
python -m pip install -e ".[dev]"
```

## Before opening a pull request

```bash
ruff check .
ruff format --check .
pytest
```

CI runs the same three commands on Python 3.11 and 3.12.

## Principles

- **Never present planned work as implemented.** Update [docs/ROADMAP.md](docs/ROADMAP.md) when a milestone's exit criteria are actually met.
- **No data, secrets or local databases in git.** `data/` contents, `.env` and `*.duckdb` are ignored on purpose.
- **Define before you measure.** New metrics need an entry in [docs/BUSINESS_METRICS.md](docs/BUSINESS_METRICS.md) with source fields and grain.
- **Test what you add.** Prefer small, deterministic tests over large fixtures.
- **Keep it small.** Do not add dependencies or layers before a milestone needs them.

## Commits

Use short imperative messages, for example `feat: add order ingestion` or `docs: clarify GMV definition`.
