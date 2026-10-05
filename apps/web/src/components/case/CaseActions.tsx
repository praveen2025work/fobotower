// What a case needs from the person looking at it, said once at the top:
// their review, their release, or who else it waits on and why not them —
// plus the release summary and the plain-words escalation card.

import { useState } from "react";
import clsx from "clsx";
import { CheckCircle2, Clock3, Eye, Hand, OctagonX, Play, Scale, Send, ShieldAlert, Ticket } from "lucide-react";

import { usePassGate, useRelease, type CaseDetail, type Finding, type Group, type ReviewFlag } from "../../api/helix";
import StatusBadge from "../StatusBadge";
import { ErrorState, formatTime, formatValue } from "../ui";

const roleList = (roles: string[]) => roles.map((r) => r.replace(/_/g, " ").toLowerCase()).join(" or ");

function count(groups: Group[], flag: ReviewFlag) {
  return groups.filter((g) => (g.flags ?? []).includes(flag)).length;
}

/** The one card at the top of a case: what is needed, from whom, and the button to do it. */
export function ActionCard({ c }: { c: CaseDetail }) {
  const release = useRelease(c.case_id);
  const w = c.waiting_on;
  const open = c.groups.filter((g) => !g.decision);
  const approved = c.groups.filter((g) => g.decision?.action === "approve");
  const stake = c.exposure != null ? `${formatValue(c.exposure)}${c.unit ? ` ${c.unit}` : ""} at stake` : null;

  if (c.status === "awaiting_review" && w) {
    const parts = [`${open.length} ${open.length === 1 ? "group" : "groups"} to decide`];
    const conf = count(open, "confirmation");
    const judg = count(open, "judgement");
    const esc = count(open, "escalated");
    if (conf) parts.push(`${conf} ${conf === 1 ? "needs" : "need"} confirmation`);
    if (judg) parts.push(`${judg} judgement ${judg === 1 ? "call" : "calls"}`);
    if (esc) parts.push(`${esc} escalated`);
    return (
      <Shell tone={w.you ? (esc ? "attention" : "action") : "waiting"} icon={w.you ? Scale : Eye}
        title={w.you ? (c.acting_for ? `Your review — covering for ${c.acting_for}` : "Your review") : "Waiting for review"}
      >
        <p>{w.you ? parts.join(" · ") : `${parts.join(" · ")}. Reviewers: ${roleList(w.roles)}.`}</p>
        {!w.you && w.why_not && <p className="mt-0.5 text-xs opacity-80">You can look but not decide: {w.why_not}.</p>}
        {w.you && esc > 0 && <p className="mt-0.5 text-xs">Escalated groups need your own explanation to approve; each shows why it was escalated.</p>}
        {stake && <p className="mt-0.5 text-xs opacity-80">{stake}</p>}
      </Shell>
    );
  }

  if (c.status === "awaiting_publish" && w && c.publish) {
    const writes = c.publish.per === "case" ? "one report" : `${approved.length} approved ${approved.length === 1 ? "result" : "results"}`;
    return (
      <Shell tone={w.you ? "action" : "waiting"} icon={w.you ? Send : Clock3} title={w.you ? "Ready for your release" : "Waiting for release"}>
        <p>
          Reviewed by {w.reviewed_by?.join(", ") || "—"}. Releasing writes {writes} to <code className="text-xs">{c.publish.tool}</code>.
        </p>
        {w.you ? (
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <button
              disabled={release.isPending}
              onClick={() => release.mutate()}
              className="inline-flex items-center gap-1.5 rounded-lg bg-brand px-3 py-1.5 text-sm font-medium text-brand-fg hover:bg-brand-strong disabled:opacity-50"
            >
              <Send size={13} /> Release write-back
            </button>
            <span className="text-xs opacity-80">Check what will be written below first.</span>
          </div>
        ) : (
          <p className="mt-0.5 text-xs opacity-80">
            Someone with {roleList(w.roles)} who did not review it releases it.
            {w.why_not && /reviewed/.test(w.why_not) && " You reviewed it, so it can't be you."}
            {w.why_not && !/reviewed/.test(w.why_not) && " You don't have that role."}
          </p>
        )}
        {release.error && <div className="mt-2"><ErrorState error={release.error} /></div>}
      </Shell>
    );
  }

  if (w?.step === "gate" && w.gate) return <GateCard c={c} />;

  if (c.status === "stopped") {
    return (
      <Shell tone="waiting" icon={OctagonX} title="Stopped at a tollgate">
        <p>{c.error ?? "A person stopped the run."}</p>
        {c.can_rerun && <p className="mt-0.5 text-xs opacity-80">Fix what was wrong, then re-run it as a new attempt; this one stays as evidence.</p>}
      </Shell>
    );
  }

  if (c.status === "completed") {
    const tickets = c.groups.filter((g) => g.ticket?.status === "raised").length;
    const signed = [...new Set(c.groups.map((g) => g.decision?.decided_by).filter(Boolean))].join(", ");
    return (
      <Shell tone="done" icon={CheckCircle2} title={c.outcome === "published" ? "Done — published" : "Done"}>
        <p>
          {c.groups.length} {c.groups.length === 1 ? "group" : "groups"} signed off{signed ? ` by ${signed}` : ""}
          {c.publish?.released ? `; released by ${c.publish.released.by} ${formatTime(c.publish.released.at)}` : ""}
          {tickets ? `; ${tickets} ${tickets === 1 ? "ticket" : "tickets"} raised for the owning teams` : ""}.
        </p>
      </Shell>
    );
  }
  return null;
}

