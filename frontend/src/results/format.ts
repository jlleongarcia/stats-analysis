export function fmtNum(v: number | null | undefined, digits = 4): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  if (v === Infinity) return "∞";
  if (v === -Infinity) return "−∞";
  if (v !== 0 && (Math.abs(v) < 1e-4 || Math.abs(v) >= 1e6)) return v.toExponential(2);
  const r = Number(v.toFixed(digits));
  return Number.isInteger(r) ? String(r) : String(r);
}

export function fmtP(p: number | null): string {
  if (p === null || Number.isNaN(p)) return "p = n/a";
  if (p < 0.001) return "p < .001";
  return `p = ${p.toFixed(3).replace(/^0/, "")}`;
}
