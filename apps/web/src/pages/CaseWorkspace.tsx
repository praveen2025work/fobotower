// The case workspace — aria-ai's 3-pane Run layout for a Helix case:
// proposals | the selected proposal (or Ask, or the run's history) | case context.

import { useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import clsx from "clsx";
import {
  AlertTriangle,
  ArrowLeft,
  BookOpen,
  Bot,
  Check,
  CheckCheck,
  ExternalLink,
  FileDown,
  GitBranch,
  History,
  Loader2,
  Lock,
  RefreshCw,
  RotateCcw,
  Send,
  ShieldAlert,
  User,
  X,
} from "lucide-react";

import { download } from "../api/client";
import {
  useBulkDecide,
  useCase,
  useDecide,
  useLegalHold,
  useReinvestigate,
  useRelease,
  useRerun,
  useRetryPublish,
  type CaseDetail,
  type CheckResult,
  type Group,
  type ToolCall,
} from "../api/helix";
import CaseChat from "../components/case/CaseChat";
import CaseHistory from "../components/case/CaseHistory";
import StatusBadge from "../components/StatusBadge";
import { Empty, ErrorState, Loading, WorkflowStepper, currentStep, formatTime, formatValue } from "../components/ui";

// Set in the office to link a case to its Phoenix trace, e.g.
// https://phoenix.internal/projects/<project>/traces/{traceId}
const TRACE_URL = import.meta.env.VITE_HELIX_TRACE_URL as string | undefined;

const decidedLabel = (action: string) => (action === "approve" ? "approved" : "rejected");

function DecidedBy({ by }: { by: string }) {
  const Icon = by.startsWith("llm") ? Bot : by === "rule" ? GitBranch : by === "playbook" ? BookOpen : User;
  const label = by.startsWith("llm") ? `model (${by.slice(4)})` : by === "rule" || by === "playbook" ? by : "no reasoner";
  return (
    <span className="inline-flex items-center gap-1 text-[11px] text-surface-500">
      <Icon size={11} /> {label}
    </span>
  );
}

const TABS = [
  { id: "proposal", label: "Proposal" },
  { id: "ask", label: "Ask about this case" },
  { id: "history", label: "Run history" },
] as const;

export default function CaseWorkspace(): JSX.Element {
  const { caseId = "" } = useParams();
  const detail = useCase(caseId);
  const [selected, setSelected] = useState<string | null>(null);
  const [tab, setTab] = useState<(typeof TABS)[number]["id"]>("proposal");

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
          {(c.attempt ?? 1) > 1 && <span className="rounded-md bg-surface-100 px-2 py-0.5 text-xs text-surface-600">attempt {c.attempt}</span>}
          {c.legal_hold && (
            <span className="inline-flex items-center gap-1 rounded-md bg-orange-100 px-2 py-0.5 text-xs font-medium text-orange-700">
              <Lock size={11} /> legal hold
            </span>
          )}
        </div>
        {c.draft && <p className="mt-1 text-sm text-surface-500">{c.draft.headline}</p>}
      </div>

      <CaseBanner c={c} />

      <div className="grid min-h-0 flex-1 gap-0 overflow-hidden rounded-xl border border-surface-200 bg-card lg:grid-cols-[18rem_1fr_19rem]">
        <aside className="border-b border-surface-200 lg:border-b-0 lg:border-r" aria-label="Proposals">
          <div className="flex items-center justify-between border-b border-surface-100 px-4 py-3">
            <h2 className="text-sm font-semibold text-surface-800">Proposals</h2>
            <span className="text-xs text-surface-500">{decided}/{c.groups.length} decided</span>
          </div>
          {c.can_decide && <BulkApprove c={c} />}
          {c.groups.length === 0 && <Empty>{c.status === "running" ? "Working on it…" : "Nothing in scope."}</Empty>}
          <ul className="max-h-[60vh] overflow-y-auto p-2 lg:max-h-none">
            {c.groups.map((g) => (
              <li key={g.group_id}>
                <button
                  onClick={() => {
                    setSelected(g.group_id);
                    setTab("proposal");
                  }}
                  aria-current={group?.group_id === g.group_id ? "true" : undefined}
                  className={clsx(
                    "mb-1 w-full rounded-lg border px-3 py-2 text-left transition-colors",
                    group?.group_id === g.group_id ? "border-accent-400 bg-accent-50/60" : "border-transparent hover:bg-surface-50",
                  )}
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="truncate text-sm font-medium text-surface-800">{g.finding?.category_name ? `${g.finding.category_name} · ${g.finding.side}` : g.label}</span>
                    <StatusBadge status={g.decision ? decidedLabel(g.decision.action) : g.finding?.status ?? "pending"} />
                  </div>
                  <div className="mt-1 flex items-center justify-between gap-2">
                    <span className="text-[11px] text-surface-500">
                      {g.item_ids.length} {c.labels.item.toLowerCase()}(s)
                      {g.finding?.verdict && <span className="ml-1.5 font-medium text-surface-700">{g.finding.verdict.replace(/_/g, " ")}</span>}
                    </span>
                    {g.finding && <DecidedBy by={g.finding.decided_by} />}
                  </div>
                </button>
              </li>
            ))}
          </ul>
        </aside>

        <section className="min-w-0 overflow-y-auto border-b border-surface-200 lg:border-b-0" aria-label="Proposal">
          <div className="flex gap-1 border-b border-surface-100 px-3 pt-2" role="tablist">
            {TABS.map((t) => (
              <button
                key={t.id}
                role="tab"
                aria-selected={tab === t.id}
                onClick={() => setTab(t.id)}
                className={clsx(
                  "-mb-px border-b-2 px-3 py-2 text-sm",
                  tab === t.id ? "border-primary-600 font-medium text-primary-700" : "border-transparent text-surface-500 hover:text-surface-800",
                )}
              >
                {t.label}
              </button>
            ))}
          </div>
          <div className="p-5">
            {tab === "proposal" &&
              (group ? <ProposalPanel key={group.group_id} c={c} group={group} /> : <Empty>Select a proposal.</Empty>)}
            {tab === "ask" && <CaseChat caseId={c.case_id} />}
            {tab === "history" && <CaseHistory key={c.status} caseId={c.case_id} />}
          </div>
        </section>

        <aside className="overflow-y-auto bg-surface-50/60 lg:border-l lg:border-surface-200" aria-label="Case context">
          <ContextPanel c={c} />
        </aside>
      </div>
    </div>
  );
}

