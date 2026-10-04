import KpiTile from "./KpiTile";
import type { KpiSummary } from "../../api/missionControlApi";

interface ScanningStripProps {
  data: KpiSummary | undefined;
  isLoading: boolean;
}

function formatCurrency(value: number): string {
  return value < 1 ? `$${value.toFixed(3)}` : `$${value.toFixed(2)}`;
}

function formatSeconds(value: number): string {
  if (value >= 60) return `${(value / 60).toFixed(1)}m`;
  return `${value.toFixed(1)}s`;
}

function PlaceholderTile({ label }: { label: string }) {
  return (
    <div className="flex min-w-[112px] shrink-0 flex-col justify-center px-3 sm:px-4">
      <span className="text-[11px] font-medium uppercase tracking-wider text-surface-500">
        {label}
      </span>
      <div
        className="mt-2 h-5 w-16 animate-pulse rounded bg-surface-100"
        data-testid="scanning-strip-skeleton"
      />
    </div>
  );
}

/**
 * 64px tall horizontal KPI ticker. Five slots: cost-24h, runs-24h, p95
 * latency, pending approvals, errors-24h.
 */
function ScanningStrip({ data, isLoading }: ScanningStripProps) {
  if (isLoading || !data) {
    return (
      <section
        aria-label="KPI summary"
        className="flex h-16 items-stretch divide-x divide-surface-200 overflow-x-auto border-b border-surface-200 bg-card"
      >
        <PlaceholderTile label="Cost · 24h" />
        <PlaceholderTile label="Runs · 24h" />
        <PlaceholderTile label="P95 latency" />
        <PlaceholderTile label="Approvals" />
        <PlaceholderTile label="Errors · 24h" />
      </section>
    );
  }

  return (
    <section
      aria-label="KPI summary"
      className="flex h-16 items-stretch divide-x divide-surface-200 overflow-x-auto border-b border-surface-200 bg-card"
    >
      <KpiTile
        label="Cost · 24h"
        value={formatCurrency(data.cost24)}
        delta={data.cost24Delta}
        goodDirection="down"
      />
      <KpiTile
        label="Runs · 24h"
        value={String(data.runs24)}
        delta={data.runs24Delta}
        goodDirection="up"
      />
      <KpiTile
        label="P95 latency"
        value={formatSeconds(data.p95)}
        delta={data.p95Delta}
        goodDirection="down"
      />
      <KpiTile
        label="Approvals"
        value={String(data.pendingApprovals)}
        delta={data.pendingDelta}
        goodDirection="down"
      />
      <KpiTile
        label="Errors · 24h"
        value={String(data.errors24)}
        delta={data.errors24Delta}
        goodDirection="down"
      />
    </section>
  );
}

export default ScanningStrip;
