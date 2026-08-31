import { create } from "zustand";
import { getComputeClient, ComputeError, type BootStage } from "../compute/ComputeClient";
import {
  db,
  deleteDataset,
  listAnalyses,
  listDatasets,
  saveAnalysis,
  saveDataset,
  uid,
} from "../data/db";
import { inferColumns } from "../data/infer";
import { parseFile } from "../data/parse";
import type {
  ColumnMeta,
  ColumnType,
  Dataset,
  ParamValues,
  Registry,
  RoleMapping,
  SavedAnalysis,
  TestResult,
} from "../types";

export const MAX_ROWS_SOFT = 100_000;

type EngineStatus = "idle" | "booting" | "ready" | "error";
type RunStatus = "idle" | "running" | "done" | "error";

interface AppState {
  // engine
  engine: EngineStatus;
  engineStage: BootStage | null;
  engineError: string | null;
  registry: Registry | null;

  // data
  datasets: Dataset[];
  activeDataset: Dataset | null;

  // analysis
  runStatus: RunStatus;
  runError: string | null;
  lastResult: TestResult | null;
  analyses: SavedAnalysis[];

  // actions
  bootEngine: () => Promise<void>;
  refreshDatasets: () => Promise<void>;
  importFile: (file: File, sheet?: string) => Promise<Dataset>;
  setActiveDataset: (id: string | null) => void;
  removeDataset: (id: string) => Promise<void>;
  setColumnType: (name: string, type: ColumnType) => void;
  runTest: (testId: string, roles: RoleMapping, params: ParamValues) => Promise<TestResult>;
  persistLastResult: (testId: string, testName: string, roles: RoleMapping, params: ParamValues) => Promise<void>;
  refreshAnalyses: () => Promise<void>;
}

export const useApp = create<AppState>((set, get) => ({
  engine: "idle",
  engineStage: null,
  engineError: null,
  registry: null,

  datasets: [],
  activeDataset: null,

  runStatus: "idle",
  runError: null,
  lastResult: null,
  analyses: [],

  async bootEngine() {
    if (get().engine === "booting" || get().engine === "ready") return;
    const client = getComputeClient();
    client.onProgress = (s) => set({ engineStage: s });
    set({ engine: "booting", engineError: null });
    try {
      const registry = await client.getRegistry();
      set({ engine: "ready", registry, engineStage: null });
    } catch (err) {
      set({
        engine: "error",
        engineError: err instanceof Error ? err.message : String(err),
      });
    }
  },

  async refreshDatasets() {
    set({ datasets: await listDatasets() });
  },

  async importFile(file, sheet) {
    const parsed = await parseFile(file, sheet);
    const columns: ColumnMeta[] = inferColumns(parsed.columns, parsed.rows);
    const ds: Dataset = {
      id: uid(),
      name: file.name.replace(/\.[^.]+$/, ""),
      createdAt: Date.now(),
      columns,
      rows: parsed.rows,
      rowCount: parsed.rows.length,
    };
    await saveDataset(ds);
    await get().refreshDatasets();
    set({ activeDataset: ds });
    return ds;
  },

  setActiveDataset(id) {
    if (id === null) return set({ activeDataset: null });
    const ds = get().datasets.find((d) => d.id === id) ?? null;
    set({ activeDataset: ds, lastResult: null, runStatus: "idle", runError: null });
    if (ds) void get().refreshAnalyses();
  },

  async removeDataset(id) {
    await deleteDataset(id);
    if (get().activeDataset?.id === id) set({ activeDataset: null });
    await get().refreshDatasets();
  },

  setColumnType(name, type) {
    const ds = get().activeDataset;
    if (!ds) return;
    const columns = ds.columns.map((c) => (c.name === name ? { ...c, type } : c));
    const updated = { ...ds, columns };
    set({ activeDataset: updated });
    void saveDataset(updated);
  },

  async runTest(testId, roles, params) {
    const ds = get().activeDataset;
    if (!ds) throw new Error("No active dataset.");
    set({ runStatus: "running", runError: null });
    try {
      const result = await getComputeClient().run(ds, testId, roles, params);
      set({ runStatus: "done", lastResult: result });
      return result;
    } catch (err) {
      const message =
        err instanceof ComputeError
          ? err.message
          : err instanceof Error
            ? err.message
            : String(err);
      set({ runStatus: "error", runError: message });
      throw err;
    }
  },

  async persistLastResult(testId, testName, roles, params) {
    const ds = get().activeDataset;
    const result = get().lastResult;
    if (!ds || !result) return;
    const record: SavedAnalysis = {
      id: uid(),
      datasetId: ds.id,
      datasetName: ds.name,
      testId,
      testName,
      roles,
      params,
      result,
      createdAt: Date.now(),
    };
    await saveAnalysis(record);
    await get().refreshAnalyses();
  },

  async refreshAnalyses() {
    const ds = get().activeDataset;
    set({ analyses: await listAnalyses(ds?.id) });
  },
}));

// keep dataset list warm on load
void db.open().then(() => useApp.getState().refreshDatasets());
