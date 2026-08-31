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

### Local (development only)

Deployment never needs this — the image builds everything itself.
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

Running the frontend outside Docker also needs the Pyodide runtime in place:
`node scripts/fetch-pyodide.mjs` (once — it is gitignored, ~115 MB).

Note that `npm run dev` serves **no service worker** (`devOptions.enabled` is
false), so the install banner and offline mode only exist in the container build.

## Installing it

The app is a PWA. Installed, it opens in its own window and runs with **no
network at all** — every computation was always local, and once the service
worker has cached the Pyodide runtime there is nothing left to fetch.

A banner in the app offers to install it, with the right wording for whatever
browser the visitor is using. It can be dismissed, and the dismissal sticks.

### Before anything else: HTTPS

Browsers only register service workers — and only offer installation — over
**HTTPS**, or over `http://localhost`. A plain-HTTP LAN or VPN address
(`http://192.168.1.x:7100`) silently gets no service worker, no install prompt
and no offline support; DevTools reports it as *"Page is not served from a
secure origin"*. A self-signed certificate does not help either, because a
certificate error also blocks service worker registration.

So the container needs real TLS in front of it — a Cloudflare Tunnel pointed at
`http://localhost:7100` is enough.

### Per platform

| Platform | Browser | How to install | Works offline |
|---|---|---|---|
| Windows | Chrome, Edge | **Install** in the banner, or the install icon in the address bar | yes |
| Linux | Chrome, Edge | same | yes |
| macOS | Chrome, Edge | same | yes |
| macOS | Safari | *File → Add to Dock* | **no — see below** |
| Android | Chrome, Edge | **Install** in the banner | yes |
| iOS, iPadOS | Safari | *Share → Add to Home Screen* | yes |
| any | Firefox | not installable | n/a |

**Windows, Linux, macOS with Chrome or Edge** — the straightforward case. The
banner's **Install** button does it in one click; the app lands in the Start
menu, Launchpad or applications list and opens in its own window.

**macOS with Safari — use Chrome or Edge instead.** Safari 17's *Add to Dock*
does produce a standalone window, but it does not keep the Pyodide cache, so the
installed app cannot start without a network. That defeats the point, so the
banner tells Safari users on macOS to switch browsers rather than offering
instructions that lead to a broken install.

**iOS and iPadOS** — Safari is the only route and there is no install prompt on
the platform, so the banner shows the *Share → Add to Home Screen* steps.
Installing matters more here than elsewhere: WebKit evicts cached data after
about a week of disuse, and home-screen web apps are exempt, so installing is
what stops the runtime being thrown away and re-downloaded. Whether the engine
runs comfortably on a given iPhone is a separate question — Pyodide with scipy
and statsmodels is memory-hungry, and iOS kills tabs that exceed its limit.

**Firefox** has no PWA install on any desktop OS, so the banner stays hidden
there. The app still runs fine in the tab.

### The first load is large

Whichever platform, the first visit downloads roughly **115 MB** of Pyodide and
scientific packages. It starts automatically on page load — `EngineBanner` boots
the engine on mount, so nothing has to be run first — and a toast confirms once
it is cached. After that the app opens offline. Installed web apps on Apple
platforms get their own storage, so expect one repeat download after installing
there.

### Behind a Cloudflare Tunnel

Point `cloudflared` at `http://localhost:7100`. Two zone settings matter, and
both fail in ways that look like the app is simply broken:

- **Rocket Loader must be off.** It rewrites `<script>` tags and breaks ES
  modules, taking down the Pyodide worker and service worker registration.
- **No "Cache Everything" rule on `/sw.js`, `/index.html` or
  `/manifest.webmanifest`.** They are served `Cache-Control: no-cache` on
  purpose; edge-caching them pins users to a stale service worker. Everything
  under `/pyodide/` and `/assets/` is immutable and safe to cache hard.

### Checking it worked

In Chrome on the client, DevTools → Application:

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
  `apple-touch-icon.png` is deliberately opaque and full-bleed — iOS renders
  transparency as black and applies its own rounded mask.