/** What each step does next, in words — for "the run goes on to …". */
const NEXT: Record<string, string> = {
  enrich: "reading more data onto the items", resolve: "looking up reference data", classify: "running the playbook",
  compare: "comparing to the baseline", group: "grouping the items", reason: "the rules and the model's investigation",
  draft: "drafting the summary",
};

/** A tollgate: a person approves the work so far before the run goes on — or stops it. */
function GateCard({ c }: { c: CaseDetail }) {
  const w = c.waiting_on!;
  const step = w.gate!;
  const pass = usePassGate(c.case_id);
  const [comment, setComment] = useState("");
  const [stopping, setStopping] = useState(false);
  const done = c.steps.slice(0, c.steps.indexOf(step));
  const inScope = c.groups.reduce((n, g) => n + g.item_ids.length, 0);
  const modelRan = c.tool_calls.some((t) => t.requested_by === "llm");
  const needWords = stopping && w.stop_needs_comment && !comment.trim();
  return (
    <Shell tone={w.you ? "action" : "waiting"} icon={Hand} title={w.you ? "Your tollgate" : "Waiting at a tollgate"}>
      <p>
        The run stopped before <strong>{NEXT[step] ?? step}</strong>, for a person to approve the work so far.
        {w.check && <> Check: <em>{w.check}</em></>}
      </p>
      <p className="mt-0.5 text-xs opacity-80">
        Done so far: {done.join(" → ")} · {c.items.length} {c.labels.item.toLowerCase()}{c.items.length === 1 ? "" : "s"}
        {c.groups.length > 0 && <>, {inScope} in scope in {c.groups.length} {c.groups.length === 1 ? "group" : "groups"}</>}
        {modelRan ? "" : " · the model has not been asked anything yet"}. The data is below; each step's state is under Run history.
      </p>
      {!w.you && <p className="mt-0.5 text-xs opacity-80">{w.why_not}.</p>}
      {(c.gate_decisions ?? []).length > 0 && (
        <p className="mt-0.5 text-xs opacity-80">
          Passed earlier: {(c.gate_decisions ?? []).map((g) => `${g.step} by ${g.decided_by}`).join(", ")}.
        </p>
      )}
      {w.you && (
        <div className="mt-2 space-y-2">
          <label className="block text-xs font-medium">
            {stopping ? `Why stop the run?${w.stop_needs_comment ? " (required)" : ""}` : "Note (optional)"}
            <textarea value={comment} onChange={(e) => setComment(e.target.value)} rows={2}
              className="mt-1 block w-full rounded-lg border border-surface-300 bg-card px-2 py-1.5 text-sm font-normal text-surface-800" />
          </label>
          <div className="flex flex-wrap gap-2">
            {!stopping ? (
              <>
                <button type="button" disabled={pass.isPending} onClick={() => pass.mutate({ step, action: "continue", comment: comment.trim() || null })}
                  className="inline-flex items-center gap-1.5 rounded-lg bg-brand px-3 py-1.5 text-sm font-medium text-brand-fg hover:bg-brand-strong disabled:opacity-50">
                  <Play size={13} /> Approve and continue
                </button>
                <button type="button" onClick={() => setStopping(true)}
                  className="inline-flex items-center gap-1.5 rounded-lg border border-red-200 px-3 py-1.5 text-sm text-red-700 hover:bg-red-50">
                  <OctagonX size={13} /> Stop the run
                </button>
              </>
            ) : (
              <>
                <button type="button" disabled={pass.isPending || needWords} onClick={() => pass.mutate({ step, action: "stop", comment: comment.trim() || null })}
                  className="inline-flex items-center gap-1.5 rounded-lg bg-red-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-red-700 disabled:opacity-50">
                  <OctagonX size={13} /> Stop here
                </button>
                <button type="button" onClick={() => setStopping(false)} className="rounded-lg border border-surface-300 px-3 py-1.5 text-sm text-surface-700 hover:bg-surface-50">
                  Cancel
                </button>
              </>
            )}
          </div>
          {pass.error && <ErrorState error={pass.error} />}
        </div>
      )}
    </Shell>
  );
}

