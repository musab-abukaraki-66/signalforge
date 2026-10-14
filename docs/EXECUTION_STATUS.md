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

## Completion sprint (2026-10-14)
- Added weekly demand forecast (`analytics/forecast.py`): chronological 8-week holdout, naive and 4-week-average baselines, damped-trend model, approximate intervals; dashboard reports ties/losses honestly.
- Dashboard now has 8 views incl. Trends & forecast, Data & quality (live re-run of all 37 checks, lineage, provenance, last build) and Definitions & methods (model cards); new visual system, mobile layout, focus rings, reduced-motion support. Browser-checked at 1400 px and 390 px: no exceptions, no horizontal scroll.
- Fixed: `SIGNALFORGE_DATA_DIR` now also moves the warehouse, so a real-data directory cannot overwrite the synthetic demo database.
- CI workflow now triggers on every push (it previously only ran on main/PRs, so it had never run on this branch).
- Real data: still not acquired. Additional official hosts tried this round (archive-beta.ics.uci.edu, uci-ics-mlr-prod.aws.uci.edu): 403. No cached copy on disk. No retail-profile pivot was built (nothing to validate it against).
- Screenshots in `docs/screenshots/` are of the synthetic demo and say so.
- Repo renamed by the owner to `musab-abukaraki-66/signalforge` (old `DATASCOPE` URLs redirect).

## Public web app and deployment (2026-10-14)
- `web/` Next.js 16 + TypeScript app: landing, live demo (6 sections, filters, decision room, forecast), CSV analyzer (parser, profiler, role-guided analysis, baselines, report/cleaned exports), methods page. Static prerender, security headers (CSP, no third-party loads), no backend.
- `signalforge export-web` exports the demo bundle; Vitest checks browser KPIs and decision-room outputs equal the Python values.
- Verified locally: lint, typecheck, 31 unit tests, production build, 70/70 Playwright checks at 1440 px and 390 px (`web/e2e/smoke.py`).
- Vercel: team has no projects; `create_project` and `create_git_project` both returned 403 (no permission to create projects). Deployed by the owner: https://datascope-zi2u.vercel.app/ (loads in the owner's browser; not testable from the build sandbox). Root `vercel.json` now defines a single public `web` service (Python deliberately excluded, no bindings). Unblock: create the project in the Vercel dashboard (Root Directory empty) or grant the connector project-creation rights, then deploy with `vercel --prod` from `web/`.

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

## Real-data acquisition attempts (2026-10-14, recovery task)
Outcome: **neither official dataset acquired; no real-data validation done.** Every attempt failed at the environment egress proxy (HTTP 403 on CONNECT), not at the source:
1. Olist, official Kaggle page and API download URL: 403. No Kaggle CLI, no `~/.kaggle`, no Kaggle credentials in the environment.
2. UCI Online Retail, official dataset page `archive.ics.uci.edu/dataset/352/online+retail`: 403.
3. UCI static download endpoint `archive.ics.uci.edu/static/public/352/online+retail.zip`: 403.
4. `ucimlrepo` package (installed from PyPI, which is reachable) calling the same UCI host: `ConnectionError`.
No mirrors were tried (provenance and licence cannot be verified). The UCI profile (retail sales semantics, forecasting instead of late delivery) was deliberately NOT built without data to validate it against.

## Unblock (one setting, then re-run the recovery prompt)
Environment settings > Network access > add `kaggle.com` and `archive.ics.uci.edu` under Allowed domains (https://code.claude.com/docs/en/cloud-environments#network-access). For Olist also add `KAGGLE_USERNAME` / `KAGGLE_KEY` as environment secrets. With UCI allowed, no credentials are needed. Alternative: place either official archive in the workspace.

## Exact next task
Follow the manual steps in `docs/DATASET_SETUP.md` to put the real Olist CSVs in a separate data dir, run `signalforge verify-raw`, then `signalforge build`, fix any schema or check failures that real data exposes, then re-run `reconcile`, `report` and `train` and review the real results.
