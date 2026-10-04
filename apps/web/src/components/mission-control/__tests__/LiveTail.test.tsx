import { describe, it, expect } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import LiveTail, { type LogLine } from "../LiveTail";

const FEED: LogLine[] = [
  { id: "1", ts: "2026-04-08T14:23:00Z", level: "info", source: "agent", message: "hello" },
  { id: "2", ts: "2026-04-08T14:23:01Z", level: "warn", source: "agent", message: "slow query" },
  { id: "3", ts: "2026-04-08T14:23:02Z", level: "error", source: "agent", message: "boom" },
];

describe("LiveTail", () => {
  it("renders an empty placeholder when no lines yet", () => {
    render(<LiveTail feed={[]} subscribe={false} />);
    expect(screen.getByText(/waiting for activity/i)).toBeInTheDocument();
  });

  it("renders one row per log line", () => {
    render(<LiveTail feed={FEED} subscribe={false} />);
    expect(screen.getAllByTestId("livetail-line")).toHaveLength(3);
    expect(screen.getByText("hello")).toBeInTheDocument();
    expect(screen.getByText("slow query")).toBeInTheDocument();
    expect(screen.getByText("boom")).toBeInTheDocument();
  });

  it("toggles the pause button between Pause and Resume", () => {
    render(<LiveTail feed={FEED} subscribe={false} />);
    const btn = screen.getByTestId("livetail-pause-toggle");
    expect(btn.textContent).toContain("Pause");
    fireEvent.click(btn);
    expect(btn.textContent).toContain("Resume");
    expect(btn).toHaveAttribute("aria-pressed", "true");
    fireEvent.click(btn);
    expect(btn.textContent).toContain("Pause");
    expect(btn).toHaveAttribute("aria-pressed", "false");
  });

  it("colour-codes lines by level", () => {
    render(<LiveTail feed={FEED} subscribe={false} />);
    const lines = screen.getAllByTestId("livetail-line");
    expect(lines[0].textContent).toContain("hello");
    // Find the message span (last child) and check its colour class.
    const errorLine = lines[2].querySelector("span:last-child");
    expect(errorLine?.className).toContain("text-red-300");
  });
});
