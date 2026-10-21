// An agent's business date at a glance, for when there are too many tasks to open one
// by one (a task per master book: 1,000–2,000 a COB). The day is grouped by the facts
// the agent's groups name (case.summarize_by: business, region, desk, product); a click
// narrows to that slice. The same break across many books is one row under "Patterns",
// approved once — each task still checks the decision as its own "Approve all" would.

import { useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import clsx from "clsx";
import { CheckCheck, ChevronRight, Layers, X } from "lucide-react";

import {
  useDecideAcross,
  useSummary,
  type AgentSummary,
  type ChecklistAnswer,
  type SummaryProposal,
  type SummaryTask,
} from "../../api/aof";
import { recorded } from "../../scope";
import StatusBadge from "../StatusBadge";
import { DueBadge } from "../Urgency";
import { Card, Empty, ErrorState, Loading } from "../ui";

const NONE = "—";
const PAGE = 50;

/** Where a task stands, in the words the summary counts it by. */
type Standing = "clean" | "waiting" | "tollgate" | "signed_off" | "running" | "failed";

function standing(t: SummaryTask): Standing {
  if (t.status === "failed" || t.status === "stopped") return "failed";
  if (t.status.startsWith("paused_before")) return "tollgate";
  if (t.status === "awaiting_review") return "waiting";
  if (t.status === "running" || t.status === "queued") return "running";
  return t.items === 0 ? "clean" : "signed_off";
}

const money = (n: number, unit?: string | null) =>
  `${n.toLocaleString("en-GB", { notation: "compact", maximumFractionDigits: 1 })}${unit ? ` ${unit}` : ""}`;

const stake = (t: SummaryTask) => t.open.reduce((a, g) => a + (g.amount ?? 0), 0);

interface Slice {
  value: string;
  tasks: SummaryTask[];
  counts: Record<Standing, number>;
  openBreaks: number;
  escalated: number;
  atStake: number;
}

function slices(tasks: SummaryTask[], by: number): Slice[] {
  const out = new Map<string, Slice>();
  for (const t of tasks) {
    const value = t.facts[by] ?? NONE;
    const s = out.get(value) ?? { value, tasks: [], counts: { clean: 0, waiting: 0, tollgate: 0, signed_off: 0, running: 0, failed: 0 }, openBreaks: 0, escalated: 0, atStake: 0 };
    s.tasks.push(t);
    s.counts[standing(t)] += 1;
    s.openBreaks += t.open.reduce((a, g) => a + g.items, 0);
    s.escalated += t.open.filter((g) => g.status === "escalated").length;
    s.atStake += stake(t);
    out.set(value, s);
  }
  return [...out.values()].sort((a, b) => b.tasks.length - a.tasks.length || a.value.localeCompare(b.value));
}

interface Pattern {
  key: string;
  label: string;
  verdict: string | null;
  group: string | null;
  books: number;
  breaks: number;
  amount: number;
  ready: { task: SummaryTask; proposal: SummaryProposal }[];
  held: Record<string, number>;
  needsComment: boolean;
}

/** Why proposals stay for one-by-one review, as "24 judgement calls". */
const HELD_WORDS: Record<string, [string, string]> = {
  confirmation: ["verdict to confirm", "verdicts to confirm"],
  judgement: ["judgement call", "judgement calls"],
  escalated: ["escalated", "escalated"],
  model: ["proposed by the model", "proposed by the model"],
  reserved: ["reserved decision", "reserved decisions"],
  authority: ["above an authority tier", "above an authority tier"],
};
const held = (k: string, n: number) => `${n} ${(HELD_WORDS[k] ?? [k, k])[n === 1 ? 0 : 1]}`;

/** The same proposal (label and verdict, in one group) across the tasks shown. */
function patterns(tasks: SummaryTask[]): Pattern[] {
  const out = new Map<string, Pattern>();
  const seen = new Set<string>();
  for (const t of tasks) {
    for (const g of t.open) {
      const key = `${t.team_group ?? ""}|${g.label}|${g.verdict ?? ""}`;
      const p = out.get(key) ?? { key, label: g.label, verdict: g.verdict, group: t.team_group, books: 0, breaks: 0, amount: 0, ready: [], held: {}, needsComment: false };
      if (!seen.has(`${key}|${t.case_id}`)) {
        seen.add(`${key}|${t.case_id}`);
        p.books += 1;
      }
      p.breaks += g.items;
      p.amount += g.amount ?? 0;
      if (g.ready) {
        p.ready.push({ task: t, proposal: g });
        p.needsComment ||= g.needs_comment;
      }
      for (const b of g.blockers) p.held[b] = (p.held[b] ?? 0) + 1;
      out.set(key, p);
    }
  }
  return [...out.values()].sort((a, b) => b.breaks - a.breaks || b.amount - a.amount);
}

export default function SummaryPanel({ capabilityId, initialDate }: { capabilityId: string; initialDate?: string }) {
  const [date, setDate] = useState<string | undefined>(initialDate);
  const summary = useSummary(capabilityId, date);
  if (summary.isLoading) return <Loading what="summary" />;
  if (summary.error) return <ErrorState error={summary.error} />;
  if (!summary.data) return null;
  return <Day key={summary.data.date ?? "none"} data={summary.data} onDate={setDate} capabilityId={capabilityId} />;
}

function Day({ data, onDate, capabilityId }: { data: AgentSummary; onDate: (d: string) => void; capabilityId: string }) {
  const dims = data.dimensions;
  const [filters, setFilters] = useState<{ dim: number; value: string }[]>([]);
  const [by, setBy] = useState(0);
  const [shown, setShown] = useState(PAGE);
  const tasks = useMemo(
    () => data.tasks.filter((t) => filters.every((f) => (t.facts[f.dim] ?? NONE) === f.value)),
    [data.tasks, filters],
  );
  const rows = useMemo(() => (dims.length ? slices(tasks, by) : []), [tasks, by, dims.length]);
  const pats = useMemo(() => patterns(tasks), [tasks]);
  const counts = useMemo(() => slices(tasks.map((t) => ({ ...t, facts: [] })), 0)[0], [tasks]);   // the whole selection as one slice
  const unit = data.tasks.find((t) => t.unit)?.unit ?? null;
  const groupNames = Object.fromEntries(data.groups.map((g) => [g.group, g.name]));
  const narrow = (value: string) => {
    setFilters([...filters, { dim: by, value }]);
    const next = dims.findIndex((_, i) => i !== by && !filters.some((f) => f.dim === i) && i > by);
    if (next >= 0) setBy(next);
    setShown(PAGE);
  };
  const ordered = useMemo(() => {
    const rank: Record<Standing, number> = { waiting: 0, tollgate: 1, failed: 2, running: 3, signed_off: 4, clean: 5 };
    return [...tasks].sort((a, b) => rank[standing(a)] - rank[standing(b)] || stake(b) - stake(a));
  }, [tasks]);

  if (!data.date) return <Empty>No tasks yet. The summary groups a day's tasks once there are some.</Empty>;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
        <label className="flex items-center gap-2 text-sm text-surface-600">
          Business date
          <select aria-label="Business date" value={data.date} onChange={(e) => onDate(e.target.value)}
            className="rounded-lg border border-surface-300 bg-card px-2 py-1 text-sm">
            {data.dates.map((d) => <option key={d} value={d}>{d}</option>)}
          </select>
        </label>
        {counts && (
          <p className="text-sm text-surface-600" aria-label="Day totals">
            <b className="font-semibold text-surface-900">{tasks.length.toLocaleString("en-GB")}</b> tasks ·{" "}
            {counts.counts.clean.toLocaleString("en-GB")} clean ·{" "}
            <span className="font-medium text-orange-700">{counts.counts.waiting.toLocaleString("en-GB")} waiting for review</span>
            {counts.counts.tollgate > 0 && <> · {counts.counts.tollgate} at a tollgate</>} ·{" "}
            {counts.counts.signed_off.toLocaleString("en-GB")} signed off
            {counts.counts.failed > 0 && <> · <span className="text-red-700">{counts.counts.failed} failed</span></>}
            {counts.atStake > 0 && <> · {money(counts.atStake, unit)} open</>}
          </p>
        )}
      </div>

      {filters.length > 0 && (
        <div className="flex flex-wrap items-center gap-2" aria-label="Filters">
          {filters.map((f, i) => (
            <button key={i} type="button" onClick={() => { setFilters(filters.slice(0, i)); setBy(f.dim); setShown(PAGE); }}
              className="inline-flex items-center gap-1 rounded-full border border-primary-200 bg-primary-50 px-2.5 py-0.5 text-xs font-medium text-primary-700 hover:bg-primary-100">
              {dims[f.dim].label}: {f.value} <X size={11} />
            </button>
          ))}
          <button type="button" onClick={() => { setFilters([]); setBy(0); setShown(PAGE); }} className="text-xs text-surface-500 hover:underline">Clear</button>
        </div>
      )}

      {dims.length > 0 && (
        <Card
          title={<span className="inline-flex items-center gap-1.5"><Layers size={14} /> By {dims[by].label.toLowerCase()}</span>}
          aside={
            <div className="flex flex-wrap gap-1" role="tablist" aria-label="Group by">
              {dims.map((d, i) => (
                <button key={d.field} type="button" role="tab" aria-selected={by === i} onClick={() => setBy(i)}
                  disabled={filters.some((f) => f.dim === i)}
                  className={clsx("rounded-md px-2 py-0.5 text-xs font-medium disabled:opacity-40",
                    by === i ? "bg-brand-accent text-brand-accent-fg" : "text-surface-600 hover:bg-surface-50")}>
                  {d.label}
                </button>
              ))}
            </div>
          }
        >
          <div className="overflow-x-auto">
            <table className="hx-rows w-full text-left text-sm">
              <thead className="text-xs text-surface-500">
                <tr>
                  <th scope="col" className="px-2 py-2 font-medium">{dims[by].label}</th>
                  <th scope="col" className="px-2 py-2 text-right font-medium">Tasks</th>
                  <th scope="col" className="px-2 py-2 text-right font-medium">Clean</th>
                  <th scope="col" className="px-2 py-2 text-right font-medium">Waiting</th>
                  <th scope="col" className="px-2 py-2 text-right font-medium">Signed off</th>
                  <th scope="col" className="px-2 py-2 text-right font-medium">Open breaks</th>
                  <th scope="col" className="px-2 py-2 text-right font-medium">Escalated</th>
                  <th scope="col" className="px-2 py-2 text-right font-medium">Open amount</th>
                  <th scope="col" className="w-32 px-2 py-2 font-medium">Done</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-surface-100">
                {rows.map((r) => {
                  const done = r.counts.clean + r.counts.signed_off;
                  const label = dims[by].field === "team_group" ? (groupNames[r.value] ?? r.value) : r.value;
                  return (
                    <tr key={r.value} className="hover:bg-surface-50">
                      <td className="px-2 py-1.5">
                        <button type="button" onClick={() => narrow(r.value)} className="inline-flex items-center gap-1 text-left font-medium text-primary-700 hover:underline">
                          {label} <ChevronRight size={12} />
                        </button>
                      </td>
                      <td className="px-2 py-1.5 text-right tabular-nums">{r.tasks.length.toLocaleString("en-GB")}</td>
                      <td className="px-2 py-1.5 text-right tabular-nums text-surface-500">{r.counts.clean.toLocaleString("en-GB")}</td>
                      <td className={clsx("px-2 py-1.5 text-right tabular-nums", r.counts.waiting && "font-medium text-orange-700")}>{r.counts.waiting.toLocaleString("en-GB")}</td>
                      <td className="px-2 py-1.5 text-right tabular-nums">{r.counts.signed_off.toLocaleString("en-GB")}</td>
                      <td className="px-2 py-1.5 text-right tabular-nums">{r.openBreaks.toLocaleString("en-GB")}</td>
                      <td className={clsx("px-2 py-1.5 text-right tabular-nums", r.escalated && "text-orange-700")}>{r.escalated}</td>
                      <td className="whitespace-nowrap px-2 py-1.5 text-right text-xs tabular-nums">{r.atStake ? money(r.atStake, unit) : NONE}</td>
                      <td className="px-2 py-1.5">
                        <div className="h-1.5 w-full overflow-hidden rounded-full bg-surface-100" title={`${done} of ${r.tasks.length} done`}>
                          <div className="h-full rounded-full bg-accent-500" style={{ width: `${(100 * done) / Math.max(1, r.tasks.length)}%` }} />
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      <Card title="The same break across many books" aside={<span className="text-xs text-surface-500">open proposals{filters.length ? " in this selection" : ""}, decided once for every task</span>}>
        {pats.length === 0 ? (
          <Empty>Nothing open here.</Empty>
        ) : (
          <ul className="divide-y divide-surface-100" aria-label="Patterns">
            {pats.map((p) => (
              <PatternRow key={p.key} p={p} capabilityId={capabilityId} unit={unit} groupName={p.group ? groupNames[p.group] : undefined}
                checklist={data.groups.find((g) => g.group === p.group)?.checklist ?? []}
                where={filters.map((f) => f.value).join(" · ")} />
            ))}
          </ul>
        )}
      </Card>

      <Card title={`Tasks${filters.length ? ` in ${filters.map((f) => f.value).join(" · ")}` : ""}`} aside={<span className="text-xs text-surface-500">waiting first, then by open amount</span>}>
        <ul className="divide-y divide-surface-100" aria-label="Tasks">
          {ordered.slice(0, shown).map((t) => <TaskRow key={t.case_id} t={t} unit={unit} />)}
        </ul>
        {ordered.length > shown && (
          <button type="button" onClick={() => setShown(shown + PAGE)} className="mt-2 text-sm font-medium text-primary-700 hover:underline">
            Show {Math.min(PAGE, ordered.length - shown)} more of {(ordered.length - shown).toLocaleString("en-GB")}
          </button>
        )}
      </Card>
    </div>
  );
}

function TaskRow({ t, unit }: { t: SummaryTask; unit: string | null }) {
  const path = `/cases/${encodeURIComponent(t.case_id)}`;
  const opens = recorded(path);
  const breaks = t.open.reduce((a, g) => a + g.items, 0);
  const body = (
    <>
      <span className="min-w-0 flex-1">
        <span className={clsx("font-medium", opens ? "text-surface-800" : "text-surface-600")}>{t.subject}</span>
        {!opens && <span className="ml-2 text-[11px] text-surface-400">in the live console</span>}
      </span>
      <span className="flex shrink-0 items-center gap-3 text-xs text-surface-500">
        {breaks > 0 && <span>{breaks} open · {money(stake(t), unit)}</span>}
        <DueBadge state={t.due_state} dueAt={t.due_at} compact />
        <StatusBadge status={standing(t) === "clean" ? "clean" : t.status} />
      </span>
    </>
  );
  return (
    <li>
      {opens ? (
        <Link to={path} className="flex items-center justify-between gap-2 px-1 py-2 text-sm hover:bg-surface-50">{body}</Link>
      ) : (
        <div className="flex items-center justify-between gap-2 px-1 py-2 text-sm">{body}</div>
      )}
    </li>
  );
}

function PatternRow({ p, capabilityId, unit, groupName, checklist, where }: {
  p: Pattern; capabilityId: string; unit: string | null; groupName?: string;
  checklist: { id: string; label: string; required: boolean }[]; where: string;
}) {
  const [open, setOpen] = useState(false);
  const [comment, setComment] = useState("");
  const [answers, setAnswers] = useState<Record<string, ChecklistAnswer["answer"]>>({});
  const [checked, setChecked] = useState(false);
  const openedAt = useRef(Date.now());
  const decide = useDecideAcross(capabilityId);
  const heldBack = Object.entries(p.held);
  const tasks = new Set(p.ready.map((r) => r.task.case_id)).size;
  const missing = (p.needsComment && !comment.trim()) || checklist.some((q) => q.required && !["yes", "n/a"].includes(answers[q.id] ?? ""));
  const submit = () => {
    const targets = new Map<string, string[]>();
    for (const r of p.ready) targets.set(r.task.case_id, [...(targets.get(r.task.case_id) ?? []), r.proposal.group_id]);
    decide.mutate({
      targets: [...targets].map(([case_id, group_ids]) => ({ case_id, group_ids })),
      action: "approve",
      comment,
      reviewSeconds: Math.round((Date.now() - openedAt.current) / 1000),
      checklist: checklist.length ? checklist.map((q) => ({ id: q.id, answer: answers[q.id] ?? null })) : undefined,
    });
  };
  return (
    <li className="py-2.5">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
        <span className="min-w-0 flex-1">
          <span className="text-sm font-medium text-surface-900">{p.label}</span>
          {p.verdict && <span className="ml-2 rounded bg-surface-100 px-1.5 py-0.5 text-[11px] font-semibold text-surface-700">{p.verdict.replace(/_/g, " ")}</span>}
          {groupName && <span className="ml-2 text-[11px] text-surface-400">{groupName}</span>}
          <span className="mt-0.5 block text-xs text-surface-500">
            {p.books.toLocaleString("en-GB")} {p.books === 1 ? "book" : "books"} · {p.breaks.toLocaleString("en-GB")} {p.breaks === 1 ? "break" : "breaks"}
            {p.amount > 0 && <> · {money(p.amount, unit)}</>}
            {heldBack.length > 0 && <> · one by one: {heldBack.map(([k, n]) => held(k, n)).join(", ")}</>}
          </span>
        </span>
        {p.ready.length > 0 && !open && (
          <button type="button" onClick={() => { setOpen(true); openedAt.current = Date.now(); }}
            className="inline-flex items-center gap-1.5 rounded-lg border border-accent-200 px-3 py-1 text-xs font-medium text-accent-700 hover:bg-accent-50">
            <CheckCheck size={13} /> Approve {p.ready.length.toLocaleString("en-GB")}
          </button>
        )}
      </div>
      {open && (
        <div className="mt-2 space-y-2 rounded-lg border border-accent-200 bg-accent-50/40 p-3 text-sm">
          <p className="text-surface-700">
            Approve <b>{p.ready.length.toLocaleString("en-GB")}</b> “{p.label}”{p.verdict && <> → {p.verdict.replace(/_/g, " ")}</>} proposals in{" "}
            <b>{tasks.toLocaleString("en-GB")}</b> {tasks === 1 ? "task" : "tasks"}{where && <> ({where})</>}. Each task checks the decision as its own
            would; anything it holds for one-by-one review stays open.
          </p>
          <label className="block text-xs font-medium text-surface-600">
            Your explanation {p.needsComment ? "(required: some were escalated)" : "(optional; it goes on every decision)"}
            <textarea value={comment} onChange={(e) => setComment(e.target.value)} rows={2}
              className="mt-1 block w-full rounded-lg border border-surface-300 px-2 py-1.5 text-sm font-normal" />
          </label>
          {checklist.length > 0 && (
            <fieldset className="space-y-1">
              <legend className="text-xs font-medium text-surface-600">Sign-off checklist, answered once for every proposal</legend>
              {checklist.map((q) => (
                <div key={q.id} className="flex flex-wrap items-center justify-between gap-2 text-xs" role="radiogroup" aria-label={q.label}>
                  <span>{q.label}{q.required && <span className="text-red-600"> *</span>}</span>
                  <span className="flex gap-1">
                    {(["yes", "no", "n/a"] as const).map((a) => (
                      <button key={a} type="button" role="radio" aria-checked={answers[q.id] === a} onClick={() => setAnswers({ ...answers, [q.id]: a })}
                        className={clsx("rounded border px-2 py-0.5", answers[q.id] === a ? "border-primary-500 bg-primary-50 text-primary-700" : "border-surface-300 text-surface-600")}>
                        {a}
                      </button>
                    ))}
                  </span>
                </div>
              ))}
            </fieldset>
          )}
          <label className="flex items-start gap-2 text-xs text-surface-700">
            <input type="checkbox" checked={checked} onChange={(e) => setChecked(e.target.checked)} className="mt-0.5" />
            I have looked at this pattern and the evidence behind it, and it is the same in every task.
          </label>
          <div className="flex flex-wrap items-center gap-2">
            <button type="button" disabled={!checked || missing || decide.isPending} onClick={submit}
              className="inline-flex items-center gap-1.5 rounded-lg bg-brand px-3 py-1.5 text-sm font-medium text-brand-fg hover:bg-brand-strong disabled:opacity-50">
              <CheckCheck size={14} /> Approve {p.ready.length.toLocaleString("en-GB")}
            </button>
            <button type="button" onClick={() => setOpen(false)} className="rounded-lg px-3 py-1.5 text-sm text-surface-600 hover:bg-surface-100">Cancel</button>
          </div>
          {decide.data && (
            <p className="text-xs text-surface-700" role="status">
              Approved {decide.data.decided.toLocaleString("en-GB")}.
              {decide.data.refused_count > 0 && <> {decide.data.refused_count} left open: {decide.data.reasons.map((r) => `${r.reason} (${r.count})`).join("; ")}.</>}
            </p>
          )}
          {decide.error && <ErrorState error={decide.error} />}
        </div>
      )}
    </li>
  );
}
