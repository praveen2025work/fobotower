// Questions controllers asked you for evidence (the desk, a trader,
// Operations): the question, the breaks it is about — only those, not the
// whole case — and a box to answer. The answer goes back to the case and to
// the model.

import { useState } from "react";
import { MessageCircleQuestion, Send } from "lucide-react";

import { useAnswerQuestion, useMyQuestions, type QuestionForMe } from "../api/aof";
import { Card, ErrorState, formatTime, formatValue } from "./ui";

function Question({ q }: { q: QuestionForMe }) {
  const answer = useAnswerQuestion();
  const [text, setText] = useState("");
  const [file, setFile] = useState<File | null>(null);
  return (
    <li className="rounded-lg border border-surface-200 p-3 text-sm">
      <p className="text-xs text-surface-500">
        {q.asked_by} asked {formatTime(q.asked_at)} · {q.case_label}: {q.subject}{q.group_label ? ` · ${q.group_label}` : ""}
      </p>
      <p className="mt-1 font-medium text-surface-900">“{q.question}”</p>
      {q.rows.length > 0 && (
        <div className="mt-2 overflow-x-auto rounded border border-surface-100">
          <table className="min-w-full text-xs">
            <thead className="bg-surface-50 text-left text-surface-500"><tr>{q.columns.map((c) => <th key={c} className="px-2 py-1 font-medium">{c}</th>)}</tr></thead>
            <tbody>{q.rows.map((r, i) => (
              <tr key={i} className="border-t border-surface-100">{q.columns.map((c) => <td key={c} className="px-2 py-1">{formatValue(r[c])}</td>)}</tr>
            ))}</tbody>
          </table>
        </div>
      )}
      <form className="mt-2 flex flex-col gap-2 sm:flex-row" onSubmit={(e) => { e.preventDefault(); answer.mutate({ requestId: q.request_id, answer: text, file }); }}>
        <label className="flex-1 text-xs font-medium text-surface-600">Your answer
          <textarea value={text} onChange={(e) => setText(e.target.value)} rows={2}
            className="mt-0.5 block w-full rounded-lg border border-surface-300 bg-card px-2 py-1 text-sm font-normal" />
        </label>
        <label className="text-xs font-medium text-surface-600 sm:w-44">Attach (PDF or Excel, optional)
          <input type="file" accept=".pdf,.xlsx,.xlsm" onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            className="mt-0.5 block w-full text-xs font-normal" />
        </label>
        <button type="submit" disabled={!text.trim() || answer.isPending}
          className="inline-flex items-center justify-center gap-1 self-end rounded-lg bg-brand px-3 py-1.5 text-sm font-medium text-brand-fg hover:bg-brand-strong disabled:opacity-50">
          <Send size={13} /> Answer
        </button>
      </form>
      {answer.error && <div className="mt-1"><ErrorState error={answer.error} /></div>}
    </li>
  );
}

export default function QuestionsForYou() {
  const mine = useMyQuestions();
  const qs = mine.data ?? [];
  if (!qs.length) return null;
  return (
    <div className="mb-4">
      <Card title={<span className="flex items-center gap-2"><MessageCircleQuestion size={14} /> Questions for you ({qs.length})</span>}>
        <ul className="space-y-3">{qs.map((q) => <Question key={q.request_id} q={q} />)}</ul>
      </Card>
    </div>
  );
}
