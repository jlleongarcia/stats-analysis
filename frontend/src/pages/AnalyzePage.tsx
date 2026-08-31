import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { RoleMapper, rolesComplete } from "../components/RoleMapper";
import { ParamControls } from "../components/ParamControls";
import { ResultView } from "../results/ResultView";
import { openReport } from "../results/report";
import { useApp } from "../state/store";
import type { ParamValues, RoleMapping, TestSpec } from "../types";

export function AnalyzePage() {
  const { activeDataset, registry, engine, runTest, runStatus, runError, lastResult, persistLastResult, analyses, refreshAnalyses } =
    useApp();
  const [params, setSearch] = useSearchParams();
  const selectedId = params.get("test") ?? "";

  const [roles, setRoles] = useState<RoleMapping>({});
  const [paramValues, setParamValues] = useState<ParamValues>({});

  const spec: TestSpec | undefined = useMemo(
    () => registry?.tests.find((t) => t.id === selectedId),
    [registry, selectedId],
  );

  useEffect(() => {
    setRoles({});
    setParamValues(
      spec ? Object.fromEntries(spec.params.map((p) => [p.key, p.default])) : {},
    );
  }, [spec]);

  useEffect(() => {
    void refreshAnalyses();
  }, [activeDataset, refreshAnalyses]);

  if (!activeDataset) {
    return <div className="page"><h1>Analyze</h1><p className="muted">Import and select a dataset first.</p></div>;
  }
  if (!registry) {
    return <div className="page"><h1>Analyze</h1><p className="muted">Waiting for the statistics engine…</p></div>;
  }

  const byFamily = registry.families.map((f) => ({
    family: f,
    tests: registry.tests.filter((t) => t.family === f),
  }));

  const canRun = spec && engine === "ready" && rolesComplete(spec.roles, roles) && runStatus !== "running";

  return (
    <div className="page analyze">
      <div className="analyze__pick">
        <h1>Analyze</h1>
        <label className="field">
          <span>Test</span>
          <select
            value={selectedId}
            onChange={(e) => setSearch(e.target.value ? { test: e.target.value } : {})}
          >
            <option value="">— choose a test —</option>
            {byFamily.map((g) => (
              <optgroup key={g.family} label={g.family}>
                {g.tests.map((t) => (
                  <option key={t.id} value={t.id}>{t.name}</option>
                ))}
              </optgroup>
            ))}
          </select>
        </label>

        {spec && (
          <>
            <p className="muted">{spec.description}</p>
            {spec.assumptions.length > 0 && (
              <p className="muted"><b>Assumes:</b> {spec.assumptions.join("; ")}</p>
            )}
            <RoleMapper
              roles={spec.roles}
              columns={activeDataset.columns}
              mapping={roles}
              onChange={setRoles}
            />
            <ParamControls params={spec.params} values={paramValues} onChange={setParamValues} />

            <button
              className="btn btn--primary"
              disabled={!canRun}
              onClick={() => void runTest(spec.id, roles, paramValues)}
            >
              {runStatus === "running" ? "Running…" : "Run test"}
            </button>
            {runError && <p className="error">{runError}</p>}
          </>
        )}
      </div>

      <div className="analyze__out">
        {lastResult && runStatus === "done" && (
          <>
            <ResultView result={lastResult} />
            <button
              className="btn"
              onClick={() =>
                void persistLastResult(lastResult.testId, lastResult.testName, roles, paramValues)
              }
            >
              Save to history
            </button>
          </>
        )}

        {analyses.length > 0 && (
          <section className="history">
            <h3>History for “{activeDataset.name}”</h3>
            <ul>
              {analyses.map((a) => (
                <li key={a.id}>
                  <span>{a.testName}</span>
                  <span className="muted">{new Date(a.createdAt).toLocaleString()}</span>
                  <button className="link" onClick={() => openReport(a)}>Open report</button>
                </li>
              ))}
            </ul>
          </section>
        )}
      </div>
    </div>
  );
}
