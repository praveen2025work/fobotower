/** Pure layout for the compiled LangGraph: turns the API's {nodes, edges}
 *  into React Flow's {nodes, edges}, positioned top-to-bottom with dagre,
 *  plus a canvas `height` sized to fit the whole thing. Nothing here
 *  mutates its `graph` argument. */

import dagre from '@dagrejs/dagre';
import { MarkerType, Position } from '@xyflow/react';

// A step node's height is its content's: padding, title, mono id, chips
// row, plus one more line for each badge it shows (paused / can-escalate —
// a future step could in principle carry both). Measured against the real
// rendered node (Chrome, the app's own fonts) and rounded up with a small
// safety margin, since a fixed guess is what let the extra badge line
// overlap the id below it.
const STEP_WIDTH = 260;
const STEP_BASE_HEIGHT = 84; // padding + title + id + chips row
const STEP_BADGE_LINE_HEIGHT = 20; // each of paused-before / can-escalate

const START_END_SIZE = { width: 96, height: 40 };

// The Escalate node's height likewise has to fit what it actually shows:
// a title, a subtitle, and one wrapped block of text per source step. Line
// count per block is estimated from its character length (mono + semibold
// mixed text, so this is deliberately a little conservative) rather than
// assumed to always be one line — that's what let CHECKS_UNAVAILABLE spill
// below the box.
const ESCALATE_WIDTH = 260;
const ESCALATE_HEADER_HEIGHT = 58; // padding + title + gap + subtitle
const ESCALATE_GROUP_GAP = 4;
const ESCALATE_LINE_HEIGHT = 15;
const ESCALATE_CHARS_PER_LINE = 34;

const CANVAS_PADDING = 56;
const MIN_CANVAS_HEIGHT = 420;
const MAX_CANVAS_HEIGHT = 1400;

// FlowGraph.jsx's "readable by default" zoom floor: below this, node text
// stops being legible, so fitView is never asked to zoom out past it —
// *unless* the laid-out content is tall enough that MAX_CANVAS_HEIGHT above
// has capped the canvas below the content's own height. In that case a
// fixed 0.85 floor would leave fitView unable to zoom out far enough, and
// Start/End end up clipped outside the canvas entirely; readability gives
// way to the diagram fitting at all. See `minZoom` below.
const DEFAULT_MIN_ZOOM = 0.85;

const WAITS_LABEL = '⏸ waits for a controller';
const ESCALATE_LABEL = 'if escalated';

const stepSize = ({ pausedBefore, canEscalate }) => {
  const badgeLines = (pausedBefore ? 1 : 0) + (canEscalate ? 1 : 0);
  return { width: STEP_WIDTH, height: STEP_BASE_HEIGHT + badgeLines * STEP_BADGE_LINE_HEIGHT };
};

const groupLineCount = (group) => {
  const text = `${group.label}: ${group.reasons.join(', ')}`;
  return Math.max(1, Math.ceil(text.length / ESCALATE_CHARS_PER_LINE));
};

const escalateSize = (groups) => {
  const groupsHeight = groups.reduce(
    (sum, g) => sum + ESCALATE_GROUP_GAP + groupLineCount(g) * ESCALATE_LINE_HEIGHT,
    0,
  );
  return { width: ESCALATE_WIDTH, height: ESCALATE_HEADER_HEIGHT + groupsHeight };
};

/** The reason codes the Escalate node ends up with, grouped by the step that
 *  raised them — read straight off the graph's own edges, never typed in. */
function reasonGroups(graph) {
  const labelById = new Map(graph.nodes.map((n) => [n.id, n.label]));
  return graph.edges
    .filter((e) => e.conditional && e.target === 'escalate')
    .map((e) => ({
      source: e.source,
      label: labelById.get(e.source) || e.source,
      reasons: e.reasons || [],
    }));
}

/** How an edge should look, independent of layout: the rule that decides is
 *  "into a paused step" first (it overrides everything else, since arriving
 *  at a paused step is true regardless of why the edge exists), then
 *  "conditional into escalate", then "conditional otherwise", then plain.
 *  The reason codes for an "if escalated" edge live on the Escalate node
 *  itself (see `reasonGroups`), not crammed onto the edge label. */
