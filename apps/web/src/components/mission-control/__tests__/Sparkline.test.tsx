import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import Sparkline from "../Sparkline";

describe("Sparkline", () => {
  it("renders a placeholder when no data is supplied", () => {
    render(<Sparkline values={[]} />);
    expect(screen.getByTestId("sparkline-empty")).toBeInTheDocument();
  });

  it("renders an svg with one polyline when values are supplied", () => {
    const { container } = render(<Sparkline values={[0.1, 0.5, 0.9]} />);
    expect(container.querySelector("svg")).toBeInTheDocument();
    expect(container.querySelectorAll("polyline").length).toBe(1);
  });

  it("clamps out-of-range values into the SVG box", () => {
    const { container } = render(
      <Sparkline values={[-0.5, 1.5, 0.5]} width={10} height={10} />,
    );
    const polyline = container.querySelector("polyline");
    expect(polyline).toBeTruthy();
    const points = polyline!.getAttribute("points") ?? "";
    // y=10 means clamped to the bottom (value 0); y=0 means clamped to the
    // top (value 1).
    expect(points).toMatch(/,10\.00/);
    expect(points).toMatch(/,0\.00/);
  });

  it("applies the requested stroke class", () => {
    const { container } = render(
      <Sparkline values={[0.5, 0.6]} strokeClass="stroke-red-500" />,
    );
    const polyline = container.querySelector("polyline");
    expect(polyline?.getAttribute("class")).toContain("stroke-red-500");
  });
});