const TONES = {
  action: "border-primary-200 bg-primary-50 text-primary-900",
  attention: "border-orange-200 bg-orange-50 text-orange-900",
  waiting: "border-surface-200 bg-surface-100 text-surface-700",
  done: "border-green-200 bg-green-50 text-green-900",
} as const;

function Shell({ tone, icon: Icon, title, children }: {
  tone: keyof typeof TONES;
  icon: typeof Scale;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section role="status" aria-label={title} className={clsx("mt-3 flex gap-3 rounded-xl border px-3 py-2.5 text-sm sm:px-4", TONES[tone])}>
      <Icon size={18} className="mt-0.5 shrink-0" />
      <div className="min-w-0 flex-1">
        <h2 className="font-semibold">{title}</h2>
        <div className="mt-0.5">{children}</div>
      </div>
    </section>
  );
}

/** Before anything is written: every approved result, who approved it, in their words. */
export function ReleaseSummary({ c }: { c: CaseDetail }) {
  if (!c.publish || !["awaiting_publish", "completed", "failed"].includes(c.status)) return null;
  if (c.status !== "awaiting_publish" && !c.publish.released) return null;
  const rows = c.groups.filter((g) => g.decision);
  const approved = rows.filter((g) => g.decision!.action === "approve");
  return (
    <section className="border-b border-surface-100 p-3 sm:p-5" aria-label="What will be released">
      <h2 className="flex items-center gap-2 text-sm font-semibold text-surface-900">
        <Send size={14} /> {c.status === "awaiting_publish" ? "What will be written" : "What was written"}
        <span className="text-xs font-normal text-surface-500">
          {approved.length} of {rows.length} approved → <code>{c.publish.tool}</code>
        </span>
      </h2>
      <ul className="mt-2 divide-y divide-surface-100 rounded-lg border border-surface-200">
        {rows.map((g) => (
          <li key={g.group_id} className="flex flex-col gap-1 px-3 py-2 text-sm sm:flex-row sm:items-start sm:gap-3">
            <div className="flex shrink-0 items-center gap-2 sm:w-48">
              <StatusBadge status={g.decision!.action === "approve" ? "approved" : "rejected"} />
              <span className="font-medium text-surface-800">{g.label}</span>
            </div>
            <p className="min-w-0 flex-1 text-surface-700">
              {g.decision!.comment || g.finding?.comment || "—"}
              {g.decision!.action !== "approve" && <span className="ml-1 text-xs text-surface-500">(not written)</span>}
            </p>
            <span className="shrink-0 text-xs text-surface-500">
              {g.decision!.decided_by}
              {g.decision!.on_behalf_of ? ` for ${g.decision!.on_behalf_of}` : ""} · {formatTime(g.decision!.decided_at)}
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}

/** Why a group was escalated, in plain words. */
export function explainEscalation(f: Finding): string {
  const reason = f.reason ?? "";
  if (reason.startsWith("UNGROUNDED_FIGURE")) {
    return `The explanation quoted figures that are not in the data (${reason.split(":").slice(1).join(":").trim()}). Helix never lets an unverified figure through, so a person decides.`;
  }
  if (reason.startsWith("REASONER_ERROR")) return `The model could not finish its investigation (${reason.split(":").slice(1).join(":").trim()}).`;
  if (/spend limit/i.test(reason)) return `${reason}. The model was not used, so a person decides.`;
  if (reason.startsWith("Held:")) return `A posting was held because a blocking test failed: ${reason.slice(5).trim()}.`;
  if (f.guard) return f.guard;
  if (f.category === "H" || /novel/i.test(f.category_name ?? "")) {
    return "No cause check or validation test explained this break, so the playbook treats it as a novel break and escalates it.";
  }
  if (/^Escalate to /.test(reason) && f.category_name) {
    return `The playbook escalates ${f.category_name.toLowerCase()}s${f.side_name ? ` (${f.side_name})` : ""} to ${f.escalate_to ?? "the owning team"} rather than settling them automatically.`;
  }
  return reason || "Escalated for a person to decide.";
}

/** The escalated group's card: why, who owns it, and what the reviewer can do. */
export function EscalationCard({ group, canDecide }: { group: Group; canDecide: boolean }) {
  const f = group.finding;
  if (!f || f.status !== "escalated") return null;
  return (
    <section className="mt-3 rounded-lg border border-orange-200 bg-orange-50 p-3 text-sm text-orange-950" aria-label="Why it was escalated">
      <h3 className="flex items-center gap-1.5 font-semibold text-orange-900">
        <ShieldAlert size={15} /> Escalated — a person decides
      </h3>
      <p className="mt-1">{explainEscalation(f)}</p>
      <dl className="mt-2 grid gap-x-4 gap-y-1 text-xs sm:grid-cols-2">
        {f.escalate_to && (
          <div><dt className="inline text-orange-800">Owning team: </dt><dd className="inline font-medium">{f.escalate_to}</dd></div>
        )}
        {f.verdict && (
          <div><dt className="inline text-orange-800">Verdict: </dt><dd className="inline font-medium">{f.verdict.replace(/_/g, " ")}</dd></div>
        )}
        {group.ticket?.reference && (
          <div className="flex items-center gap-1"><Ticket size={11} /> Ticket {group.ticket.reference}</div>
        )}
      </dl>
      {canDecide && !group.decision && (
        <div className="mt-2 border-t border-orange-200 pt-2 text-xs">
          <p className="font-medium text-orange-900">What you can do</p>
          <ul className="mt-0.5 list-disc space-y-0.5 pl-4">
            <li><strong>Approve</strong> with your own explanation if you are satisfied — it is recorded with your name.</li>
            <li><strong>Reject</strong> and say why — it goes back as not accepted.</li>
            <li><strong>Investigate again</strong> — tell the model what to check (below).</li>
            <li>Attach supporting evidence on the Case side.</li>
          </ul>
        </div>
      )}
    </section>
  );
}
