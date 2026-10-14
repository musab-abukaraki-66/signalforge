# Execution status (handoff note)

Last updated: 2026-10-14.

## Done and verified
- Rebrand to SIGNALFORGE (package `signalforge`, env var `SIGNALFORGE_DATA_DIR`, docs, metadata).
- Data engineering: bronze (text, unchanged, hashed manifest) -> silver (typed) -> gold (star schema + RFM mart) in DuckDB, Parquet export, 37 quality checks (32 blocking, 5 warnings), atomic build (a failed build leaves the previous warehouse intact).
- Analytics: single-definition KPIs, filters, breakdowns, cohorts, findings report, independent pandas reconciliation (all 6 KPIs match).
- Dashboard (Streamlit): Overview, Products and sellers, Delivery and experience, Customers, Decision Room, Definitions. Checked visually in headless Chromium and by `streamlit.testing`.
- Late-delivery model: leakage-free features at purchase time, chronological 60/20/20 split, baseline + 2 models, threshold chosen on validation, test metrics, calibration, segment errors, metadata JSON.
- Decision Room: holdout evidence vs assumption-based scenario, no invented costs or benefits.
- Power BI: documentation only, no `.pbix`.
- Tests: `pytest` (38 passing), `ruff check` and `ruff format --check` clean.

## Decisions
- Real Olist data could not be downloaded here (egress proxy returns 403 for kaggle.com and huggingface.co). Everything was run on a seeded SYNTHETIC generator (`signalforge demo-data`); every artifact is labelled as synthetic. No real finding is claimed anywhere.
- Source column names follow the public dataset description and are unconfirmed against the real files; ingestion fails loudly on a mismatch.
- Model reporting is honest: on the synthetic holdout the model beats the base-rate baseline only slightly (PR-AUC 0.134 vs 0.116). The generator was not tuned to flatter it.

## Known issues
- `review_id` uniqueness in the real data is unverified; silver de-duplicates on (review_id, order_id).
- The geolocation file is not ingested (not needed yet).
- No CI run observed yet (workflow updated but not pushed-and-run in this session unless noted in the final report).

## Real-data validation attempt (2026-10-14)
Blocked, not performed: no Kaggle CLI, no credentials, kaggle.com returns 403 from the egress policy. No real results exist. Added `signalforge verify-raw` (file/column/non-empty checks, SHA-256 provenance, rejects the synthetic marker) and a guard so `demo-data` cannot overwrite real files. Items still to verify on real data: review/order relationships, payment aggregation, undelivered/censored orders, KPI reconciliation populations, geolocation.

## Exact next task
Follow the manual steps in `docs/DATASET_SETUP.md` to put the real Olist CSVs in a separate data dir, run `signalforge verify-raw`, then `signalforge build`, fix any schema or check failures that real data exposes, then re-run `reconcile`, `report` and `train` and review the real results.
