/** Turn an uploaded CSV / TSV / Excel file into rows + column names. */
import Papa from "papaparse";
import * as XLSX from "xlsx";

export interface ParsedTable {
  columns: string[];
  rows: Record<string, unknown>[];
  sheetNames?: string[];
  sheet?: string;
}

const EXCEL_RE = /\.(xlsx|xls|xlsm|xlsb|ods)$/i;
const COMBINING_MARKS = /\p{Diacritic}/gu;

export async function parseFile(file: File, sheet?: string): Promise<ParsedTable> {
  if (EXCEL_RE.test(file.name)) return parseExcel(await file.arrayBuffer(), sheet);
  return parseDelimited(await file.text());
}

function parseDelimited(text: string): ParsedTable {
  const res = Papa.parse<Record<string, unknown>>(text, {
    header: true,
    dynamicTyping: true,
    skipEmptyLines: "greedy",
    transformHeader: (h, i) => cleanHeader(h, i),
  });
  const rows = res.data.filter((r) => Object.values(r).some((v) => v !== null && v !== ""));
  const columns = res.meta.fields ?? Object.keys(rows[0] ?? {});
  return { columns: dedupe(columns), rows };
}

function parseExcel(buf: ArrayBuffer, sheet?: string): ParsedTable {
  const wb = XLSX.read(buf, { type: "array", cellDates: true });
  const sheetNames = wb.SheetNames;
  const chosen = sheet && sheetNames.includes(sheet) ? sheet : sheetNames[0];
  const ws = wb.Sheets[chosen];
  const matrix = XLSX.utils.sheet_to_json<unknown[]>(ws, { header: 1, blankrows: false, defval: null });
  if (matrix.length === 0) return { columns: [], rows: [], sheetNames, sheet: chosen };

  const headerRow = matrix[0].map((h, i) => cleanHeader(h, i));
  const columns = dedupe(headerRow);
  const rows: Record<string, unknown>[] = [];
  for (let r = 1; r < matrix.length; r++) {
    const raw = matrix[r];
    if (!raw || raw.every((v) => v === null || v === "")) continue;
    const obj: Record<string, unknown> = {};
    columns.forEach((c, i) => {
      obj[c] = normalizeCell(raw[i]);
    });
    rows.push(obj);
  }
  return { columns, rows, sheetNames, sheet: chosen };
}

function cleanHeader(h: unknown, i: number): string {
  if (h === null || h === undefined || h === "") return `column_${i + 1}`;
  const s = String(h).normalize("NFKD").replace(COMBINING_MARKS, "").trim();
  return s || `column_${i + 1}`;
}

function normalizeCell(v: unknown): unknown {
  if (v instanceof Date) return v.toISOString().slice(0, 10);
  if (v === "") return null;
  return v;
}

function dedupe(names: string[]): string[] {
  const seen = new Map<string, number>();
  return names.map((n) => {
    const base = n || "column";
    const count = seen.get(base) ?? 0;
    seen.set(base, count + 1);
    return count === 0 ? base : `${base}_${count + 1}`;
  });
}
