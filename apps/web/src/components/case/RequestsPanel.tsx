// Asking for evidence instead of assuming it (FOBO skill §13): the questions
// asked about this case, their answers, and a form to ask one of the
// capability's targets (the desk, a trader, Operations) about a group or the
// whole case. A group with an open question waits for the answer.

import { useState } from "react";
import { MessageCircleQuestion, Send, X } from "lucide-react";

import { useAskForEvidence, useCancelRequest, type CaseDetail } from "../../api/aof";
import { download } from "../../api/client";
import StatusBadge from "../StatusBadge";
import { ErrorState, formatTime } from "../ui";

export default function RequestsPanel({ c }: { c: CaseDetail }) {
  const requests = c.requests ?? [];
  const targets = c.request_targets ?? [];
  const ask = useAskForEvidence(c.case_id);
  const cancel = useCancelRequest(c.case_id);
  const [open, setOpen] = useState(false);
  const [target, setTarget] = useState(targets[0]?.id ?? "");
  const [group, setGroup] = useState<string>("");
  const [question, setQuestion] = useState("");
  if (!targets.length && !requests.length) return null;
  const label = (gid: string | null) => (gid ? c.groups.find((g) => g.group_id === gid)?.label ?? gid : "whole case");

  return (
    <section className="rounded-lg border border-surface-200 bg-card p-3" aria-label="Questions">
      <h2 className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-surface-500">
        <MessageCircleQuestion size={12} /> Questions
      </h2>
      {requests.length === 0 && <p className="mt-1 text-xs text-surface-500">None asked. Ask rather than assume.</p>}
      <ul className="mt-2 space-y-2">
        {requests.map((r) => (
          <li key={r.request_id} className="rounded-md border border-surface-100 p-2 text-xs">
            <div className="flex items-center gap-2">
              <span className="font-medium text-surface-800">{r.target_name}</span>
              <StatusBadge status={r.status === "open" ? "pending" : r.status === "answered" ? "approved" : "inactive"} />
              {r.status === "open" && c.can_ask && (
                <button type="button" aria-label="Cancel question" onClick={() => cancel.mutate(r.request_id)}
                  className="ml-auto rounded p-0.5 text-surface-400 hover:bg-surface-100 hover:text-surface-700"><X size={12} /></button>
              )}
            </div>
            <p className="mt-0.5 text-[11px] text-surface-500">About {label(r.group_id)} · {r.asked_by} · {formatTime(r.asked_at)}</p>
            <p className="mt-1 text-surface-800">“{r.question}”</p>
            {r.answer && <p className="mt-1 rounded bg-green-50 px-2 py-1 text-green-900">{r.answer} <span className="text-[11px] text-green-700">— {r.answered_by}</span></p>}
            {r.attachment && (
              <button type="button" onClick={() => void download(r.attachment!.url.replace(/^\/api/, ""), r.attachment!.name)}
                className="mt-1 text-[11px] font-medium text-primary-700 hover:underline">Attached: {r.attachment.name.split("--").pop()}</button>
            )}
            {r.status === "open" && (r.reminded_at || r.escalated_at) && (
              <p className="mt-1 text-[11px] text-surface-500">
                {r.escalated_at ? `Unanswered: reviewers told ${formatTime(r.escalated_at)}` : `Reminded ${formatTime(r.reminded_at!)}`}
              </p>
            )}
            {r.status === "open" && r.group_id && <p className="mt-1 text-[11px] text-orange-700">This group waits for the answer before it is decided.</p>}
          </li>
        ))}
      </ul>
      {c.can_ask && !open && (
        <button type="button" onClick={() => setOpen(true)}
          className="mt-2 inline-flex items-center gap-1 rounded-lg border border-primary-200 px-2.5 py-1 text-xs font-medium text-primary-700 hover:bg-primary-50">
          <MessageCircleQuestion size={12} /> Ask for evidence
        </button>
      )}
      {c.can_ask && open && (
        <form className="mt-2 space-y-2 text-xs" onSubmit={(e) => {
          e.preventDefault();
          ask.mutate({ target, question, group_id: group || null }, { onSuccess: () => { setQuestion(""); setOpen(false); } });
        }}>
          <label className="block font-medium text-surface-600">Ask
            <select value={target} onChange={(e) => setTarget(e.target.value)} className="mt-0.5 block w-full rounded-lg border border-surface-300 bg-card px-2 py-1">
              {targets.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
            </select>
          </label>
          <label className="block font-medium text-surface-600">About
            <select value={group} onChange={(e) => setGroup(e.target.value)} className="mt-0.5 block w-full rounded-lg border border-surface-300 bg-card px-2 py-1">
              <option value="">the whole case</option>
              {c.groups.map((g) => <option key={g.group_id} value={g.group_id}>{g.label}</option>)}
            </select>
          </label>
          <label className="block font-medium text-surface-600">Question
            <textarea value={question} onChange={(e) => setQuestion(e.target.value)} rows={3}
              className="mt-0.5 block w-full rounded-lg border border-surface-300 bg-card px-2 py-1 font-normal" />
          </label>
          <div className="flex gap-2">
            <button type="submit" disabled={!question.trim() || ask.isPending}
              className="inline-flex items-center gap-1 rounded-lg bg-brand px-2.5 py-1 font-medium text-brand-fg hover:bg-brand-strong disabled:opacity-50">
              <Send size={12} /> Send
            </button>
            <button type="button" onClick={() => setOpen(false)} className="rounded-lg border border-surface-300 px-2.5 py-1 text-surface-700">Cancel</button>
          </div>
          {ask.error && <ErrorState error={ask.error} />}
        </form>
      )}
      {cancel.error && <div className="mt-2"><ErrorState error={cancel.error} /></div>}
    </section>
  );
}
