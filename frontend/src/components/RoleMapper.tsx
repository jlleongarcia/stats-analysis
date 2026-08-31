import { columnsForRole } from "../data/infer";
import type { ColumnMeta, RoleMapping, RoleSpec } from "../types";

interface Props {
  roles: RoleSpec[];
  columns: ColumnMeta[];
  mapping: RoleMapping;
  onChange: (next: RoleMapping) => void;
}

export function RoleMapper({ roles, columns, mapping, onChange }: Props) {
  const set = (key: string, value: string | string[]) => onChange({ ...mapping, [key]: value });

  return (
    <div className="roles">
      {roles.map((role) => {
        const choices = columnsForRole(columns, role.dtype);
        const current = mapping[role.key];
        return (
          <label key={role.key} className="roles__field" title={role.help}>
            <span className="roles__label">
              {role.label}
              {!role.required && <em className="muted"> (optional)</em>}
            </span>

            {role.multiple ? (
              <select
                multiple
                size={Math.min(6, Math.max(3, choices.length))}
                value={(Array.isArray(current) ? current : []) as string[]}
                onChange={(e) =>
                  set(role.key, Array.from(e.target.selectedOptions, (o) => o.value))
                }
              >
                {choices.map((c) => (
                  <option key={c.name} value={c.name}>{c.name}</option>
                ))}
              </select>
            ) : (
              <select
                value={typeof current === "string" ? current : ""}
                onChange={(e) => set(role.key, e.target.value)}
              >
                <option value="">— choose —</option>
                {choices.map((c) => (
                  <option key={c.name} value={c.name}>{c.name}</option>
                ))}
              </select>
            )}
            {role.help && <span className="muted roles__help">{role.help}</span>}
          </label>
        );
      })}
    </div>
  );
}

/** True when every required role has a value. */
export function rolesComplete(roles: RoleSpec[], mapping: RoleMapping): boolean {
  return roles.every((r) => {
    if (!r.required) return true;
    const v = mapping[r.key];
    if (r.multiple) return Array.isArray(v) && v.length > 0;
    return typeof v === "string" && v.length > 0;
  });
}
