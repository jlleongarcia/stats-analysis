/**
 * Copies the freshly built `stats_core` wheel into the frontend's public folder
 * so the Pyodide worker can micropip-install it at runtime.
 *
 * Run from anywhere:  node scripts/copy-wheel.mjs
 * (wired into the frontend's `predev` / `prebuild` npm scripts)
 */
import { execSync } from "node:child_process";
import { existsSync, mkdirSync, readdirSync, copyFileSync, rmSync, statSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const distDir = join(root, "dist");
const outDir = join(root, "frontend", "public", "pyodide-packages");

// The wheel keeps its real PEP 427 filename (name-version-python-abi-platform).
// micropip parses that filename to register the distribution, so a "stable"
// short name like stats_core.whl makes install() fail with InvalidWheelFilename.
// vite.config.ts discovers the file at build time and passes it to the app.
const isWheel = (f) => f.startsWith("stats_analysis-") && f.endsWith(".whl");

// In container builds the wheel is copied in from the Python build stage; don't
// try to rebuild it here (there is no `uv` in the Node image).
if (process.env.SKIP_WHEEL_BUILD) {
  const present = existsSync(outDir) && readdirSync(outDir).filter(isWheel);
  if (present && present.length) {
    console.log(`[copy-wheel] SKIP_WHEEL_BUILD set, wheel present (${present[0]}) - nothing to do`);
    // There is no `uv` here to rebuild with, but staying silent about a stale
    // wheel is how the browser ends up running last week's Python against
    // today's UI - which surfaces as fields missing from engine responses
    // rather than as anything that looks like a build problem.
    const sources = join(root, "stats_core");
    if (existsSync(sources)) {
      const wheelMtime = statSync(join(outDir, present[0])).mtimeMs;
      if (wheelMtime < newestSourceMtime()) {
        console.warn(
          `\n[copy-wheel] WARNING: ${present[0]} is OLDER than stats_core/.\n` +
            "  The browser will install stale Python. This cannot be rebuilt here\n" +
            "  (no uv in this image). Fix it with either:\n" +
            "    host:   npm run sync-core        (rebuilds and copies the wheel)\n" +
            "    docker: docker compose build     (rebuilds the wheel stage)\n",
        );
      }
    }
    process.exit(0);
  }
  console.warn("[copy-wheel] SKIP_WHEEL_BUILD set but no stats_analysis wheel in", outDir);
  process.exit(1);
}

function newestWheel() {
  if (!existsSync(distDir)) return null;
  const wheels = readdirSync(distDir)
    .filter(isWheel)
    .map((f) => ({ f, m: statSync(join(distDir, f)).mtimeMs }))
    .sort((a, b) => b.m - a.m);
  return wheels[0]?.f ?? null;
}

/** Newest mtime across everything that ends up inside the wheel. */
function newestSourceMtime() {
  let newest = 0;
  const walk = (dir) => {
    for (const entry of readdirSync(dir, { withFileTypes: true })) {
      if (entry.name === "__pycache__") continue;
      const full = join(dir, entry.name);
      if (entry.isDirectory()) walk(full);
      else newest = Math.max(newest, statSync(full).mtimeMs);
    }
  };
  walk(join(root, "stats_core"));
  for (const f of ["pyproject.toml", "README.md"]) {
    const p = join(root, f);
    if (existsSync(p)) newest = Math.max(newest, statSync(p).mtimeMs);
  }
  return newest;
}

let wheel = newestWheel();
// A stale wheel is worse than a missing one: the version in pyproject rarely
// changes, so the filename stays identical and the browser silently runs
// yesterday's Python against today's UI. Rebuild whenever any source is newer.
const stale =
  wheel && statSync(join(distDir, wheel)).mtimeMs < newestSourceMtime();
if (!wheel || stale) {
  console.log(
    stale
      ? "[copy-wheel] stats_core changed since the wheel was built - rebuilding"
      : "[copy-wheel] no wheel in dist/ - building it with `uv build --wheel`",
  );
  execSync("uv build --wheel", { cwd: root, stdio: "inherit" });
  wheel = newestWheel();
}
if (!wheel) {
  console.error("[copy-wheel] could not find or build the stats_core wheel");
  process.exit(1);
}

mkdirSync(outDir, { recursive: true });
// Drop any wheel from an earlier version so the build-time lookup stays unambiguous.
for (const stale of readdirSync(outDir).filter(isWheel)) {
  if (stale !== wheel) rmSync(join(outDir, stale));
}
copyFileSync(join(distDir, wheel), join(outDir, wheel));
console.log(`[copy-wheel] ${wheel} -> frontend/public/pyodide-packages/`);