/** Running, failed or escalated: say so at the top, with the way forward. */
function CaseBanner({ c }: { c: CaseDetail }) {
  const rerun = useRerun(c.case_id);
  const navigate = useNavigate();
  if (c.status === "running") {
    return (
      <div role="status" className="mb-3 flex items-center gap-2 rounded-lg border border-primary-200 bg-primary-50 px-3 py-2 text-sm text-primary-700">
        <Loader2 size={14} className="animate-spin" /> Running — this page updates by itself.
      </div>
    );
  }
  if (!["failed", "escalated"].includes(c.status)) return null;
  return (
    <div className="mb-3 flex flex-wrap items-center gap-3 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">
      <AlertTriangle size={14} className="shrink-0" />
      <span className="min-w-0 flex-1">
        {c.status === "failed" ? "The run failed" : "The run was escalated"}
        {c.error ? `: ${c.error}` : "."}
      </span>
      {c.can_rerun && (
        <button
          disabled={rerun.isPending}
          onClick={() => rerun.mutate(undefined, { onSuccess: (d) => navigate(`/cases/${encodeURIComponent(d.case_id)}`) })}
          className="inline-flex items-center gap-1.5 rounded-lg bg-brand px-3 py-1.5 text-sm font-medium text-brand-fg hover:bg-brand-strong disabled:opacity-50"
        >
          <RotateCcw size={13} /> Run again
        </button>
      )}
      {rerun.error && <div className="w-full"><ErrorState error={rerun.error} /></div>}
    </div>
  );
}

/** One click for every undecided group the run proposed; escalations need their own words. */
function BulkApprove({ c }: { c: CaseDetail }) {
  const bulk = useBulkDecide(c.case_id);
  const ready = c.groups.filter((g) => !g.decision && g.finding?.status === "proposed");
  if (ready.length < 2) return null;
  const refused = bulk.data?.refused ?? [];
  return (
    <div className="border-b border-surface-100 px-3 py-2">
      <button
        disabled={bulk.isPending}
        onClick={() => bulk.mutate({ groupIds: ready.map((g) => g.group_id), action: "approve", comment: "" })}
        className="inline-flex w-full items-center justify-center gap-1.5 rounded-lg border border-accent-200 px-3 py-1.5 text-xs font-medium text-accent-700 hover:bg-accent-50 disabled:opacity-50"
      >
        <CheckCheck size={13} /> Approve all {ready.length} proposed
      </button>
      {refused.length > 0 && <p className="mt-1 text-[11px] text-orange-700">{refused.length} need your own decision.</p>}
      {bulk.error && <div className="mt-1"><ErrorState error={bulk.error} /></div>}
    </div>
  );
}

