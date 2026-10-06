// The case workspace — aria-ai's 3-pane Run layout for an Agent One Finance case:
// proposals | the selected proposal (or Ask, or the run's history) | case context.

import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import clsx from "clsx";
import {
  AlertTriangle,
  ArrowLeft,
  BookOpen,
  Bot,
  FileSpreadsheet,
  Repeat,
  Scale,
  Ticket,
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
  type ChecklistAnswer,
  type CheckResult,
  type Group,
  type ReviewFlag,
  type ToolCall,
} from "../api/aof";
import { ActionCard, EscalationCard, ReleaseSummary } from "../components/case/CaseActions";
import CaseChat from "../components/case/CaseChat";
import EvidencePanel from "../components/case/EvidencePanel";
import RequestsPanel from "../components/case/RequestsPanel";
import FollowThroughPanel from "../components/case/FollowThroughPanel";
import DataSetsPanel from "../components/case/DataSetsPanel";
import { CaseLinks, GroupSteps } from "../components/case/StepsV2";
import { ChecklistAnswers, SignOffChecklist, checklistComplete } from "../components/case/SignOffChecklist";
import CaseHistory from "../components/case/CaseHistory";
import StatusBadge from "../components/StatusBadge";
import { DueBadge } from "../components/Urgency";
import { Empty, ErrorState, Loading, WorkflowStepper, currentStep, formatTime, formatValue } from "../components/ui";

