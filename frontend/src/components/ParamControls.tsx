import type { ParamSpec, ParamValues } from "../types";

interface Props {
  params: ParamSpec[];
  values: ParamValues;
  onChange: (next: ParamValues) => void;
}

export function ParamControls({ params, values, onChange }: Props) {
  if (params.length === 0) return null;
  const set = (k: string, v: unknown) => onChange({ ...values, [k]: v });

  return (
    <div className="params">
      {params.map((p) => {
        const val = values[p.key] ?? p.default;
        return (
          <label key={p.key} className="params__field" title={p.help}>
            <span>{p.label}</span>
            {p.type === "select" ? (
              <select value={String(val ?? "")} onChange={(e) => set(p.key, e.target.value)}>
                {p.choices.map((c) => (
                  <option key={c} value={c}>{c}</option>
                ))}
              </select>
            ) : p.type === "bool" ? (
              <input
                type="checkbox"
                checked={Boolean(val)}
                onChange={(e) => set(p.key, e.target.checked)}
              />
            ) : p.type === "number" ? (
              <input
                type="number"
                step="any"
                value={val === null || val === undefined ? "" : String(val)}
                onChange={(e) => set(p.key, e.target.value === "" ? null : Number(e.target.value))}
              />
            ) : (
              <input
                type="text"
                placeholder="comma-separated"
                value={Array.isArray(val) ? val.join(", ") : String(val ?? "")}
                onChange={(e) => {
                  const parts = e.target.value
                    .split(",")
                    .map((s) => s.trim())
                    .filter(Boolean)
                    .map(Number);
                  set(p.key, parts.length ? parts : null);
                }}
              />
            )}
          </label>
        );
      })}
    </div>
  );
}
