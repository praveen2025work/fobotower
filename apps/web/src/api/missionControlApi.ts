// aria-ai's Mission Control types, kept with the same shapes so its components
// (components/mission-control/*) are reused unchanged — fed by Agent One Finance's one
// /api/operations endpoint instead of aria-ai's seven.

import { useQuery } from "@tanstack/react-query";

import { api } from "./client";

export interface FleetAgent {
  name: string;
  team: string;
  env: string;
  /** active | degraded | error | paused */
  status: string;
  runs24: number;
  errs24: number;
  /** seconds */
  p95: number;
  tokens24: number;
  cost24: number;
  /** 24 hourly success-rate points 0..1, oldest → newest */
  sparkline: number[];
  lastRunAt: string | null;
  /** Agent One Finance: where a click on the row goes (the capability or team group). */
  href?: string;
}

export interface Incident {
  id: string;
  title: string;
  affecting: string;
  /** Minutes since first occurrence. */
  sinceMinutes: number;
  count: number;
  /** error | degraded */
  status: string;
}

export interface KpiSummary {
  cost24: number;
  cost24Delta: number;
  runs24: number;
  runs24Delta: number;
  /** seconds */
  p95: number;
  p95Delta: number;
  pendingApprovals: number;
  pendingDelta: number;
  errors24: number;
  errors24Delta: number;
}

export interface ConnectorHealth {
  id: string;
  name: string;
  transport: string;
  classification: string;
  status: "up" | "down";
  error: string | null;
  tools_allowed: number;
  tools_served: number;
  latency_ms: number;
}

export interface Operations {
  health: { status: string; database: string; llm: string; tracing: string; entitlement: string };
  connectors: ConnectorHealth[];
  kpi: KpiSummary;
  fleet: FleetAgent[];
  incidents: Incident[];
  tail: { id: string; ts: string; level: string; source: string; message: string }[];
}

export function useOperations() {
  return useQuery({
    queryKey: ["operations"],
    queryFn: () => api.get<Operations>("/operations"),
    refetchInterval: 15_000,
  });
}
