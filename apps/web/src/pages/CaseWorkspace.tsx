// The case workspace — aria-ai's 3-pane Run layout for a Helix case:
// proposals | the selected proposal, its evidence and sign-off | case context.

import { useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import clsx from "clsx";
import { ArrowLeft, Bot, Check, ExternalLink, GitBranch, History, Send, ShieldAlert, User, X } from "lucide-react";

import { useCase, useDecide, useRelease, type CaseDetail, type Group, type ToolCall } from "../api/helix";
import StatusBadge from "../components/StatusBadge";
import { Empty, ErrorState, Loading, WorkflowStepper, currentStep, formatTime, formatValue } from "../components/ui";

// Set in the office to link a case to its Phoenix trace, e.g.
// https://phoenix.internal/projects/<project>/traces/{traceId}
const TRACE_URL = import.meta.env.VITE_HELIX_TRACE_URL as string | undefined;

const decidedLabel = (action: string) => (action === "approve" ? "approved" : "rejected");

function DecidedBy({ by }: { by: string }) {
  const Icon = by.startsWith("llm") ? Bot : by === "rule" ? GitBranch : User;
  const label = by.startsWith("llm") ? `model (${by.slice(4)})` : by === "rule" ? "rule" : "no reasoner";
  return (
    <span className="inline-flex items-center gap-1 text-[11px] text-surface-500">
      <Icon size={11} /> {label}
    </span>
  );
}

export default function CaseWorkspace(): JSX.Element {
  const { caseId = "" } = useParams();
  const detail = useCase(caseId);
  const [selected, setSelected] = useState<string | null>(null);

  if (detail.isLoading) return <Loading what="case" />;
  if (detail.error) return <ErrorState error={detail.error} />;
  if (!detail.data) return <Empty>Not found.</Empty>;
  const c = detail.data;
  const group = c.groups.find((g) => g.group_id === selected) ?? c.groups.find((g) => !g.decision) ?? c.groups[0];
  const decided = c.groups.filter((g) => g.decision).length;

  return (
    <div className="flex h-full flex-col">
      <div className="mb-4">
        <Link to={`/capabilities/${encodeURIComponent(c.capability_id)}`} className="inline-flex items-center gap-1 text-xs text-surface-500 hover:text-primary-700">
          <ArrowLeft size={12} /> {c.capability_id}
        </Link>
        <div className="mt-1 flex flex-wrap items-center gap-3">
          <h1 className="text-2xl font-bold tracking-tight text-surface-900">{c.labels.case}: {c.subject}</h1>
          <StatusBadge status={c.status} />
          {c.outcome && c.outcome !== c.status && <StatusBadge status={c.outcome} />}
          {c.team_group && (
            <Link
              to={`/capabilities/${encodeURIComponent(c.capability_id)}/groups/${encodeURIComponent(c.team_group)}`}
              className="rounded-md bg-primary-50 px-2 py-0.5 text-xs font-medium text-primary-700 hover:underline"
            >
              group {c.team_group} v{c.team_group_version}
            </Link>
          )}
        </div>
        {c.draft && <p className="mt-1 text-sm text-surface-500">{c.draft.headline}</p>}
      </div>

      <div className="grid min-h-0 flex-1 gap-0 overflow-hidden rounded-xl border border-surface-200 bg-white lg:grid-cols-[18rem_1fr_19rem]">
        {/* Left: proposals */}
        <aside className="border-b border-surface-200 lg:border-b-0 lg:border-r" aria-label="Proposals">
          <div className="flex items-center justify-between border-b border-surface-100 px-4 py-3">
            <h2 className="text-sm font-semibold text-surface-800">Proposals</h2>
            <span className="text-xs text-surface-500">{decided}/{c.groups.length} decided</span>
          </div>
          {c.groups.length === 0 && <Empty>Nothing in scope.</Empty>}
          <ul className="max-h-[60vh] overflow-y-auto p-2 lg:max-h-none">
            {c.groups.map((g) => (
              <li key={g.group_id}>
                <button
                  onClick={() => setSelected(g.group_id)}
                  aria-current={group?.group_id === g.group_id ? "true" : undefined}
                  className={clsx(
                    "mb-1 w-full rounded-lg border px-3 py-2 text-left transition-colors",
                    group?.group_id === g.group_id ? "border-accent-400 bg-accent-50/60" : "border-transparent hover:bg-surface-50",
                  )}
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="truncate text-sm font-medium text-surface-800">{g.label}</span>
                    <StatusBadge status={g.decision ? decidedLabel(g.decision.action) : g.finding?.status ?? "pending"} />
                  </div>
                  <div className="mt-1 flex items-center justify-between">
                    <span className="text-[11px] text-surface-500">{g.item_ids.length} {c.labels.item.toLowerCase()}(s)</span>
                    {g.finding && <DecidedBy by={g.finding.decided_by} />}
                  </div>
                </button>
              </li>
            ))}
          </ul>
        </aside>

        {/* Centre: the selected proposal */}
        <section className="min-w-0 overflow-y-auto border-b border-surface-200 p-5 lg:border-b-0" aria-label="Proposal">
          {group ? <ProposalPanel key={group.group_id} c={c} group={group} /> : <Empty>Select a proposal.</Empty>}
        </section>

        {/* Right: case context */}
        <aside className="overflow-y-auto bg-surface-50/60 lg:border-l lg:border-surface-200" aria-label="Case context">
          <ContextPanel c={c} />
        </aside>
      </div>
    </div>
  );
}

function ProposalPanel({ c, group }: { c: CaseDetail; group: Group }) {
  const decide = useDecide(c.case_id);
  const [comment, setComment] = useState("");
  const f = group.finding;
  const items = useMemo(() => c.items.filter((i) => group.item_ids.includes(i.item_id)), [c.items, group.item_ids]);
  const evidence = useMemo(() => evidenceFor(c.tool_calls, group), [c.tool_calls, group]);

  return (
    <div className="space-y-5">
      <div>
        <div className="flex flex-wrap items-center gap-2">
          <h2 className="text-lg font-semibold text-surface-900">{group.label}</h2>
          {f && <StatusBadge status={f.status} />}
          {f && <DecidedBy by={f.decided_by} />}
        </div>
        {f?.comment && <p className="mt-3 rounded-lg border border-surface-200 bg-surface-50 p-3 text-sm leading-relaxed text-surface-800">{f.comment}</p>}
        {f?.reason && (
          <p className="mt-2 flex items-start gap-1.5 text-sm text-orange-700">
            <ShieldAlert size={14} className="mt-0.5 shrink-0" /> Escalated: {f.reason}
          </p>
        )}
        {f?.usage?.cost_usd != null && (
          <p className="mt-2 text-[11px] text-surface-500">
            {f.model} · {f.usage.turns ?? "?"} turns · ${f.usage.cost_usd.toFixed(4)}
          </p>
        )}
        {group.priors.length > 0 && (
          <div className="mt-3 rounded-lg border border-primary-100 bg-primary-50/50 p-3">
            <p className="flex items-center gap-1.5 text-xs font-semibold text-primary-700"><History size={12} /> Approved before</p>
            {group.priors.slice(0, 2).map((p) => (
              <p key={p.case_id + p.at} className="mt-1 text-xs text-surface-700">“{p.comment}” <span className="text-surface-500">— {p.decided_by}</span></p>
            ))}
          </div>
        )}
      </div>

      {group.decision ? (
        <p className="flex items-center gap-2 rounded-lg border border-surface-200 p-3 text-sm">
          <StatusBadge status={decidedLabel(group.decision.action)} />
          by <span className="font-medium">{group.decision.decided_by}</span> {formatTime(group.decision.decided_at)}
          {group.decision.comment && <span className="text-surface-600">— {group.decision.comment}</span>}
        </p>
      ) : c.can_decide ? (
        <div className="rounded-lg border border-surface-200 p-3">
          <label className="block text-xs font-medium text-surface-600">
            Your explanation (optional — replaces the proposal's when approved)
            <textarea
              value={comment}
              onChange={(e) => setComment(e.target.value)}
              rows={2}
              className="mt-1 block w-full rounded-lg border border-surface-300 px-3 py-2 text-sm font-normal focus:border-primary-400 focus:outline-none"
            />
          </label>
          <div className="mt-2 flex gap-2">
            <button
              disabled={decide.isPending}
              onClick={() => decide.mutate({ groupId: group.group_id, action: "approve", comment })}
              className="inline-flex items-center gap-1.5 rounded-lg bg-accent-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-accent-700 disabled:opacity-50"
            >
              <Check size={14} /> Approve
            </button>
            <button
              disabled={decide.isPending}
              onClick={() => decide.mutate({ groupId: group.group_id, action: "reject", comment })}
              className="inline-flex items-center gap-1.5 rounded-lg border border-red-200 px-3 py-1.5 text-sm font-medium text-red-700 hover:bg-red-50 disabled:opacity-50"
            >
              <X size={14} /> Reject
            </button>
          </div>
          {decide.error && <div className="mt-2"><ErrorState error={decide.error} /></div>}
        </div>
      ) : null}

      <div>
        <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-surface-500">{c.labels.item}s ({items.length})</h3>
        <div className="overflow-x-auto rounded-lg border border-surface-200">
          <table className="w-full text-left text-xs">
            <thead className="bg-surface-50 text-surface-500">
              <tr>{c.columns.map((col) => <th key={col} scope="col" className="px-3 py-2 font-medium">{col.replace(/_/g, " ")}</th>)}</tr>
            </thead>
            <tbody className="divide-y divide-surface-100">
              {items.map((it) => (
                <tr key={it.item_id}>{c.columns.map((col) => <td key={col} className="px-3 py-1.5 tabular-nums">{formatValue(it[col])}</td>)}</tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div>
        <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-surface-500">Evidence ({evidence.length} connector calls)</h3>
        <ul className="space-y-1 text-xs">
          {evidence.map((t) => (
            <li key={t.call_id} className="flex flex-wrap items-center gap-x-3 gap-y-0.5 rounded-md border border-surface-100 px-2 py-1.5">
              <code className="font-medium text-surface-800">{t.tool}</code>
              <span className="text-surface-500">by {t.requested_by}</span>
              {t.allowed ? (
                <span className="text-surface-600">
                  {t.error ? `error: ${t.error}` : t.requested_by === "publish" ? `written · ${t.latency_ms} ms` : `${t.row_count ?? "—"} rows · ${t.latency_ms} ms`}
                </span>
              ) : (
                <span className="text-red-700">refused: {t.denied_reason}</span>
              )}
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

/** Calls whose arguments name this group (e.g. its account), plus the case-wide loads. */
function evidenceFor(calls: ToolCall[], group: Group): ToolCall[] {
  const keyValues = Object.values(group.group_key).map(String);
  return calls.filter((t) => {
    const args = Object.values(t.arguments).map(String);
    const mentions = keyValues.some((v) => args.includes(v));
    const caseWide = !Object.keys(group.group_key).some((k) => k in t.arguments);
    return mentions || caseWide;
  });
}

function ContextPanel({ c }: { c: CaseDetail }) {
  const release = useRelease(c.case_id);

  const byWho = c.tool_calls.reduce<Record<string, number>>((acc, t) => ({ ...acc, [t.requested_by]: (acc[t.requested_by] ?? 0) + 1 }), {});
  const refused = c.tool_calls.filter((t) => !t.allowed).length;

  return (
    <div className="space-y-5 p-4 text-sm">
      <div>
        <h2 className="mb-2 text-xs font-semibold uppercase tracking-wider text-surface-500">Case</h2>
        <dl className="space-y-1">
          {Object.entries(c.case_key).map(([k, v]) => (
            <div key={k} className="flex justify-between gap-2"><dt className="text-surface-500">{k}</dt><dd className="font-medium">{v}</dd></div>
          ))}
          <div className="flex justify-between gap-2"><dt className="text-surface-500">Opened</dt><dd>{formatTime(c.opened_at)} · {c.opened_by}</dd></div>
          <div className="flex justify-between gap-2"><dt className="text-surface-500">Manifest</dt><dd>v{c.manifest_version}</dd></div>
          <div className="flex justify-between gap-2">
            <dt className="text-surface-500">Trace</dt>
            <dd className="truncate">
              {c.trace_id && TRACE_URL ? (
                <a href={TRACE_URL.replace("{traceId}", c.trace_id)} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-primary-700 hover:underline">
                  Phoenix <ExternalLink size={11} />
                </a>
              ) : (
                <span className="font-mono text-[11px] text-surface-500">{c.trace_id ? `${c.trace_id.slice(0, 12)}…` : "tracing off"}</span>
              )}
            </dd>
          </div>
        </dl>
      </div>

      <div>
        <h2 className="mb-2 text-xs font-semibold uppercase tracking-wider text-surface-500">Workflow</h2>
        <WorkflowStepper steps={c.steps} pauseBefore={c.pause_before} current={currentStep(c.status)} />
      </div>

      {c.publish && (
        <div className="rounded-lg border border-surface-200 bg-white p-3">
          <h2 className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-surface-500"><Send size={12} /> Write-back</h2>
          <p className="mt-1 text-xs text-surface-600">
            Approved explanations go to <code>{c.publish.tool}</code> once someone with {c.publish.approver_roles.join(", ")} who did not
            review this case releases it.
          </p>
          {c.status === "awaiting_publish" && c.publish.can_release && (
            <button
              disabled={release.isPending}
              onClick={() => release.mutate()}
              className="mt-2 inline-flex items-center gap-1.5 rounded-lg bg-primary-700 px-3 py-1.5 text-sm font-medium text-white hover:bg-primary-800 disabled:opacity-50"
            >
              <Send size={13} /> Release write-back
            </button>
          )}
          {c.status === "awaiting_publish" && !c.publish.can_release && (
            <p className="mt-2 text-xs font-medium text-surface-500">Waiting for a second person to release it.</p>
          )}
          {c.outcome === "published" && <p className="mt-2 text-xs font-medium text-green-700">Published.</p>}
          {release.error && <div className="mt-2"><ErrorState error={release.error} /></div>}
        </div>
      )}

      <div>
        <h2 className="mb-2 text-xs font-semibold uppercase tracking-wider text-surface-500">Evidence</h2>
        <dl className="space-y-1">
          {Object.entries(byWho).map(([who, n]) => (
            <div key={who} className="flex justify-between"><dt className="text-surface-500">calls by {who}</dt><dd>{n}</dd></div>
          ))}
          <div className="flex justify-between"><dt className="text-surface-500">refused</dt><dd className={refused ? "font-medium text-red-700" : ""}>{refused}</dd></div>
        </dl>
      </div>
    </div>
  );
}
