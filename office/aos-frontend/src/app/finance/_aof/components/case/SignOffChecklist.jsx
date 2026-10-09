// Generated from apps/web/src/components/case/SignOffChecklist.tsx by apps/web/office/convert.mjs. Office changes to this file are
// kept by aof_sync.py on the next update; see docs/agent-one-finance/office/conversion-guide.md.
// The sign-off checklist (review.checklist): each question with what Agent One Finance
// already knows next to it, answered yes / no / n/a before approving.

import clsx from "clsx";
const CHOICES = ["yes", "no", "n/a"];

/** Approving needs every required question answered yes or n/a. */
export function checklistComplete(questions, answers) {
  return questions.every((q) => !q.required || ["yes", "n/a"].includes(answers[q.id]?.answer ?? ""));
}

export function SignOffChecklist({ questions, answers, onChange }) {
  const set = (id, patch) => onChange({ ...answers, [id]: { ...(answers[id] ?? { id, answer: null }), ...patch } });
  return (
    <fieldset className="mb-3 rounded-lg border border-surface-200 p-2">
      <legend className="px-1 text-xs font-semibold text-surface-700">Sign-off checklist</legend>
      <ol className="space-y-2">
        {questions.map((q, i) => (
          <li key={q.id} className="text-xs">
            <div className="flex flex-wrap items-center gap-2">
              <span className="min-w-0 flex-1 font-medium text-surface-800">
                {i + 1}. {q.label}
                {q.required && (
                  <span className="text-red-600" aria-label="required">
                    {" "}
                    *
                  </span>
                )}
              </span>
              <span
                role="radiogroup"
                aria-label={q.label}
                className="inline-flex overflow-hidden rounded-md border border-surface-300"
              >
                {CHOICES.map((choice) => (
                  <button
                    key={choice}
                    type="button"
                    role="radio"
                    aria-checked={answers[q.id]?.answer === choice}
                    onClick={() => set(q.id, { answer: choice })}
                    className={clsx(
                      "px-2 py-0.5",
                      answers[q.id]?.answer === choice
                        ? "bg-primary-600 text-white"
                        : "bg-card text-surface-700 hover:bg-surface-50",
                    )}
                  >
                    {choice}
                  </button>
                ))}
              </span>
            </div>
            {q.known && (
              <p className="mt-0.5 line-clamp-1 text-surface-500" title={q.known}>
                Found: {q.known}
              </p>
            )}
            {answers[q.id]?.answer === "no" && (
              <input
                aria-label={`Note for ${q.label}`}
                placeholder="What is missing?"
                value={answers[q.id]?.note ?? ""}
                onChange={(e) => set(q.id, { note: e.target.value })}
                className="mt-1 w-full rounded-md border border-surface-300 px-2 py-1"
              />
            )}
          </li>
        ))}
      </ol>
    </fieldset>
  );
}

export function ChecklistAnswers({ answers }) {
  return (
    <ul className="mt-2 space-y-0.5 text-xs text-surface-600">
      {answers.map((a) => (
        <li key={a.id}>
          <span className="font-medium text-surface-800">{a.answer ?? "—"}</span> · {a.label}
          {a.note ? <span className="text-surface-500"> — {a.note}</span> : null}
        </li>
      ))}
    </ul>
  );
}
