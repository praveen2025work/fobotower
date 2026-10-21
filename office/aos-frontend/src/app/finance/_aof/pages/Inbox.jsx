// Generated from apps/web/src/pages/Inbox.tsx by apps/web/office/convert.mjs. Office changes to this file are
// kept by aof_sync.py on the next update; see office/README.md.
import { useMemo, useState } from "react";
import { Link } from "../office/router";
import clsx from "clsx";
import { Layers, UserCheck } from "lucide-react";

import { currentUser } from "../api/client";
import { useInbox } from "../api/aof";
import DelegationPanel from "../components/DelegationPanel";
import QuestionsForYou from "../components/QuestionsForYou";
import TaskLink from "../components/TaskLink";
import { useIsPhone } from "../hooks/useIsPhone";
import StatusBadge from "../components/StatusBadge";
import { DueBadge, ageText, urgency } from "../components/Urgency";
import { Card, Empty, ErrorState, Loading, PageHeader, formatTime, formatValue } from "../components/ui";

/** Many tasks of one agent, group and business date waiting on the same person (a task per
 *  master book is hundreds a COB): one row that opens the agent's Summary, where they are
 *  worked by region, desk or pattern. */
const RUN = 6;

export function collapseRuns(rows) {
  const runs = new Map();
  for (const r of rows) {
    if (!r.summary_date || r.acting_for) continue;
    const key = [r.capability_id, r.team_group ?? "", r.summary_date, r.action].join("|");
    runs.set(key, [...(runs.get(key) ?? []), r]);
  }
  const out = [];
  const placed = new Set();
  for (const r of rows) {
    const key = [r.capability_id, r.team_group ?? "", r.summary_date, r.action].join("|");
    const run = r.summary_date && !r.acting_for ? runs.get(key) : undefined;
    if (!run || run.length < RUN) out.push(r);
    else if (!placed.has(key)) {
      placed.add(key);
      out.push({
        key,
        capability_id: r.capability_id,
        capability_name: r.capability_name,
        case_label: r.case_label,
        date: r.summary_date,
        action: r.action,
        rows: run,
      });
    }
  }
  return out;
}

const isRun = (e) => "rows" in e;
const summaryLink = (run) =>
  `/capabilities/${encodeURIComponent(run.capability_id)}?tab=summary&date=${encodeURIComponent(run.date)}`;

function runTotals(run) {
  const open = run.rows.reduce((a, r) => a + r.groups - r.decided, 0);
  const groups = run.rows.reduce((a, r) => a + r.groups, 0);
  const escalated = run.rows.reduce((a, r) => a + r.escalated, 0);
  const exposure = run.rows.reduce((a, r) => a + (r.exposure ?? 0), 0);
  const first = [...run.rows].sort((a, b) => urgency(a) - urgency(b))[0];
  return { open, groups, escalated, exposure, unit: run.rows.find((r) => r.unit)?.unit, first };
}

function RunText({ run }) {
  return (
    <>
      <span className="inline-flex items-center gap-1">
        <Layers size={13} className="shrink-0" /> {run.case_label} · {run.date}:{" "}
        {run.rows.length.toLocaleString("en-GB")} tasks
      </span>
      <span className="block text-xs font-normal text-surface-500">
        Work them by region, desk or pattern in the summary
      </span>
    </>
  );
}

