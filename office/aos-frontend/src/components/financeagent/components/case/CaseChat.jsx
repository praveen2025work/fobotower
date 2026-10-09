// Generated from apps/web/src/components/case/CaseChat.tsx by apps/web/office/convert.mjs. Office changes to this file are
// kept by aof_sync.py on the next update; see docs/agent-one-finance/office/conversion-guide.md.
// Ask about a case — aria-ai's chat idea, scoped to one case. Answers come
// from the case's own data and its capability's read tools (through the
// gateway), and any figure the answer cannot trace is flagged under it.

import { useState } from "react";
import { AlertTriangle, Bot, Loader2, Send, User } from "lucide-react";

import { useAsk, useMessages } from "../../api/aof";
import { ErrorState, formatTime } from "../ui";

function Bubble({ m }) {
  const mine = m.role === "user";
  const unverified = m.meta?.unverified_figures ?? [];
  return (
    <li className={mine ? "ml-8" : "mr-8"}>
      <div className={mine ? "rounded-lg bg-primary-50 p-3" : "rounded-lg border border-surface-200 bg-card p-3"}>
        <p className="mb-1 flex items-center gap-1.5 text-[11px] text-surface-500">
          {mine ? <User size={11} /> : <Bot size={11} />} {m.author}
          {m.created_at && <span>· {formatTime(m.created_at)}</span>}
          {!mine && m.meta?.tool_calls?.length ? <span>· {m.meta.tool_calls.length} lookup(s)</span> : null}
        </p>
        <p className="whitespace-pre-wrap text-sm leading-relaxed text-surface-800">{m.text}</p>
        {unverified.length > 0 && (
          <p className="mt-2 flex items-start gap-1.5 text-xs text-orange-700">
            <AlertTriangle size={12} className="mt-0.5 shrink-0" />
            Not traceable to this case's data: {unverified.map((n) => n.toLocaleString()).join(", ")}
          </p>
        )}
      </div>
    </li>
  );
}

export default function CaseChat({ caseId }) {
  const thread = useMessages(caseId);
  const ask = useAsk(caseId);
  const [question, setQuestion] = useState("");

  const send = () => {
    const q = question.trim();
    if (!q) return;
    ask.mutate(q, { onSuccess: () => setQuestion("") });
  };

  return (
    <div className="flex h-full flex-col gap-3">
      <p className="text-xs text-surface-500">
        Ask about this case in plain words. Answers use only the case's data and its capability's read tools; every
        lookup is audited.
      </p>
      <ul className="flex-1 space-y-2" aria-label="Conversation">
        {(thread.data ?? []).map((m, i) => (
          <Bubble key={m.message_id ?? i} m={m} />
        ))}
        {thread.data?.length === 0 && <li className="text-sm text-surface-400">No questions yet.</li>}
      </ul>
      {ask.error && <ErrorState error={ask.error} />}
      <div className="flex items-end gap-2">
        <label className="flex-1 text-xs font-medium text-surface-600">
          Your question
          <textarea
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                send();
              }
            }}
            rows={2}
            placeholder="e.g. Why is SOFR FUT different, and who owns it?"
            className="mt-1 block w-full rounded-lg border border-surface-300 px-3 py-2 text-sm font-normal focus:border-primary-400 focus:outline-none"
          />
        </label>
        <button
          onClick={send}
          disabled={ask.isPending || !question.trim()}
          className="inline-flex items-center gap-1.5 rounded-lg bg-brand px-3 py-2 text-sm font-medium text-brand-fg hover:bg-brand-strong disabled:opacity-50"
        >
          {ask.isPending ? <Loader2 size={14} className="animate-spin" /> : <Send size={14} />} Ask
        </button>
      </div>
    </div>
  );
}
