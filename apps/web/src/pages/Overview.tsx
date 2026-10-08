import { Link } from "react-router-dom";
import { AlertTriangle, ArrowRight, Ban, Bot, Clock, Timer } from "lucide-react";

import { currentUser } from "../api/client";
import { useInbox, useMe, useOverview } from "../api/aof";
import StatCard from "../components/StatCard";
import { urgency } from "../components/Urgency";
import { Card, CountUp, Empty, ErrorState, Fold, Loading } from "../components/ui";
import { InboxTable } from "./Inbox";

/** The banner: what is waiting on me, in three numbers, and the way in. */
function OverviewHero({ review, overdue, release }: { review?: number; overdue: number; release?: number }) {
  const waiting = (review ?? 0) + (release ?? 0);
  const tiles: [string, number | undefined][] = [["to review", review], ["overdue", overdue], ["to release", release]];
  return (
    <section aria-label="Overview" className="hx-hero hx-rise mb-5 grid gap-5 p-5 sm:p-7 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-center">
      <div className="min-w-0">
        <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">
          {waiting ? `${waiting} ${waiting === 1 ? "case is" : "cases are"} waiting on you` : "Nothing is waiting on you"}
        </h1>
        {waiting > 0 && (
          <Link to="/inbox" className="mt-4 inline-flex items-center gap-1.5 rounded-lg bg-nav-mark px-3.5 py-2 text-sm font-semibold text-nav-bg hover:opacity-90">
            Start with the most urgent <ArrowRight size={14} />
          </Link>
        )}
      </div>
      <div className="grid grid-cols-3 gap-2 lg:w-80">
        {tiles.map(([label, n]) => (
          <div key={label} className="hx-glass rounded-xl px-3 py-2.5">
            <p className="hx-gradient-text text-2xl font-bold tabular-nums">{n == null ? "–" : <CountUp value={n} />}</p>
            <p className="text-[11px] leading-tight text-nav-fg">{label}</p>
          </div>
        ))}
      </div>
    </section>
  );
}

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
      <OverviewHero review={overview.data?.awaiting_my_review} overdue={overdue} release={overview.data?.awaiting_my_release} />
      {overview.isLoading && <Loading what="overview" />}
      {overview.error && <ErrorState error={overview.error} />}
      {overview.data && (
        <>
          {(overview.data.hours_saved_30d || (measured && measured.decisions > 0) || admin) && (
            <Fold className="mb-4" remember="overview-impact" title="Impact"
              summary={[overview.data.hours_saved_30d && `${overview.data.hours_saved_30d.value} h saved in 30 days`,
                measured && measured.decisions > 0 && `${measured.hours_saved} h measured`].filter(Boolean).join(" · ")}>
              <div className="hx-stagger grid grid-cols-2 gap-2 sm:gap-3 md:grid-cols-4">
                {overview.data.hours_saved_30d && <StatCard icon={Clock} value={`${overview.data.hours_saved_30d.value} h`} label="Hours saved (30 days)" />}
                {measured && measured.decisions > 0 && <StatCard icon={Timer} value={`${measured.hours_saved} h`} label="Hours saved (measured)" />}
                <StatCard icon={AlertTriangle} value={overview.data.escalated_groups} label="Escalated to people" />
                {admin && <StatCard icon={Bot} value={overview.data.model_calls_24h} label="Model tool calls (24h)" />}
                {admin && <StatCard icon={Ban} value={overview.data.refused_calls_24h} label="Refused calls (24h)" />}
              </div>
              <p className="mt-2 text-[11px] text-surface-500">
                {overview.data.hours_saved_30d && <>Declared: {overview.data.hours_saved_30d.basis}. </>}
                {measured && <>Measured: {measured.basis}{measured.median_seconds != null && ` · median ${Math.round(measured.median_seconds)} s per decision`}.</>}
              </p>
            </Fold>
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
                <ul className="-my-1 divide-y divide-surface-100">
                  {[...overview.data.capabilities].map((c) => {
                    const n = (pre: string[]) => Object.entries(c.statuses).filter(([k]) => pre.some((p) => k.startsWith(p))).reduce((a, [, v]) => a + v, 0);
                    return { c, waiting: n(["awaiting", "paused"]), done: n(["completed"]) };
                  }).sort((x, y) => y.waiting - x.waiting).map(({ c, waiting, done }) => (
                    <li key={c.id}>
                      <Link to={`/capabilities/${encodeURIComponent(c.id)}`} className="group flex items-baseline gap-3 py-2">
                        <span className="min-w-0 flex-1 truncate text-sm font-medium text-surface-800 group-hover:text-primary-700">{c.name}</span>
                        <span className="shrink-0 text-xs tabular-nums text-surface-500">
                          {waiting ? <><b className="font-semibold text-surface-800">{waiting}</b> waiting</> : done ? `${done} done` : "–"}
                        </span>
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
