import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import ScanningStrip from "../ScanningStrip";
import type { KpiSummary } from "../../../api/missionControlApi";

const KPI: KpiSummary = {
  cost24: 1.508,
  cost24Delta: -4.2,
  runs24: 19,
  runs24Delta: 6.0,
  p95: 41.2,
  p95Delta: 1.2,
  pendingApprovals: 3,
  pendingDelta: 0,
  errors24: 2,
  errors24Delta: 12.5,
};

describe("ScanningStrip", () => {
  it("renders skeleton tiles when loading", () => {
    render(<ScanningStrip data={undefined} isLoading />);
    expect(screen.getAllByTestId("scanning-strip-skeleton").length).toBeGreaterThan(0);
  });

  it("renders all five KPI labels with their numeric values", () => {
    render(<ScanningStrip data={KPI} isLoading={false} />);
    expect(screen.getByText("Cost · 24h")).toBeInTheDocument();
    expect(screen.getByText("Runs · 24h")).toBeInTheDocument();
    expect(screen.getByText("P95 latency")).toBeInTheDocument();
    expect(screen.getByText("Approvals")).toBeInTheDocument();
    expect(screen.getByText("Errors · 24h")).toBeInTheDocument();
    expect(screen.getByText("$1.51")).toBeInTheDocument();
    expect(screen.getByText("19")).toBeInTheDocument();
    expect(screen.getByText("3")).toBeInTheDocument();
    expect(screen.getByText("2")).toBeInTheDocument();
  });

  it("formats P95 over a minute as minutes", () => {
    render(<ScanningStrip data={{ ...KPI, p95: 75 }} isLoading={false} />);
    expect(screen.getByText("1.3m")).toBeInTheDocument();
  });
});
