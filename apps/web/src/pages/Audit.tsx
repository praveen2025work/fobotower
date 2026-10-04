import { useState } from "react";
import { Link } from "react-router-dom";

import { useAudit, useCapabilities, type AuditEvent } from "../api/helix";
import StatusBadge from "../components/StatusBadge";
import { Card, Empty, ErrorState, Loading, PageHeader, formatTime } from "../components/ui";

function What({ e }: { e: AuditEvent }) {
  if (e.kind === "tool_call") {
    return (
      <span>
        <code className="text-xs">{e.tool}</code> <span className="text-surface-500">by {e.requested_by}</span>{" "}
        {e.allowed ? <span className="text-surface-500">· {e.row_count ?? "—"} rows</span> : <span className="text-red-700">· refused: {e.detail}</span>}
      </span>
    );
  }
  if (e.kind === "decision") {
    return <span><StatusBadge status={e.action ?? ""} /> <span className="text-surface-600">{e.detail}</span></span>;
  }
  return <span className="text-surface-700">{e.detail}</span>;
}

/** Who did what, on which data — connector calls, sign-offs, releases — within the caller's scope. */
export default function Audit(): JSX.Element {
  const [capability, setCapability] = useState<string>("");
  const [kind, setKind] = useState<string>("");
  const caps = useCapabilities();
  const events = useAudit(capability || undefined);
  const rows = (events.data ?? []).filter((e) => !kind || e.kind === kind || (kind === "refused" && e.kind === "tool_call" && !e.allowed));

  return (
    <div>
      <PageHeader
        title="Audit"
        subtitle="The system of record. Model behaviour (prompts, timings, tokens) is in Phoenix, joined on the case."
        actions={
          <div className="flex min-w-0 flex-wrap gap-2">
            <select aria-label="Capability" value={capability} onChange={(e) => setCapability(e.target.value)} className="min-w-0 max-w-full rounded-lg border border-surface-300 bg-card px-2 py-1.5 text-sm">
              <option value="">All capabilities</option>
              {caps.data?.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
            <select aria-label="Event kind" value={kind} onChange={(e) => setKind(e.target.value)} className="min-w-0 max-w-full rounded-lg border border-surface-300 bg-card px-2 py-1.5 text-sm">
              <option value="">All events</option>
              <option value="tool_call">Connector calls</option>
              <option value="refused">Refused calls</option>
              <option value="decision">Sign-offs</option>
              <option value="release">Releases</option>
            </select>
          </div>
        }
      />
      <Card>
        {events.isLoading && <Loading what="audit" />}
        {events.error && <ErrorState error={events.error} />}
        {events.data && rows.length === 0 && <Empty>No events.</Empty>}
        {rows.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[40rem] text-left text-sm">
              <thead className="text-xs text-surface-500">
                <tr>
                  <th scope="col" className="px-2 py-2 font-medium">When</th>
                  <th scope="col" className="px-2 py-2 font-medium">Who</th>
                  <th scope="col" className="px-2 py-2 font-medium">Case</th>
                  <th scope="col" className="px-2 py-2 font-medium">What</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-surface-100">
                {rows.map((e, i) => (
                  <tr key={`${e.kind}-${e.at}-${i}`}>
                    <td className="whitespace-nowrap px-2 py-2 text-xs text-surface-500">{formatTime(e.at)}</td>
                    <td className="px-2 py-2 text-xs">{e.actor}</td>
                    <td className="px-2 py-2 text-xs"><Link className="text-primary-700 hover:underline" to={`/cases/${encodeURIComponent(e.case_id)}`}>{e.subject}</Link></td>
                    <td className="px-2 py-2 text-xs"><What e={e} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}
