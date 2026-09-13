/**
 * SPC Studio state.
 *
 * Kept separate from `useApp` because the Studio is a workflow, not a
 * request/response page: it holds a stage, a set of pending analyst rulings and
 * a certified baseline, none of which the rest of the app cares about.
 *
 * The engine stays stateless. Every call re-sends the full exclusion set, so
 * the authoritative workflow state is right here and in IndexedDB — a worker
 * restart costs nothing, and unlike the Streamlit original, a page refresh does
 * not destroy the decision log.
 */
import { create } from "zustand";
import { ComputeError, getComputeClient } from "../compute/ComputeClient";
import { deleteStudy, listStudies, saveStudy, uid } from "../data/db";
import type {
  Dataset,
  RuleConfig,
  SpcBaseline,
  SpcCapability,
  SpcDecision,
  SpcEvaluation,
  SpcStudy,
} from "../types";
import { DEFAULT_RULE_CONFIG } from "../types";

/**
 * setup   — choose the column and rule thresholds
 * review  — pass 1 evaluated; the analyst rules on each flagged point
 * certified — baseline established; charts, audit trail and capability
 */
export type SpcStage = "setup" | "review" | "certified";

type Busy = false | "evaluating" | "certifying" | "capability";

interface SpcState {
  stage: SpcStage;
  busy: Busy;
  error: string | null;

  column: string;
  orderColumn: string | null;
  ruleConfig: RuleConfig;

  evaluation: SpcEvaluation | null;
  /** Analyst rulings keyed by position within the evaluated pass. */
  decisions: Record<number, SpcDecision>;
  baseline: SpcBaseline | null;
  capability: SpcCapability | null;
  usl: string;
  lsl: string;

  studies: SpcStudy[];
  studyId: string | null;

  setColumn: (column: string) => void;
  setOrderColumn: (column: string | null) => void;
  setRuleConfig: (patch: Partial<RuleConfig>) => void;
  setSpec: (which: "usl" | "lsl", value: string) => void;

  setDecision: (position: number, patch: Partial<SpcDecision>) => void;
  removeAllFlagged: (cause: string) => void;
  clearDecisions: () => void;

  evaluate: (dataset: Dataset) => Promise<void>;
  certify: (dataset: Dataset) => Promise<void>;
  computeCapability: (dataset: Dataset) => Promise<void>;

  reset: () => void;
  refreshStudies: (datasetId?: string) => Promise<void>;
  persist: (dataset: Dataset) => Promise<void>;
  loadStudy: (study: SpcStudy) => void;
  discardStudy: (id: string, datasetId: string) => Promise<void>;
}

/** Columnar view of a dataset, matching what the worker expects. */
function toColumnar(dataset: Dataset): Record<string, unknown[]> {
  const out: Record<string, unknown[]> = {};
  for (const col of dataset.columns) {
    out[col.name] = dataset.rows.map((row) => row[col.name] ?? null);
  }
  return out;
}

function message(err: unknown): string {
  if (err instanceof ComputeError) return err.message;
  return err instanceof Error ? err.message : String(err);
}

const BLANK = {
  stage: "setup" as SpcStage,
  busy: false as Busy,
  error: null,
  evaluation: null,
  decisions: {} as Record<number, SpcDecision>,
  baseline: null,
  capability: null,
  studyId: null,
};