/** Phones: one card per case — what it is, what it needs, how urgent. */
function InboxCards({ rows }) {
  return (
    <ul className="divide-y divide-surface-100">
      {collapseRuns(rows).map((r) =>
        isRun(r) ? (
          <li key={r.key}>
            <Link to={summaryLink(r)} className="block py-3 active:bg-surface-50">
              <div className="flex items-start justify-between gap-2">
                <span className="min-w-0 font-medium leading-snug text-primary-700">
                  <RunText run={r} />
                </span>
                <StatusBadge status={r.action} />
              </div>
              <div className="mt-1.5 text-xs text-surface-600">
                {runTotals(r).open.toLocaleString("en-GB")} of {runTotals(r).groups.toLocaleString("en-GB")} to decide ·{" "}
                {r.capability_name}
              </div>
            </Link>
          </li>
        ) : (
          <li key={r.case_id}>
            <TaskLink id={r.case_id} className="block py-3 active:bg-surface-50">
              <div className="flex items-start justify-between gap-2">
                <span className="min-w-0 font-medium leading-snug text-primary-700">
                  {r.subject}
                  <span className="block text-xs font-normal text-surface-500">
                    {r.case_label} · {r.capability_name}
                  </span>
                </span>
                <StatusBadge status={r.action} />
              </div>
              <div className="mt-1.5 flex flex-wrap items-center gap-1.5 text-xs text-surface-600">
                <WhatsLeft r={r} />
                {r.acting_for && (
                  <span className="inline-flex items-center gap-1 rounded bg-accent-50 px-1.5 text-[11px] font-medium text-accent-800">
                    <UserCheck size={10} /> for {r.acting_for}
                  </span>
                )}
              </div>
              <div className="mt-1.5 flex flex-wrap items-center gap-2 text-xs text-surface-500">
                <DueBadge dueAt={r.due_at} state={r.due_state} compact />
                {r.exposure != null && (
                  <span className="tabular-nums text-surface-700">
                    {formatValue(r.exposure)}
                    {r.unit ? ` ${r.unit}` : ""} at stake
                  </span>
                )}
              </div>
            </TaskLink>
          </li>
        ),
      )}
    </ul>
  );
}

/** What is left to do on a case, in one line, with the one flag that matters most. */
export function WhatsLeft({ r }) {
  if (r.gate) return <span>Approve the work so far</span>;
  const open = r.groups - r.decided;
  const flags = [
    [r.escalated, "escalated", "bg-orange-100 text-orange-800"],
    [r.needs_confirmation ?? 0, "to confirm", "bg-orange-100 text-orange-800"],
    [r.judgement_calls ?? 0, "judgement", "bg-orange-100 text-orange-800"],
  ];
  const shown = flags.filter(([n]) => n > 0);
  const top = shown[0];
  return (
    <span
      className="inline-flex flex-wrap items-center gap-1.5"
      title={shown.map(([n, l]) => `${n} ${l}`).join(" · ") || undefined}
    >
      <span>
        {open} of {r.groups} to decide
      </span>
      {top && (
        <span className={`rounded px-1.5 py-0.5 text-[10px] font-semibold ${top[2]}`}>
          {top[0]} {top[1]}
        </span>
      )}
    </span>
  );
}

