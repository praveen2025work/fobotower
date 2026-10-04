import { describe, it, expect } from "vitest";
import { render, fireEvent, act } from "@testing-library/react";
import { useStickyBottom } from "../useStickyBottom";

interface ScrollSimMockNode extends HTMLDivElement {
  __scrollHeight: number;
  __clientHeight: number;
  __scrollTop: number;
}

/**
 * Configurable scrollable container — jsdom doesn't compute layout, so we
 * stub the geometry properties manually.
 */
function ScrollHarness({
  scrollHeight,
  clientHeight,
  initialScrollTop,
  threshold,
  enabled,
  onMount,
}: {
  scrollHeight: number;
  clientHeight: number;
  initialScrollTop: number;
  threshold?: number;
  enabled?: boolean;
  onMount: (node: ScrollSimMockNode, hook: ReturnType<typeof useStickyBottom>) => void;
}) {
  const result = useStickyBottom<HTMLDivElement>({ threshold, enabled });
  return (
    <div
      ref={(el) => {
        if (!el) return;
        const node = el as ScrollSimMockNode;
        // Each ref callback can be invoked multiple times across renders;
        // Object.defineProperty fails the second time because the
        // descriptor is non-configurable. Define once, then just refresh
        // the underlying values on subsequent passes.
        const dynamic = node as unknown as { __scrollHeight?: number };
        if (typeof dynamic.__scrollHeight !== "number") {
          Object.defineProperty(node, "scrollHeight", { get: () => node.__scrollHeight });
          Object.defineProperty(node, "clientHeight", { get: () => node.__clientHeight });
          Object.defineProperty(node, "scrollTop", {
            get: () => node.__scrollTop,
            set: (v: number) => { node.__scrollTop = v; },
            configurable: true,
          });
        }
        node.__scrollHeight = scrollHeight;
        node.__clientHeight = clientHeight;
        node.__scrollTop = initialScrollTop;
        // Forward the ref the hook needs.
        (result.ref as unknown as { current: HTMLDivElement }).current = node;
        onMount(node, result);
      }}
    />
  );
}

describe("useStickyBottom", () => {
  it("considers the user at the bottom by default", async () => {
    let captured!: { node: ScrollSimMockNode; hook: ReturnType<typeof useStickyBottom> };
    render(
      <ScrollHarness
        scrollHeight={500}
        clientHeight={100}
        initialScrollTop={400}
        onMount={(n, h) => { captured = { node: n, hook: h }; }}
      />,
    );
    expect(captured.hook.isAtBottom).toBe(true);
  });

  it("flips to false when the user scrolls up past the threshold", async () => {
    const captures: Array<ReturnType<typeof useStickyBottom>> = [];
    let captured!: { node: ScrollSimMockNode };
    render(
      <ScrollHarness
        scrollHeight={500}
        clientHeight={100}
        initialScrollTop={400}
        threshold={40}
        onMount={(n, h) => {
          captured = { node: n };
          captures.push(h);
        }}
      />,
    );
    // Move 100px above the bottom — exceeds threshold 40.
    captured.node.__scrollTop = 300;
    await act(async () => {
      fireEvent.scroll(captured.node);
    });
    // Last captured value reflects the post-scroll state. The mount may
    // re-invoke the callback once after the scroll handler updates state.
    const latest = captures[captures.length - 1];
    expect(latest.isAtBottom).toBe(false);
  });

  it("returns isAtBottom=false when explicitly disabled", () => {
    let captured!: { hook: ReturnType<typeof useStickyBottom> };
    render(
      <ScrollHarness
        scrollHeight={500}
        clientHeight={100}
        initialScrollTop={400}
        enabled={false}
        onMount={(_, h) => { captured = { hook: h }; }}
      />,
    );
    expect(captured.hook.isAtBottom).toBe(false);
  });

  it("scrollToBottom moves scrollTop to scrollHeight", () => {
    let captured!: { node: ScrollSimMockNode; hook: ReturnType<typeof useStickyBottom> };
    render(
      <ScrollHarness
        scrollHeight={500}
        clientHeight={100}
        initialScrollTop={0}
        onMount={(n, h) => { captured = { node: n, hook: h }; }}
      />,
    );
    captured.hook.scrollToBottom();
    expect(captured.node.__scrollTop).toBe(500);
  });
});
