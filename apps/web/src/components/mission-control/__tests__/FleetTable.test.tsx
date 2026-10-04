// From aria-ai (platform-ui/src/components/mission-control/__tests__); two cases
// updated for the Helix adaptation (empty-state wording, row link).
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import FleetTable from "../FleetTable";
import type { FleetAgent } from "../../../api/missionControlApi";

const navigateMock = vi.fn();

vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual<typeof import("react-router-dom")>(
    "react-router-dom",
  );
  return { ...actual, useNavigate: () => navigateMock };
});

const SPARK = Array.from({ length: 24 }, (_, i) => 0.9 - (i % 5) * 0.05);

const AGENTS: FleetAgent[] = [
  {
    name: "pnl-producer-agent",
    team: "Finance",
    env: "prod",
    status: "active",
    runs24: 6,
    errs24: 0,
    p95: 13.6,
    tokens24: 105_832,
    cost24: 0.53,
    sparkline: SPARK,
    lastRunAt: new Date(Date.now() - 60_000).toISOString(),
  },
  {
    name: "risk-monitoring-agent",
    team: "Risk",
    env: "uat",
    status: "degraded",
    runs24: 3,
    errs24: 2,
    p95: 6.2,
    tokens24: 11_440,
    cost24: 0.057,
    sparkline: SPARK,
    lastRunAt: null,
  },
];

function renderTable(agents: FleetAgent[] | undefined, opts: { isLoading?: boolean; isError?: boolean } = {}) {
  return render(
    <MemoryRouter>
      <FleetTable
        agents={agents}
        isLoading={opts.isLoading ?? false}
        isError={opts.isError}
        onRetry={() => {}}
      />
    </MemoryRouter>,
  );
}

describe("FleetTable", () => {
  it("renders one row per agent with the correct status dot", () => {
    renderTable(AGENTS);
    const rows = screen.getAllByTestId("fleet-row");
    expect(rows).toHaveLength(2);
    const dots = screen.getAllByTestId("fleet-status-dot");
    expect(dots[0].className).toContain("bg-green-600");
    expect(dots[1].className).toContain("bg-orange-600");
  });

  it("shows skeleton rows when loading and no data is present", () => {
    renderTable(undefined, { isLoading: true });
    expect(screen.queryByTestId("fleet-row")).not.toBeInTheDocument();
  });

  it("shows the empty-state message when no agents are returned", () => {
    renderTable([]);
    // Helix wording: a fleet row is a capability × team group in the user's scope
    expect(screen.getByText(/no cases in your scope/i)).toBeInTheDocument();
  });

  it("renders error state and retry button when isError is true", () => {
    renderTable(undefined, { isError: true });
    expect(screen.getByText(/failed to load/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /retry/i })).toBeInTheDocument();
  });

  it("navigates to the row's capability or group when clicked", () => {
    navigateMock.mockClear();
    renderTable([{ ...AGENTS[0], href: "/capabilities/recon.investigation/groups/cats-motif" }, AGENTS[1]]);
    fireEvent.click(screen.getAllByTestId("fleet-row")[0]);
    expect(navigateMock).toHaveBeenCalledWith("/capabilities/recon.investigation/groups/cats-motif");
  });

  it("renders an em dash when lastRunAt is null", () => {
    renderTable([{ ...AGENTS[1] }]);
    expect(screen.getByText("—")).toBeInTheDocument();
  });
});
