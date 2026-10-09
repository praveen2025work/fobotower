// Generated from apps/web/src/components/case/DataSetsPanel.tsx by apps/web/office/convert.mjs. Office changes to this file are
// kept by aof_sync.py on the next update; see docs/agent-one-finance/office/conversion-guide.md.
// What the run's data steps did: the named data sets it used (FX rates, limits,
// roll-ups), the items it set aside and why, and steps skipped this time.

import { useState } from "react";
import { Database } from "lucide-react";

import { formatValue } from "../ui";

export default function DataSetsPanel({ c }) {
  const [open, setOpen] = useState(null);
  const sets = c.datasets ?? [];
  const aside = c.excluded ?? [];
  const skipped = c.draft?.skipped_steps ?? [];
  if (!sets.length && !aside.length && !skipped.length) return null;
  const label = (id) => c.step_labels?.[id] ?? id;
  const byStep = aside.reduce((acc, e) => ({ ...acc, [e.by]: [...(acc[e.by] ?? []), e] }), {});
  return (
    <div>
      <h2 className="mb-2 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-surface-500">
        <Database size={12} /> Data used and set aside
      </h2>
      {sets.map((d) => (
        <div key={d.name} className="mb-1.5 text-xs">
          <button
            type="button"
            onClick={() => setOpen(open === d.name ? null : d.name)}
            className="flex w-full items-center gap-2 text-left hover:underline"
          >
            <span className="font-medium text-surface-800">{d.name}</span>
            <span className="text-surface-500">
              {d.row_count} rows · {d.source}
            </span>
          </button>
          {open === d.name && (
            <div className="mt-1 max-h-48 overflow-auto rounded border border-surface-100">
              <table className="min-w-full text-[11px]">
                <thead className="bg-surface-50 text-left text-surface-500">
                  <tr>
                    {d.columns.map((k) => (
                      <th key={k} className="px-1.5 py-0.5 font-medium">
                        {k}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {d.rows.map((r, i) => (
                    <tr key={i} className="border-t border-surface-100">
                      {d.columns.map((k) => (
                        <td key={k} className="px-1.5 py-0.5 tabular-nums">
                          {formatValue(r[k])}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      ))}
      {Object.entries(byStep).map(([step, xs]) => (
        <p key={step} className="mb-1 text-xs text-surface-600" title={xs.map((x) => x.item_id).join(", ")}>
          <span className="font-medium">{xs.length} set aside</span> by {label(step)}: {xs[0].reason}
          {xs.length > 1 ? "…" : ""}
        </p>
      ))}
      {skipped.length > 0 && (
        <p className="text-xs text-surface-500">Skipped this run: {skipped.map(label).join(", ")}</p>
      )}
    </div>
  );
}
