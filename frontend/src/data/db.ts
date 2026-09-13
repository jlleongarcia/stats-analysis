/** Local-only persistence (IndexedDB via Dexie): datasets, analyses, SPC studies. */
import Dexie, { type Table } from "dexie";
import type { Dataset, SavedAnalysis, SpcStudy } from "../types";

class StatsDB extends Dexie {
  datasets!: Table<Dataset, string>;
  analyses!: Table<SavedAnalysis, string>;
  spcStudies!: Table<SpcStudy, string>;

  constructor() {
    super("stats-analysis");
    this.version(1).stores({
      datasets: "id, name, createdAt",
      analyses: "id, datasetId, testId, createdAt",
    });
    // v2 adds SPC studies. Dexie carries existing stores forward, so an upgrade
    // keeps every dataset and analysis already on the device.
    this.version(2).stores({
      datasets: "id, name, createdAt",
      analyses: "id, datasetId, testId, createdAt",
      spcStudies: "id, datasetId, column, updatedAt",
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
  await db.transaction("rw", db.datasets, db.analyses, db.spcStudies, async () => {
    await db.datasets.delete(id);
    await db.analyses.where("datasetId").equals(id).delete();
    await db.spcStudies.where("datasetId").equals(id).delete();
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

export async function listStudies(datasetId?: string): Promise<SpcStudy[]> {
  const coll = datasetId
    ? db.spcStudies.where("datasetId").equals(datasetId)
    : db.spcStudies.toCollection();
  return (await coll.toArray()).sort((a, b) => b.updatedAt - a.updatedAt);
}

export async function saveStudy(study: SpcStudy): Promise<void> {
  await db.spcStudies.put(study);
}

export async function deleteStudy(id: string): Promise<void> {
  await db.spcStudies.delete(id);
}
