import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import KpiTile from "../KpiTile";

describe("KpiTile", () => {
  it("renders label and value", () => {
    render(<KpiTile label="Cost · 24h" value="$1.20" />);
    expect(screen.getByText("Cost · 24h")).toBeInTheDocument();
    expect(screen.getByText("$1.20")).toBeInTheDocument();
  });

  it("hides delta when undefined", () => {
    render(<KpiTile label="Runs" value="42" />);
    expect(screen.queryByTestId("kpi-delta")).not.toBeInTheDocument();
  });

  it("shows green delta when up is good and delta positive", () => {
    render(<KpiTile label="Runs" value="42" delta={5} goodDirection="up" />);
    const delta = screen.getByTestId("kpi-delta");
    expect(delta.className).toContain("text-green-600");
    expect(delta.textContent).toContain("5.0%");
  });

  it("shows red delta when up is good but delta negative", () => {
    render(<KpiTile label="Runs" value="42" delta={-2.5} goodDirection="up" />);
    const delta = screen.getByTestId("kpi-delta");
    expect(delta.className).toContain("text-red-600");
    expect(delta.textContent).toContain("2.5%");
  });

  it("shows green delta when down is good (cost falling)", () => {
    render(<KpiTile label="Cost" value="$1.20" delta={-4.2} goodDirection="down" />);
    expect(screen.getByTestId("kpi-delta").className).toContain("text-green-600");
  });

  it("uses neutral colour when delta is exactly 0", () => {
    render(<KpiTile label="Runs" value="42" delta={0} />);
    expect(screen.getByTestId("kpi-delta").className).toContain("text-surface-500");
  });
});