// Set in the office to link a case to its Phoenix trace, e.g.
// https://phoenix.internal/projects/<project>/traces/{traceId}
const TRACE_URL = import.meta.env.VITE_AOF_TRACE_URL as string | undefined;

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
  const openedAt = useRef(Date.now());
  // Phones show one pane at a time; wide screens show all three side by side.
  const [pane, setPane] = useState<"list" | "detail" | "case">("detail");

  if (detail.isLoading) return <Loading what="case" />;
  if (detail.error) return <ErrorState error={detail.error} />;
  if (!detail.data) return <Empty>Not found.</Empty>;
  const c = detail.data;
  // Open on what most needs a person: escalated, then needing confirmation, then a judgement call.
  const undecided = c.groups.filter((g) => !g.decision);
  const firstWith = (f: ReviewFlag) => undecided.find((g) => (g.flags ?? []).includes(f));
  const group =
    c.groups.find((g) => g.group_id === selected) ??
    firstWith("escalated") ?? firstWith("confirmation") ?? firstWith("judgement") ?? undecided[0] ?? c.groups[0];
  const decided = c.groups.filter((g) => g.decision).length;

  return (
    <div className="flex flex-col lg:h-full">
      <div className="mb-4">
        <Link to={`/capabilities/${encodeURIComponent(c.capability_id)}`} className="inline-flex items-center gap-1 text-xs text-surface-500 hover:text-primary-700">
          <ArrowLeft size={12} /> {c.capability_id}
        </Link>
        <div className="mt-1 flex flex-wrap items-center gap-3">
          <DecidedRing c={c} />
          <h1 className="text-lg font-bold leading-tight tracking-tight text-surface-900 sm:text-2xl">{c.labels.case}: {c.subject}</h1>
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
          <DueBadge dueAt={c.due_at} state={c.due_state ?? null} />
          <button
            onClick={() => void download(`/cases/${encodeURIComponent(c.case_id)}/export.xlsx`, `${c.case_id}.xlsx`)}
            className="inline-flex items-center gap-1.5 rounded-lg border border-surface-300 px-2.5 py-1 text-xs font-medium text-surface-700 hover:bg-surface-50 sm:ml-auto"
          >
            <FileSpreadsheet size={13} /> Download Excel
          </button>
        </div>
        {c.draft && <p className="mt-1 text-sm text-surface-500">{c.draft.headline}</p>}
        {c.follow_up_of && (
          <p className="mt-1 text-sm text-surface-600">
            Late items for <Link to={`/cases/${encodeURIComponent(c.follow_up_of)}`} className="text-primary-700 hover:underline">the day's case</Link>:
            only the breaks it did not have.
          </p>
        )}
        {(c.follow_ups ?? []).length > 0 && (() => {
          const ups = (c.follow_ups ?? []).filter((f) => f.outcome !== "no_new_items");
          const late = ups.reduce((n, f) => n + (f.items ?? 0), 0);
          const open = ups.filter((f) => !["completed", "failed", "stopped"].includes(f.status)).length;
          return (
            <div className="mt-1 text-sm text-surface-600">
              <p>
                The day: {c.items.length} {(c.labels?.item ?? "item").toLowerCase()}s here, {late} late in {ups.length} follow-up{ups.length === 1 ? "" : "s"}
                {open > 0 && <span className="font-medium text-orange-700"> · {open} still open</span>}
              </p>
              <p className="flex flex-wrap items-center gap-x-2">
                Late items since:
                {(c.follow_ups ?? []).map((f) => (
                  <Link key={f.case_id} to={`/cases/${encodeURIComponent(f.case_id)}`} className="text-primary-700 hover:underline">
                    {f.subject.split(" · ").pop()}{f.outcome === "no_new_items" ? " (nothing new)" : ` (${f.items ?? 0}, ${f.status.replace(/_/g, " ")})`}
                  </Link>
                ))}
              </p>
            </div>
          );
        })()}
        <ActionCard c={c} />
      </div>

      <CaseBanner c={c} />

      <div className="sticky top-0 z-10 -mx-3 mb-2 bg-surface-50/95 px-3 py-1.5 backdrop-blur lg:hidden" role="tablist" aria-label="Case sections">
        <div className="grid grid-cols-3 gap-1 rounded-lg border border-surface-200 bg-card p-1">
          {([
            ["list", `Proposals ${decided}/${c.groups.length}`],
            ["detail", "Review"],
            ["case", "Case"],
          ] as const).map(([id, label]) => (
            <button
              key={id}
              role="tab"
              aria-selected={pane === id}
              onClick={() => setPane(id)}
              className={clsx(
                "rounded-md px-2 py-1.5 text-xs font-medium",
                pane === id ? "bg-brand-accent text-brand-accent-fg" : "text-surface-600",
              )}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      <div className="grid gap-0 rounded-xl border border-surface-200 bg-card lg:min-h-0 lg:flex-1 lg:grid-cols-[18rem_1fr_19rem] lg:overflow-hidden">
        <aside className={clsx("border-surface-200 lg:block lg:border-r", pane !== "list" && "hidden")} aria-label="Proposals">
          <div className="flex items-center justify-between border-b border-surface-100 px-4 py-3">
            <h2 className="text-sm font-semibold text-surface-800">Proposals</h2>
            <span className="text-xs text-surface-500">{decided}/{c.groups.length} decided</span>
          </div>
          {c.can_decide && <BulkApprove c={c} openedAt={openedAt.current} />}
          {c.groups.length === 0 && <Empty>{c.status === "running" ? "Working on it…" : "Nothing in scope."}</Empty>}
          <ul className="p-2 lg:overflow-y-auto">
            {c.groups.map((g) => (
              <li key={g.group_id}>
                <button
                  onClick={() => {
                    setSelected(g.group_id);
                    setTab("proposal");
                    setPane("detail");
                  }}
                  aria-current={group?.group_id === g.group_id ? "true" : undefined}
                  className={clsx(
                    "mb-1 w-full rounded-lg border px-3 py-2 text-left transition-colors",
                    group?.group_id === g.group_id ? "border-accent-400 bg-accent-50/60" : "border-transparent hover:bg-surface-50",
                    !g.decision && g.finding?.status === "escalated" && "border-l-4 border-l-orange-400",
                  )}
                >
                  <div className="flex items-start justify-between gap-2">
                    <span className="line-clamp-2 text-sm font-medium leading-snug text-surface-800" title={g.label}>{g.label}</span>
                    <StatusBadge status={g.decision ? decidedLabel(g.decision.action) : g.finding?.status ?? "pending"} />
                  </div>
                  {!g.decision && <FlagChips flags={g.flags ?? []} />}
                  <div className="mt-1 flex items-center justify-between gap-2">
                    <span className="text-[11px] text-surface-500">
                      {g.item_ids.length} {c.labels.item.toLowerCase()}(s)
                      {g.finding?.verdict && <span className="ml-1.5 font-medium text-surface-700">{g.finding.verdict.replace(/_/g, " ")}</span>}
                    </span>
                    {g.finding && <DecidedBy by={g.finding.decided_by} />}
                  </div>
                  {g.ticket?.reference && (
                    <span className="mt-1 inline-flex items-center gap-1 text-[11px] text-primary-700"><Ticket size={11} /> {g.ticket.reference}</span>
                  )}
                </button>
              </li>
            ))}
          </ul>
        </aside>

        <section className={clsx("min-w-0 lg:block lg:overflow-y-auto", pane !== "detail" && "hidden")} aria-label="Proposal">
          <ReleaseSummary c={c} />
          <div className="flex gap-1 overflow-x-auto border-b border-surface-100 px-2 pt-2 sm:px-3" role="tablist">
            {TABS.map((t) => (
              <button
                key={t.id}
                role="tab"
                aria-selected={tab === t.id}
                onClick={() => setTab(t.id)}
                className={clsx(
                  "-mb-px shrink-0 whitespace-nowrap border-b-2 px-2.5 py-2 text-xs sm:px-3 sm:text-sm",
                  tab === t.id ? "border-primary-600 font-medium text-primary-700" : "border-transparent text-surface-500 hover:text-surface-800",
                )}
              >
                {t.label}
              </button>
            ))}
          </div>
          <div className="p-3 sm:p-5">
            {tab === "proposal" &&
              (group ? <ProposalPanel key={group.group_id} c={c} group={group} /> : <Empty>Select a proposal.</Empty>)}
            {tab === "ask" && <CaseChat caseId={c.case_id} />}
            {tab === "history" && <CaseHistory key={c.status} caseId={c.case_id} />}
          </div>
        </section>

        <aside className={clsx("bg-surface-50/60 lg:block lg:overflow-y-auto lg:border-l lg:border-surface-200", pane !== "case" && "hidden")} aria-label="Case context">
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

/** One click for the undecided proposals that need nothing more than a click.
 *  Groups the capability marks for one-by-one review (review.bulk_exclude —
 *  e.g. a verdict needing confirmation, a judgement call) are left out. */
function BulkApprove({ c, openedAt }: { c: CaseDetail; openedAt: number }) {
  const bulk = useBulkDecide(c.case_id);
  const open = c.groups.filter((g) => !g.decision && g.finding?.status === "proposed");
  const ready = open.filter((g) => !(g.bulk_blockers ?? []).length);
  const held = open.length - ready.length;
  if (ready.length < 2 && held === 0) return null;
  const refused = bulk.data?.refused ?? [];
  return (
    <div className="border-b border-surface-100 px-3 py-2">
      {ready.length >= 2 && (
        <button
          disabled={bulk.isPending}
          onClick={() =>
            bulk.mutate({
              groupIds: ready.map((g) => g.group_id),
              action: "approve",
              comment: "",
              reviewSeconds: Math.round((Date.now() - openedAt) / 1000),
            })
          }
          className="inline-flex w-full items-center justify-center gap-1.5 rounded-lg border border-accent-200 px-3 py-1.5 text-xs font-medium text-accent-700 hover:bg-accent-50 disabled:opacity-50"
        >
          <CheckCheck size={13} /> Approve {ready.length} straightforward
        </button>
      )}
      {held > 0 && (
        <p className="mt-1 text-[11px] text-surface-600">
          {held} {held === 1 ? "needs" : "need"} one-by-one review (confirmation or judgement).
        </p>
      )}
      {refused.length > 0 && <p className="mt-1 text-[11px] text-orange-700">{refused.length} need your own decision: {refused[0].reason}</p>}
      {bulk.error && <div className="mt-1"><ErrorState error={bulk.error} /></div>}
    </div>
  );
}

const FLAG_UI: Record<ReviewFlag, { label: string; cls: string } | null> = {
  confirmation: { label: "Needs confirmation", cls: "bg-yellow-100 text-yellow-800" },
  judgement: { label: "Needs your judgement", cls: "bg-purple-100 text-purple-800" },
  escalated: null, // the status badge already says so
  model: null,
};

function FlagChips({ flags }: { flags: ReviewFlag[] }) {
  const shown = flags.map((f) => FLAG_UI[f]).filter(Boolean) as { label: string; cls: string }[];
  if (!shown.length) return null;
  return (
    <div className="mt-1 flex flex-wrap gap-1">
      {shown.map((f) => (
        <span key={f.label} className={clsx("rounded px-1.5 py-0.5 text-[10px] font-semibold", f.cls)}>{f.label}</span>
      ))}
    </div>
  );
}


interface TestResult {
  id: string;
  status: "pass" | "fail" | "not_run";
  check: string;
  on_fail: string;
  why?: string;
}

function TestsCell({ tests }: { tests: TestResult[] }) {
  const failed = tests.filter((t) => t.status === "fail");
  const notRun = tests.filter((t) => t.status === "not_run");
  return (
    <span className="inline-flex flex-nowrap items-center gap-0.5 whitespace-nowrap">
      {failed.map((t) => (
        <span key={t.id} title={`${t.id} failed: ${t.check} — ${t.on_fail}`} className="rounded bg-red-100 px-1 font-mono text-[10px] font-semibold text-red-700">
          {t.id}
        </span>
      ))}
      {notRun.length > 0 && (
        <span title={notRun.map((t) => `${t.id}: ${t.why}`).join("\n")} className="rounded bg-yellow-100 px-1 text-[10px] text-yellow-700">
          {notRun.length} not run
        </span>
      )}
      <span className="text-[10px] text-surface-400">{tests.length - failed.length - notRun.length} pass</span>
    </span>
  );
}

function ChecksCell({ checks }: { checks: CheckResult[] }) {
  return (
    <span className="inline-flex flex-nowrap gap-0.5 whitespace-nowrap">
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
      <div><span className="text-surface-500">Side</span><p className="font-medium text-surface-800">{f.side_name ?? f.side}</p></div>
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
      {f.sme_review && (
        <p className="col-span-full mt-1 flex items-start gap-1.5 rounded-md bg-purple-50 px-2 py-1 font-medium text-purple-800">
          <Scale size={12} className="mt-0.5 shrink-0" /> Needs your judgement: the model investigated this one; check its reasoning before you decide.
        </p>
      )}
    </div>
  );
}

function ProposalPanel({ c, group }: { c: CaseDetail; group: Group }) {
  const decide = useDecide(c.case_id);
  const reinvestigate = useReinvestigate(c.case_id);
  const [comment, setComment] = useState("");
  const [note, setNote] = useState("");
  const [confirmed, setConfirmed] = useState(false);
  const [answers, setAnswers] = useState<Record<string, ChecklistAnswer>>({});
  const shownAt = useRef(Date.now());
  useEffect(() => {
    shownAt.current = Date.now();
    setAnswers({});
  }, [group.group_id]);
  const questions = group.checklist ?? [];
  const checklistOk = checklistComplete(questions, answers);
  const f = group.finding;
  const confirmMode = c.review?.confirm ?? "tick_and_comment";
  const needsConfirm = (group.flags ?? []).includes("confirmation") && confirmMode !== "none";
  const recurring = c.recurring ?? {};
  const items = useMemo(() => c.items.filter((i) => group.item_ids.includes(i.item_id)), [c.items, group.item_ids]);
  const evidence = useMemo(() => evidenceFor(c.tool_calls, group), [c.tool_calls, group]);
  const rules = c.review?.require_comment ?? ["reject", "escalated"];
  const needsWordsToApprove =
    (f?.status === "escalated" && rules.includes("escalated")) || (needsConfirm && confirmMode === "tick_and_comment");
  const needsWordsToReject = rules.includes("reject");
  const hasChecks = items.some((i) => Array.isArray(i.checks));
  const hasTests = items.some((i) => Array.isArray(i.tests) && (i.tests as unknown[]).length > 0);
  const sentBack = f?.reinvestigations ?? 0;
  const canSendBack = c.can_decide && sentBack < (c.review?.max_reinvestigations ?? 2);
  // approved by some, but more different people must approve (dual review, authority tier)
  const morePeople = group.approvals && !group.approvals.settled && group.approvals.by.length > 0 ? group.approvals : null;

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
        {f?.sections && f.sections.length > 0 ? (
          <dl className="mt-3 space-y-2 rounded-lg border border-surface-200 bg-surface-50 p-3 text-sm">
            {f.sections.map((sec) => (
              <div key={sec.id}>
                <dt className="text-xs font-semibold uppercase tracking-wide text-surface-500">{sec.label}</dt>
                <dd className={clsx("leading-relaxed", sec.text ? "text-surface-800" : "italic text-surface-400")}>{sec.text || "not answered"}</dd>
              </div>
            ))}
          </dl>
        ) : (
          f?.comment && <p className="mt-3 rounded-lg border border-surface-200 bg-surface-50 p-3 text-sm leading-relaxed text-surface-800">{f.comment}</p>
        )}
        <EscalationCard group={group} canDecide={c.can_decide} />
        <GroupSteps group={group} />
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

      {group.decision && (group.approvals?.settled ?? true) ? (
        <div className="rounded-lg border border-surface-200 p-3 text-sm">
          <p className="flex flex-wrap items-center gap-2">
            <StatusBadge status={decidedLabel(group.decision.action)} />
            by <span className="font-medium">{group.decision.decided_by}</span>
            {group.decision.on_behalf_of && <span className="text-surface-600">for {group.decision.on_behalf_of} (covering)</span>}
            {formatTime(group.decision.decided_at)}
            {group.decision.confirmed && <span className="rounded bg-yellow-100 px-1.5 py-0.5 text-[10px] font-semibold text-yellow-800">confirmed</span>}
          </p>
          {group.decision.comment && <p className="mt-1 text-surface-600">{group.decision.comment}</p>}
          {group.decision.checklist && group.decision.checklist.length > 0 && <ChecklistAnswers answers={group.decision.checklist} />}
          {group.ticket && (
            <p className={clsx("mt-2 flex items-center gap-1.5 text-xs", group.ticket.status === "raised" ? "text-primary-700" : "text-red-700")}>
              <Ticket size={12} />
              {group.ticket.status === "raised" ? (
                <>
                  Ticket{" "}
                  {group.ticket.url ? (
                    <a href={group.ticket.url} target="_blank" rel="noreferrer" className="font-medium underline">{group.ticket.reference}</a>
                  ) : (
                    <span className="font-medium">{group.ticket.reference}</span>
                  )}{" "}
                  raised for {f?.escalate_to ?? "the owning team"}
                </>
              ) : (
                <>Ticket not raised: {group.ticket.error}</>
              )}
            </p>
          )}
        </div>
      ) : c.can_decide ? (
        <div className="rounded-lg border border-surface-200 p-3">
          {morePeople && (
            <p className="mb-2 text-xs text-surface-600">
              Approved by {morePeople.by.join(", ")}; {morePeople.needed - morePeople.by.length} more {morePeople.needed - morePeople.by.length === 1 ? "person" : "people"} must approve — someone else.
            </p>
          )}
          {needsConfirm && (
            <label className="mb-2 flex items-start gap-2 rounded-md bg-yellow-50 px-2 py-1.5 text-xs text-yellow-900">
              <input type="checkbox" checked={confirmed} onChange={(e) => setConfirmed(e.target.checked)} className="mt-0.5" />
              <span>
                I confirm this verdict although {f?.requires_confirmation?.replace(/^.*depends on unset policy:\s*/, "the policy ") ?? "a policy"} is not yet set.
              </span>
            </label>
          )}
          {questions.length > 0 && <SignOffChecklist questions={questions} answers={answers} onChange={setAnswers} />}
          <label className="block text-xs font-medium text-surface-600">
            {needsWordsToApprove
              ? needsConfirm && f?.status !== "escalated"
                ? "Your explanation (required to confirm this verdict)"
                : "Your explanation (required: this group was escalated)"
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
              disabled={decide.isPending || (needsWordsToApprove && !comment.trim()) || (needsConfirm && !confirmed) || !checklistOk}
              title={checklistOk ? undefined : "Answer the required checklist questions yes or n/a"}
              onClick={() =>
                decide.mutate({
                  groupId: group.group_id,
                  action: "approve",
                  comment,
                  confirmed: needsConfirm ? confirmed : false,
                  checklist: questions.length ? Object.values(answers) : undefined,
                  reviewSeconds: Math.round((Date.now() - shownAt.current) / 1000),
                })
              }
              className="inline-flex items-center gap-1.5 rounded-lg bg-brand-accent px-3 py-1.5 text-sm font-medium text-brand-accent-fg hover:bg-brand-accent-strong disabled:opacity-50"
            >
              <Check size={14} /> Approve
            </button>
            <button
              disabled={decide.isPending || (needsWordsToReject && !comment.trim())}
              onClick={() =>
                decide.mutate({
                  groupId: group.group_id,
                  action: "reject",
                  comment,
                  reviewSeconds: Math.round((Date.now() - shownAt.current) / 1000),
                })
              }
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
                {c.columns.map((col) => (
                  <th key={col} scope="col" className={clsx("whitespace-nowrap px-3 py-2 font-medium", typeof items[0]?.[col] === "number" && "text-right")}>
                    {col.replace(/_/g, " ")}
                  </th>
                ))}
                {hasChecks && <th scope="col" className="px-3 py-2 font-medium">checks</th>}
                {hasTests && <th scope="col" className="px-3 py-2 font-medium">tests</th>}
              </tr>
            </thead>
            <tbody className="divide-y divide-surface-100">
              {items.map((it) => (
                <tr key={it.item_id}>
                  {c.columns.map((col, i) => {
                    const v = it[col];
                    const numeric = typeof v === "number";
                    const long = typeof v === "string" && v.length > 28;
                    return (
                      <td
                        key={col}
                        className={clsx(
                          "px-3 py-1.5 tabular-nums",
                          numeric ? "whitespace-nowrap text-right" : long ? "min-w-[14rem] max-w-[22rem] whitespace-normal" : "whitespace-nowrap",
                        )}
                      >
                        {formatValue(v)}
                        {i === 0 && recurring[it.item_id] && (
                          <span
                            title={`Also in: ${recurring[it.item_id].earlier.map((e) => e.subject).join(", ")}`}
                            className="ml-1.5 inline-flex items-center gap-0.5 rounded bg-orange-100 px-1 text-[10px] font-semibold text-orange-700"
                          >
                            <Repeat size={9} /> {recurring[it.item_id].runs} runs
                          </span>
                        )}
                        {i === 0 && typeof it.carried_verdict === "string" && it.carried_verdict && (
                          <span
                            title={`Decided ${String(it.carried_verdict).replace(/_/g, " ")} in ${String(it.carried_from ?? "the last run")}; still open`}
                            className="ml-1.5 inline-flex items-center rounded bg-amber-100 px-1 text-[10px] font-semibold text-amber-800"
                          >
                            carried · {String(it.carried_verdict).replace(/_/g, " ")}
                          </span>
                        )}
                      </td>
                    );
                  })}
                  {hasChecks && <td className="px-3 py-1.5"><ChecksCell checks={(it.checks as CheckResult[]) ?? []} /></td>}
                  {hasTests && <td className="px-3 py-1.5"><TestsCell tests={(it.tests as TestResult[]) ?? []} /></td>}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div>
        <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-surface-500">Data used ({evidence.length} system calls)</h3>
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
            <p className="mt-2 text-xs font-medium text-primary-700">You can release it: use the button at the top, after checking what will be written.</p>
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

      <RequestsPanel c={c} />

      <FollowThroughPanel c={c} />

      <CaseLinks c={c} />

      <DataSetsPanel c={c} />

      <EvidencePanel c={c} canUpload={c.can_decide || c.status === "awaiting_review"} />

      <LegalHold c={c} />

      <div>
        <h2 className="mb-2 text-xs font-semibold uppercase tracking-wider text-surface-500">Data used</h2>
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

/** How many of the case's groups are settled, as a ring beside the title. */
function DecidedRing({ c }: { c: CaseDetail }) {
  const total = c.groups.length;
  if (!total) return null;
  const settled = c.groups.filter((g) => g.decision && (g.approvals?.settled ?? true)).length;
  const pct = Math.round((settled / total) * 100);
  const color = pct === 100 ? "rgb(var(--c-green-600))" : "rgb(var(--c-primary-600))";
  return (
    <span className="hx-ring-wrap shrink-0" role="img" aria-label={`${settled} of ${total} groups decided`} title={`${settled} of ${total} groups decided`}>
      <span className="hx-ring" style={{ ["--hx-target" as string]: pct, ["--hx-ring-color" as string]: color }} />
      <span className="hx-ring-label text-surface-700">{settled}/{total}</span>
    </span>
  );
}
