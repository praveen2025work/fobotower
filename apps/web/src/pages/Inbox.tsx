import { Link } from "react-router-dom";

import { useInbox, type InboxRow } from "../api/helix";
import StatusBadge from "../components/StatusBadge";
import { Card, Empty, ErrorState, Loading, PageHeader, formatTime } from "../components/ui";

export function InboxTable({ rows }: { rows: InboxRow[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-sm">
        <thead className="text-xs text-surface-500">
          <tr>
            <th scope="col" className="px-2 py-2 font-medium">Needs</th>
            <th scope="col" className="px-2 py-2 font-medium">Case</th>
            <th scope="col" className="px-2 py-2 font-medium">Capability</th>
            <th scope="col" className="px-2 py-2 font-medium">Proposals</th>
            <th scope="col" className="px-2 py-2 font-medium">Opened</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-surface-100">
          {rows.map((r) => (
            <tr key={r.case_id} className="hover:bg-surface-50">
              <td className="px-2 py-2"><StatusBadge status={r.action} /></td>
              <td className="px-2 py-2">
                <Link to={`/cases/${encodeURIComponent(r.case_id)}`} className="font-medium text-primary-700 hover:underline">
                  {r.case_label}: {r.subject}
                </Link>
              </td>
              <td className="px-2 py-2 text-surface-600">{r.capability_name}</td>
              <td className="px-2 py-2 text-xs text-surface-600">
                {r.decided}/{r.groups} decided · {r.proposed} proposed
                {r.escalated > 0 && <span className="ml-1 font-medium text-orange-700">· {r.escalated} escalated</span>}
              </td>
              <td className="px-2 py-2 text-xs text-surface-500">{formatTime(r.opened_at)} · {r.opened_by}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** One queue across every capability: what waits on the signed-in user. */
export default function InboxPage(): JSX.Element {
  const inbox = useInbox();
  return (
    <div>
      <PageHeader title="Inbox" subtitle="Cases waiting for your review or your release of a write-back, oldest first." />
      <Card>
        {inbox.isLoading && <Loading what="inbox" />}
        {inbox.error && <ErrorState error={inbox.error} />}
        {inbox.data && (inbox.data.length === 0 ? <Empty>Nothing is waiting on you.</Empty> : <InboxTable rows={inbox.data} />)}
      </Card>
    </div>
  );
}
