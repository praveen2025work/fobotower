'use client';

import { useEffect, useRef, useState } from 'react';
import { FlowGraph } from './FlowGraph';
import { WorkflowGraph } from './WorkflowGraph';

// Below this container width, the React Flow diagram doesn't have room to
// show more than a sliver of the chain even at its zoom floor — the
// existing stacked card view reads better there instead.
export const NARROW_BREAKPOINT = 640;

/** Measures its own rendered width — not the window's; the "Active
 *  workflow" card can be narrower than the viewport on a wide screen too —
 *  via a ResizeObserver on the returned ref. SSR-safe: starts `null`
 *  (unmeasured, so `isNarrow` reads false) and only updates once the
 *  browser reports a real width. */
function useContainerWidth() {
  const ref = useRef(null);
  const [width, setWidth] = useState(null);
  useEffect(() => {
    const el = ref.current;
    if (!el || typeof ResizeObserver === 'undefined') return undefined;
    const observer = new ResizeObserver((entries) => {
      const entry = entries[0];
      if (entry) setWidth(entry.contentRect.width);
    });
    observer.observe(el);
    return () => observer.disconnect();
  }, []);
  return [ref, width];
}

/** The "Active workflow" card's contents. Wide enough (≥`NARROW_BREAKPOINT`)
 *  and it's the interactive React Flow diagram; narrower and it's the same
 *  stacked card view the tab always used, since the diagram has nowhere to
 *  put the chain at a legible zoom. Either way, clicking a step (or, on the
 *  diagram, the Escalate node) opens it via `onSelect(id)`. */
export function ActiveWorkflowGraph({ config, catalogue, reasoner, graphState, onRetryGraph, onSelect }) {
  const [ref, width] = useContainerWidth();
  const isNarrow = width != null && width < NARROW_BREAKPOINT;

  return (
    <div ref={ref}>
      {isNarrow ? (
        <>
          <p className="text-[11px] mb-2" style={{ color: 'var(--text-muted)' }}>
            Open on a wider screen to see the diagram.
          </p>
          <WorkflowGraph config={config} catalogue={catalogue} reasoner={reasoner} onSelect={onSelect} />
        </>
      ) : (
        <>
          {graphState.state === 'loading' && (
            <p className="text-[12px]" style={{ color: 'var(--text-muted)' }}>
              Loading the diagram…
            </p>
          )}
          {graphState.state === 'error' && (
            <div className="flex items-center gap-3 text-[12px]" style={{ color: 'var(--clr-red)' }}>
              {graphState.error}
              <button
                type="button"
                onClick={onRetryGraph}
                className="px-3 py-1 rounded-full"
                style={{ border: '1px solid var(--border)' }}
              >
                Retry
              </button>
            </div>
          )}
          {graphState.state === 'ready' && (
            <FlowGraph graph={graphState.graph} reasoner={reasoner} onSelect={onSelect} />
          )}
        </>
      )}
    </div>
  );
}
