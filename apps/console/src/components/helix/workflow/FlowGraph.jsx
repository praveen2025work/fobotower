'use client';

import { useMemo } from 'react';
import { Background, Controls, MiniMap, ReactFlow } from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { EndNode, EscalateNode, StartNode, StepNode } from './FlowNodes';
import { toFlow } from './graphLayout';

const nodeTypes = { start: StartNode, end: EndNode, step: StepNode, escalate: EscalateNode };

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
  '--xy-minimap-background-color': 'var(--bg-card-solid)',
  '--xy-minimap-mask-background-color': 'var(--bg-hover)',
  '--xy-minimap-node-background-color': 'var(--border)',
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

/** The active workflow's compiled LangGraph, read-only: pan and zoom, no
 *  dragging or connecting. Clicking a step or the Escalate node opens it in
 *  the side panel via `onSelect(id)`. */
export function FlowGraph({ graph, reasoner, onSelect }) {
  const { nodes: laidOut, edges } = useMemo(() => toFlow(graph), [graph]);
  const nodes = useMemo(
    () => laidOut.map((n) => ({ ...n, data: { ...n.data, reasoner, onSelect } })),
    [laidOut, reasoner, onSelect],
  );

  return (
    <div>
      <div style={{ height: 560, width: '100%', ...flowTheme }}>
        <ReactFlow
          nodes={nodes}
          edges={edges}
          nodeTypes={nodeTypes}
          fitView
          nodesDraggable={false}
          nodesConnectable={false}
          elementsSelectable={false}
          panOnScroll
          zoomOnScroll
          proOptions={{ hideAttribution: true }}
        >
          <Background />
          <Controls showInteractive={false} />
          <MiniMap className="hidden md:block" pannable={false} zoomable={false} />
        </ReactFlow>
      </div>
      <Legend />
    </div>
  );
}
