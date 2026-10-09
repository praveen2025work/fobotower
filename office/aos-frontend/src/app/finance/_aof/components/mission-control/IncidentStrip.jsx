// Generated from apps/web/src/components/mission-control/IncidentStrip.tsx by apps/web/office/convert.mjs. Office changes to this file are
// kept by aof_sync.py on the next update; see docs/agent-one-finance/office/conversion-guide.md.
import clsx from "clsx";
import { useState } from "react";
import { AlertTriangle } from "lucide-react";
const STATUS_STRIPE = {
  error: "bg-red-600",
  degraded: "bg-orange-600",
  warning: "bg-orange-600",
};

function relativeFromMinutes(mins) {
  if (mins < 60) return `${mins}m`;
  const h = Math.floor(mins / 60);
  if (h < 24) return `${h}h`;
  return `${Math.floor(h / 24)}d`;
}

/**
 * Footer strip — last-24h incidents, horizontal scroll on overflow. Click
 * a chip to expand inline with affected agent + count + time-since.
 */
function IncidentStrip({ incidents, isLoading }) {
  const [expandedId, setExpandedId] = useState(null);

  if (isLoading && !incidents) {
    return (
      <section
        aria-label="Recent incidents"
        className="flex h-[72px] items-center gap-3 overflow-x-auto border-t border-surface-200 bg-card px-4"
      >
        {Array.from({ length: 4 }).map((_, i) => (
          <div
            key={i}
            data-testid="incident-skeleton"
            className="h-12 w-48 shrink-0 animate-pulse rounded-md bg-surface-100"
          />
        ))}
      </section>
    );
  }

  const list = incidents ?? [];
  if (list.length === 0) {
    return (
      <section
        aria-label="Recent incidents"
        className="flex h-[72px] items-center gap-3 border-t border-surface-200 bg-card px-4"
      >
        <span className="font-mono text-[11px] uppercase tracking-wider text-surface-500">
          No active incidents · last 24h
        </span>
      </section>
    );
  }

  return (
    <section
      aria-label="Recent incidents"
      className="flex h-[72px] items-stretch gap-3 overflow-x-auto border-t border-surface-200 bg-card px-4 py-3"
    >
      {list.map((incident) => {
        const stripe = STATUS_STRIPE[incident.status.toLowerCase()] ?? "bg-surface-400";
        const expanded = expandedId === incident.id;
        return (
          <button
            key={incident.id}
            type="button"
            onClick={() => setExpandedId(expanded ? null : incident.id)}
            data-testid="incident-chip"
            data-expanded={expanded ? "true" : "false"}
            aria-expanded={expanded}
            className={clsx(
              "flex h-full shrink-0 items-stretch overflow-hidden rounded-md border border-surface-200 bg-surface-50 text-left transition-colors hover:bg-surface-100",
              expanded ? "min-w-[24rem]" : "min-w-[14rem]",
            )}
          >
            <span className={clsx("w-1 shrink-0", stripe)} aria-hidden />
            <div className="flex min-w-0 flex-1 items-center gap-2 px-3">
              <AlertTriangle size={14} className="shrink-0 text-surface-500" />
              <div className="min-w-0 flex-1">
                <p className="truncate text-xs font-semibold text-surface-900">{incident.title}</p>
                <p className="truncate font-mono text-[11px] text-surface-500">
                  {incident.affecting} · {relativeFromMinutes(incident.sinceMinutes)} · {incident.count}×
                </p>
                {expanded && (
                  <p className="mt-1 truncate font-mono text-[11px] text-surface-700">status: {incident.status}</p>
                )}
              </div>
            </div>
          </button>
        );
      })}
    </section>
  );
}

export default IncidentStrip;
