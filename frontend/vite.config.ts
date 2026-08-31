import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { VitePWA } from "vite-plugin-pwa";
import { readdirSync } from "node:fs";
import { fileURLToPath } from "node:url";

// The wheel carries its full PEP 427 filename (micropip refuses anything else),
// so the name changes with every version bump. Resolve it once here rather than
// making the app fetch a manifest at runtime. `sync-core` puts it in place via
// the predev/prebuild hooks, so it is always present by the time this runs.
function statsCoreWheel(): string {
  const dir = fileURLToPath(new URL("./public/pyodide-packages", import.meta.url));
  const found = readdirSync(dir).filter((f) => f.startsWith("stats_analysis-") && f.endsWith(".whl"));
  if (found.length !== 1) {
    throw new Error(
      `expected exactly one stats_analysis wheel in ${dir}, found ${found.length}. ` +
        "Run `npm run sync-core`.",
    );
  }
  return found[0];
}

const STATS_CORE_WHEEL = statsCoreWheel();

// Keep in sync with the default in scripts/fetch-pyodide.mjs, which vendors
// this exact release into public/pyodide/.
const PYODIDE_VERSION = "0.26.4";

export default defineConfig({
  base: "./",
  worker: { format: "es" },
  build: {
    target: "es2022",
    sourcemap: true,
  },
  server: { port: 7100, strictPort: true },
  preview: { port: 7100, strictPort: true },
  plugins: [
    react(),
    VitePWA({
      registerType: "autoUpdate",
      includeAssets: [
        "favicon.svg",
        "robots.txt",
        "icons/apple-touch-icon.png",
        `pyodide-packages/${STATS_CORE_WHEEL}`,
      ],
      manifest: {
        // Explicit id: without one the install identity is derived from
        // start_url, so moving the app would orphan every existing install.
        id: "stats-analysis",
        name: "Stats Analysis",
        short_name: "Stats",
        description: "Upload a dataset and run statistical tests entirely in your browser.",
        theme_color: "#0f172a",
        background_color: "#0f172a",
        display: "standalone",
        start_url: "./",
        scope: "./",
        icons: [
          { src: "icons/icon-192.png", sizes: "192x192", type: "image/png" },
          { src: "icons/icon-512.png", sizes: "512x512", type: "image/png" },
          { src: "icons/icon-512-maskable.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
        ],
      },
      workbox: {
        // The app shell is small and precached. The Pyodide runtime is ~115 MB
        // and lives under public/pyodide/: too big to precache (it would block
        // the service worker install), so it is cached on first use instead.
        globPatterns: ["**/*.{js,css,html,svg,png,ico,woff2,webmanifest}"],
        globIgnores: ["pyodide/**"],
        maximumFileSizeToCacheInBytes: 6 * 1024 * 1024,
        navigateFallbackDenylist: [/^\/pyodide-packages\//, /^\/pyodide\//],
        runtimeCaching: [
          {
            // Same-origin Pyodide runtime: wasm, stdlib and package wheels.
            // Immutable per release, so CacheFirst with a version-keyed cache
            // name -- bumping PYODIDE_VERSION retires the old cache wholesale.
            urlPattern: /\/pyodide\/.*\.(mjs|js|wasm|zip|whl|json)$/,
            handler: "CacheFirst",
            options: {
              cacheName: `pyodide-${PYODIDE_VERSION}`,
              expiration: { maxEntries: 200, maxAgeSeconds: 60 * 60 * 24 * 365 },
              cacheableResponse: { statuses: [0, 200] },
            },
          },
          {
            urlPattern: /\/pyodide-packages\/.*\.whl$/,
            handler: "CacheFirst",
            options: {
              cacheName: "stats-core-wheel",
              expiration: { maxEntries: 4, maxAgeSeconds: 60 * 60 * 24 * 30 },
              cacheableResponse: { statuses: [0, 200] },
            },
          },
        ],
      },
      devOptions: { enabled: false },
    }),
  ],
  define: {
    __STATS_CORE_WHEEL__: JSON.stringify(STATS_CORE_WHEEL),
  },
});
