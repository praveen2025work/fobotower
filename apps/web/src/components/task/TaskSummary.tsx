// A task's Summary tab: for a task that reconciles every book of a region at once
// (Rates EMEA: about 300 books, 3,000 positions), what it read, what it found broken
// down the way its group says (task.summarize_by: desk, product, book), the proposals
// that cover many books each, and the model session behind them.

import { useState } from "react";
import clsx from "clsx";
import { Bot, BookOpen, ChevronDown, ChevronRight, Cpu, Database, GitBranch, Layers, User } from "lucide-react";

import { useTaskSummary, type ModelSessionInfo, type ModelUsage, type SummaryRow, type TaskSummaryView } from "../../api/aof";
import StatusBadge from "../StatusBadge";
import { Card, Empty, ErrorState, Loading } from "../ui";

const n = (v: number | undefined | null) => (v ?? 0).toLocaleString("en-GB");
const money = (v: number | undefined, unit?: string | null) =>
  v === undefined ? "—" : `${v.toLocaleString("en-GB", { notation: "compact", maximumFractionDigits: 1 })}${unit ? ` ${unit}` : ""}`;
const words = (field: string) => field.replace(/_/g, " ");
const heading = (field: string) => words(field).replace(/^./, (c) => c.toUpperCase());
const plural = (count: number, one: string) => `${n(count)} ${one}${count === 1 ? "" : "s"}`;

export default function TaskSummary({ taskId, version, onProposal }: {
  taskId: string;
  /** changes when the task's decisions do */
  version: string;
  onProposal: (groupId: string) => void;
}) {
  const summary = useTaskSummary(taskId, version);
  if (summary.isLoading) return <Loading what="summary" />;
  if (summary.error) return <ErrorState error={summary.error} />;
  if (!summary.data) return null;
  return <Body s={summary.data} onProposal={onProposal} />;
}

