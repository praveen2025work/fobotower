import { Cable, Lock } from "lucide-react";

import { usePlatform } from "../api/helix";
import StatusBadge from "../components/StatusBadge";
import { Card, ErrorState, Loading, PageHeader } from "../components/ui";

/** What the Agent One Finance team has onboarded: MCP connectors, their tool allow-list, and the core steps. */
export default function Connectors(): JSX.Element {
  const platform = usePlatform();
  return (
    <div>
      <PageHeader
        title="Connectors"
        subtitle="Bank systems onboarded by the Agent One Finance team as MCP servers. Capabilities may only use the tools listed here."
      />
      {platform.isLoading && <Loading what="connectors" />}
      {platform.error && <ErrorState error={platform.error} />}
      {platform.data && (
        <div className="space-y-4">
          <div className="grid gap-4 lg:grid-cols-2">
            {platform.data.connectors.map((c) => (
              <Card
                key={c.id}
                title={<span className="flex items-center gap-2"><Cable size={14} className="text-accent-600" /> {c.name}</span>}
                aside={<span className="font-mono text-[11px] text-surface-500">{c.id} · {c.transport} · {c.classification}</span>}
              >
                <ul className="divide-y divide-surface-100">
                  {c.tools.map((t) => (
                    <li key={t.name} className="flex flex-wrap items-center gap-2 py-2 text-sm">
                      <code className="text-xs font-medium">{t.name}</code>
                      <StatusBadge status={t.access} />
                      {t.scope && (
                        <span className="inline-flex items-center gap-1 text-[11px] text-surface-500">
                          <Lock size={10} /> scoped by {t.scope.arg} → {t.scope.key}
                        </span>
                      )}
                      <span className="w-full text-xs text-surface-500">{t.description}</span>
                    </li>
                  ))}
                </ul>
              </Card>
            ))}
          </div>
          <Card title="Core step library">
            <ul className="grid gap-2 text-sm sm:grid-cols-2 lg:grid-cols-3">
              {platform.data.steps.map((s) => (
                <li key={s.name} className="rounded-lg border border-surface-200 p-2.5">
                  <span className="font-medium">{s.name}</span>
                  {s.gate && <span className="ml-2 rounded bg-primary-50 px-1.5 py-0.5 text-[10px] font-medium text-primary-700">mandatory gate</span>}
                  <p className="text-xs text-surface-500">{s.label}</p>
                </li>
              ))}
            </ul>
          </Card>
        </div>
      )}
    </div>
  );
}
