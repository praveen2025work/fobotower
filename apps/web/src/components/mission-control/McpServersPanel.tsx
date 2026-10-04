import { Server } from "lucide-react";

import type { ConnectorHealth } from "../../api/missionControlApi";

function dotClass(status: string | undefined): string {
  switch (status) {
    case "up":
      return "bg-success-600";
    case "down":
      return "bg-danger-600";
    default:
      return "bg-surface-400";
  }
}

/**
 * aria-ai's compact MCP-servers panel, on Helix's live connector probes:
 * each onboarded connector is asked to list its tools; down means no answer.
 */
function McpServersPanel({ connectors, isLoading }: { connectors: ConnectorHealth[] | undefined; isLoading: boolean }): JSX.Element {
  const servers = connectors ?? [];
  return (
    <section data-testid="mcp-servers-panel" className="flex h-full flex-col rounded-lg border border-surface-200 bg-card">
      <header className="flex items-center justify-between border-b border-surface-100 px-3 py-2">
        <h3 className="text-xs font-semibold uppercase tracking-wide text-surface-700">MCP connectors</h3>
        <span className="font-mono text-[10px] text-surface-500">
          {isLoading ? "—" : `${servers.filter((s) => s.status === "up").length}/${servers.length} up`}
        </span>
      </header>
      <ul className="flex-1 overflow-y-auto">
        {servers.map((s) => (
          <li key={s.id} className="flex items-center gap-2 border-t border-surface-100 px-3 py-2 text-xs" data-testid="mcp-row" title={s.error ?? undefined}>
            <span aria-label={s.status} className={`inline-block h-2 w-2 shrink-0 rounded-full ${dotClass(s.status)}`} />
            <Server size={12} className="shrink-0 text-surface-400" />
            <span className="truncate font-medium text-surface-900">{s.name}</span>
            <span className="ml-auto shrink-0 font-mono text-[10px] text-surface-500">
              {s.status === "up" ? `${s.tools_served} tools · ${s.latency_ms} ms` : "down"}
            </span>
          </li>
        ))}
        {!isLoading && servers.length === 0 && (
          <li className="px-3 py-4 text-center text-xs text-surface-400">No connectors onboarded.</li>
        )}
      </ul>
    </section>
  );
}

export default McpServersPanel;
