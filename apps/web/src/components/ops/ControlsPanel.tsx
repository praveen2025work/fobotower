// Run-the-bank controls: off switches (capability, team group, connector) and
// the schedules in force. The server decides who may switch what.

import { useMemo, useState } from "react";
import clsx from "clsx";
import { CalendarClock, Power } from "lucide-react";

import { useCapabilities, usePlatform, useSchedules, useSetSwitch, useSwitches } from "../../api/helix";
import { ErrorState, formatTime } from "../ui";

export function SwitchesPanel() {
  const switches = useSwitches();
  const caps = useCapabilities();
  const platform = usePlatform();
  const set = useSetSwitch();
  const [kind, setKind] = useState<"capability" | "group" | "connector">("capability");
  const [target, setTarget] = useState("");
  const [reason, setReason] = useState("");

  const targets = useMemo(() => {
    if (kind === "connector") return (platform.data?.connectors ?? []).map((c) => c.id);
    if (kind === "group") return (caps.data ?? []).flatMap((c) => c.groups.map((g) => `${c.id}/${g.group}`));
    return (caps.data ?? []).map((c) => c.id);
  }, [kind, caps.data, platform.data]);

  const off = (switches.data ?? []).filter((s) => s.off);
  return (
    <section className="rounded-xl border border-surface-200 bg-card" aria-label="Off switches">
      <header className="flex items-center justify-between border-b border-surface-100 px-4 py-3">
        <h2 className="flex items-center gap-1.5 text-sm font-semibold text-surface-900"><Power size={14} /> Off switches</h2>
        <span className={clsx("text-xs", off.length ? "font-medium text-red-700" : "text-surface-500")}>{off.length} off</span>
      </header>
      <ul className="divide-y divide-surface-100">
        {(switches.data ?? []).map((s) => (
          <li key={`${s.kind}:${s.target}`} className="flex flex-wrap items-center gap-2 px-4 py-2 text-xs">
            <span className={clsx("rounded px-1.5 py-0.5 font-medium", s.off ? "bg-red-100 text-red-700" : "bg-green-100 text-green-700")}>
              {s.off ? "OFF" : "on"}
            </span>
            <span className="text-surface-500">{s.kind}</span>
            <code className="font-medium text-surface-800">{s.target}</code>
            <span className="min-w-0 flex-1 truncate text-surface-600" title={s.reason}>{s.reason}</span>
            <span className="text-surface-400">{s.set_by} · {formatTime(s.set_at)}</span>
            {s.can_switch && s.off && (
              <button onClick={() => set.mutate({ kind: s.kind, target: s.target, off: false, reason: "" })} className="text-primary-700 hover:underline">
                switch on
              </button>
            )}
          </li>
        ))}
        {switches.data?.length === 0 && <li className="px-4 py-3 text-xs text-surface-400">Everything is on.</li>}
      </ul>
      <div className="flex flex-wrap items-end gap-2 border-t border-surface-100 px-4 py-3 text-xs">
        <label className="text-surface-600">
          Kind
          <select aria-label="Switch kind" value={kind} onChange={(e) => { setKind(e.target.value as typeof kind); setTarget(""); }}
            className="mt-1 block rounded-md border border-surface-300 px-2 py-1">
            <option value="capability">capability</option>
            <option value="group">team group</option>
            <option value="connector">connector</option>
          </select>
        </label>
        <label className="text-surface-600">
          What
          <select aria-label="Switch target" value={target} onChange={(e) => setTarget(e.target.value)}
            className="mt-1 block max-w-[16rem] rounded-md border border-surface-300 px-2 py-1">
            <option value="">choose…</option>
            {targets.map((t) => <option key={t} value={t}>{t}</option>)}
          </select>
        </label>
        <label className="min-w-[10rem] flex-1 text-surface-600">
          Why
          <input aria-label="Switch reason" value={reason} onChange={(e) => setReason(e.target.value)} placeholder="e.g. GL outage INC-4411"
            className="mt-1 block w-full rounded-md border border-surface-300 px-2 py-1" />
        </label>
        <button
          disabled={!target || !reason.trim() || set.isPending}
          onClick={() => set.mutate({ kind, target, off: true, reason }, { onSuccess: () => setReason("") })}
          className="rounded-md bg-red-600 px-3 py-1.5 font-medium text-white hover:bg-red-700 disabled:opacity-50"
        >
          Switch off
        </button>
      </div>
      {set.error && <div className="px-4 pb-3"><ErrorState error={set.error} /></div>}
    </section>
  );
}

export function SchedulesPanel() {
  const schedules = useSchedules();
  return (
    <section className="rounded-xl border border-surface-200 bg-card" aria-label="Schedules">
      <header className="flex items-center justify-between border-b border-surface-100 px-4 py-3">
        <h2 className="flex items-center gap-1.5 text-sm font-semibold text-surface-900"><CalendarClock size={14} /> Schedules</h2>
        <span className="text-xs text-surface-500">{schedules.data?.length ?? 0}</span>
      </header>
      <ul className="divide-y divide-surface-100">
        {(schedules.data ?? []).map((s) => (
          <li key={`${s.capability_id}/${s.team_group ?? ""}`} className="px-4 py-2 text-xs">
            <div className="flex flex-wrap items-center gap-2">
              <code className="font-medium text-surface-800">{s.capability_id}{s.team_group ? ` / ${s.team_group}` : ""}</code>
              <span className="font-mono text-surface-600">{s.schedule}</span>
              <span className="text-surface-400">{s.timezone}</span>
              <span className="ml-auto text-surface-600">next {s.next_run ? formatTime(s.next_run) : "—"}</span>
            </div>
            <p className="mt-0.5 text-surface-500">{s.keys.length} case(s) each run, as {s.opens_as}</p>
          </li>
        ))}
        {schedules.data?.length === 0 && <li className="px-4 py-3 text-xs text-surface-400">No schedules you can see.</li>}
      </ul>
    </section>
  );
}
