/** Pure layout for the compiled LangGraph: turns the API's {nodes, edges}
 *  into React Flow's {nodes, edges}, positioned top-to-bottom with dagre.
 *  Nothing here mutates its `graph` argument. */

import dagre from '@dagrejs/dagre';
import { MarkerType, Position } from '@xyflow/react';

const SIZE = {
  step: { width: 230, height: 84 },
  escalate: { width: 176, height: 68 },
  start: { width: 92, height: 40 },
  end: { width: 92, height: 40 },
};

const sizeFor = (kind) => SIZE[kind] || SIZE.step;

const WAITS_LABEL = '⏸ waits for a controller';
const ESCALATE_LABEL = 'if escalated';

/** How an edge should look, independent of layout: the rule that decides is
 *  "into a paused step" first (it overrides everything else, since arriving
 *  at a paused step is true regardless of why the edge exists), then
 *  "conditional into escalate", then "conditional otherwise", then plain. */
function edgeLook(edge, pausedIds) {
  if (pausedIds.has(edge.target)) {
    return { color: 'var(--clr-amber)', dashed: true, label: WAITS_LABEL };
  }
  if (edge.conditional && edge.target === 'escalate') {
    const reasons = edge.reasons || [];
    const label = reasons.length ? `${ESCALATE_LABEL} (${reasons.join(', ')})` : ESCALATE_LABEL;
    return { color: 'var(--clr-red)', dashed: true, label };
  }
  if (edge.conditional) {
    return { color: 'var(--text-muted)', dashed: false, label: edge.label || 'otherwise' };
  }
  return { color: 'var(--text-muted)', dashed: false, label: null };
}

export function toFlow(graph) {
  const pausedIds = new Set(graph.nodes.filter((n) => n.paused_before).map((n) => n.id));
  const escalateSources = new Set(
    graph.edges.filter((e) => e.conditional && e.target === 'escalate').map((e) => e.source),
  );

  const g = new dagre.graphlib.Graph();
  g.setGraph({ rankdir: 'TB', nodesep: 64, ranksep: 88, marginx: 20, marginy: 20 });
  g.setDefaultEdgeLabel(() => ({}));
  for (const n of graph.nodes) {
    const { width, height } = sizeFor(n.kind);
    g.setNode(n.id, { width, height });
  }
  for (const e of graph.edges) {
    g.setEdge(e.source, e.target);
  }
  dagre.layout(g);

  const nodes = graph.nodes.map((n) => {
    const { width, height } = sizeFor(n.kind);
    const pos = g.node(n.id);
    const canEscalate = escalateSources.has(n.id);
    return {
      id: n.id,
      type: n.kind,
      position: { x: pos.x - width / 2, y: pos.y - height / 2 },
      width,
      height,
      draggable: false,
      connectable: false,
      sourcePosition: Position.Bottom,
      targetPosition: Position.Top,
      data: {
        label: n.label,
        decidedBy: n.decided_by,
        pausedBefore: n.paused_before,
        canEscalate,
      },
    };
  });

  const edges = graph.edges.map((e) => {
    const look = edgeLook(e, pausedIds);
    const toEscalate = e.conditional && e.target === 'escalate';
    return {
      id: `${e.source}->${e.target}`,
      source: e.source,
      target: e.target,
      sourceHandle: toEscalate ? 'right' : 'bottom',
      targetHandle: toEscalate ? 'left' : 'top',
      type: 'smoothstep',
      animated: false,
      style: {
        stroke: look.color,
        strokeWidth: 1.5,
        ...(look.dashed ? { strokeDasharray: '6 4' } : {}),
      },
      label: look.label,
      labelStyle: { fill: look.color, fontSize: 10, fontWeight: 600 },
      labelBgPadding: [4, 2],
      labelBgStyle: { fill: 'var(--bg-card-solid)' },
      markerEnd: { type: MarkerType.ArrowClosed, color: look.color },
    };
  });

  return { nodes, edges };
}
