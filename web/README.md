# SIGNALFORGE web app

Public interface: a labelled **synthetic** demo and an in-browser **CSV analyzer**. Next.js (App Router) + TypeScript, no backend, no database, no third-party scripts.

```bash
cd web
npm ci
npm run dev          # http://localhost:3000
npm run lint && npm run typecheck && npm test && npm run build
```

- **Demo data** is `public/demo/demo-bundle.json`, exported by the Python pipeline: `signalforge demo-data && signalforge build && signalforge train && signalforge export-web`. The browser recomputes KPIs from the bundled orders; `tests/demo.test.ts` checks they equal the Python values.
- **CSV analyzer** (`src/lib/csv.ts`, `profile.ts`, `analyze.ts`, `export.ts`): runs entirely in the browser, limits 10 MB / 200,000 rows, nothing uploaded or stored.
- **Browser tests:** `python e2e/smoke.py http://localhost:3000 [screenshot-dir]` (Playwright for Python; set `CHROMIUM_PATH` if needed). Covers desktop 1440 px and mobile 390 px.
- **Deploy:** the repository-root `vercel.json` declares this app as the `web` service (public at `/`). Import the repo in Vercel with the Root Directory left empty; no environment variables are required. The Python code is not a Vercel service.