function ChecksCell({ checks }: { checks: CheckResult[] }) {
  return (
    <span className="inline-flex gap-0.5">
      {checks.map((ch) => (
        <span
          key={ch.id}
          title={ch.positive ? `${ch.id}: ${ch.reason}` : `${ch.id}: ruled out`}
          className={clsx(
            "rounded px-1 font-mono text-[10px]",
            ch.positive ? "bg-orange-100 font-semibold text-orange-700" : "bg-surface-100 text-surface-400",
          )}
        >
          {ch.id}
        </span>
      ))}
    </span>
  );
}

function PlaybookPanel({ group }: { group: Group }) {
  const f = group.finding;
  if (!f?.category && !f?.verdict) return null;
  return (
    <div className="mt-3 grid grid-cols-2 gap-x-4 gap-y-1 rounded-lg border border-surface-200 p-3 text-xs sm:grid-cols-4" aria-label="Playbook">
      <div><span className="text-surface-500">Category</span><p className="font-medium text-surface-800">{f.category} · {f.category_name}</p></div>
      <div><span className="text-surface-500">Side</span><p className="font-medium text-surface-800">{f.side}</p></div>
      <div><span className="text-surface-500">Verdict</span><p className="font-semibold text-surface-900">{f.verdict?.replace(/_/g, " ") ?? "—"}</p></div>
      <div><span className="text-surface-500">Owner</span><p className="font-medium text-surface-800">{f.escalate_to ?? "—"}</p></div>
      {f.requires_confirmation && (
        <p className="col-span-full mt-1 flex items-start gap-1.5 text-yellow-700">
          <AlertTriangle size={12} className="mt-0.5 shrink-0" /> Requires controller confirmation: {f.requires_confirmation}
        </p>
      )}
      {f.guard && (
        <p className="col-span-full flex items-start gap-1.5 text-orange-700">
          <ShieldAlert size={12} className="mt-0.5 shrink-0" /> {f.guard}
        </p>
      )}
      {f.sme_review && <p className="col-span-full text-surface-600">Judgement call: investigated by the model, decided by a subject-matter expert.</p>}
    </div>
  );
}

