import { useEffect } from "react";
import { useApp } from "../state/store";

/** Drops the service worker's copy of the Pyodide runtime and reloads.
 *
 * The runtime is cached CacheFirst, which never revalidates — so if a bad
 * response ever landed in there (a proxy error page, a truncated download) the
 * engine stays broken and plain "Retry" re-reads the same bytes. Runtime caches
 * also survive service worker updates, so deploying a fix does not clear it
 * either. This is the only way out from inside the app. */
async function clearEngineCache(): Promise<void> {
  if ("caches" in window) {
    const names = await caches.keys();
    await Promise.all(
      names
        .filter((n) => n.startsWith("pyodide-") || n === "stats-core-wheel")
        .map((n) => caches.delete(n)),
    );
  }
  location.reload();
}

/** Shows Pyodide boot progress / errors and kicks off the boot on mount. */
export function EngineBanner() {
  const { engine, engineStage, engineError, bootEngine } = useApp();

  useEffect(() => {
    void bootEngine();
  }, [bootEngine]);

  if (engine === "ready") return null;

  return (
    <div className={`engine engine--${engine}`}>
      {engine === "booting" && (
        <>
          <span className="spinner" aria-hidden />
          <span>
            Starting the statistics engine…
            {engineStage && <b> {engineStage.stage}</b>}
            {engineStage?.detail && <span className="muted"> ({engineStage.detail})</span>}
          </span>
        </>
      )}
      {engine === "error" && (
        <>
          <span>⚠ Could not start the engine: {engineError}</span>
          <button onClick={() => void bootEngine()}>Retry</button>
          <button onClick={() => void clearEngineCache()} title="Re-download the Python runtime">
            Reset cached engine
          </button>
        </>
      )}
      {engine === "idle" && <span>Statistics engine not started.</span>}
    </div>
  );
}
