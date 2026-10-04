import { describe, it, expect } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import IncidentStrip from "../IncidentStrip";
import type { Incident } from "../../../api/missionControlApi";

const INCIDENTS: Incident[] = [
  {
    id: "inc_01",
    title: "MCP timeout: fobo-risk",
    affecting: "risk-monitoring-agent",
    sinceMinutes: 23,
    count: 2,
    status: "error",
  },
  {
    id: "inc_02",
    title: "P95 latency above SLO",
    affecting: "onboarding-agent",
    sinceMinutes: 90,
    count: 1,
    status: "degraded",
  },
];

describe("IncidentStrip", () => {
  it("renders skeletons while loading", () => {
    render(<IncidentStrip incidents={undefined} isLoading />);
    expect(screen.getAllByTestId("incident-skeleton").length).toBeGreaterThan(0);
  });

  it("renders an empty-state when there are no incidents", () => {
    render(<IncidentStrip incidents={[]} isLoading={false} />);
    expect(screen.getByText(/no active incidents/i)).toBeInTheDocument();
  });

  it("renders one chip per incident with relative time", () => {
    render(<IncidentStrip incidents={INCIDENTS} isLoading={false} />);
    const chips = screen.getAllByTestId("incident-chip");
    expect(chips).toHaveLength(2);
    // 90 mins → 1h relative formatter
    expect(screen.getByText(/onboarding-agent · 1h · 1×/)).toBeInTheDocument();
    expect(screen.getByText(/risk-monitoring-agent · 23m · 2×/)).toBeInTheDocument();
  });

  it("expands a chip when clicked and collapses on second click", () => {
    render(<IncidentStrip incidents={INCIDENTS} isLoading={false} />);
    const chips = screen.getAllByTestId("incident-chip");
    fireEvent.click(chips[0]);
    expect(chips[0]).toHaveAttribute("data-expanded", "true");
    fireEvent.click(chips[0]);
    expect(chips[0]).toHaveAttribute("data-expanded", "false");
  });
});
