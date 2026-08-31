# syntax=docker/dockerfile:1

# ---------------------------------------------------------------------------
# Stage 1 — build the framework-free `stats_core` wheel with CPython.
# The browser installs this exact artifact into Pyodide via micropip.
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS wheel
WORKDIR /src
RUN pip install --no-cache-dir build==1.2.2.post1
COPY pyproject.toml README.md ./
COPY stats_core ./stats_core
RUN python -m build --wheel --outdir /out
# Keep the wheel's real PEP 427 filename: micropip parses it, and a renamed
# short form fails with InvalidWheelFilename. /opt/wheel is also what the dev
# container restores from once the bind mount hides the built-in copy.
RUN mkdir -p /opt/wheel && cp /out/stats_analysis-*-py3-none-any.whl /opt/wheel/

# ---------------------------------------------------------------------------
# Stage 2 — vendor the Pyodide runtime (~115 MB) so the browser never has to
# reach a CDN. Cached as its own layer: it only re-runs when the fetch script
# changes, not on every frontend edit.
# ---------------------------------------------------------------------------
FROM node:20-bookworm-slim AS pyodide
WORKDIR /src
COPY scripts/fetch-pyodide.mjs ./
RUN node fetch-pyodide.mjs --out /opt/pyodide

# ---------------------------------------------------------------------------
# Stage 3 — frontend dependencies + the wheel in place (also the dev image).
# ---------------------------------------------------------------------------
FROM node:20-bookworm-slim AS frontend-base
WORKDIR /app/frontend
ENV SKIP_WHEEL_BUILD=1
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install
COPY frontend ./
COPY scripts /app/scripts
COPY --from=wheel /opt/wheel /opt/wheel
COPY --from=pyodide /opt/pyodide /opt/pyodide
RUN mkdir -p public/pyodide-packages && cp /opt/wheel/*.whl public/pyodide-packages/
# public/pyodide is bind-mounted away in the dev profile; dev-entrypoint.sh
# restores it there from /opt.
RUN cp -r /opt/pyodide public/pyodide
EXPOSE 7100

# ---------------------------------------------------------------------------
# Stage 4 — production static build.
# ---------------------------------------------------------------------------
FROM frontend-base AS build
RUN npm run build

# ---------------------------------------------------------------------------
# Stage 5 — nginx serving the static PWA.
# ---------------------------------------------------------------------------
FROM nginx:1.27-alpine AS runtime
COPY docker/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/frontend/dist /usr/share/nginx/html
EXPOSE 80
# 127.0.0.1, not "localhost": in Alpine that resolves to ::1 first and the
# healthcheck fails before nginx ever gets a chance to answer.
HEALTHCHECK --interval=30s --timeout=3s CMD wget -qO- http://127.0.0.1/ >/dev/null || exit 1
