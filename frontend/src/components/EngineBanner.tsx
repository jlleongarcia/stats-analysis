import { useEffect } from "react";
import { useApp } from "../state/store";

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
        </>
      )}
      {engine === "idle" && <span>Statistics engine not started.</span>}
    </div>
  );
}
