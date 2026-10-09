// Generated from apps/web/src/components/mission-control/FleetTable.tsx by apps/web/office/convert.mjs. Office changes to this file are
// kept by aof_sync.py on the next update; see office/README.md.
import clsx from "clsx";
import { useNavigate } from "../../office/router";
import Sparkline from "./Sparkline";
const STATUS_DOT = {
  active: "bg-green-600",
  healthy: "bg-green-600",
  degraded: "bg-orange-600",
  error: "bg-red-600",
  paused: "bg-surface-400",
  inactive: "bg-surface-400",
};

function statusDotClass(status) {
  return STATUS_DOT[status.toLowerCase()] ?? "bg-surface-400";
}

function formatRelative(iso) {
  if (!iso) return "—";
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "—";
  const minutes = Math.max(0, Math.round((Date.now() - then) / 60_000));
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

function formatCost(value) {
  return value < 1 ? `$${value.toFixed(3)}` : `$${value.toFixed(2)}`;
}

function SkeletonRow() {
  return (
    <tr className="border-t border-surface-100">
      <td className="px-3 py-2.5">
        <div className="h-2.5 w-2.5 animate-pulse rounded-full bg-surface-200" />
      </td>
      <td className="px-3 py-2.5">
        <div className="h-3 w-32 animate-pulse rounded bg-surface-100" />
      </td>
      <td className="px-3 py-2.5">
        <div className="h-3 w-20 animate-pulse rounded bg-surface-100" />
      </td>
      <td className="px-3 py-2.5">
        <div className="h-6 w-24 animate-pulse rounded bg-surface-100" />
      </td>
      <td className="px-3 py-2.5 text-right">
        <div className="ml-auto h-3 w-12 animate-pulse rounded bg-surface-100" />
      </td>
    </tr>
  );
}

/**
 * From aria-ai's Mission Control, adapted for Agent One Finance: a "fleet" row is a
 * capability × team group, and a click opens that group (agent.href).
 *
 * Left column of the Mission Control grid — 6/12 cols, single source of
 * truth for "what are my agents doing right now". Click row → agent detail.
 */
function FleetTable({ agents, isLoading, isError, onRetry, emptyMessage }) {
  const navigate = useNavigate();

  return (
    <section
      aria-label="Capability fleet"
      className="flex h-full flex-col overflow-hidden rounded-xl border border-surface-200 bg-card"
    >
      <header className="flex items-center justify-between border-b border-surface-200 px-4 py-3">
        <h2 className="text-sm font-semibold text-surface-900">Fleet</h2>
        <span className="font-mono text-[11px] uppercase tracking-wider text-surface-500">
          {agents?.length ?? 0} groups
        </span>
      </header>

      {isError ? (
        <div className="flex flex-1 flex-col items-center justify-center gap-3 p-6 text-center">
          <p className="text-sm text-red-700">Failed to load fleet status.</p>
          {onRetry && (
            <button
              type="button"
              onClick={onRetry}
              className="rounded-md border border-surface-200 px-3 py-1.5 text-xs font-medium text-surface-700 hover:bg-surface-50"
            >
              Retry
            </button>
          )}
        </div>
      ) : (
        <div className="flex-1 overflow-auto">
          <table className="w-full min-w-[30rem] text-sm">
            <thead className="bg-surface-50 text-[11px] uppercase tracking-wider text-surface-500">
              <tr>
                <th className="w-6 px-3 py-2 text-left font-medium" />
                <th className="px-3 py-2 text-left font-medium">Group</th>
                <th className="px-3 py-2 text-left font-medium">Last run</th>
                <th className="px-3 py-2 text-left font-medium">24h</th>
                <th className="px-3 py-2 text-right font-medium">Cost · 24h</th>
              </tr>
            </thead>
            <tbody>
              {isLoading && !agents
                ? Array.from({ length: 5 }).map((_, i) => <SkeletonRow key={i} />)
                : (agents ?? []).map((agent) => (
                    <tr
                      key={`${agent.team}/${agent.name}`}
                      onClick={() => navigate(agent.href ?? "/capabilities")}
                      className="cursor-pointer border-t border-surface-100 transition-colors hover:bg-surface-50"
                      data-testid="fleet-row"
                    >
                      <td className="px-3 py-2.5">
                        <span
                          aria-label={agent.status}
                          data-testid="fleet-status-dot"
                          className={clsx("inline-block h-2 w-2 rounded-full", statusDotClass(agent.status))}
                        />
                      </td>
                      <td className="px-3 py-2.5">
                        <div className="font-medium text-surface-900">{agent.name}</div>
                        <div className="text-[11px] text-surface-500">
                          {agent.team} · {agent.env}
                        </div>
                      </td>
                      <td className="px-3 py-2.5 font-mono text-xs text-surface-600">
                        {formatRelative(agent.lastRunAt)}
                      </td>
                      <td className="px-3 py-2.5">
                        <Sparkline values={agent.sparkline} />
                      </td>
                      <td className="px-3 py-2.5 text-right font-mono text-xs tabular-nums text-surface-700">
                        {formatCost(agent.cost24)}
                      </td>
                    </tr>
                  ))}
              {!isLoading && agents && agents.length === 0 && (
                <tr>
                  <td colSpan={5} className="p-6 text-center text-sm text-surface-500">
                    {emptyMessage ?? "No cases in your scope yet."}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

export default FleetTable;
