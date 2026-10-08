// How urgent a case is: its deadline (manifest case.due) and its age, shown
// the same way wherever cases are listed.

import clsx from "clsx";
import { Clock } from "lucide-react";

import type { DueState } from "../api/aof";
import { formatTime } from "./ui";

export function relativeTo(at: string): string {
  const mins = Math.round((new Date(at).getTime() - Date.now()) / 60000);
  const abs = Math.abs(mins);
  const span = abs < 60 ? `${abs} min` : abs < 48 * 60 ? `${Math.round(abs / 60)} h` : `${Math.round(abs / 1440)} days`;
  return mins >= 0 ? `in ${span}` : `${span} ago`;
}

export function ageText(hours: number | undefined): string {
  if (hours == null) return "";
  if (hours < 1) return "new";
  if (hours < 48) return `${Math.round(hours)} h old`;
  return `${Math.round(hours / 24)} days old`;
}

/** "Due 01 Oct, 11:00 (in 3 h)" — red when overdue, orange when due soon. In lists
 *  (`compact`) it is coloured text only: a column of filled badges is noise. */
export function DueBadge({ dueAt, state, compact = false }: { dueAt?: string | null; state?: DueState; compact?: boolean }) {
  if (!dueAt || !state) return null;
  const cls = compact
    ? (state === "overdue" ? "px-0 text-red-700" : state === "due_soon" ? "px-0 text-orange-700" : "px-0 text-surface-500")
    : (state === "overdue" ? "bg-red-100 text-red-700" : state === "due_soon" ? "bg-orange-100 text-orange-800" : "bg-surface-100 text-surface-600");
  const word = state === "overdue" ? "Overdue" : "Due";
  return (
    <span className={clsx("inline-flex items-center gap-1 whitespace-nowrap rounded-md px-2 py-0.5 text-xs font-medium", cls)} title={formatTime(dueAt)}>
      <Clock size={11} />
      {compact ? `${word} ${relativeTo(dueAt)}` : `${word} ${formatTime(dueAt)} (${relativeTo(dueAt)})`}
    </span>
  );
}

/** Rank for "most urgent first": overdue, then due soonest, then oldest. */
export function urgency(r: { due_state?: DueState; due_at?: string | null; opened_at: string }): number {
  const due = r.due_at ? new Date(r.due_at).getTime() : Number.POSITIVE_INFINITY;
  const band = r.due_state === "overdue" ? 0 : r.due_state === "due_soon" ? 1 : r.due_at ? 2 : 3;
  return band * 1e15 + (Number.isFinite(due) ? due : new Date(r.opened_at).getTime());
}
