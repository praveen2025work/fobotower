import { screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";

import { mockApi, renderAt } from "../../test/render";
import Operations from "../Operations";

afterEach(() => vi.unstubAllGlobals());

it("shows platform health, connector probes, the fleet and incidents for run-the-bank", async () => {
  mockApi({
    "GET /operations": {
      health: { status: "healthy", database: "connected", llm: "agent-sdk", tracing: "phoenix", entitlement: "central" },
      connectors: [
        { id: "cats", name: "CATS", transport: "http", classification: "confidential", status: "up", error: null, tools_allowed: 1, tools_served: 1, latency_ms: 12 },
        { id: "motif", name: "MOTIF", transport: "http", classification: "confidential", status: "down", error: "ConnectError", tools_allowed: 2, tools_served: 0, latency_ms: 3000 },
      ],
      kpi: { cost24: 1.25, cost24Delta: 10, runs24: 7, runs24Delta: 0, p95: 0.4, p95Delta: -5, pendingApprovals: 2, pendingDelta: 0, errors24: 1, errors24Delta: 0 },
      fleet: [{ name: "CATS vs MOTIF (FOBO)", team: "Reconciliation investigation", env: "cats-motif", status: "degraded", runs24: 7, errs24: 1, p95: 0.4, tokens24: 9000, cost24: 1.25, sparkline: Array(24).fill(1), lastRunAt: null, href: "/capabilities/recon.investigation/groups/cats-motif" }],
      incidents: [{ id: "error-motif.positions", title: "Connector errors from motif.positions", affecting: "motif", sinceMinutes: 12, count: 3, status: "error" }],
      tail: [{ id: "t1", ts: "2026-10-04T10:00:00Z", level: "warn", source: "llm", message: "ledger.postings refused: not allowed" }],
    },
    "GET /inbox": [],
  });
  renderAt("/operations", "/operations", <Operations />);
  expect(await screen.findByText(/Platform Healthy/)).toBeInTheDocument();
  expect(screen.getByText("LLM: agent-sdk")).toBeInTheDocument();
  expect(screen.getByText("1/2 up")).toBeInTheDocument();
  expect(screen.getByText("CATS vs MOTIF (FOBO)")).toBeInTheDocument();
  expect(screen.getByText(/Connector errors from motif.positions/)).toBeInTheDocument();
  expect(screen.getByText(/ledger.postings refused/)).toBeInTheDocument();
});