export const useSpc = create<SpcState>((set, get) => ({
  ...BLANK,
  column: "",
  orderColumn: null,
  ruleConfig: { ...DEFAULT_RULE_CONFIG },
  usl: "",
  lsl: "",
  studies: [],

  setColumn(column) {
    // Changing what is being charted invalidates every ruling made about the
    // old column, so drop them rather than silently re-applying by position.
    set({ ...BLANK, column, usl: "", lsl: "" });
  },
  setOrderColumn(orderColumn) {
    set({ ...BLANK, orderColumn, column: get().column });
  },
  setRuleConfig(patch) {
    set((s) => ({ ruleConfig: { ...s.ruleConfig, ...patch } }));
  },
  setSpec(which, value) {
    set({ [which]: value } as Pick<SpcState, "usl" | "lsl">);
  },

  setDecision(position, patch) {
    set((s) => {
      const current = s.decisions[position] ?? { position, remove: false, cause: "" };
      return { decisions: { ...s.decisions, [position]: { ...current, ...patch } } };
    });
  },

  removeAllFlagged(cause) {
    const evaluation = get().evaluation;
    if (!evaluation) return;
    const decisions: Record<number, SpcDecision> = {};
    for (const position of evaluation.flagged) {
      decisions[position] = { position, remove: true, cause };
    }
    set({ decisions });
  },

  clearDecisions() {
    set({ decisions: {} });
  },

  async evaluate(dataset) {
    const { column, orderColumn, ruleConfig } = get();
    if (!column) return set({ error: "Choose a measurement column first." });
    set({ busy: "evaluating", error: null });
    try {
      const evaluation = await getComputeClient().spc<SpcEvaluation>("evaluate", {
        data: toColumnar(dataset),
        column,
        orderColumn,
        ruleConfig,
      });
      set({
        evaluation,
        stage: "review",
        busy: false,
        decisions: {},
        baseline: null,
        capability: null,
      });
    } catch (err) {
      set({ busy: false, error: message(err) });
    }
  },

  async certify(dataset) {
    const { column, orderColumn, ruleConfig, decisions } = get();
    set({ busy: "certifying", error: null });
    try {
      const baseline = await getComputeClient().spc<SpcBaseline>("certify", {
        data: toColumnar(dataset),
        column,
        orderColumn,
        ruleConfig,
        decisions: Object.values(decisions),
      });
      set({ baseline, stage: "certified", busy: false });
      await get().persist(dataset);
    } catch (err) {
      // An undocumented removal comes back from Python as a DataError; it is a
      // methodological guard rail, not a crash, so it belongs inline.
      set({ busy: false, error: message(err) });
    }
  },

  async computeCapability(dataset) {
    const { column, orderColumn, ruleConfig, baseline, usl, lsl } = get();
    const upper = Number(usl);
    const lower = Number(lsl);
    if (!usl.trim() || !lsl.trim() || Number.isNaN(upper) || Number.isNaN(lower)) {
      return set({ error: "Enter both specification limits as numbers." });
    }
    set({ busy: "capability", error: null });
    try {
      const capability = await getComputeClient().spc<SpcCapability>("capability", {
        data: toColumnar(dataset),
        column,
        orderColumn,
        ruleConfig,
        // Capability is measured on the certified baseline, and mrBar carries
        // the bridging mask that produced it — so sigma_within matches the
        // control chart exactly instead of being re-derived across the gaps.
        excluded: baseline?.removedSourceRows ?? [],
        mrBar: baseline?.limits.mr_bar,
        usl: upper,
        lsl: lower,
      });
      set({ capability, busy: false });
    } catch (err) {
      set({ busy: false, error: message(err) });
    }
  },

  reset() {
    set({ ...BLANK });
  },

  async refreshStudies(datasetId) {
    set({ studies: await listStudies(datasetId) });
  },

  async persist(dataset) {
    const { column, orderColumn, ruleConfig, decisions, baseline, studyId, studies } = get();
    const now = Date.now();
    const id = studyId ?? uid();
    // Re-certifying an open study updates it in place; createdAt belongs to the
    // original study, not to the latest save.
    const createdAt = studies.find((s) => s.id === id)?.createdAt ?? now;
    const study: SpcStudy = {
      id,
      datasetId: dataset.id,
      datasetName: dataset.name,
      column,
      orderColumn,
      ruleConfig,
      decisions: Object.values(decisions),
      baseline,
      createdAt,
      updatedAt: now,
    };
    await saveStudy(study);
    set({ studyId: id });
    await get().refreshStudies(dataset.id);
  },

  loadStudy(study) {
    set({
      ...BLANK,
      studyId: study.id,
      column: study.column,
      orderColumn: study.orderColumn,
      ruleConfig: study.ruleConfig,
      decisions: Object.fromEntries(study.decisions.map((d) => [d.position, d])),
      baseline: study.baseline,
      stage: study.baseline ? "certified" : "setup",
    });
  },

  async discardStudy(id, datasetId) {
    await deleteStudy(id);
    if (get().studyId === id) set({ ...BLANK });
    await get().refreshStudies(datasetId);
  },
}));
