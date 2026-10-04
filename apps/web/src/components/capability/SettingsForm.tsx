// Everyday settings as a form, for owners who would rather not edit YAML:
// policy thresholds, reviewers, schedule, deadline and review controls.
// It shows only what the owner may change (a group: its capability's
// `configurable` paths), and submits a draft — another owner approves it,
// exactly as with a YAML change.

import { useMemo, useState } from "react";
import { Save, SlidersHorizontal } from "lucide-react";

import { Card, ErrorState } from "../ui";

type Json = Record<string, unknown>;
export type Changes = Record<string, unknown>; // dotted path -> new value

const FLAGS = [
  { id: "confirmation", label: "Verdicts that need confirmation" },
  { id: "judgement", label: "Judgement calls" },
  { id: "escalated", label: "Escalated groups" },
  { id: "model", label: "Anything the model proposed" },
] as const;

function get(obj: unknown, path: string): unknown {
  return path.split(".").reduce<unknown>((o, k) => (o && typeof o === "object" ? (o as Json)[k] : undefined), obj);
}

/** A copy of obj with value at a dotted path (objects on the way are copied, not mutated). */
export function setPath(obj: Json, path: string, value: unknown): Json {
  const [head, ...rest] = path.split(".");
  const out = { ...obj };
  out[head] = rest.length ? setPath(((obj[head] as Json) ?? {}) as Json, rest.join("."), value) : value;
  return out;
}

export function allowed(configurable: string[] | null, path: string): boolean {
  if (configurable === null) return true;
  return configurable.some(
    (c) => c === path || path.startsWith(`${c}.`) || (c.endsWith(".*") && path.startsWith(c.slice(0, -1))),
  );
}

const CRON_HINT: Record<string, string> = {
  "30 6 * * 1-5": "06:30 every business day",
  "15 7 * * 1-5": "07:15 every business day",
  "0 9 3 * *": "09:00 on the 3rd of each month",
};

