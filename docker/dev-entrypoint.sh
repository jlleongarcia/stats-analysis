#!/bin/sh
# Dev container: make sure the stats_core wheel (baked into the image at
# /opt/stats_core.whl) is present in the bind-mounted public folder, then run
# whatever command was passed (defaults to the Vite dev server).
set -e

mkdir -p public/pyodide-packages
if [ ! -f public/pyodide-packages/stats_core.whl ] && [ -f /opt/stats_core.whl ]; then
  cp /opt/stats_core.whl public/pyodide-packages/stats_core.whl
  echo "[dev-entrypoint] installed stats_core.whl into public/pyodide-packages/"
fi

if [ ! -d node_modules ] || [ -z "$(ls -A node_modules 2>/dev/null)" ]; then
  echo "[dev-entrypoint] installing npm dependencies…"
  npm install
fi

exec "$@"
