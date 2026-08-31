#!/bin/sh
# Dev container: the bind mount hides the copies baked into the image, so
# restore the stats_core wheel and the vendored Pyodide runtime from /opt if the
# host tree lacks them, then run whatever command was passed (default: Vite).
set -e

mkdir -p public/pyodide-packages
if [ -z "$(ls public/pyodide-packages/*.whl 2>/dev/null)" ] && [ -d /opt/wheel ]; then
  cp /opt/wheel/*.whl public/pyodide-packages/
  echo "[dev-entrypoint] installed $(ls /opt/wheel) into public/pyodide-packages/"
fi

if [ ! -d public/pyodide ] && [ -d /opt/pyodide ]; then
  echo "[dev-entrypoint] installing the vendored Pyodide runtime into public/pyodide/ …"
  cp -r /opt/pyodide public/pyodide
fi

if [ ! -d node_modules ] || [ -z "$(ls -A node_modules 2>/dev/null)" ]; then
  echo "[dev-entrypoint] installing npm dependencies…"
  npm install
fi

exec "$@"
