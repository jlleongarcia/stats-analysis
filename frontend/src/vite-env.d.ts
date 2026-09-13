/// <reference types="vite/client" />
/// <reference types="vite-plugin-pwa/client" />
/// <reference types="vite-plugin-pwa/react" />

/** Filename of the bundled stats_core wheel, injected by vite.config.ts. */
declare const __STATS_CORE_WHEEL__: string;

/**
 * Pyodide packages to load at boot, injected by vite.config.ts from
 * scripts/pyodide-runtime.json -- the same list scripts/fetch-pyodide.mjs
 * vendors, so the two cannot drift.
 */
declare const __PYODIDE_PACKAGES__: string[];
