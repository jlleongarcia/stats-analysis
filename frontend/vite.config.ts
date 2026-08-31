import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { VitePWA } from "vite-plugin-pwa";

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
      includeAssets: ["favicon.svg", "robots.txt", "pyodide-packages/stats_core.whl"],
      manifest: {
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
        // The app shell is small; Pyodide + its wheels are large and come from a
        // CDN, so cache those at runtime rather than precaching them.
        globPatterns: ["**/*.{js,css,html,svg,woff2}"],
        maximumFileSizeToCacheInBytes: 6 * 1024 * 1024,
        navigateFallbackDenylist: [/^\/pyodide-packages\//],
        runtimeCaching: [
          {
            urlPattern: new RegExp(`^https://cdn\\.jsdelivr\\.net/pyodide/v${PYODIDE_VERSION.replace(/\./g, "\\.")}/`),
            handler: "CacheFirst",
            options: {
              cacheName: `pyodide-${PYODIDE_VERSION}`,
              expiration: { maxEntries: 200, maxAgeSeconds: 60 * 60 * 24 * 90 },
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
    __PYODIDE_VERSION__: JSON.stringify(PYODIDE_VERSION),
  },
});
