// What steps v2 add to a case, where people look for it: on a group, who may
// approve it (authority tier, reserved decisions), the journals proposed and
// the messages drafted or sent; beside the case, the case that opened it, the
// cases it opened and its clocks.

import { Link } from "react-router-dom";
import clsx from "clsx";
import { AlarmClock, GitFork, Lock, Mail, ShieldCheck } from "lucide-react";

import type { CaseDetail, Group } from "../../api/helix";
import StatusBadge from "../StatusBadge";
import { formatTime, formatValue } from "../ui";

const roles = (r: string[]) => r.map((x) => x.replace(/_/g, " ").toLowerCase()).join(" or ");

export function GroupSteps({ group }: { group: Group }) {
  const f = group.finding;
  if (!f) return null;
  const a = group.approvals;
  return (
    <div className="mt-3 space-y-2">
      {(f.authority || f.reserved) && (
        <div className="flex flex-wrap items-center gap-2 text-xs">
          {f.authority && (
            <span className="inline-flex items-center gap-1 rounded bg-surface-100 px-1.5 py-0.5 text-surface-700" title={`from ${f.authority.source}`}>
              <ShieldCheck size={12} /> {f.authority.label}: {roles(f.authority.roles)}
              {f.authority.approvals > 1 && <> · {f.authority.approvals} different people</>}
              {f.authority.lane !== "standard" && <> · {f.authority.lane} lane</>}
              {!f.authority.bulk && <> · one by one</>}
            </span>
          )}
          {f.reserved && (
            <span className="inline-flex items-center gap-1 rounded bg-amber-50 px-1.5 py-0.5 text-amber-900">
              <Lock size={12} /> Reserved for {roles(f.reserved.roles)}: {f.reserved.reason}
            </span>
          )}
          {a && a.needed > 1 && !a.settled && (
            <span className="text-surface-600">
              {a.by.length} of {a.needed} approvals{a.by.length ? ` (${a.by.join(", ")})` : ""}
            </span>
          )}
        </div>
      )}
      {f.withheld_proposal && (
        <p className="text-xs text-amber-900">The model proposed “{f.withheld_proposal}”, a decision reserved for people; it is withheld for you to decide.</p>
      )}
      {f.entries && (
        <div className="rounded-lg border border-surface-200">
          <p className="flex flex-wrap items-center gap-2 border-b border-surface-100 px-2 py-1.5 text-xs font-semibold text-surface-700">
            Journal {f.entries.journal_id}
            {f.entries.period && <span className="font-normal text-surface-500">period {f.entries.period}</span>}
            <span className={clsx("ml-auto font-normal", f.entries.balanced ? "text-green-700" : "text-red-700")}>
              {f.entries.balanced ? "balanced" : "not balanced"}
            </span>
          </p>
          <table className="min-w-full text-xs">
            <thead className="text-left text-[11px] text-surface-500">
              <tr><th className="px-2 py-1">Account</th><th className="px-2 py-1 text-right">Debit</th><th className="px-2 py-1 text-right">Credit</th><th className="px-2 py-1">Narrative</th></tr>
            </thead>
            <tbody>
              {f.entries.lines.map((l, i) => (
                <tr key={i} className="border-t border-surface-100">
                  <td className="px-2 py-1 font-mono">{l.account}</td>
                  <td className="px-2 py-1 text-right">{l.side === "debit" ? formatValue(l.amount) : ""}</td>
                  <td className="px-2 py-1 text-right">{l.side === "credit" ? formatValue(l.amount) : ""}</td>
                  <td className="px-2 py-1 text-surface-600">{l.narrative}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {f.entries.problems.length > 0 && (
            <ul className="border-t border-surface-100 px-2 py-1.5 text-xs text-red-700">
              {f.entries.problems.map((p) => <li key={p}>{p}</li>)}
            </ul>
          )}
        </div>
      )}
      {(f.sent_message || f.draft_message) && <Message group={group} />}
    </div>
  );
}

function Message({ group }: { group: Group }) {
  const f = group.finding!;
  const m = f.sent_message ?? f.draft_message!;
  const sent = f.sent_message && !f.sent_message.error;
  return (
    <div className="rounded-lg border border-surface-200 p-2 text-xs">
      <p className="flex flex-wrap items-center gap-2 font-semibold text-surface-700">
        <Mail size={12} /> {sent ? "Sent" : f.sent_message?.error ? "Not sent" : "Draft message (not sent)"}
        <span className="font-normal text-surface-500">to {m.to}</span>
        {sent && f.sent_message?.approved_by && <span className="font-normal text-surface-500">· approved by {f.sent_message.approved_by}</span>}
      </p>
      <p className="mt-1 font-medium text-surface-800">{m.subject}</p>
      <p className="mt-0.5 whitespace-pre-wrap text-surface-700">{m.body}</p>
      {f.sent_message?.error && <p className="mt-1 text-red-700">{f.sent_message.error}</p>}
    </div>
  );
}

/** The case that opened this one, the cases it opened, and its clocks. */
export function CaseLinks({ c }: { c: CaseDetail }) {
  const kids = c.children ?? [];
  const clocks = c.clocks ?? [];
  if (!c.parent_case_id && kids.length === 0 && clocks.length === 0) return null;
  const now = Date.now();
  return (
    <div className="space-y-3">
      {c.parent_case_id && (
        <p className="flex items-center gap-1.5 text-xs text-surface-600">
          <GitFork size={12} /> Opened by{" "}
          <Link to={`/cases/${encodeURIComponent(c.parent_case_id)}`} className="text-primary-700 hover:underline">its parent case</Link>
        </p>
      )}
      {kids.length > 0 && (
        <div>
          <h2 className="mb-1 text-xs font-semibold uppercase tracking-wider text-surface-500">
            Child cases · {kids.filter((k) => ["completed", "failed", "stopped", "escalated"].includes(k.status)).length} of {kids.length} finished
          </h2>
          <ul className="space-y-1">
            {kids.map((k) => (
              <li key={k.case_id} className="flex items-center gap-2 text-xs">
                <Link to={`/cases/${encodeURIComponent(k.case_id)}`} className="min-w-0 flex-1 truncate text-primary-700 hover:underline">{k.subject}</Link>
                <StatusBadge status={k.status} />
              </li>
            ))}
          </ul>
        </div>
      )}
      {clocks.length > 0 && (
        <div>
          <h2 className="mb-1 text-xs font-semibold uppercase tracking-wider text-surface-500">Clocks</h2>
          <ul className="space-y-1">
            {clocks.map((k) => {
              const due = new Date(k.due_at).getTime();
              const state = now > due ? "breached" : now > due - k.warn_before_hours * 3600_000 ? "due soon" : "on time";
              return (
                <li key={k.id} className="flex items-center gap-2 text-xs">
                  <AlarmClock size={12} className={clsx(state === "breached" ? "text-red-600" : state === "due soon" ? "text-amber-600" : "text-surface-400")} />
                  <span className="min-w-0 flex-1 truncate">{k.label}</span>
                  <span className={clsx(state === "breached" ? "font-medium text-red-700" : state === "due soon" ? "text-amber-800" : "text-surface-500")}>
                    {state} · {formatTime(k.due_at)}
                  </span>
                </li>
              );
            })}
          </ul>
        </div>
      )}
    </div>
  );
}
