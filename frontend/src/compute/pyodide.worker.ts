/// <reference lib="webworker" />
/**
 * Pyodide worker: boots CPython in WASM, installs numpy/pandas/scipy/statsmodels
 * plus the local `stats_core` wheel, then dispatches `run_test` calls.
 *
 * All data crosses the boundary as JSON strings - this keeps the Python side
 * framework-free and avoids leaking PyProxy handles.
 */
import type { WorkerRequest, WorkerResponse } from "./protocol";


// eslint-disable-next-line @typescript-eslint/no-explicit-any
let pyodide: any = null;
let bootPromise: Promise<void> | null = null;

function post(msg: WorkerResponse) {
  (self as DedicatedWorkerGlobalScope).postMessage(msg);
}

const BOOTSTRAP = `
import json
from stats_core import run_test as _rt, get_registry as _gr

def _run(test_id, data_json, roles_json, params_json):
    return json.dumps(_rt(
        test_id,
        json.loads(data_json),
        json.loads(roles_json),
        json.loads(params_json),
    ))

def _registry():
    return json.dumps(_gr())
`;

async function boot(wheelUrl: string, pyodideUrl: string): Promise<void> {
  post({ kind: "progress", stage: "Downloading Python runtime" });
  // Served from our own origin (see scripts/fetch-pyodide.mjs), never a CDN:
  // the app has to keep working on an offline or firewalled network.
  const { loadPyodide } = await import(/* @vite-ignore */ `${pyodideUrl}pyodide.mjs`);
  pyodide = await loadPyodide({ indexURL: pyodideUrl });

  post({ kind: "progress", stage: "Loading scientific packages", detail: "numpy, pandas, scipy, statsmodels" });
  await pyodide.loadPackage(["micropip", "numpy", "pandas", "scipy", "statsmodels"]);

  post({ kind: "progress", stage: "Installing stats_core" });
  // deps=False: numpy/pandas/scipy/statsmodels are already loaded as native
  // Pyodide packages; let micropip only unpack our pure-Python wheel.
  pyodide.globals.set("_wheel_url", wheelUrl);
  await pyodide.runPythonAsync("import micropip; await micropip.install(_wheel_url, deps=False)");

  pyodide.runPython(BOOTSTRAP);
  post({ kind: "progress", stage: "Ready" });
}

function ensureBooted(wheelUrl: string, pyodideUrl: string): Promise<void> {
  if (!bootPromise) bootPromise = boot(wheelUrl, pyodideUrl);
  return bootPromise;
}

function toError(err: unknown): { message: string; kindHint: "data" | "internal" } {
  const raw = err instanceof Error ? err.message : String(err);
  // stats_core raises DataError (a ValueError) for bad inputs / role mappings.
  const m = raw.match(/DataError:\s*(.*?)(?:\n|$)/);
  if (m) return { message: m[1].trim(), kindHint: "data" };
  const v = raw.match(/ValueError:\s*(.*?)(?:\n|$)/);
  if (v) return { message: v[1].trim(), kindHint: "data" };
  const lines = raw.trim().split("\n");
  return { message: lines[lines.length - 1] || raw, kindHint: "internal" };
}

self.onmessage = async (ev: MessageEvent<WorkerRequest>) => {
  const req = ev.data;
  try {
    if (req.kind === "init") {
      await ensureBooted(req.wheelUrl, req.pyodideUrl);
      post({ kind: "ready", id: req.id });
      return;
    }

    if (!pyodide) {
      post({ kind: "error", id: req.id, message: "Compute engine is not ready yet." });
      return;
    }

    if (req.kind === "registry") {
      const json = pyodide.globals.get("_registry")();
      post({ kind: "registry", id: req.id, registry: JSON.parse(json) });
      return;
    }

    if (req.kind === "run") {
      const json = pyodide.globals.get("_run")(
        req.testId,
        JSON.stringify(req.data),
        JSON.stringify(req.roles),
        JSON.stringify(req.params),
      );
      post({ kind: "result", id: req.id, result: JSON.parse(json) });
      return;
    }
  } catch (err) {
    const { message, kindHint } = toError(err);
    post({ kind: "error", id: (req as { id: string }).id, message, kindHint });
  }
};
