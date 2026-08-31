/**
 * Vendors the Pyodide runtime into the frontend so the app never contacts a CDN.
 *
 * Downloads only what this app actually boots: the core runtime files plus the
 * transitive dependency closure of micropip/numpy/pandas/scipy/statsmodels,
 * resolved from `pyodide-lock.json` (11 packages, ~40 MB -- the full Pyodide
 * distribution is several hundred MB, so the closure matters).
 *
 * Every download is verified against the sha256 in the lock file. Re-running is
 * cheap: files already present with a matching hash are skipped.
 *
 * Usage:  node scripts/fetch-pyodide.mjs [--version 0.26.4] [--out DIR]
 */
import { createHash } from "node:crypto";
import { mkdirSync, existsSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");

function arg(name, fallback) {
  const i = process.argv.indexOf(`--${name}`);
  return i !== -1 && process.argv[i + 1] ? process.argv[i + 1] : fallback;
}

// Keep in sync with PYODIDE_VERSION in frontend/vite.config.ts.
const VERSION = arg("version", process.env.PYODIDE_VERSION || "0.26.4");
const OUT = resolve(arg("out", join(root, "frontend", "public", "pyodide")));
const BASE = `https://cdn.jsdelivr.net/pyodide/v${VERSION}/full/`;

// Loaded eagerly by the worker's `loadPackage` call; everything else these pull
// in is resolved from the lock file below.
const WANTED = ["micropip", "numpy", "pandas", "scipy", "statsmodels"];

// The runtime itself. `pyodide-lock.json` must be present too: loadPyodide()
// reads it from indexURL to resolve packages.
const CORE = ["pyodide.mjs", "pyodide.asm.js", "pyodide.asm.wasm", "python_stdlib.zip"];

const sha256 = (buf) => createHash("sha256").update(buf).digest("hex");

async function download(file, expected) {
  const dest = join(OUT, file);
  if (existsSync(dest)) {
    const have = readFileSync(dest);
    if (!expected || sha256(have) === expected) return { file, bytes: have.length, cached: true };
  }
  const res = await fetch(BASE + file);
  if (!res.ok) throw new Error(`${file}: HTTP ${res.status}`);
  const buf = Buffer.from(await res.arrayBuffer());
  if (expected && sha256(buf) !== expected) {
    throw new Error(`${file}: sha256 mismatch (lock says ${expected})`);
  }
  writeFileSync(dest, buf);
  return { file, bytes: buf.length, cached: false };
}

/** Transitive closure of WANTED over the lock file's `depends` graph. */
function closure(packages) {
  const seen = new Set();
  const stack = [...WANTED];
  while (stack.length) {
    const key = stack.pop().toLowerCase();
    if (seen.has(key)) continue;
    const pkg = packages[key];
    if (!pkg) throw new Error(`package "${key}" is not in pyodide-lock.json`);
    seen.add(key);
    stack.push(...pkg.depends);
  }
  return [...seen].sort();
}

mkdirSync(OUT, { recursive: true });

console.log(`[fetch-pyodide] v${VERSION} -> ${OUT}`);
const lock = await download("pyodide-lock.json");
const { packages } = JSON.parse(readFileSync(join(OUT, "pyodide-lock.json"), "utf8"));

const names = closure(packages);
console.log(`[fetch-pyodide] ${names.length} packages: ${names.join(", ")}`);

const jobs = [
  ...CORE.map((f) => [f, null]),
  ...names.map((n) => [packages[n].file_name, packages[n].sha256]),
];

let total = lock.bytes;
let fetched = lock.cached ? 0 : 1;
for (const [file, hash] of jobs) {
  const r = await download(file, hash);
  total += r.bytes;
  if (!r.cached) fetched += 1;
  console.log(`  ${r.cached ? "cached " : "fetched"} ${file} (${(r.bytes / 1048576).toFixed(1)} MiB)`);
}

console.log(
  `[fetch-pyodide] done - ${jobs.length + 1} files, ${(total / 1048576).toFixed(1)} MiB total ` +
    `(${fetched} downloaded this run)`,
);