export function InboxTable({ rows, limit }) {
  const money = rows.some((r) => r.exposure != null);
  const phone = useIsPhone();
  const entries = collapseRuns(rows).slice(0, limit);
  if (phone) return <InboxCards rows={entries.flatMap((e) => (isRun(e) ? e.rows : [e]))} />;
  return (
    <>
      <div className="overflow-x-auto">
        <table className="hx-rows w-full text-left text-sm">
          <thead className="text-xs text-surface-500">
            <tr>
              <th scope="col" className="px-2 py-2 font-medium">
                Needs
              </th>
              <th scope="col" className="px-2 py-2 font-medium">
                Task
              </th>
              <th scope="col" className="px-2 py-2 font-medium">
                Agent
              </th>
              <th scope="col" className="px-2 py-2 font-medium">
                What's left
              </th>
              {money && (
                <th scope="col" className="px-2 py-2 text-right font-medium">
                  At stake
                </th>
              )}
              <th scope="col" className="px-2 py-2 font-medium">
                When
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-surface-100">
            {entries.map((r) =>
              isRun(r) ? (
                <RunRow key={r.key} run={r} money={money} />
              ) : (
                <tr key={r.case_id} className="hover:bg-surface-50">
                  <td className="px-2 py-2">
                    <StatusBadge status={r.action} />
                  </td>
                  <td className="min-w-[14rem] px-2 py-2">
                    <TaskLink id={r.case_id} className="font-medium text-primary-700 hover:underline">
                      {r.case_label}: {r.subject}
                    </TaskLink>
                    {r.follow_up_of && !/late items/i.test(r.subject) && (
                      <Link
                        to={`/cases/${encodeURIComponent(r.follow_up_of)}`}
                        title="Late items for a book and date already worked — see the day's task"
                        className="ml-2 rounded bg-surface-100 px-1.5 py-0.5 text-[10px] font-semibold text-surface-800 hover:underline"
                      >
                        late items
                      </Link>
                    )}
                    {r.acting_for && (
                      <span className="ml-2 inline-flex items-center gap-1 rounded bg-accent-50 px-1.5 py-0.5 text-[10px] font-medium text-accent-800">
                        <UserCheck size={10} /> for {r.acting_for}
                      </span>
                    )}
                  </td>
                  <td className="px-2 py-2 text-surface-600">{r.capability_name}</td>
                  <td className="px-2 py-2 text-xs text-surface-600">
                    <WhatsLeft r={r} />
                  </td>
                  {money && (
                    <td className="whitespace-nowrap px-2 py-2 text-right text-xs tabular-nums text-surface-700">
                      {r.exposure != null ? `${formatValue(r.exposure)}${r.unit ? ` ${r.unit}` : ""}` : "—"}
                    </td>
                  )}
                  <td
                    className="px-2 py-2 text-xs text-surface-500"
                    title={`Opened ${formatTime(r.opened_at)} by ${r.opened_by}${ageText(r.age_hours) ? ` · ${ageText(r.age_hours)}` : ""}`}
                  >
                    <DueBadge dueAt={r.due_at} state={r.due_state} compact />
                  </td>
                </tr>
              ),
            )}
          </tbody>
        </table>
      </div>
    </>
  );
}

function RunRow({ run, money }) {
  const t = runTotals(run);
  return (
    <tr className="hover:bg-surface-50">
      <td className="px-2 py-2">
        <StatusBadge status={run.action} />
      </td>
      <td className="min-w-[14rem] px-2 py-2">
        <Link to={summaryLink(run)} className="font-medium text-primary-700 hover:underline">
          <RunText run={run} />
        </Link>
      </td>
      <td className="px-2 py-2 text-surface-600">{run.capability_name}</td>
      <td className="px-2 py-2 text-xs text-surface-600">
        <span className="inline-flex flex-wrap items-center gap-1.5">
          <span>
            {t.open.toLocaleString("en-GB")} of {t.groups.toLocaleString("en-GB")} to decide
          </span>
          {t.escalated > 0 && (
            <span className="rounded bg-orange-100 px-1.5 py-0.5 text-[10px] font-semibold text-orange-800">
              {t.escalated} escalated
            </span>
          )}
        </span>
      </td>
      {money && (
        <td className="whitespace-nowrap px-2 py-2 text-right text-xs tabular-nums text-surface-700">
          {t.exposure ? `${formatValue(Math.round(t.exposure))}${t.unit ? ` ${t.unit}` : ""}` : "—"}
        </td>
      )}
      <td className="px-2 py-2 text-xs text-surface-500">
        <DueBadge dueAt={t.first.due_at} state={t.first.due_state} compact />
      </td>
    </tr>
  );
}

const FILTERS = [
  { id: "all", label: "All", test: () => true },
  { id: "urgent", label: "Overdue or due soon", test: (r) => r.due_state === "overdue" || r.due_state === "due_soon" },
  { id: "confirm", label: "Needs confirmation", test: (r) => (r.needs_confirmation ?? 0) > 0 },
  { id: "judgement", label: "Judgement calls", test: (r) => (r.judgement_calls ?? 0) > 0 },
  { id: "escalated", label: "Escalated", test: (r) => r.escalated > 0 },
  { id: "covering", label: "Covering for others", test: (r) => !!r.acting_for },
];