function Body({ s, onProposal }: { s: TaskSummaryView; onProposal: (groupId: string) => void }) {
  const item = s.item_label.toLowerCase();
  // The finest breakdown field the sources cover (book): "300 books read, 151 clean".
  const unitField = [...s.by].reverse().find((f) => s.sources.some((x) => x.distinct[f] !== undefined));
  const source = s.sources.find((x) => unitField && x.distinct[unitField] !== undefined);
  const labels = Object.fromEntries(s.proposals.map((p) => [p.group_id, p.label]));
  // Counted per row and proposal when the sources carry it (books), else not shown.
  const last = unitField;
  return (
    <div className="space-y-4">
      <dl className="grid grid-cols-2 gap-2 sm:grid-cols-4" aria-label="Task totals">
        <Tile label="Read" value={s.sources.map((x) => n(x.rows)).join(" / ") || "—"}
          note={source && unitField ? `${plural(source.distinct[unitField], words(unitField))} · ${s.sources.map((x) => x.tool).join(", ")}` : s.sources.map((x) => x.tool).join(", ")} />
        <Tile label={`${s.item_label}s`} value={n(s.items.count)}
          note={[
            unitField && s.items.distinct[unitField] !== undefined ? `in ${plural(s.items.distinct[unitField], words(unitField))}` : null,
            source && unitField ? `${n(source.without_items[unitField])} clean` : null,
          ].filter(Boolean).join(" · ")} />
        <Tile label="Gross" value={money(s.items.gross, s.unit)} note={s.items.net !== undefined ? `net ${money(s.items.net, s.unit)}` : undefined} />
        <Tile label="To decide" value={n(s.items.open)} accent={s.items.open > 0}
          note={`${item}s in ${plural(s.proposals.filter((p) => !p.decision).length, "open proposal")} of ${s.proposals.length}`} />
      </dl>

      {s.breakdown.length > 0 && (
        <Card title={<span className="inline-flex items-center gap-1.5"><Layers size={14} /> {`By ${s.by.map(words).join(" → ")}`}</span>}
          aside={<span className="text-xs text-surface-500">largest first · open a row for the level below</span>}>
          <div className="overflow-x-auto">
            <table className="hx-rows w-full text-left text-sm" aria-label="Breakdown">
              <thead className="text-xs text-surface-500">
                <tr>
                  <th scope="col" className="px-2 py-2 font-medium">{heading(s.by[0])}</th>
                  <th scope="col" className="px-2 py-2 text-right font-medium">{s.item_label}s</th>
                  {last && s.by.length > 1 && <th scope="col" className="px-2 py-2 text-right font-medium">{heading(last)}s</th>}
                  <th scope="col" className="px-2 py-2 text-right font-medium">Net</th>
                  <th scope="col" className="px-2 py-2 text-right font-medium">Gross</th>
                  <th scope="col" className="px-2 py-2 text-right font-medium">Open</th>
                  <th scope="col" className="px-2 py-2 font-medium">In proposals</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-surface-100">
                {s.breakdown.map((r) => (
                  <Branch key={r.value} row={r} depth={0} last={last ?? ""} unit={s.unit} labels={labels} wide={!!last && s.by.length > 1} onProposal={onProposal} />
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      <Card title={`Proposals${unitField ? ` across ${plural(s.items.distinct[unitField] ?? 0, words(unitField))}` : ""}`}
        aside={<span className="text-xs text-surface-500">one decision covers every {item} in it</span>}>
        {s.proposals.length === 0 ? (
          <Empty>No proposals.</Empty>
        ) : (
          <div className="overflow-x-auto">
            <table className="hx-rows w-full text-left text-sm" aria-label="Proposals across the task">
              <thead className="text-xs text-surface-500">
                <tr>
                  <th scope="col" className="px-2 py-2 font-medium">Proposal</th>
                  <th scope="col" className="px-2 py-2 text-right font-medium">{s.item_label}s</th>
                  {last && <th scope="col" className="px-2 py-2 text-right font-medium">{heading(last)}s</th>}
                  <th scope="col" className="px-2 py-2 text-right font-medium">Gross</th>
                  <th scope="col" className="px-2 py-2 font-medium">Verdict</th>
                  <th scope="col" className="px-2 py-2 font-medium">Proposed by</th>
                  <th scope="col" className="px-2 py-2 font-medium">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-surface-100">
                {s.proposals.map((p) => (
                  <tr key={p.group_id} className="hover:bg-surface-50">
                    <td className="px-2 py-1.5">
                      <button type="button" onClick={() => onProposal(p.group_id)} className="text-left font-medium text-primary-700 hover:underline">{p.label}</button>
                      {p.escalate_to && <span className="ml-2 text-[11px] text-surface-500">owner {p.escalate_to}</span>}
                    </td>
                    <td className="px-2 py-1.5 text-right tabular-nums">{n(p.items)}</td>
                    {last && <td className="px-2 py-1.5 text-right tabular-nums">{n(p.distinct[last])}</td>}
                    <td className="whitespace-nowrap px-2 py-1.5 text-right text-xs tabular-nums">{money(p.gross, s.unit)}</td>
                    <td className="px-2 py-1.5 text-xs font-medium text-surface-700">{p.verdict?.replace(/_/g, " ") ?? "—"}</td>
                    <td className="px-2 py-1.5"><ProposedBy by={p.decided_by} /></td>
                    <td className="px-2 py-1.5">
                      <StatusBadge status={p.decision ? (p.decision.action === "approve" ? "approved" : "rejected") : p.status ?? "pending"} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <ModelSession m={s.model} />
    </div>
  );
}

function Tile({ label, value, note, accent }: { label: string; value: string; note?: string; accent?: boolean }) {
  return (
    <div className="rounded-lg border border-surface-200 bg-card px-3 py-2">
      <dt className="text-[11px] font-medium uppercase tracking-wider text-surface-500">{label}</dt>
      <dd className={clsx("mt-0.5 text-lg font-semibold tabular-nums", accent ? "text-orange-700" : "text-surface-900")}>{value}</dd>
      {note && <dd className="text-[11px] leading-snug text-surface-500">{note}</dd>}
    </div>
  );
}

function Branch({ row, depth, last, unit, labels, wide, onProposal }: {
  row: SummaryRow; depth: number; last: string; unit: string | null; labels: Record<string, string>; wide: boolean;
  onProposal: (groupId: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const deeper = row.children.length > 0;
  return (
    <>
      <tr className="hover:bg-surface-50">
        <td className="px-2 py-1.5" style={{ paddingLeft: `${0.5 + depth * 1.25}rem` }}>
          {deeper ? (
            <button type="button" onClick={() => setOpen(!open)} aria-expanded={open}
              className="inline-flex items-center gap-1 text-left font-medium text-surface-800 hover:text-primary-700">
              {open ? <ChevronDown size={12} /> : <ChevronRight size={12} />} <span className="whitespace-nowrap">{row.value}</span>
            </button>
          ) : (
            <span className="whitespace-nowrap font-medium text-surface-700">{row.value}</span>
          )}
        </td>
        <td className="px-2 py-1.5 text-right tabular-nums">{n(row.items)}</td>
        {wide && <td className="px-2 py-1.5 text-right tabular-nums text-surface-600">{row.field === last ? "" : n(row.distinct[last])}</td>}
        <td className="whitespace-nowrap px-2 py-1.5 text-right text-xs tabular-nums">{money(row.net, unit)}</td>
        <td className="whitespace-nowrap px-2 py-1.5 text-right text-xs tabular-nums">{money(row.gross, unit)}</td>
        <td className={clsx("px-2 py-1.5 text-right tabular-nums", row.open > 0 && "font-medium text-orange-700")}>{n(row.open)}</td>
        <td className="px-2 py-1.5">
          <div className="flex flex-wrap gap-1">
            {row.proposals.slice(0, 2).map((p) => (
              <button key={p.group_id} type="button" onClick={() => onProposal(p.group_id)} title={labels[p.group_id] ?? p.group_id}
                className="max-w-[11rem] truncate rounded-full border border-surface-200 px-2 py-0.5 text-[11px] text-surface-600 hover:border-primary-300 hover:text-primary-700">
                {labels[p.group_id] ?? p.group_id} · {p.items}
              </button>
            ))}
            {row.proposals.length > 2 && <span className="text-[11px] text-surface-400">+{row.proposals.length - 2}</span>}
          </div>
        </td>
      </tr>
      {open && row.children.map((c) => (
        <Branch key={c.value} row={c} depth={depth + 1} last={last} unit={unit} labels={labels} wide={wide} onProposal={onProposal} />
      ))}
    </>
  );
}

function ProposedBy({ by }: { by: string | null }) {
  const kind = (by ?? "none").split(":")[0];
  const Icon = kind === "llm" ? Bot : kind === "rule" ? GitBranch : kind === "playbook" ? BookOpen : User;
  const label = kind === "llm" ? "model" : kind === "none" ? "no reasoner" : kind;
  return <span className="inline-flex items-center gap-1 text-[11px] text-surface-600"><Icon size={11} /> {label}</span>;
}

function usageText(u: ModelUsage): string | null {
  const parts = [
    u.input_tokens !== undefined || u.output_tokens !== undefined ? `${n(u.input_tokens)} in / ${n(u.output_tokens)} out tokens` : null,
    u.cost_usd !== undefined ? `$${u.cost_usd.toFixed(4)}` : null,
    u.turns !== undefined ? plural(u.turns, "turn") : null,
    u.duration_ms !== undefined ? `${(u.duration_ms / 1000).toFixed(1)} s` : null,
  ].filter(Boolean);
  return parts.length ? parts.join(" · ") : null;
}

const DECIDERS: Record<string, string> = { playbook: "the playbook", rule: "a rule", llm: "the model", none: "no reasoner" };

/** The model session: who decided what, which model, what it cost against the limits, what it looked up. */
function ModelSession({ m }: { m: ModelSessionInfo }) {
  const used = usageText(m.usage);
  const limits = [
    m.limits.max_cost_usd_per_task !== null ? `$${m.limits.max_cost_usd_per_task} a task` : null,
    m.limits.max_cost_usd_per_day !== null ? `$${m.limits.max_cost_usd_per_day} a day` : null,
  ].filter(Boolean);
  return (
    <Card title={<span className="inline-flex items-center gap-1.5"><Cpu size={14} /> Model session</span>}
      aside={<span className="text-xs text-surface-500">{m.adapters.length ? `adapter ${m.adapters.join(", ")}` : "the model was not asked"}</span>}>
      <dl className="grid gap-x-6 gap-y-2 text-sm sm:grid-cols-2" aria-label="Model session">
        <div>
          <dt className="text-xs text-surface-500">Proposals by</dt>
          <dd className="text-surface-800">
            {Object.entries(m.decided_by).map(([k, v]) => `${v} by ${DECIDERS[k] ?? k}`).join(" · ") || "—"}
          </dd>
        </div>
        <div>
          <dt className="text-xs text-surface-500">Model</dt>
          <dd className="font-mono text-xs text-surface-800">{m.models.join(", ") || "—"}</dd>
        </div>
        <div>
          <dt className="text-xs text-surface-500">Usage</dt>
          <dd className="text-surface-800">{used ?? "not reported by the adapter"}</dd>
        </div>
        <div>
          <dt className="text-xs text-surface-500">Cost limit</dt>
          <dd className="text-surface-800">{limits.length ? limits.join(" · ") : "none set for this agent"}</dd>
        </div>
        <div>
          <dt className="text-xs text-surface-500">Lookups the model made</dt>
          <dd className="text-surface-800">
            {m.lookups.count === 0 ? "none" : Object.entries(m.lookups.by_tool).map(([t, c]) => `${t} ×${c}`).join(" · ")}
            {m.lookups.refused > 0 && <span className="ml-1 text-red-700">({m.lookups.refused} refused)</span>}
          </dd>
        </div>
        <div>
          <dt className="text-xs text-surface-500">Offered</dt>
          <dd className="text-surface-800">
            <span className="font-mono text-xs">{m.tools.join(", ") || "no tools"}</span>
            <span className="text-xs text-surface-500"> · instructions {n(m.instructions_chars)} characters</span>
          </dd>
        </div>
        {m.specialists.length > 0 && (
          <div className="sm:col-span-2">
            <dt className="text-xs text-surface-500">Specialists it may hand work to</dt>
            <dd className="text-surface-800">
              {m.specialists.map((sp) => (
                <p key={sp.name}><b className="font-medium">{sp.name}</b>: {sp.description} <span className="font-mono text-[11px] text-surface-500">{sp.tools.join(", ")}</span></p>
              ))}
            </dd>
          </div>
        )}
        {m.skill_session && (
          <div className="sm:col-span-2">
            <dt className="text-xs text-surface-500">Skill session</dt>
            <dd className="text-surface-800">
              {m.skill_session.skill_file ?? "agent instructions"} · {plural(m.skill_session.results ?? 0, "result")}
              {usageText(m.skill_session) && <> · {usageText(m.skill_session)}</>}
              {m.skill_session.failure && <span className="text-red-700"> · {m.skill_session.failure}</span>}
              <span className="text-xs text-surface-500"> — the conversation is on the Model session tab</span>
            </dd>
          </div>
        )}
        {m.chat.answers > 0 && (
          <div className="sm:col-span-2">
            <dt className="text-xs text-surface-500">Ask about this task</dt>
            <dd className="text-surface-800">{plural(m.chat.answers, "answer")}{usageText(m.chat.usage) && <> · {usageText(m.chat.usage)}</>}</dd>
          </div>
        )}
      </dl>
      {m.groups.length > 0 && (
        <div className="mt-3 overflow-x-auto">
          <table className="hx-rows w-full text-left text-sm" aria-label="Model calls">
            <thead className="text-xs text-surface-500">
              <tr>
                <th scope="col" className="px-2 py-2 font-medium">Proposal the model reasoned</th>
                <th scope="col" className="px-2 py-2 font-medium">Model</th>
                <th scope="col" className="px-2 py-2 font-medium">Outcome</th>
                <th scope="col" className="px-2 py-2 font-medium">Usage</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-surface-100">
              {m.groups.map((g) => (
                <tr key={g.group_id}>
                  <td className="px-2 py-1.5 font-medium text-surface-800">{g.label}</td>
                  <td className="px-2 py-1.5 font-mono text-xs">{g.model ?? "—"}</td>
                  <td className="px-2 py-1.5"><StatusBadge status={g.status ?? "pending"} />{g.reason && <span className="ml-1 text-[11px] text-surface-500">{g.reason}</span>}</td>
                  <td className="px-2 py-1.5 text-xs text-surface-600">
                    {usageText(g) ?? "—"}
                    {g.session_id && <span className="ml-1 font-mono text-[10px] text-surface-400">{g.session_id}</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <p className="mt-3 inline-flex items-center gap-1 text-[11px] text-surface-500">
        <Database size={11} /> Every lookup is in the task's audit; figures the model cites are checked against the tools before anyone sees them.
      </p>
    </Card>
  );
}
