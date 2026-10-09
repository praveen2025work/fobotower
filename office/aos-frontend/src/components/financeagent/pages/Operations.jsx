// Generated from apps/web/src/pages/Operations.tsx by apps/web/office/convert.mjs. Office changes to this file are
// kept by aof_sync.py on the next update; see docs/agent-one-finance/office/conversion-guide.md.
// Run-the-bank: aria-ai's Mission Control, on Agent One Finance. The components are
// aria-ai's (components/mission-control); the data is Agent One Finance's /api/operations,
// scoped to what the signed-in user may see.

import { Link } from "../office/router";

import { currentUser } from "../api/client";
import { useInbox, useMe } from "../api/aof";
import { useOperations } from "../api/missionControlApi";
import FleetTable from "../components/mission-control/FleetTable";
import HealthBanner from "../components/mission-control/HealthBanner";
import IncidentStrip from "../components/mission-control/IncidentStrip";
import LiveTail from "../components/mission-control/LiveTail";
import McpServersPanel from "../components/mission-control/McpServersPanel";
import ScanningStrip from "../components/mission-control/ScanningStrip";
import { SchedulesPanel, SwitchesPanel } from "../components/ops/ControlsPanel";
import SupportGuide from "../components/ops/SupportGuide";
import StatusBadge from "../components/StatusBadge";
import { ErrorState } from "../components/ui";

export default function Operations() {
  const ops = useOperations();
  const inbox = useInbox();
  const me = useMe(currentUser());
  // Platform support holds no data scope: say why case panels are empty.
  const support = !!me.data?.is_admin && Object.keys(me.data?.data_scopes ?? {}).length === 0;

  return (
    <div className="-m-3 flex min-h-[calc(100vh-3.5rem)] flex-col sm:-m-4 lg:-m-6">
      <HealthBanner health={ops.data?.health} />
      <ScanningStrip data={ops.data?.kpi} isLoading={ops.isLoading} />
      {ops.error && (
        <div className="p-4">
          <ErrorState error={ops.error} />
        </div>
      )}

      <div className="grid flex-1 grid-cols-12 gap-3 p-3 sm:gap-4 sm:p-4">
        {support ? (
          <div className="col-span-12 lg:col-span-9">
            <SupportGuide what="Cases, reviews and their run figures" className="h-full" />
          </div>
        ) : (
          <>
            <div className="col-span-12 lg:col-span-6">
              <FleetTable
                agents={ops.data?.fleet}
                isLoading={ops.isLoading}
                isError={ops.isError}
                onRetry={() => ops.refetch()}
              />
            </div>
            <div className="col-span-12 lg:col-span-3">
              <section className="flex h-full flex-col rounded-xl border border-surface-200 bg-card">
                <header className="flex items-center justify-between border-b border-surface-100 px-4 py-3">
                  <h2 className="text-sm font-semibold text-surface-900">Waiting on people</h2>
                  <span className="text-xs text-surface-500">{inbox.data?.length ?? 0}</span>
                </header>
                <ul className="flex-1 divide-y divide-surface-100 overflow-y-auto">
                  {(inbox.data ?? []).map((r) => (
                    <li key={r.case_id} className="px-4 py-2.5">
                      <Link
                        to={`/cases/${encodeURIComponent(r.case_id)}`}
                        className="text-sm font-medium text-primary-700 hover:underline"
                      >
                        {r.subject}
                      </Link>
                      <div className="mt-0.5 flex items-center gap-2 text-[11px] text-surface-500">
                        <StatusBadge status={r.action} /> {r.capability_name}
                      </div>
                    </li>
                  ))}
                  {inbox.data?.length === 0 && (
                    <li className="px-4 py-6 text-center text-xs text-surface-400">Nothing waiting on you.</li>
                  )}
                </ul>
              </section>
            </div>
          </>
        )}
        <div className="col-span-12 flex flex-col gap-3 lg:col-span-3">
          <div className="min-h-64 flex-1">
            <LiveTail feed={ops.data?.tail ?? []} subscribe={false} />
          </div>
          <div className="h-60">
            <McpServersPanel connectors={ops.data?.connectors} isLoading={ops.isLoading} />
          </div>
        </div>
      </div>

      <div className="grid grid-cols-12 gap-3 px-3 pb-4 sm:gap-4 sm:px-4">
        <div className="col-span-12 lg:col-span-7">
          <SwitchesPanel />
        </div>
        <div className="col-span-12 lg:col-span-5">
          <SchedulesPanel
            emptyMessage={
              support
                ? "Schedules belong to the business teams' capabilities; none are visible to platform support."
                : undefined
            }
          />
        </div>
      </div>

      <IncidentStrip incidents={ops.data?.incidents} isLoading={ops.isLoading} />
    </div>
  );
}
