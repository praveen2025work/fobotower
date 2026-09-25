'use client';

import { useEffect, useMemo } from 'react';
import { Background, Controls, ReactFlow, useReactFlow } from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { EndNode, EscalateNode, StartNode, StepNode } from './FlowNodes';
import { toFlow } from './graphLayout';

const nodeTypes = { start: StartNode, end: EndNode, step: StepNode, escalate: EscalateNode };

// "Readable by default": start at zoom 1, and don't let the initial fit (or
// a user's own zoom-out) go further than it has to. The actual floor comes
// from `toFlow()` — normally this same 0.85, but it gives way for a graph
// whose laid-out content is taller than graphLayout.js's canvas-height cap,
// so Start/End can never end up clipped outside the canvas with nowhere
// left to zoom out to.
const MAX_ZOOM = 1.5;
const FIT_PADDING = 0.08;

// Maps the theme's own CSS variables onto React Flow's `--xy-*` variables,
// so the diagram follows light/dark mode instead of shipping its own colours.
const flowTheme = {
  '--xy-background-color': 'var(--bg-page)',
  '--xy-background-pattern-color': 'var(--border)',
  '--xy-node-background-color': 'var(--bg-card-solid)',
  '--xy-node-border': '1px solid var(--border)',
  '--xy-node-color': 'var(--text-primary)',
  '--xy-node-boxshadow-hover': 'var(--card-shadow)',
  '--xy-node-boxshadow-selected': 'var(--card-shadow)',
  '--xy-edge-stroke': 'var(--text-muted)',
  '--xy-edge-stroke-selected': 'var(--clr-blue)',
  '--xy-edge-label-background-color': 'var(--bg-card-solid)',
  '--xy-edge-label-color': 'var(--text-secondary)',
  '--xy-handle-background-color': 'var(--text-muted)',
  '--xy-handle-border-color': 'var(--bg-card-solid)',
  '--xy-controls-button-background-color': 'var(--bg-card-solid)',
  '--xy-controls-button-background-color-hover': 'var(--bg-hover)',
  '--xy-controls-button-color': 'var(--text-secondary)',
  '--xy-controls-button-border-color': 'var(--border)',
  '--xy-attribution-background-color': 'transparent',
};

function Legend() {
  return (
    <p
      className="text-[10.5px] mt-1.5 flex flex-wrap gap-x-3 gap-y-0.5"
      style={{ color: 'var(--text-muted)' }}
    >
      <span>solid = next step</span>
      <span style={{ color: 'var(--clr-red)' }}>red dashed = if escalated</span>
      <span style={{ color: 'var(--clr-amber)' }}>amber = waits for a controller</span>
    </p>
  );
}

/** Fits the diagram to its container whenever the laid-out graph changes
 *  (mount, or a different active version). Deliberately *not* the `fitView`
 *  boolean prop: that fits once, synchronously, on the very first render —
 *  before this component mounts at all — and was why the diagram used to
 *  render at the library's default zoom/pan (1, untranslated) instead of a
 *  real fit, clipping Start/Resolve at the top and Record/End at the
 *  bottom. It also can't be driven by `useNodesInitialized`: that hook only
 *  flips true once React Flow's own ResizeObserver measures each node's
 *  *rendered* size, but since every node here already carries an explicit
 *  `width`/`height` from `graphLayout.js` (dagre needs them for layout
 *  math), React Flow treats them as already "sized" and never attaches that
 *  observer — so the hook stays false forever. Keying a plain effect off the
 *  laid-out nodes/edges (stable per `graph`, via `toFlow`'s memo) fires
 *  right after mount and again only when the graph actually changes, not on
 *  every incidental re-render (e.g. `reasoner` or `onSelect` changing) —
 *  otherwise a re-fit would keep resetting a user's manual pan/zoom. */
function FitOnReady({ layoutKey, minZoom }) {
  const { fitView } = useReactFlow();
  useEffect(() => {
    fitView({ padding: FIT_PADDING, minZoom, maxZoom: MAX_ZOOM, duration: 0 });
  }, [layoutKey, minZoom, fitView]);
  return null;
}

/** The active workflow's compiled LangGraph, read-only: pan (drag) and zoom
 *  (Controls' buttons), no dragging nodes or connecting them. The canvas is
 *  sized to the layout itself (see `graphLayout.js`'s `height`) so the whole
 *  graph fits without zooming out past `MIN_ZOOM`; the page scrolls past it
 *  normally rather than the canvas capturing wheel input. Clicking a step or
 *  the Escalate node opens it in the side panel via `onSelect(id)`. */
export function FlowGraph({ graph, reasoner, onSelect }) {
  const { nodes: laidOut, edges, height, minZoom } = useMemo(() => toFlow(graph), [graph]);
  const nodes = useMemo(
    () => laidOut.map((n) => ({ ...n, data: { ...n.data, reasoner, onSelect } })),
    [laidOut, reasoner, onSelect],
  );

  return (
    <div>
      <div style={{ height, width: '100%', ...flowTheme }}>
        <ReactFlow
          nodes={nodes}
          edges={edges}
          nodeTypes={nodeTypes}
          minZoom={minZoom}
          maxZoom={MAX_ZOOM}
          nodesDraggable={false}
          nodesConnectable={false}
          elementsSelectable={false}
          // Read-only view: React Flow's own node/edge wrapper elements
          // would otherwise each be a second tab stop next to a step
          // node's own "Open <label>" button, doubling the number of tab
          // stops per node with nothing extra for a keyboard user to do
          // at the wrapper.
          nodesFocusable={false}
          edgesFocusable={false}
          zoomOnScroll={false}
          panOnScroll={false}
          preventScrolling={false}
          proOptions={{ hideAttribution: true }}
        >
          <FitOnReady layoutKey={laidOut} minZoom={minZoom} />
          <Background />
          <Controls showInteractive={false} />
        </ReactFlow>
      </div>
      <Legend />
    </div>
  );
}
