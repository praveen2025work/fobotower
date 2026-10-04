import type { ReactNode } from "react";
import clsx from "clsx";
import { AlertTriangle, Check, Loader2, Pause } from "lucide-react";

import { ApiError } from "../api/client";

export function PageHeader({ title, subtitle, actions }: { title: string; subtitle?: ReactNode; actions?: ReactNode }) {
  return (
    <div className="mb-4 flex flex-wrap items-end justify-between gap-3 sm:mb-5">
      <div className="min-w-0">
        <h1 className="text-xl font-bold tracking-tight text-surface-900 sm:text-2xl">{title}</h1>
        {subtitle && <p className="mt-1 text-sm text-surface-500">{subtitle}</p>}
      </div>
      {actions}
    </div>
  );
}

export function Card({ title, aside, children, className }: { title?: ReactNode; aside?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section className={clsx("min-w-0 rounded-xl border border-surface-200 bg-card", className)}>
      {(title || aside) && (
        <header className="flex items-center justify-between gap-2 border-b border-surface-100 px-4 py-3">
          {title && <h2 className="text-sm font-semibold text-surface-800">{title}</h2>}
          {aside}
        </header>
      )}
      <div className="p-3 sm:p-4">{children}</div>
    </section>
  );
}

export function Loading({ what }: { what: string }) {
  return (
    <p className="flex items-center gap-2 py-6 text-sm text-surface-500">
      <Loader2 size={16} className="animate-spin" /> Loading {what}…
    </p>
  );
}

export function ErrorState({ error }: { error: unknown }) {
  const message = error instanceof Error ? error.message : String(error);
  const problems = error instanceof ApiError ? error.problems : [];
  return (
    <div role="alert" className="flex gap-2 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-800">
      <AlertTriangle size={16} className="mt-0.5 shrink-0" />
      <div>
        {message}
        {problems.length > 0 && (
          <ul className="mt-1 list-disc pl-5">
            {problems.map((p) => (
              <li key={p}>{p}</li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return <p className="py-6 text-center text-sm text-surface-400">{children}</p>;
}

const GATES = new Set(["validate", "review", "record"]);

/** The capability's workflow as a stepper; `current` is where the case stands. */
export function WorkflowStepper({ steps, pauseBefore = [], current }: { steps: string[]; pauseBefore?: string[]; current?: string | null }) {
  const at = current ? steps.indexOf(current) : -1;
  return (
    <ol className="flex flex-wrap items-center gap-1.5" aria-label="Workflow">
      {steps.map((s, i) => {
        const done = at >= 0 ? i < at : current === "__done__";
        const here = i === at;
        return (
          <li key={s} className="flex items-center gap-1.5">
            {pauseBefore.includes(s) && <Pause size={11} className="text-surface-400" aria-label="pauses for a person" />}
            <span
              className={clsx(
                "inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-[11px] font-medium",
                here && "border-accent-500 bg-accent-50 text-accent-700",
                done && "border-surface-200 bg-surface-50 text-surface-500",
                !here && !done && "border-surface-200 text-surface-600",
                GATES.has(s) && !here && "border-dashed",
              )}
              title={GATES.has(s) ? "mandatory gate" : undefined}
            >
              {done && <Check size={10} />}
              {s}
            </span>
            {i < steps.length - 1 && <span className="text-surface-300">›</span>}
          </li>
        );
      })}
    </ol>
  );
}

export function formatValue(v: unknown): string {
  if (typeof v === "number") return v.toLocaleString("en-GB", { maximumFractionDigits: 2 });
  if (v === null || v === undefined) return "—";
  return String(v);
}

export function formatTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("en-GB", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" });
}

/** Where a case stands in its workflow, from its status. */
export function currentStep(status: string): string | null {
  if (status === "awaiting_review") return "review";
  if (status === "awaiting_publish") return "publish";
  if (status === "completed") return "__done__";
  return null;
}