const SORTS = {
  urgent: { label: "Most urgent first", cmp: (a, b) => urgency(a) - urgency(b) },
  money: { label: "Most at stake first", cmp: (a, b) => (b.exposure ?? -1) - (a.exposure ?? -1) },
  oldest: { label: "Oldest first", cmp: (a, b) => a.opened_at.localeCompare(b.opened_at) },
  newest: { label: "Newest first", cmp: (a, b) => b.opened_at.localeCompare(a.opened_at) },
};

/** One queue across every capability: what waits on the signed-in user. */
export default function InboxPage() {
  const inbox = useInbox();
  const [filter, setFilter] = useState("all");
  const [sort, setSort] = useState("urgent");
  const [capability, setCapability] = useState("");
  const rows = inbox.data ?? [];
  const capabilities = useMemo(
    () => [...new Map(rows.map((r) => [r.capability_id, r.capability_name])).entries()],
    [rows],
  );
  const shown = useMemo(() => {
    const test = FILTERS.find((f) => f.id === filter).test;
    return rows.filter((r) => test(r) && (!capability || r.capability_id === capability)).sort(SORTS[sort].cmp);
  }, [rows, filter, sort, capability]);

  return (
    <div>
      <PageHeader title="Inbox" subtitle="Tasks waiting for your review or your release of a write-back." />
      <QuestionsForYou />
      <Card>
        {inbox.isLoading && <Loading what="inbox" />}
        {inbox.error && <ErrorState error={inbox.error} />}
        {inbox.data && rows.length === 0 && <Empty>Nothing is waiting on you.</Empty>}
        {rows.length > 0 && (
          <>
            <div className="mb-3 flex flex-wrap items-center gap-2">
              <div
                className="-mx-1 flex w-full gap-1 overflow-x-auto px-1 pb-1 sm:w-auto sm:flex-wrap sm:overflow-visible sm:pb-0"
                role="group"
                aria-label="Filter"
              >
                {FILTERS.map((f) => {
                  const n = rows.filter(f.test).length;
                  if (f.id !== "all" && n === 0) return null;
                  return (
                    <button
                      key={f.id}
                      onClick={() => setFilter(f.id)}
                      aria-pressed={filter === f.id}
                      className={clsx(
                        "shrink-0 whitespace-nowrap rounded-full border px-2.5 py-1 text-xs font-medium",
                        filter === f.id
                          ? "border-primary-400 bg-primary-50 text-primary-800"
                          : "border-surface-200 text-surface-600 hover:bg-surface-50",
                      )}
                    >
                      {f.label} <span className="text-surface-400">{n}</span>
                    </button>
                  );
                })}
              </div>
              <div className="flex w-full flex-wrap gap-2 sm:ml-auto sm:w-auto">
                {capabilities.length > 1 && (
                  <select
                    aria-label="Agent"
                    value={capability}
                    onChange={(e) => setCapability(e.target.value)}
                    className="rounded-lg border border-surface-300 bg-card px-2 py-1 text-xs"
                  >
                    <option value="">All agents</option>
                    {capabilities.map(([id, name]) => (
                      <option key={id} value={id}>
                        {name}
                      </option>
                    ))}
                  </select>
                )}
                <select
                  aria-label="Sort"
                  value={sort}
                  onChange={(e) => setSort(e.target.value)}
                  className="rounded-lg border border-surface-300 bg-card px-2 py-1 text-xs"
                >
                  {Object.entries(SORTS).map(([id, s]) => (
                    <option key={id} value={id}>
                      {s.label}
                    </option>
                  ))}
                </select>
              </div>
            </div>
            {shown.length === 0 ? <Empty>Nothing matches this filter.</Empty> : <InboxTable rows={shown} />}
          </>
        )}
      </Card>
      <DelegationPanel me={currentUser()} />
    </div>
  );
}
