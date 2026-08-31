/** Local-only persistence (IndexedDB via Dexie): datasets + saved analyses. */
import Dexie, { type Table } from "dexie";
import type { Dataset, SavedAnalysis } from "../types";

class StatsDB extends Dexie {
  datasets!: Table<Dataset, string>;
  analyses!: Table<SavedAnalysis, string>;

  constructor() {
    super("stats-analysis");
    this.version(1).stores({
      datasets: "id, name, createdAt",
      analyses: "id, datasetId, testId, createdAt",
    });
  }
}

export const db = new StatsDB();

export const uid = (): string =>
  (crypto.randomUUID?.() ?? `id-${Date.now()}-${Math.random().toString(16).slice(2)}`);

export async function listDatasets(): Promise<Dataset[]> {
  return db.datasets.orderBy("createdAt").reverse().toArray();
}

export async function saveDataset(ds: Dataset): Promise<void> {
  await db.datasets.put(ds);
}

export async function deleteDataset(id: string): Promise<void> {
  await db.transaction("rw", db.datasets, db.analyses, async () => {
    await db.datasets.delete(id);
    await db.analyses.where("datasetId").equals(id).delete();
  });
}

export async function listAnalyses(datasetId?: string): Promise<SavedAnalysis[]> {
  const coll = datasetId
    ? db.analyses.where("datasetId").equals(datasetId)
    : db.analyses.toCollection();
  return (await coll.toArray()).sort((a, b) => b.createdAt - a.createdAt);
}

export async function saveAnalysis(a: SavedAnalysis): Promise<void> {
  await db.analyses.put(a);
}

export async function deleteAnalysis(id: string): Promise<void> {
  await db.analyses.delete(id);
}
