// Generated from apps/web/src/components/capability/RecurringPanel.tsx by apps/web/office/convert.mjs. Office changes to this file are
// kept by aof_sync.py on the next update; see office/README.md.
// Items that keep coming back (manifest insights.recurring): the same item on
// the same book / entity, run after run — a root cause to fix upstream.

import { Link } from "../../office/router";
import { Repeat } from "lucide-react";

import { useRecurring } from "../../api/aof";
import { Card, Empty, ErrorState, Loading } from "../ui";

export default function RecurringPanel({ capabilityId, teamGroup }) {
  const rows = useRecurring(capabilityId, teamGroup);
  return (
    <Card
      title={
        <span className="flex items-center gap-2">
          <Repeat size={14} /> Recurring
        </span>
      }
    >
      {rows.isLoading && <Loading what="recurring items" />}
      {rows.error && <ErrorState error={rows.error} />}
      {rows.data?.length === 0 && <Empty>Nothing has come back more than once in recent runs.</Empty>}
      {!!rows.data?.length && (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="text-xs text-surface-500">
              <tr>
                <th scope="col" className="px-2 py-1.5 font-medium">
                  Item
                </th>
                <th scope="col" className="px-2 py-1.5 font-medium">
                  Where
                </th>
                <th scope="col" className="px-2 py-1.5 text-right font-medium">
                  Runs
                </th>
                <th scope="col" className="px-2 py-1.5 font-medium">
                  Latest
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-surface-100">
              {rows.data.slice(0, 15).map((r) => (
                <tr key={`${r.team_group}-${JSON.stringify(r.same)}-${r.item_id}`}>
                  <td className="px-2 py-1.5 font-medium text-surface-800">{r.item_id}</td>
                  <td className="px-2 py-1.5 text-xs text-surface-600">{Object.values(r.same).join(" · ") || "—"}</td>
                  <td className="px-2 py-1.5 text-right tabular-nums">
                    <span className="rounded bg-orange-100 px-1.5 text-xs font-semibold text-orange-700">{r.runs}</span>
                  </td>
                  <td className="px-2 py-1.5 text-xs">
                    <Link
                      to={`/cases/${encodeURIComponent(r.latest_case_id)}`}
                      className="text-primary-700 hover:underline"
                    >
                      {r.latest_subject}
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}
