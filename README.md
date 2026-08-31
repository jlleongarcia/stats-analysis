# Stats Analysis

A Progressive Web App for statistical analysis of tabular data. Upload a CSV or
Excel file and run descriptive statistics, normality tests, t-tests,
non-parametric tests, ANOVA (one-way / Welch / two-way / repeated-measures /
ANCOVA), correlation, regression, chi-square and variance tests — **entirely in
your browser**. Nothing is uploaded to a server.

## How it works

| Layer | Tech | Notes |
|---|---|---|
| Compute | **Pyodide** (CPython → WASM) in a Web Worker | runs `numpy`, `pandas`, `scipy`, `statsmodels` |
| Statistics | **`stats_core`** — a framework-free Python package | same code runs under pytest on CPython and in Pyodide |
| UI | React + TypeScript + Vite | |
| Offline / install | `vite-plugin-pwa` (Workbox) | app shell precached; Pyodide + wheels runtime-cached |
| Persistence | IndexedDB via Dexie | datasets & saved analyses stay on your device |
| Charts | Vega-Lite | |

The browser and the test suite execute the **identical** statistical code: the
frontend installs the very wheel that `pytest` validates.

```
stats_core/          framework-free statistical implementations + registry
tests/               pytest suite (+ the sample .xls spreadsheets, gitignored)
frontend/            the PWA
scripts/copy-wheel.mjs  builds/copies the stats_core wheel into the frontend
Dockerfile              multi-stage: build wheel → build PWA → nginx
docker-compose.yml      `web` (prod) and `dev` (Vite HMR) services
```

## Quick start

### Docker (no toolchain needed)

```bash
docker compose up web            # http://localhost:8080  (production build)
docker compose --profile dev up dev   # http://localhost:5173  (Vite + HMR)
```

### Local

Prerequisites: Python ≥ 3.11 with [uv](https://docs.astral.sh/uv/), Node ≥ 20.

```bash
# 1. stats core: install deps and run the test suite
uv sync
uv run pytest

# 2. frontend
cd frontend
npm install
npm run dev          # `predev` builds + copies the stats_core wheel automatically
```

Build for production: `cd frontend && npm run build` → `frontend/dist/`.

## Testing the statistics

`tests/` contains a pytest suite that checks every registered test against direct
`scipy` / `statsmodels` calls, using 11 real sample spreadsheets (longitudinal
olive-oil chemistry). The spreadsheets themselves are gitignored; drop them into
`tests/` to run the data-backed checks (the suite skips gracefully without them).

```bash
uv run pytest -q
```

## Adding a statistical test

1. Implement `def my_test(frame, roles, params) -> TestResult` in the relevant
   `stats_core/*.py` module. Use `stats_core._util` helpers; raise `DataError`
   for bad inputs.
2. Append one `TestSpec(...)` to `REGISTRY` in `stats_core/registry.py`,
   declaring its `roles` (which columns it needs) and `params`.
3. Add a validation test in `tests/`.
4. `uv build --wheel` (or just `npm run dev` — it rebuilds the wheel).

The UI — role pickers, parameter controls, the guided flow, report export — is
generated from the registry, so no frontend change is required.

## Notes / limits

- First load downloads ~10–15 MB of Pyodide + scientific wheels; cached
  afterwards (works offline once cached).
- Analyses run single-threaded in WASM; datasets above ~100k rows will be slow
  and the UI warns about it.
- PWA install icons (`frontend/public/icons/icon-*.png`) are referenced by the
  manifest but not committed — add your own 192/512 px PNGs for a polished
  install experience.
