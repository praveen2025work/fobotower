// Trial runs: try a version (a draft, or the live one after a model change) on
// people's past decisions, in hidden shadow cases, and see how often it agrees.

import { useState } from "react";

import { useEvals, useStartEval, type EvalRunRow } from "../../api/aof";
import StatusBadge from "../StatusBadge";
import { Empty, ErrorState, formatTime } from "../ui";

const pct = (v: number | null) => (v == null ? "—" : `${Math.round(v * 100)}%`);

function Summary({ r }: { r: EvalRunRow }) {
  const s = r.summary;
  if (!s || s.cases === undefined) return null;
  return (
    <span className="flex flex-wrap gap-x-3 text-xs text-surface-600">
      <span>{s.cases} cases · {s.groups_compared} groups</span>
      <span className="font-medium text-surface-900">agree {pct(s.agreement_rate)}</span>
      {s.verdict_match_rate != null && <span>verdict {pct(s.verdict_match_rate)}</span>}
      <span>wording {pct(s.wording_mean)}</span>
      <span>{s.escalated} escalated · {s.disagree} disagree · {s.missing} missing · {s.new} new</span>
      <span>${s.cost_usd.toFixed(2)}</span>
    </span>
  );
}

export default function EvalsPanel({ capabilityId, versions, groups }: {
  capabilityId: string;
  versions: number[];
  groups: string[];
}) {
  const runs = useEvals(capabilityId);
  const start = useStartEval(capabilityId);
  const [version, setVersion] = useState<number | "">("");
  const [group, setGroup] = useState<string>(groups[0] ?? "");
  return (
    <div className="space-y-3">
      <p className="text-xs text-surface-500">
        Each past case people settled is replayed, hidden, on the version you choose — through the same tools, never
        writing anything — and its findings are compared with what people decided. Scores are also in Phoenix.
      </p>
      <div className="flex flex-wrap items-end gap-2 text-xs">
        <label className="text-surface-600">
          Version
          <select aria-label="Eval version" value={version} onChange={(e) => setVersion(e.target.value ? Number(e.target.value) : "")}
            className="mt-1 block rounded-md border border-surface-300 px-2 py-1">
            <option value="">live</option>
            {versions.map((v) => <option key={v} value={v}>v{v}</option>)}
          </select>
        </label>
        {groups.length > 0 && (
          <label className="text-surface-600">
            Group
            <select aria-label="Eval group" value={group} onChange={(e) => setGroup(e.target.value)}
              className="mt-1 block rounded-md border border-surface-300 px-2 py-1">
              {groups.map((g) => <option key={g} value={g}>{g}</option>)}
            </select>
          </label>
        )}
        <button
          disabled={start.isPending}
          onClick={() => start.mutate({ version: version === "" ? undefined : version, team_group: groups.length ? group : null })}
          className="rounded-lg bg-brand px-3 py-1.5 font-medium text-brand-fg hover:bg-brand-strong disabled:opacity-50"
        >
          Run eval
        </button>
      </div>
      {start.error && <ErrorState error={start.error} />}
      {runs.error && <ErrorState error={runs.error} />}
      {runs.data?.length === 0 && <Empty>No eval runs yet.</Empty>}
      <ul className="divide-y divide-surface-100 rounded-lg border border-surface-200" aria-label="Eval runs">
        {(runs.data ?? []).map((r) => (
          <li key={r.run_id} className="space-y-1 px-3 py-2">
            <div className="flex flex-wrap items-center gap-2 text-xs">
              <StatusBadge status={r.status} />
              <span className="font-mono">v{r.version}{r.team_group ? ` · ${r.team_group} v${r.group_version}` : ""}</span>
              <span className="text-surface-500">by {r.started_by} {formatTime(r.started_at)}</span>
            </div>
            <Summary r={r} />
            {r.error && <p className="text-xs text-red-700">{r.error}</p>}
          </li>
        ))}
      </ul>
    </div>
  );
}