export default function SettingsForm({
  manifest,
  configurable,
  onSubmit,
  pending,
  error,
  done,
}: {
  manifest: Json;
  /** Paths this owner may set; null = everything (a capability's own owners). */
  configurable: string[] | null;
  onSubmit: (changes: Changes, note: string) => void;
  pending: boolean;
  error: unknown;
  done: string | null;
}) {
  const policy = (manifest.policy ?? {}) as Record<string, { value: unknown; unit?: string | null }>;
  const initial = useMemo(() => {
    const due = (get(manifest, "case.due") ?? null) as Json | null;
    return {
      policy: Object.fromEntries(Object.entries(policy).map(([k, v]) => [k, v.value === null || v.value === undefined ? "" : String(v.value)])),
      roles: ((get(manifest, "review.roles") as string[]) ?? []).join(", "),
      schedule: (get(manifest, "case.schedule") as string) ?? "",
      dueDays: due ? String(due.business_days ?? 0) : "",
      dueAt: due ? String(due.at ?? "") : "",
      bulk: (get(manifest, "review.bulk_exclude") as string[]) ?? ["confirmation", "judgement"],
      delegation: Boolean(get(manifest, "review.allow_delegation")),
    };
  }, [manifest]); // eslint-disable-line react-hooks/exhaustive-deps
  const [v, setV] = useState(initial);
  const [note, setNote] = useState("");

  const can = (p: string) => allowed(configurable, p);
  const showPolicy = Object.keys(policy).length > 0 && Object.keys(policy).some((k) => can(`policy.${k}`));
  const opensOnSchedule = get(manifest, "case.opens_on") === "schedule";

  const changes = (): Changes => {
    const out: Changes = {};
    for (const [k, raw] of Object.entries(v.policy)) {
      if (raw === initial.policy[k] || !can(`policy.${k}`)) continue;
      const num = Number(raw);
      out[`policy.${k}`] = { ...policy[k], value: raw.trim() === "" ? null : Number.isFinite(num) && raw.trim() !== "" ? num : raw };
    }
    if (v.roles !== initial.roles && can("review.roles")) out["review.roles"] = v.roles.split(",").map((r) => r.trim()).filter(Boolean);
    if (v.schedule !== initial.schedule && can("case.schedule")) out["case.schedule"] = v.schedule.trim() || null;
    if ((v.dueDays !== initial.dueDays || v.dueAt !== initial.dueAt) && can("case.due")) {
      const current = (get(manifest, "case.due") ?? {}) as Json;
      out["case.due"] = v.dueDays === "" && v.dueAt === "" ? null : { ...current, business_days: Number(v.dueDays || 0), at: v.dueAt || null };
    }
    if (v.bulk.join() !== initial.bulk.join() && can("review.bulk_exclude")) out["review.bulk_exclude"] = v.bulk;
    if (v.delegation !== initial.delegation && can("review.allow_delegation")) out["review.allow_delegation"] = v.delegation;
    return out;
  };
  const pendingChanges = changes();
  const count = Object.keys(pendingChanges).length;

  return (
    <Card title={<span className="flex items-center gap-2"><SlidersHorizontal size={14} /> Settings</span>}>
      <form
        className="space-y-4 text-sm"
        onSubmit={(e) => {
          e.preventDefault();
          onSubmit(pendingChanges, note);
        }}
      >
        {showPolicy && (
          <fieldset>
            <legend className="text-xs font-semibold uppercase tracking-wider text-surface-500">Thresholds</legend>
            <p className="mt-0.5 text-[11px] text-surface-500">Leave empty for “not confirmed yet”: verdicts that depend on it are flagged for confirmation.</p>
            <div className="mt-2 grid gap-2 sm:grid-cols-2">
              {Object.entries(policy).filter(([k]) => can(`policy.${k}`)).map(([k, p]) => (
                <label key={k} className="text-xs font-medium text-surface-600">
                  {k.replace(/_/g, " ")}{p.unit ? ` (${p.unit})` : ""}
                  <input
                    id={`policy-${k}`}
                    value={v.policy[k]}
                    placeholder="not confirmed"
                    onChange={(e) => setV({ ...v, policy: { ...v.policy, [k]: e.target.value } })}
                    className="mt-1 block w-full rounded-lg border border-surface-300 px-2 py-1.5 text-sm font-normal tabular-nums"
                  />
                </label>
              ))}
            </div>
          </fieldset>
        )}

        {can("review.roles") && (
          <label className="block text-xs font-medium text-surface-600">
            Reviewers (roles, comma-separated)
            <input id="review-roles" value={v.roles} onChange={(e) => setV({ ...v, roles: e.target.value })} className="mt-1 block w-full rounded-lg border border-surface-300 px-2 py-1.5 text-sm font-normal" />
          </label>
        )}

        {opensOnSchedule && can("case.schedule") && (
          <label className="block text-xs font-medium text-surface-600">
            Schedule (cron: minute hour day month weekday)
            <input id="case-schedule" value={v.schedule} onChange={(e) => setV({ ...v, schedule: e.target.value })} className="mt-1 block w-full rounded-lg border border-surface-300 px-2 py-1.5 font-mono text-sm font-normal" />
            {CRON_HINT[v.schedule.trim()] && <span className="mt-0.5 block text-[11px] font-normal text-surface-500">{CRON_HINT[v.schedule.trim()]}</span>}
          </label>
        )}

        {can("case.due") && (
          <fieldset>
            <legend className="text-xs font-semibold uppercase tracking-wider text-surface-500">Deadline</legend>
            <div className="mt-1 flex flex-wrap gap-2">
              <label className="text-xs font-medium text-surface-600">
                Business days after {String(get(manifest, "case.due.from") ?? "opening")}
                <input id="due-days" type="number" min={0} max={60} value={v.dueDays} onChange={(e) => setV({ ...v, dueDays: e.target.value })} className="mt-1 block w-28 rounded-lg border border-surface-300 px-2 py-1.5 text-sm font-normal" />
              </label>
              <label className="text-xs font-medium text-surface-600">
                At (HH:MM)
                <input id="due-at" type="time" value={v.dueAt} onChange={(e) => setV({ ...v, dueAt: e.target.value })} className="mt-1 block rounded-lg border border-surface-300 px-2 py-1.5 text-sm font-normal" />
              </label>
            </div>
          </fieldset>
        )}

        {can("review.bulk_exclude") && (
          <fieldset>
            <legend className="text-xs font-semibold uppercase tracking-wider text-surface-500">“Approve all” leaves for one-by-one review</legend>
            <div className="mt-1 grid gap-1 sm:grid-cols-2">
              {FLAGS.map((f) => (
                <label key={f.id} className="flex items-center gap-2 text-xs text-surface-700">
                  <input
                    type="checkbox"
                    checked={v.bulk.includes(f.id)}
                    onChange={(e) => setV({ ...v, bulk: e.target.checked ? [...v.bulk, f.id] : v.bulk.filter((x) => x !== f.id) })}
                  />
                  {f.label}
                </label>
              ))}
            </div>
          </fieldset>
        )}

        {can("review.allow_delegation") && (
          <label className="flex items-center gap-2 text-xs text-surface-700">
            <input type="checkbox" checked={v.delegation} onChange={(e) => setV({ ...v, delegation: e.target.checked })} />
            Reviewers may hand their reviews to a colleague while away
          </label>
        )}

        <div className="flex flex-wrap items-end gap-2 border-t border-surface-100 pt-3">
          <label className="min-w-[12rem] flex-1 text-xs font-medium text-surface-600">
            Note for the approver
            <input id="settings-note" value={note} onChange={(e) => setNote(e.target.value)} className="mt-1 block w-full rounded-lg border border-surface-300 px-2 py-1.5 text-sm font-normal" />
          </label>
          <button type="submit" disabled={pending || count === 0} className="inline-flex items-center gap-2 rounded-lg bg-brand px-4 py-2 text-sm font-medium text-brand-fg hover:bg-brand-strong disabled:opacity-50">
            <Save size={14} /> Submit settings for approval{count > 0 ? ` (${count} change${count > 1 ? "s" : ""})` : ""}
          </button>
        </div>
        {!!error && <ErrorState error={error} />}
        {done && <p className="text-sm text-green-700">{done}</p>}
      </form>
    </Card>
  );
}
