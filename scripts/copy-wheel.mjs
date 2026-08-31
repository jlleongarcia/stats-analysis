/**
 * Copies the freshly built `stats_core` wheel into the frontend's public folder
 * under a stable name so the Pyodide worker can micropip-install it at runtime.
 *
 * Run from anywhere:  node scripts/copy-wheel.mjs
 * (wired into the frontend's `predev` / `prebuild` npm scripts)
 */
import { execSync } from "node:child_process";
import { existsSync, mkdirSync, readdirSync, copyFileSync, writeFileSync, statSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const distDir = join(root, "dist");
const outDir = join(root, "frontend", "public", "pyodide-packages");
const dest = join(outDir, "stats_core.whl");

// In container builds the wheel is copied in from the Python build stage; don't
// try to rebuild it here (there is no `uv` in the Node image).
if (process.env.SKIP_WHEEL_BUILD) {
  if (existsSync(dest)) {
    console.log("[copy-wheel] SKIP_WHEEL_BUILD set and wheel present - nothing to do");
    process.exit(0);
  }
  console.warn("[copy-wheel] SKIP_WHEEL_BUILD set but no wheel at", dest);
  process.exit(0);
}

function newestWheel() {
  if (!existsSync(distDir)) return null;
  const wheels = readdirSync(distDir)
    .filter((f) => f.startsWith("stats_analysis-") && f.endsWith(".whl"))
    .map((f) => ({ f, m: statSync(join(distDir, f)).mtimeMs }))
    .sort((a, b) => b.m - a.m);
  return wheels[0]?.f ?? null;
}

let wheel = newestWheel();
if (!wheel) {
  console.log("[copy-wheel] no wheel in dist/ - building it with `uv build --wheel`");
  execSync("uv build --wheel", { cwd: root, stdio: "inherit" });
  wheel = newestWheel();
}
if (!wheel) {
  console.error("[copy-wheel] could not find or build the stats_core wheel");
  process.exit(1);
}

mkdirSync(outDir, { recursive: true });
copyFileSync(join(distDir, wheel), dest);
writeFileSync(
  join(outDir, "manifest.json"),
  JSON.stringify({ wheel: "stats_core.whl", source: wheel, builtAt: new Date().toISOString() }, null, 2),
);
console.log(`[copy-wheel] ${wheel} -> frontend/public/pyodide-packages/stats_core.whl`);
