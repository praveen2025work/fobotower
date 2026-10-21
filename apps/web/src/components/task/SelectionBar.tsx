// Decide the proposals a reviewer ticked — in the Proposals list or on the Summary —
// at once: one explanation, one confirmation and one sign-off checklist for all of
// them. Every proposal is still checked on its own by the review rules: those the
// agent keeps for one-by-one review (review.bulk_exclude: a judgement call, a
// verdict needing confirmation) are left out of Approve and say so.

import { useState } from "react";
import clsx from "clsx";
import { Check, X } from "lucide-react";

import { useBulkDecide, type ChecklistAnswer, type TaskDetail } from "../../api/aof";
import { ErrorState } from "../ui";
import { SignOffChecklist, checklistComplete } from "./SignOffChecklist";

const HELD: Record<string, string> = {
  confirmation: "the verdict needs confirming on its own",
  judgement: "a judgement call",
  reserved: "reserved for named people",
  authority: "its authority tier",
};

export default function SelectionBar({ c, picked, onClear, openedAt, onOpen }: {
  c: TaskDetail;
  /** the ticked proposals still open */
  picked: string[];
  onClear: () => void;
  openedAt: number;
  onOpen: (groupId: string) => void;
}) {
  const bulk = useBulkDecide(c.task_id);
  const [comment, setComment] = useState("");
  const [confirmed, setConfirmed] = useState(false);
  const [answers, setAnswers] = useState<Record<string, ChecklistAnswer>>({});
  const groups = c.groups.filter((g) => picked.includes(g.group_id) && !g.decision);
  const result = bulk.data;
  if (!groups.length && !result && !bulk.error) return null;

  const item = (c.labels?.item ?? "item").toLowerCase();
  const approvable = groups.filter((g) => !(g.bulk_blockers ?? []).length);
  const held = groups.filter((g) => (g.bulk_blockers ?? []).length);
  const rules = c.review?.require_comment ?? ["reject", "escalated"];
  const confirmMode = c.review?.confirm ?? "tick_and_comment";
  const needsConfirm = confirmMode !== "none" && approvable.some((g) => (g.flags ?? []).includes("confirmation"));
  const wordsToApprove =
    (rules.includes("escalated") && approvable.some((g) => g.finding?.status === "escalated")) ||
    (needsConfirm && confirmMode === "tick_and_comment");
  const wordsToReject = rules.includes("reject");
  const questions = approvable[0]?.checklist ?? [];
  const words = comment.trim().length > 0;
  const approveBlock = !approvable.length
    ? "none of the selected can be approved together"
    : wordsToApprove && !words
      ? "approving escalated or confirmed verdicts needs your explanation"
      : needsConfirm && !confirmed
        ? "tick to confirm the verdicts"
        : !checklistComplete(questions, answers)
          ? "answer the sign-off checklist"
          : null;
  const rejectBlock = !groups.length ? "nothing selected" : wordsToReject && !words ? "rejecting needs your reason" : null;
  const breaks = groups.reduce((a, g) => a + g.item_ids.length, 0);
  const labelOf = (id: string) => c.groups.find((g) => g.group_id === id)?.label ?? id;

  const send = (action: "approve" | "reject") =>
    bulk.mutate(
      {
        groupIds: (action === "approve" ? approvable : groups).map((g) => g.group_id),
        action,
        comment,
        reviewSeconds: Math.round((Date.now() - openedAt) / 1000),
        confirmed: action === "approve" && confirmed,
        checklist: action === "approve" && questions.length ? Object.values(answers) : undefined,
      },
      {
        onSuccess: () => {
          setComment("");
          setConfirmed(false);
          setAnswers({});
        },
      },
    );

  return (
    <section aria-label="Selected proposals" className="rounded-lg border border-accent-300 bg-card p-3 text-sm shadow-sm">
      {groups.length > 0 && (
        <>
          <div className="flex items-start justify-between gap-2">
            <p className="text-surface-800">
              <b className="font-semibold">{groups.length} selected</b>
              <span className="text-surface-500"> · {breaks.toLocaleString("en-GB")} {item}{breaks === 1 ? "" : "s"}</span>
            </p>
            <button type="button" onClick={() => { onClear(); bulk.reset(); }} className="inline-flex items-center gap-1 text-xs text-surface-500 hover:text-surface-800">
              <X size={12} /> Clear
            </button>
          </div>
          {held.length > 0 && (
            <div className="mt-1 text-[11px] text-orange-800">
              <p>{held.length === 1 ? "One is" : `${held.length} are`} decided one by one, so Approve leaves {held.length === 1 ? "it" : "them"} out (Reject includes {held.length === 1 ? "it" : "them"}):</p>
              <ul className="mt-0.5 space-y-0.5">
                {held.map((g) => (
                  <li key={g.group_id}>
                    <button type="button" onClick={() => onOpen(g.group_id)} className="text-left font-medium text-primary-700 hover:underline">{g.label}</button>
                    <span className="text-surface-500"> — {(g.bulk_blockers ?? []).map((b) => HELD[b] ?? b).join(", ")}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
          {questions.length > 0 && approvable.length > 0 && (
            <div className="mt-2"><SignOffChecklist questions={questions} answers={answers} onChange={setAnswers} /></div>
          )}
          <textarea
            aria-label="Your explanation for the selected proposals"
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            rows={2}
            placeholder="Your explanation, for every selected proposal"
            className="mt-2 w-full rounded-md border border-surface-300 px-2 py-1.5 text-sm"
          />
          {needsConfirm && (
            <label className="mt-1 flex items-start gap-2 text-xs text-surface-700">
              <input type="checkbox" checked={confirmed} onChange={(e) => setConfirmed(e.target.checked)} className="mt-0.5" />
              I confirm the verdicts of the selected proposals that need confirming
            </label>
          )}
          <div className="mt-2 flex flex-wrap gap-2">
            <button
              type="button"
              disabled={!!approveBlock || bulk.isPending}
              title={approveBlock ?? undefined}
              onClick={() => send("approve")}
              className="inline-flex items-center gap-1.5 rounded-lg bg-brand-accent px-3 py-1.5 text-xs font-semibold text-brand-accent-fg disabled:opacity-50"
            >
              <Check size={13} /> Approve {approvable.length}
            </button>
            <button
              type="button"
              disabled={!!rejectBlock || bulk.isPending}
              title={rejectBlock ?? undefined}
              onClick={() => send("reject")}
              className="inline-flex items-center gap-1.5 rounded-lg border border-surface-300 px-3 py-1.5 text-xs font-semibold text-surface-700 hover:bg-surface-50 disabled:opacity-50"
            >
              <X size={13} /> Reject {groups.length}
            </button>
          </div>
          {approveBlock && approvable.length > 0 && <p className="mt-1 text-[11px] text-surface-500">To approve: {approveBlock}.</p>}
        </>
      )}
      {result && (
        <div role="status" className={clsx("text-xs", groups.length > 0 && "mt-2 border-t border-surface-100 pt-2")}>
          <p className="text-surface-700">
            {result.decided.length} decided{result.refused.length ? `, ${result.refused.length} left open` : ""}.
          </p>
          {result.refused.length > 0 && (
            <ul className="mt-0.5 space-y-0.5 text-orange-800">
              {result.refused.map((r) => (
                <li key={r.group_id}>
                  <button type="button" onClick={() => onOpen(r.group_id)} className="font-medium text-primary-700 hover:underline">{labelOf(r.group_id)}</button>: {r.reason}
                </li>
              ))}
            </ul>
          )}
          {!groups.length && (
            <button type="button" onClick={() => bulk.reset()} className="mt-1 text-[11px] text-surface-500 hover:underline">Dismiss</button>
          )}
        </div>
      )}
      {bulk.error && <div className="mt-2"><ErrorState error={bulk.error} /></div>}
    </section>
  );
}
