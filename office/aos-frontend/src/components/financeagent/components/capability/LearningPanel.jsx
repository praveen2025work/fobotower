// Generated from apps/web/src/components/capability/LearningPanel.tsx by apps/web/office/convert.mjs. Office changes to this file are
// kept by aof_sync.py on the next update; see docs/agent-one-finance/office/conversion-guide.md.
// Learning from the work (manifest insights): items nothing explained — for
// the playbook's or the rules' owners to turn into new checks — and groups
// the model proposed that reviewers keep approving unchanged: candidates for
// a rule or a deterministic category.

import { Link } from "../../office/router";
import { Lightbulb } from "lucide-react";

import { useLearning } from "../../api/aof";
import { Card, ErrorState, Loading } from "../ui";

export default function LearningPanel({ capabilityId, teamGroup }) {
  const q = useLearning(capabilityId, teamGroup);
  const d = q.data;
  return (
    <Card
      title={
        <span className="flex items-center gap-2">
          <Lightbulb size={14} /> Learning from the work
        </span>
      }
    >
      {q.isLoading && <Loading what="insights" />}
      {q.error && <ErrorState error={q.error} />}
      {d && (
        <div className="grid gap-4 lg:grid-cols-2">
          <section aria-label="Unexplained">
            <h3 className="mb-1 text-xs font-semibold uppercase tracking-wider text-surface-500">
              Nothing explained these
            </h3>
            {d.unexplained.length === 0 ? (
              <p className="text-xs text-surface-500">
                Every item in recent runs was explained by a check, a rule or the model.
              </p>
            ) : (
              <>
                <p className="mb-1 text-xs text-surface-600">
                  {d.unexplained_by_reason.map((r) => `${r.items} × ${r.why}`).join(" · ")}
                </p>
                <ul className="space-y-0.5 text-xs">
                  {d.unexplained.slice(0, 10).map((r) => (
                    <li key={r.case_id + r.item_id} className="flex gap-2">
                      <span className="font-medium text-surface-800">{r.item_id}</span>
                      <span className="min-w-0 flex-1 truncate text-surface-500">{r.why}</span>
                      <Link
                        to={`/cases/${encodeURIComponent(r.case_id)}`}
                        className="shrink-0 text-primary-700 hover:underline"
                      >
                        {r.subject}
                      </Link>
                    </li>
                  ))}
                </ul>
              </>
            )}
          </section>
          <section aria-label="Proposed checks" className="lg:col-span-2">
            <h3 className="mb-1 text-xs font-semibold uppercase tracking-wider text-surface-500">
              Checks the decisions suggest
            </h3>
            {!d.proposed_checks?.length ? (
              <p className="text-xs text-surface-500">
                Not enough approved judgement calls with different verdicts yet to learn a condition from.
              </p>
            ) : (
              <>
                <p className="mb-1 text-xs text-surface-600">
                  A condition on the data that picked out the verdict people approved. Add it as a check only after
                  replaying it on past cases.
                </p>
                <ul className="space-y-1 text-xs">
                  {d.proposed_checks.slice(0, 10).map((p) => (
                    <li
                      key={JSON.stringify([p.team_group, p.category, p.verdict, p.when])}
                      className="flex flex-wrap items-baseline gap-x-2"
                    >
                      <code className="rounded bg-surface-100 px-1 py-0.5 text-surface-800">{p.when}</code>
                      <span className="text-surface-600">
                        → {p.verdict.replace(/_/g, " ")} in {p.category}
                      </span>
                      <span className="text-surface-500">
                        {p.covers} of {p.of} cases · {p.wrong ? `${p.wrong} wrong` : "never wrong"} (
                        {Math.round(p.precision * 100)}%)
                      </span>
                    </li>
                  ))}
                </ul>
              </>
            )}
          </section>
          <section aria-label="Could be a rule">
            <h3 className="mb-1 text-xs font-semibold uppercase tracking-wider text-surface-500">Could be a rule</h3>
            {d.automation.length === 0 ? (
              <p className="text-xs text-surface-500">
                No model proposal has been approved unchanged often enough yet.
              </p>
            ) : (
              <ul className="space-y-1 text-xs">
                {d.automation.slice(0, 10).map((a) => (
                  <li key={JSON.stringify([a.team_group, a.group_key, a.verdict])}>
                    <span className="font-medium text-surface-800">{a.label}</span>
                    {a.verdict && <span className="text-surface-600"> → {a.verdict.replace(/_/g, " ")}</span>}
                    <span className="text-surface-500"> · approved {a.approved}× as proposed, never rejected</span>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </div>
      )}
    </Card>
  );
}
