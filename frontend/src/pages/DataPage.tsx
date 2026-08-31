import { useState } from "react";
import { FileDrop } from "../components/FileDrop";
import { DataGrid } from "../components/DataGrid";
import { ColumnTypePanel } from "../components/ColumnTypePanel";
import { useApp, MAX_ROWS_SOFT } from "../state/store";

export function DataPage() {
  const {
    datasets,
    activeDataset,
    importFile,
    setActiveDataset,
    removeDataset,
    setColumnType,
  } = useApp();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleFile(file: File) {
    setBusy(true);
    setError(null);
    try {
      await importFile(file);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="page">
      <h1>Data</h1>
      <FileDrop onFile={handleFile} busy={busy} />
      {error && <p className="error">Could not import: {error}</p>}

      {datasets.length > 0 && (
        <div className="dataset-list">
          {datasets.map((d) => (
            <div
              key={d.id}
              className={`dataset-chip ${activeDataset?.id === d.id ? "is-active" : ""}`}
            >
              <button onClick={() => setActiveDataset(d.id)}>
                {d.name} <span className="muted">· {d.rowCount.toLocaleString()}×{d.columns.length}</span>
              </button>
              <button
                className="dataset-chip__x"
                title="Delete dataset"
                onClick={() => void removeDataset(d.id)}
              >
                ×
              </button>
            </div>
          ))}
        </div>
      )}

      {activeDataset && (
        <>
          {activeDataset.rowCount > MAX_ROWS_SOFT && (
            <p className="warn-box">
              This dataset has {activeDataset.rowCount.toLocaleString()} rows. Analyses run
              in-browser and may be slow above ~{MAX_ROWS_SOFT.toLocaleString()} rows.
            </p>
          )}
          <section>
            <h2>Preview</h2>
            <DataGrid dataset={activeDataset} />
          </section>
          <section>
            <h2>Column types</h2>
            <p className="muted">
              Inferred automatically — override any that are wrong before analysing.
            </p>
            <ColumnTypePanel columns={activeDataset.columns} onChange={setColumnType} />
          </section>
        </>
      )}
    </div>
  );
}
