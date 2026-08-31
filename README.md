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
| Offline / install | `vite-plugin-pwa` (Workbox) | app shell precached; the self-hosted Pyodide runtime is cached on first use |
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
docker compose up web                 # http://localhost:7100  (production build)
docker compose --profile dev up dev   # http://localhost:7100  (Vite + HMR)
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

## Installing it as a desktop app

The app is a PWA: users can install it and then run it with no network at all.
An **Install app** button appears in the header once the browser reports the app
as installable; Chrome/Edge also show an install icon in the address bar.

Once installed it opens in its own window, off the taskbar or Start menu, and
keeps working offline — the service worker precaches the app shell, and the
Pyodide runtime is cached the first time the page loads (`EngineBanner` boots the
engine on mount, so no analysis has to be run first). Expect that first load to
pull ~115 MB.

### The one hard requirement: a secure context

Browsers only register service workers — and only offer installation — over
**HTTPS**, or over `http://localhost` / `http://127.0.0.1`. A plain-HTTP LAN or
VPN address (`http://192.168.1.x:7100`, `http://100.x.x.x:7100`) silently gets
no service worker, no install prompt and no offline support.

So `docker compose up web` is installable on the machine running it, but serving
it to other PCs needs TLS in front. A **self-signed certificate does not work**:
browsers block service worker registration on a certificate error, which yields
an app that looks installable but has no offline capability. Use a real
certificate — a Cloudflare Tunnel, `tailscale serve`, or a reverse proxy with
Let's Encrypt.

### Behind a Cloudflare Tunnel

Point `cloudflared` at the container (`http://localhost:7100`); Cloudflare
terminates TLS with a valid certificate, which satisfies the secure-context
requirement. Two settings on the zone matter:

- **Rocket Loader must be off.** It rewrites `<script>` tags and breaks ES
  modules, which takes down both the worker and service worker registration.
- **Do not put a "Cache Everything" rule on `/sw.js`, `/index.html` or
  `/manifest.webmanifest`.** They are served `Cache-Control: no-cache` on
  purpose; edge-caching them pins users to a stale service worker.

Assets under `/pyodide/` and `/assets/` are immutable and safe to cache hard.

### Checking it worked

In Chrome on the client, open DevTools → Application:

- *Manifest* — no errors, all three icons resolve.
- *Service workers* — one worker, "activated and is running".
- *Cache storage* — `workbox-precache-*` after load, and `pyodide-0.26.4` once
  the engine has booted.

Then tick **Network → Offline** and reload: the app should come up normally.

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

- The Pyodide runtime is **vendored, not fetched from a CDN**: `scripts/fetch-pyodide.mjs`
  resolves the dependency closure of `micropip`/`numpy`/`pandas`/`scipy`/`statsmodels`
  from `pyodide-lock.json` (11 packages, ~115 MB), verifies each file's sha256 and
  bakes them into the image under `/pyodide/`. Nothing external is ever contacted,
  so the app works on a firewalled or air-gapped network.
- The first page load downloads that ~115 MB from *your* server; the service worker
  caches it, and every later run — including fully offline — is served from cache.
  Keep the version in `scripts/fetch-pyodide.mjs` and `frontend/vite.config.ts` in sync.
- Analyses run single-threaded in WASM; datasets above ~100k rows will be slow
  and the UI warns about it.
- PWA install icons in `frontend/public/icons/` are generated from
  `frontend/pwa-source/*.svg`; replace those sources and re-rasterise to rebrand.