function edgeLook(edge, pausedIds) {
  if (pausedIds.has(edge.target)) {
    return { color: 'var(--clr-amber)', dashed: true, label: WAITS_LABEL };
  }
  if (edge.conditional && edge.target === 'escalate') {
    return { color: 'var(--clr-red)', dashed: true, label: ESCALATE_LABEL };
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
  const groups = reasonGroups(graph);

  // Every node's own content decides its size — not a single fixed guess
  // per kind — computed once up front so dagre's layout and the rendered
  // node agree on exactly the same box.
  const sizeOf = (n) => {
    if (n.kind === 'step') {
      return stepSize({ pausedBefore: n.paused_before, canEscalate: escalateSources.has(n.id) });
    }
    if (n.kind === 'escalate') return escalateSize(groups);
    return START_END_SIZE;
  };
  const sizeById = new Map(graph.nodes.map((n) => [n.id, sizeOf(n)]));

  const g = new dagre.graphlib.Graph();
  g.setGraph({ rankdir: 'TB', nodesep: 110, ranksep: 52, marginx: 24, marginy: 20, align: 'UL' });
  g.setDefaultEdgeLabel(() => ({}));
  for (const n of graph.nodes) {
    const { width, height } = sizeById.get(n.id);
    g.setNode(n.id, { width, height });
  }
  for (const e of graph.edges) {
    g.setEdge(e.source, e.target);
  }
  dagre.layout(g);

  const nodes = graph.nodes.map((n) => {
    const { width, height } = sizeById.get(n.id);
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
        ...(n.kind === 'escalate' ? { reasonGroups: groups } : {}),
      },
    };
  });

  // Source order (top to bottom, same order as `groups`), so each
  // escalate-bound edge can get its own vertical lane (via `stepPosition`,
  // the fraction of the way from source to target where a smoothstep edge
  // makes its turn — and, for this exact handle pairing [Right → Left],
  // also exactly where React Flow places the edge's label). Smoothstep's
  // path for two horizontally-opposed handles is source → (turn) → target,
  // where the turn's x is `stepPosition` of the way from source to target,
  // and the two runs either side of it sit at the SOURCE's y (before the
  // turn) and the TARGET's y (after). A default `stepPosition` of 0.5
  // gives every escalate-bound edge the same turn-x, so an earlier (higher,
  // further from Escalate) step's long source-side run — at ITS OWN y —
  // extends past a later (lower, closer) step's row and crosses that
  // step's short run, right where its label sits.
  //
  // Fix: the step closer to Escalate turns early (small stepPosition — its
  // vertical run sits near ITS OWN source, short, since it has little
  // distance to cover), and the step further away turns late (large
  // stepPosition — its vertical run sits near Escalate, so its long
  // source-side run stays up at its own height, above every closer step's
  // row, instead of cutting through it). `groups` is already ordered top
  // to bottom, i.e. furthest-from-Escalate to closest, so that's index 0 →
  // MAX, last index → MIN.
  const ESCALATE_STEP_MIN = 0.08;
  const ESCALATE_STEP_MAX = 0.92;
  const escalateSourceIndex = new Map(groups.map((g, i) => [g.source, i]));
  const escalateStepPosition = (source) => {
    const n = groups.length;
    if (n <= 1) return 0.5;
    const i = escalateSourceIndex.get(source);
    return ESCALATE_STEP_MAX - (i / (n - 1)) * (ESCALATE_STEP_MAX - ESCALATE_STEP_MIN);
  };

  const edges = graph.edges.map((e) => {
    const look = edgeLook(e, pausedIds);
    const intoEscalate = e.conditional && e.target === 'escalate';
    // Escalate's own route to End is a distinct path from the main chain's
    // record→End edge: it uses End's right-side handle (entered from the
    // escalate lane) instead of sharing End's top handle with the chain,
    // so it can never read as "rejoining" the chain partway down.
    const escalateToEnd = e.source === 'escalate' && e.target === '__end__';
    return {
      id: `${e.source}->${e.target}`,
      source: e.source,
      target: e.target,
      sourceHandle: intoEscalate ? 'right' : 'bottom',
      // Each step that can escalate gets its own target handle on Escalate
      // (`in-<step id>`, rendered by FlowNodes.jsx spread along its left
      // edge in source order) rather than all sharing one — otherwise a
      // later step's short hop in can cross an earlier step's longer one,
      // right where its label sits.
      targetHandle: intoEscalate ? `in-${e.source}` : escalateToEnd ? 'escalate-in' : 'top',
      type: 'smoothstep',
      animated: false,
      ...(intoEscalate ? { pathOptions: { stepPosition: escalateStepPosition(e.source) } } : {}),
      style: {
        stroke: look.color,
        strokeWidth: 1.5,
        ...(look.dashed ? { strokeDasharray: '6 4' } : {}),
      },
      label: look.label,
      labelStyle: { fill: look.color, fontSize: 11, fontWeight: 600 },
      labelBgPadding: [6, 3],
      labelBgBorderRadius: 3,
      labelBgStyle: { fill: 'var(--bg-card-solid)', fillOpacity: 0.95 },
      markerEnd: { type: MarkerType.ArrowClosed, color: look.color },
    };
  });

  const contentBottom = nodes.length
    ? Math.max(...nodes.map((n) => n.position.y + n.height))
    : 0;
  const height = Math.min(
    MAX_CANVAS_HEIGHT,
    Math.max(MIN_CANVAS_HEIGHT, Math.round(contentBottom + CANVAS_PADDING)),
  );
  // The zoom fitView actually needs to show the whole chain in a canvas of
  // this height. Only lower than DEFAULT_MIN_ZOOM when the cap above bit —
  // for every graph that fits within MAX_CANVAS_HEIGHT (every graph today),
  // this is exactly DEFAULT_MIN_ZOOM, unchanged.
  const minZoom = contentBottom > 0 ? Math.min(DEFAULT_MIN_ZOOM, height / contentBottom) : DEFAULT_MIN_ZOOM;

  return { nodes, edges, height, minZoom };
}
