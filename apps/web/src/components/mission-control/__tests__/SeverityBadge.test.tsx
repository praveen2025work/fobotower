import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import SeverityBadge from "../SeverityBadge";

describe("SeverityBadge", () => {
  it("renders the severity label uppercase", () => {
    render(<SeverityBadge severity="high" />);
    expect(screen.getByText(/high/i)).toBeInTheDocument();
  });

  it("applies red styles for high severity", () => {
    const { container } = render(<SeverityBadge severity="high" />);
    expect(container.firstChild).toHaveAttribute("data-severity", "high");
    expect(container.firstChild?.nodeName).toBe("SPAN");
    expect((container.firstChild as HTMLElement).className).toContain("bg-red-100");
  });

  it("applies yellow styles for medium severity (with med alias)", () => {
    const { container, rerender } = render(<SeverityBadge severity="medium" />);
    expect((container.firstChild as HTMLElement).className).toContain("bg-yellow-100");
    rerender(<SeverityBadge severity="med" />);
    expect((container.firstChild as HTMLElement).className).toContain("bg-yellow-100");
  });

  it("falls back to low styles for unknown severities", () => {
    const { container } = render(<SeverityBadge severity="garbage" />);
    expect(container.firstChild).toHaveAttribute("data-severity", "low");
  });
});
