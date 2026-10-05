// Follow-through: what became of this case's decisions in the next run of
// its series — cleared, or still open (and so carried into that run).

import { Link } from "react-router-dom";
import { CheckCircle2, RotateCw } from "lucide-react";
import type { CaseDetail } from "../../api/helix";

export default function FollowThroughPanel({ c }: { c: CaseDetail }) {
  const spec = c.follow_through_spec;
  if (!spec) return null;
  const ft = c.follow_through;
  const next = spec.order_by;
  return (
    <div>
      <h2 className="mb-2 text-xs font-semibold uppercase tracking-wider text-surface-500">Follow-through</h2>
      {!ft ? (
        <p className="text-xs text-surface-500">
          Each decision{spec.verdicts.length ? ` (${spec.verdicts.join(", ").replace(/_/g, " ")})` : ""} is re-checked on the next {next}.
          Nothing has been checked yet.
        </p>
      ) : (
        <>
          <p className="mb-2 text-xs text-surface-600">
            Checked on the next {next}: <span className="font-medium text-emerald-700">{ft.cleared} cleared</span>
            {" · "}
            <span className={ft.still_open ? "font-medium text-orange-700" : ""}>{ft.still_open} still open</span>
          </p>
          <ul className="space-y-1">
            {ft.items.map((r) => (
              <li key={r.item_id} className="flex items-center gap-2 text-xs">
                {r.status === "cleared"
                  ? <CheckCircle2 size={13} className="shrink-0 text-emerald-600" aria-label="cleared" />
                  : <RotateCw size={13} className="shrink-0 text-orange-600" aria-label="still open" />}
                <span className="min-w-0 flex-1 truncate font-medium text-surface-800">{r.item_id}</span>
                <span className="shrink-0 text-surface-500">{(r.verdict ?? "").replace(/_/g, " ")}</span>
                {r.status === "still_open" && (
                  <Link to={`/cases/${encodeURIComponent(r.checked_in)}`} className="shrink-0 text-primary-700 hover:underline">reopened</Link>
                )}
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}