function ProposalPanel({ c, group }: { c: CaseDetail; group: Group }) {
  const decide = useDecide(c.case_id);
  const reinvestigate = useReinvestigate(c.case_id);
  const [comment, setComment] = useState("");
  const [note, setNote] = useState("");
  const f = group.finding;
  const items = useMemo(() => c.items.filter((i) => group.item_ids.includes(i.item_id)), [c.items, group.item_ids]);
  const evidence = useMemo(() => evidenceFor(c.tool_calls, group), [c.tool_calls, group]);
  const rules = c.review?.require_comment ?? ["reject", "escalated"];
  const needsWordsToApprove = f?.status === "escalated" && rules.includes("escalated");
  const needsWordsToReject = rules.includes("reject");
  const hasChecks = items.some((i) => Array.isArray(i.checks));
  const sentBack = f?.reinvestigations ?? 0;
  const canSendBack = c.can_decide && sentBack < (c.review?.max_reinvestigations ?? 2);

  return (
    <div className="space-y-5">
      <div>
        <div className="flex flex-wrap items-center gap-2">
          <h2 className="text-lg font-semibold text-surface-900">{group.label}</h2>
          {f && <StatusBadge status={f.status} />}
          {f && <DecidedBy by={f.decided_by} />}
          {sentBack > 0 && <span className="text-[11px] text-surface-500">re-investigated {sentBack}×</span>}
        </div>
        <PlaybookPanel group={group} />
        {f?.comment && <p className="mt-3 rounded-lg border border-surface-200 bg-surface-50 p-3 text-sm leading-relaxed text-surface-800">{f.comment}</p>}
        {f?.reason && (
          <p className="mt-2 flex items-start gap-1.5 text-sm text-orange-700">
            <ShieldAlert size={14} className="mt-0.5 shrink-0" /> Escalated: {f.reason}
          </p>
        )}
        {f?.previous && (
          <p className="mt-2 text-xs text-surface-500">
            Before “{f.reviewer_note}”: {f.previous.comment || f.previous.reason}
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
            {group.priors.slice(0, 3).map((p) => (
              <p key={p.case_id + p.at} className="mt-1 text-xs text-surface-700">
                “{p.comment}” <span className="text-surface-500">— {p.decided_by}{p.match && p.match !== "same subject" ? ` · ${p.match}` : ""}</span>
              </p>
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
            {needsWordsToApprove
              ? "Your explanation (required: this group was escalated)"
              : "Your explanation (optional — replaces the proposal's when approved; required to reject)"}
            <textarea
              value={comment}
              onChange={(e) => setComment(e.target.value)}
              rows={2}
              className="mt-1 block w-full rounded-lg border border-surface-300 px-3 py-2 text-sm font-normal focus:border-primary-400 focus:outline-none"
            />
          </label>
          <div className="mt-2 flex flex-wrap gap-2">
            <button
              disabled={decide.isPending || (needsWordsToApprove && !comment.trim())}
              onClick={() => decide.mutate({ groupId: group.group_id, action: "approve", comment })}
              className="inline-flex items-center gap-1.5 rounded-lg bg-brand-accent px-3 py-1.5 text-sm font-medium text-brand-accent-fg hover:bg-brand-accent-strong disabled:opacity-50"
            >
              <Check size={14} /> Approve
            </button>
            <button
              disabled={decide.isPending || (needsWordsToReject && !comment.trim())}
              onClick={() => decide.mutate({ groupId: group.group_id, action: "reject", comment })}
              className="inline-flex items-center gap-1.5 rounded-lg border border-red-200 px-3 py-1.5 text-sm font-medium text-red-700 hover:bg-red-50 disabled:opacity-50"
            >
              <X size={14} /> Reject
            </button>
          </div>
          {decide.error && <div className="mt-2"><ErrorState error={decide.error} /></div>}
          {c.review?.dual_review_when && (
            <p className="mt-2 text-[11px] text-surface-500">Large groups need two approvers ({c.review.dual_review_when}).</p>
          )}
          {canSendBack && (
            <div className="mt-3 border-t border-surface-100 pt-3">
              <label className="block text-xs font-medium text-surface-600">
                Not convinced? Ask the model to look again
                <input
                  value={note}
                  onChange={(e) => setNote(e.target.value)}
                  placeholder="e.g. Check the October reversal before concluding"
                  className="mt-1 block w-full rounded-lg border border-surface-300 px-3 py-1.5 text-sm font-normal focus:border-primary-400 focus:outline-none"
                />
              </label>
              <button
                disabled={reinvestigate.isPending || !note.trim()}
                onClick={() => reinvestigate.mutate({ groupId: group.group_id, note }, { onSuccess: () => setNote("") })}
                className="mt-2 inline-flex items-center gap-1.5 rounded-lg border border-surface-300 px-3 py-1.5 text-xs font-medium text-surface-700 hover:bg-surface-50 disabled:opacity-50"
              >
                <RefreshCw size={12} /> Investigate again
              </button>
              {reinvestigate.error && <div className="mt-2"><ErrorState error={reinvestigate.error} /></div>}
            </div>
          )}
        </div>
      ) : null}

      <div>
        <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-surface-500">{c.labels.item}s ({items.length})</h3>
        <div className="overflow-x-auto rounded-lg border border-surface-200">
          <table className="w-full text-left text-xs">
            <thead className="bg-surface-50 text-surface-500">
              <tr>
                {c.columns.map((col) => <th key={col} scope="col" className="whitespace-nowrap px-3 py-2 font-medium">{col.replace(/_/g, " ")}</th>)}
                {hasChecks && <th scope="col" className="px-3 py-2 font-medium">checks</th>}
              </tr>
            </thead>
            <tbody className="divide-y divide-surface-100">
              {items.map((it) => (
                <tr key={it.item_id}>
                  {c.columns.map((col) => <td key={col} className="whitespace-nowrap px-3 py-1.5 tabular-nums">{formatValue(it[col])}</td>)}
                  {hasChecks && <td className="px-3 py-1.5"><ChecksCell checks={(it.checks as CheckResult[]) ?? []} /></td>}
                </tr>
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

function LegalHold({ c }: { c: CaseDetail }) {
  const hold = useLegalHold(c.case_id);
  const [reason, setReason] = useState("");
  if (!c.can_hold && !c.legal_hold) return null;
  return (
    <div className="rounded-lg border border-surface-200 bg-card p-3">
      <h2 className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-surface-500"><Lock size={12} /> Legal hold</h2>
      {c.legal_hold ? (
        <p className="mt-1 text-xs text-surface-700">On hold: {c.legal_hold_reason}. Retention will not remove this case.</p>
      ) : (
        <p className="mt-1 text-xs text-surface-600">Kept until its retention period ends.</p>
      )}
      {c.can_hold &&
        (c.legal_hold ? (
          <button onClick={() => hold.mutate({ hold: false })} className="mt-2 text-xs text-primary-700 hover:underline">Lift the hold</button>
        ) : (
          <div className="mt-2 flex gap-1">
            <input
              aria-label="Hold reason"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="Reason, e.g. FCA enquiry"
              className="min-w-0 flex-1 rounded-md border border-surface-300 px-2 py-1 text-xs"
            />
            <button
              disabled={!reason.trim() || hold.isPending}
              onClick={() => hold.mutate({ hold: true, reason })}
              className="rounded-md border border-surface-300 px-2 py-1 text-xs font-medium text-surface-700 hover:bg-surface-50 disabled:opacity-50"
            >
              Hold
            </button>
          </div>
        ))}
      {hold.error && <div className="mt-2"><ErrorState error={hold.error} /></div>}
    </div>
  );
}

function ContextPanel({ c }: { c: CaseDetail }) {
  const release = useRelease(c.case_id);
  const retry = useRetryPublish(c.case_id);

  const byWho = c.tool_calls.reduce<Record<string, number>>((acc, t) => ({ ...acc, [t.requested_by]: (acc[t.requested_by] ?? 0) + 1 }), {});
  const refused = c.tool_calls.filter((t) => !t.allowed).length;
  const attempts = c.attempts ?? [];

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

      {attempts.length > 1 && (
        <div>
          <h2 className="mb-2 text-xs font-semibold uppercase tracking-wider text-surface-500">Attempts</h2>
          <ul className="space-y-1">
            {attempts.map((a) => (
              <li key={a.case_id} className="flex items-center justify-between gap-2 text-xs">
                <Link to={`/cases/${encodeURIComponent(a.case_id)}`} className={clsx("hover:underline", a.case_id === c.case_id ? "font-semibold text-surface-900" : "text-primary-700")}>
                  attempt {a.attempt}
                </Link>
                <StatusBadge status={a.status} />
              </li>
            ))}
          </ul>
        </div>
      )}

      <div>
        <h2 className="mb-2 text-xs font-semibold uppercase tracking-wider text-surface-500">Workflow</h2>
        <WorkflowStepper steps={c.steps} pauseBefore={c.pause_before} current={currentStep(c.status)} />
      </div>

      {c.publish && (
        <div className="rounded-lg border border-surface-200 bg-card p-3">
          <h2 className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-surface-500"><Send size={12} /> Write-back</h2>
          <p className="mt-1 text-xs text-surface-600">
            Approved results go to <code>{c.publish.tool}</code> once someone with {c.publish.approver_roles.join(", ")} who did not
            review this case releases it.
          </p>
          {c.status === "awaiting_publish" && c.publish.can_release && (
            <button
              disabled={release.isPending}
              onClick={() => release.mutate()}
              className="mt-2 inline-flex items-center gap-1.5 rounded-lg bg-brand px-3 py-1.5 text-sm font-medium text-brand-fg hover:bg-brand-strong disabled:opacity-50"
            >
              <Send size={13} /> Release write-back
            </button>
          )}
          {c.status === "awaiting_publish" && !c.publish.can_release && (
            <p className="mt-2 text-xs font-medium text-surface-500">Waiting for a second person to release it.</p>
          )}
          {c.outcome === "published" && <p className="mt-2 text-xs font-medium text-green-700">Published.</p>}
          {c.outcome === "publish_failed" && (
            <div className="mt-2">
              <p className="text-xs text-red-700">Some writes did not land. A retry sends only those, with the same keys.</p>
              {c.can_retry_publish && (
                <button
                  disabled={retry.isPending}
                  onClick={() => retry.mutate()}
                  className="mt-2 inline-flex items-center gap-1.5 rounded-lg bg-brand px-3 py-1.5 text-sm font-medium text-brand-fg hover:bg-brand-strong disabled:opacity-50"
                >
                  <RotateCcw size={13} /> Retry write-back
                </button>
              )}
              {retry.error && <div className="mt-2"><ErrorState error={retry.error} /></div>}
            </div>
          )}
          {(c.documents ?? []).map((d) => (
            <button
              key={d.url}
              onClick={() => void download(d.url.replace(/^\/api/, ""), d.name)}
              className="mt-2 flex w-full items-center gap-2 rounded-md border border-surface-200 px-2 py-1.5 text-left text-xs hover:bg-surface-50"
              title={d.sha256 ? `sha256 ${d.sha256}` : undefined}
            >
              <FileDown size={14} className="shrink-0 text-primary-600" />
              <span className="min-w-0 flex-1 truncate font-medium text-surface-800">{d.name}</span>
              <span className="shrink-0 text-surface-400">{d.pages ? `${d.pages} p` : ""}</span>
            </button>
          ))}
          {release.error && <div className="mt-2"><ErrorState error={release.error} /></div>}
        </div>
      )}

      <LegalHold c={c} />

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
