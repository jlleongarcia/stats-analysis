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
# stable name, and a copy outside the app tree for the dev container
RUN cp /out/stats_analysis-*-py3-none-any.whl /opt/stats_core.whl

# ---------------------------------------------------------------------------
# Stage 2 — frontend dependencies + the wheel in place (also the dev image).
# ---------------------------------------------------------------------------
FROM node:20-bookworm-slim AS frontend-base
WORKDIR /app/frontend
ENV SKIP_WHEEL_BUILD=1
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install
COPY frontend ./
COPY scripts /app/scripts
COPY --from=wheel /opt/stats_core.whl /opt/stats_core.whl
RUN mkdir -p public/pyodide-packages && cp /opt/stats_core.whl public/pyodide-packages/stats_core.whl

# ---------------------------------------------------------------------------
# Stage 3 — production static build.
# ---------------------------------------------------------------------------
FROM frontend-base AS build
RUN npm run build

# ---------------------------------------------------------------------------
# Stage 4 — nginx serving the static PWA.
# ---------------------------------------------------------------------------
FROM nginx:1.27-alpine AS runtime
COPY docker/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/frontend/dist /usr/share/nginx/html
EXPOSE 80
HEALTHCHECK --interval=30s --timeout=3s CMD wget -qO- http://localhost/ >/dev/null || exit 1
