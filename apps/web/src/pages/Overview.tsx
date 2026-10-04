import { Link } from "react-router-dom";
import { AlertTriangle, Ban, Bot, Clock, Inbox, Layers, Send, Timer } from "lucide-react";

import { currentUser } from "../api/client";
import { useInbox, useMe, useOverview } from "../api/helix";
import StatCard from "../components/StatCard";
import StatusBadge from "../components/StatusBadge";
import { urgency } from "../components/Urgency";
import { Card, Empty, ErrorState, Loading, PageHeader } from "../components/ui";
import { InboxTable } from "./Inbox";

/** Home: what needs me, and how every capability I can see is doing. */
export default function Overview(): JSX.Element {
  const overview = useOverview();
  const inbox = useInbox();
  const me = useMe(currentUser());
  const admin = !!me.data?.is_admin;
  const overdue = (inbox.data ?? []).filter((r) => r.due_state === "overdue").length;
  const measured = overview.data?.measured_review;
  const urgentFirst = [...(inbox.data ?? [])].sort((a, b) => urgency(a) - urgency(b));

  return (
    <div>
      <PageHeader title="Overview" subtitle="Everything waiting on you, across every capability you can use." />
      {overview.isLoading && <Loading what="overview" />}
      {overview.error && <ErrorState error={overview.error} />}
      {overview.data && (
        <>
          <div className="mb-5 grid grid-cols-2 gap-2 sm:gap-3 md:grid-cols-3 xl:grid-cols-6">
            {overview.data.hours_saved_30d && (
              <div title={overview.data.hours_saved_30d.basis}>
                <StatCard icon={Clock} value={`${overview.data.hours_saved_30d.value} h`} label="Hours saved (30 days)" />
              </div>
            )}
            {measured && measured.decisions > 0 && (
              <div title={measured.basis}>
                <StatCard icon={Timer} value={`${measured.hours_saved} h`} label="Hours saved (measured)" />
              </div>
            )}
            <StatCard icon={Inbox} value={overview.data.awaiting_my_review} label="Awaiting my review" />
            <StatCard icon={Clock} value={overdue} label="Overdue" />
            <StatCard icon={Send} value={overview.data.awaiting_my_release} label="Awaiting my release" />
            <StatCard icon={AlertTriangle} value={overview.data.escalated_groups} label="Escalated to people" />
            {admin && <StatCard icon={Bot} value={overview.data.model_calls_24h} label="Model tool calls (24h)" />}
            {admin && <StatCard icon={Ban} value={overview.data.refused_calls_24h} label="Refused calls (24h)" />}
          </div>

          {overview.data.hours_saved_30d && (
            <p className="-mt-3 mb-1 text-[11px] text-surface-500">Hours saved (declared): {overview.data.hours_saved_30d.basis}.</p>
          )}
          {measured && (
            <p className="mb-5 text-[11px] text-surface-500">
              Measured: {measured.basis}
              {measured.median_seconds != null && ` · median ${Math.round(measured.median_seconds)} s per decision`}.
            </p>
          )}
          <div className="grid gap-4 xl:grid-cols-3">
            <Card title="My inbox" className="xl:col-span-2" aside={<Link to="/inbox" className="text-xs font-medium text-primary-600 hover:underline">Open inbox</Link>}>
              {inbox.isLoading && <Loading what="inbox" />}
              {inbox.error && <ErrorState error={inbox.error} />}
              {inbox.data && (inbox.data.length === 0 ? <Empty>Nothing is waiting on you.</Empty> : <InboxTable rows={urgentFirst.slice(0, 8)} />)}
            </Card>

            <Card title="Capabilities">
              {overview.data.capabilities.length === 0 ? (
                <Empty>No capabilities for your roles.</Empty>
              ) : (
                <ul className="space-y-3">
                  {overview.data.capabilities.map((c) => (
                    <li key={c.id}>
                      <Link to={`/capabilities/${encodeURIComponent(c.id)}`} className="group block rounded-lg border border-surface-200 p-3 hover:border-primary-300">
                        <div className="flex items-center gap-2">
                          <Layers size={14} className="text-accent-600" />
                          <span className="text-sm font-semibold text-surface-800 group-hover:text-primary-700">{c.name}</span>
                        </div>
                        <div className="mt-2 flex flex-wrap gap-1.5">
                          {Object.entries(c.statuses).map(([status, n]) => (
                            <span key={status} className="inline-flex items-center gap-1 text-xs text-surface-500">
                              <StatusBadge status={status} /> {n}
                            </span>
                          ))}
                          {Object.keys(c.statuses).length === 0 && <span className="text-xs text-surface-400">No {c.case_label.toLowerCase()}s yet</span>}
                        </div>
                      </Link>
                    </li>
                  ))}
                </ul>
              )}
            </Card>
          </div>
        </>
      )}
    </div>
  );
}
