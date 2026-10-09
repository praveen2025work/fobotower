// Generated from apps/web/src/components/ui.tsx by apps/web/office/convert.mjs. Office changes to this file are
// kept by aof_sync.py on the next update; see docs/agent-one-finance/office/conversion-guide.md.
import { useEffect, useState } from "react";
import clsx from "clsx";
import { AlertTriangle, Check, ChevronRight, Loader2, Pause } from "lucide-react";

import { ApiError } from "../api/client";

export function PageHeader({ title, subtitle, actions }) {
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

export function Card({ title, aside, children, className }) {
  return (
    <section className={clsx("hx-panel min-w-0 rounded-xl border border-surface-200 bg-card", className)}>
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

/** Whether a fold is open, remembered per person in this browser (a convenience only). */
export function useRemembered(key, initial) {
  const read = () => {
    if (!key) return initial;
    try {
      const v = localStorage.getItem(`aof.fold.${key}`);
      return v == null ? initial : v === "1";
    } catch {
      return initial;
    }
  };
  const [open, setOpen] = useState(read);
  const set = (v) => {
    setOpen(v);
    if (key) {
      try {
        localStorage.setItem(`aof.fold.${key}`, v ? "1" : "0");
      } catch {
        /* storage blocked: keep it for this visit */
      }
    }
  };
  return [open, set];
}

/** Progressive disclosure: secondary information folded away until asked for.
 *  `summary` stays visible when closed (e.g. "5 system calls"), so nothing is hidden silently. */
export function Fold({ title, summary, children, defaultOpen = false, remember, className }) {
  const [open, setOpen] = useRemembered(remember, defaultOpen);
  return (
    <div className={className}>
      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen(!open)}
        className="group flex w-full items-center gap-1.5 py-1 text-left text-xs font-semibold uppercase tracking-wide text-surface-500 hover:text-surface-800"
      >
        <ChevronRight size={13} className={clsx("shrink-0 transition-transform", open && "rotate-90")} />
        <span>{title}</span>
        {summary != null && !open && (
          <span className="ml-1 truncate font-normal normal-case tracking-normal text-surface-400">{summary}</span>
        )}
      </button>
      {open && <div className="mt-1.5">{children}</div>}
    </div>
  );
}

export function Loading({ what }) {
  return (
    <div className="py-4" aria-busy="true">
      <p className="flex items-center gap-2 text-sm text-surface-500">
        <Loader2 size={16} className="animate-spin" /> Loading {what}…
      </p>
      <div className="mt-3 space-y-2" aria-hidden="true">
        <div className="hx-skeleton h-3 w-11/12" />
        <div className="hx-skeleton h-3 w-9/12" />
        <div className="hx-skeleton h-3 w-10/12" />
      </div>
    </div>
  );
}

/** A number that counts up to its value when it first shows (instantly under reduced motion). */
export function CountUp({ value, suffix = "" }) {
  const [shown, setShown] = useState(value);
  useEffect(() => {
    const still =
      process.env.NODE_ENV === "test" ||
      typeof window === "undefined" ||
      !window.requestAnimationFrame ||
      window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    if (still || !Number.isFinite(value) || value === 0) return setShown(value);
    const start = performance.now();
    const whole = Number.isInteger(value);
    let frame = 0;
    const tick = (t) => {
      const k = Math.min(1, (t - start) / 900);
      const eased = 1 - Math.pow(1 - k, 3);
      const v = value * eased;
      setShown(whole ? Math.round(v) : Math.round(v * 10) / 10);
      if (k < 1) frame = requestAnimationFrame(tick);
    };
    setShown(0);
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [value]);
  return (
    <span className="tabular-nums">
      {shown.toLocaleString("en-GB")}
      {suffix}
    </span>
  );
}

export function ErrorState({ error }) {
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

export function Empty({ children }) {
  return <p className="py-6 text-center text-sm text-surface-400">{children}</p>;
}

const GATES = new Set(["validate", "review", "record"]);

/** The capability's workflow as a stepper; `current` is where the case stands. */
export function WorkflowStepper({ steps, pauseBefore = [], current }) {
  const at = current ? steps.indexOf(current) : -1;
  return (
    <ol className="flex flex-wrap items-center gap-1.5" aria-label="Workflow">
      {steps.map((s, i) => {
        const done = at >= 0 ? i < at : current === "__done__";
        const here = i === at;
        return (
          <li key={s} className="flex items-center gap-1.5">
            {pauseBefore.includes(s) && (
              <Pause size={11} className="text-surface-400" aria-label="pauses for a person" />
            )}
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

export function formatValue(v) {
  if (typeof v === "number") return v.toLocaleString("en-GB", { maximumFractionDigits: 2 });
  if (v === null || v === undefined) return "—";
  return String(v);
}

export function formatTime(iso) {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("en-GB", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" });
}

/** Where a case stands in its workflow, from its status. */
export function currentStep(status) {
  if (status === "awaiting_review") return "review";
  if (status === "awaiting_publish") return "publish";
  if (status === "completed") return "__done__";
  return null;
}
