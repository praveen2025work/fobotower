// Generated from apps/web/src/components/case/CaseHistory.tsx by apps/web/office/convert.mjs. Office changes to this file are
// kept by aof_sync.py on the next update; see docs/agent-one-finance/office/conversion-guide.md.
// The run, step by step — aria-ai's run history, from the case's LangGraph
// checkpoints: when each step ran and for how long, what it left behind, and
// where people came in. "As it was" opens the state at that point.

import { useState } from "react";
import clsx from "clsx";
import { CircleDot, Hourglass, Play, Square, Users } from "lucide-react";

import { api } from "../../api/client";
import { useHistory } from "../../api/aof";
import { Empty, ErrorState, Loading, formatTime } from "../ui";

const ICON = { start: Play, step: CircleDot, people: Users, waiting: Hourglass, end: Square };

function duration(e) {
  if (!e.ended_at) return "";
  const ms = new Date(e.ended_at).getTime() - new Date(e.at).getTime();
  return ms < 1000 ? `${ms} ms` : `${(ms / 1000).toFixed(1)} s`;
}

export default function CaseHistory({ caseId }) {
  const history = useHistory(caseId);
  const [state, setState] = useState(null);

  if (history.isLoading) return <Loading what="history" />;
  if (history.error) return <ErrorState error={history.error} />;
  const rows = history.data ?? [];
  if (rows.length === 0) return <Empty>The run has not started.</Empty>;

  const open = async (id) => {
    const body = await api.get(`/cases/${encodeURIComponent(caseId)}/history/${encodeURIComponent(id)}`);
    setState({ id, body });
  };

  return (
    <div className="space-y-3">
      <ol className="relative space-y-1 border-l border-surface-200 pl-4" aria-label="Run history">
        {rows.map((e) => {
          const Icon = ICON[e.event];
          return (
            <li key={e.checkpoint_id} className="relative">
              <span
                className={clsx(
                  "absolute -left-[22px] top-1 rounded-full bg-card p-0.5",
                  e.event === "people"
                    ? "text-primary-600"
                    : e.event === "waiting"
                      ? "text-orange-700"
                      : "text-surface-400",
                )}
              >
                <Icon size={12} />
              </span>
              <div className="flex flex-wrap items-baseline gap-x-3 text-sm">
                <span className={clsx("font-medium", e.event === "people" ? "text-primary-700" : "text-surface-800")}>
                  {e.event === "waiting" ? `waiting before ${e.step}` : e.step}
                </span>
                <span className="text-[11px] text-surface-500">{formatTime(e.at)}</span>
                {duration(e) && <span className="text-[11px] text-surface-500">{duration(e)}</span>}
                <span className="text-[11px] text-surface-400" title="what the run held after this step">
                  → {e.items} items · {e.groups} groups · {e.findings} findings
                </span>
                <button
                  onClick={() => void open(e.checkpoint_id)}
                  className="text-[11px] text-primary-700 hover:underline"
                >
                  as it was
                </button>
              </div>
            </li>
          );
        })}
      </ol>
      {state && (
        <div className="rounded-lg border border-surface-200">
          <div className="flex items-center justify-between border-b border-surface-100 px-3 py-2">
            <span className="text-xs font-medium text-surface-600">State at {state.id.slice(0, 8)}…</span>
            <button onClick={() => setState(null)} className="text-xs text-surface-500 hover:text-surface-800">
              close
            </button>
          </div>
          <pre className="max-h-80 overflow-auto bg-code-bg p-3 font-mono text-[11px] text-code-fg">
            {JSON.stringify(state.body, null, 1)}
          </pre>
        </div>
      )}
    </div>
  );
}
