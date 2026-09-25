import { describe, expect, it } from 'vitest';
import fixture from './__fixtures__/graph.json';
import { toFlow } from './graphLayout';

describe('toFlow', () => {
  it('positions every node with finite coordinates', () => {
    const { nodes } = toFlow(fixture);
    expect(nodes).toHaveLength(fixture.nodes.length);
    for (const n of nodes) {
      expect(Number.isFinite(n.position.x)).toBe(true);
      expect(Number.isFinite(n.position.y)).toBe(true);
    }
  });

  it("places the escalate node beside the main chain, at a different x", () => {
    const { nodes } = toFlow(fixture);
    const byId = Object.fromEntries(nodes.map((n) => [n.id, n]));
    expect(byId.escalate.position.x).not.toBe(byId.resolve.position.x);
    expect(byId.escalate.position.x).not.toBe(byId.gather.position.x);
  });

  it('colours the resolve→escalate edge red and dashed, with a short label (no reason codes crammed on it)', () => {
    const { edges } = toFlow(fixture);
    const edge = edges.find((e) => e.source === 'resolve' && e.target === 'escalate');
    expect(edge).toBeTruthy();
    expect(edge.style.stroke).toBe('var(--clr-red)');
    expect(edge.style.strokeDasharray).toBeTruthy();
    expect(edge.animated).toBe(false);
    expect(edge.label).toBe('if escalated');
  });

  it("puts the reason codes on the Escalate node instead, grouped by source step", () => {
    const { nodes } = toFlow(fixture);
    const escalate = nodes.find((n) => n.id === 'escalate');
    const expected = fixture.edges
      .filter((e) => e.conditional && e.target === 'escalate')
      .map((e) => ({
        source: e.source,
        label: fixture.nodes.find((n) => n.id === e.source).label,
        reasons: e.reasons,
      }));
    expect(expected.length).toBeGreaterThan(0);
    expect(escalate.data.reasonGroups).toEqual(expected);
  });

  it('marks the "otherwise" edges solid with a small label', () => {
    const { edges } = toFlow(fixture);
    const edge = edges.find((e) => e.source === 'resolve' && e.target === 'gather');
    expect(edge.style.strokeDasharray).toBeFalsy();
    expect(edge.label).toBe('otherwise');
  });

  it('marks the edge into a paused step amber and dashed, with a wait label', () => {
    const { edges } = toFlow(fixture);
    const edge = edges.find((e) => e.target === 'review');
    expect(edge).toBeTruthy();
    expect(edge.style.stroke).toBe('var(--clr-amber)');
    expect(edge.style.strokeDasharray).toBeTruthy();
    expect(edge.label).toContain('waits for a controller');
  });

  it('gives every edge a closed arrowhead', () => {
    const { edges } = toFlow(fixture);
    for (const e of edges) {
      expect(e.markerEnd?.type).toBe('arrowclosed');
    }
  });

  it('still lays out when a node is dropped and a new edge takes its place', () => {
    const nodes = fixture.nodes.filter((n) => n.id !== 'rank');
    const edges = fixture.edges
      .filter((e) => e.source !== 'rank' && e.target !== 'rank')
      .concat([{ source: 'reason', target: 'draft', conditional: false, label: null }]);
    const graph = { ...fixture, nodes, edges };
    const { nodes: flowNodes, edges: flowEdges } = toFlow(graph);
    expect(flowNodes).toHaveLength(nodes.length);
    expect(flowEdges).toHaveLength(edges.length);
    for (const n of flowNodes) {
      expect(Number.isFinite(n.position.x)).toBe(true);
      expect(Number.isFinite(n.position.y)).toBe(true);
    }
  });

  it('does not mutate the graph it is given', () => {
    const before = JSON.parse(JSON.stringify(fixture));
    toFlow(fixture);
    expect(fixture).toEqual(before);
  });

  describe('node sizes', () => {
    it('gives a step with a badge line (paused-before or can-escalate) more height than one without', () => {
      const { nodes } = toFlow(fixture);
      const byId = Object.fromEntries(nodes.map((n) => [n.id, n]));
      // 'resolve' can escalate (a badge line); 'group' has neither.
      expect(byId.resolve.height).toBeGreaterThan(byId.group.height);
      // 'review' pauses before it (a badge line); 'group' has neither.
      expect(byId.review.height).toBeGreaterThan(byId.group.height);
      // Tall enough for the real content (title + id + chips + badge),
      // not just "taller than the baseline" — this is what let the badge
      // line overlap the id above it.
      expect(byId.resolve.height).toBeGreaterThanOrEqual(96);
      expect(byId.group.height).toBeGreaterThanOrEqual(78);
    });

    it("grows the Escalate node's height with the number of reason lines it must show", () => {
      const { nodes } = toFlow(fixture);
      const twoGroups = nodes.find((n) => n.id === 'escalate');

      // Drop the 'gather' escalation edge: only one source step left.
      const oneGroupGraph = {
        ...fixture,
        edges: fixture.edges.filter(
          (e) => !(e.conditional && e.target === 'escalate' && e.source === 'gather'),
        ),
      };
      const oneGroup = toFlow(oneGroupGraph).nodes.find((n) => n.id === 'escalate');

      expect(twoGroups.height).toBeGreaterThan(oneGroup.height);
      // Tall enough for both groups' wrapped text (each wraps to 2 lines
      // at this width) — real content, not just "taller than one group".
      expect(twoGroups.height).toBeGreaterThanOrEqual(120);
    });

    it('keeps the main chain in a single straight column', () => {
      const { nodes } = toFlow(fixture);
      const chain = ['resolve', 'gather', 'group', 'reason', 'rank', 'draft', 'validate', 'review', 'record'];
      const xs = new Set(chain.map((id) => nodes.find((n) => n.id === id).position.x));
      expect(xs.size).toBe(1);
    });
  });

  describe('escalate→End routing', () => {
    it('routes escalate→__end__ through a distinct handle pair from record→__end__', () => {
      const { edges } = toFlow(fixture);
      const escalateToEnd = edges.find((e) => e.source === 'escalate' && e.target === '__end__');
      const chainToEnd = edges.find((e) => e.source !== 'escalate' && e.target === '__end__');
      expect(escalateToEnd).toBeTruthy();
      expect(chainToEnd).toBeTruthy();

      // End's own right-side handle — not the top handle the main chain's
      // last step arrives through — so the two paths can never share a
      // segment or read as "the escalated run rejoins the chain".
      expect(escalateToEnd.targetHandle).toBe('escalate-in');
      expect(chainToEnd.targetHandle).not.toBe('escalate-in');
      expect(escalateToEnd.targetHandle).not.toBe(chainToEnd.targetHandle);
    });

    it("gives each step that can escalate its own target handle on Escalate, distinct from the others", () => {
      const { edges } = toFlow(fixture);
      const intoEscalate = edges.filter((e) => e.target === 'escalate');
      expect(intoEscalate.length).toBeGreaterThan(1);
      const handles = intoEscalate.map((e) => e.targetHandle);
      expect(new Set(handles).size).toBe(handles.length);
      for (const e of intoEscalate) {
        expect(e.targetHandle).toBe(`in-${e.source}`);
      }
    });

    it("spreads escalate-bound edges' turn points (stepPosition) so no two share the same one", () => {
      const { edges } = toFlow(fixture);
      const intoEscalate = edges.filter((e) => e.target === 'escalate');
      const positions = intoEscalate.map((e) => e.pathOptions?.stepPosition);
      for (const p of positions) {
        expect(typeof p).toBe('number');
      }
      expect(new Set(positions).size).toBe(positions.length);
    });
  });

  describe('canvas height', () => {
    it('fits the whole real graph at close to zoom 1, never below the 0.85 floor', () => {
      const { nodes, height } = toFlow(fixture);
      const contentBottom = Math.max(...nodes.map((n) => n.position.y + n.height));
      // Within the agreed cap...
      expect(height).toBeLessThanOrEqual(1400);
      // ...and close enough to the content's own height that fitting the
      // whole graph in (React Flow's fitView, bounded by that same floor)
      // never needs to zoom out past readability.
      expect(height / contentBottom).toBeGreaterThanOrEqual(0.85);
    });

    it('never drops below a sensible floor for a tiny graph', () => {
      const tiny = {
        ...fixture,
        nodes: [
          { id: '__start__', kind: 'start', label: 'Start', paused_before: false },
          { id: '__end__', kind: 'end', label: 'End', paused_before: false },
        ],
        edges: [{ source: '__start__', target: '__end__', conditional: false, label: null }],
      };
      const { height } = toFlow(tiny);
      expect(height).toBeGreaterThanOrEqual(400);
    });

    it('caps the height for a graph much taller than the cap', () => {
      const nodes = [{ id: '__start__', kind: 'start', label: 'Start', paused_before: false }];
      const edges = [];
      for (let i = 0; i < 40; i += 1) {
        nodes.push({ id: `s${i}`, kind: 'step', label: `Step ${i}`, decided_by: 'code', paused_before: false });
        edges.push({
          source: i === 0 ? '__start__' : `s${i - 1}`,
          target: `s${i}`,
          conditional: false,
          label: null,
        });
      }
      const { height } = toFlow({ ...fixture, nodes, edges });
      expect(height).toBe(1400);
    });

    it('lets the zoom floor give way when the capped canvas is shorter than the content, so Start and End still fit', () => {
      // Many paused steps (each with a badge line, so taller than a plain
      // step) — content comfortably exceeds MAX_CANVAS_HEIGHT even after
      // the cap, unlike the real graph today (which fits within the 0.85
      // floor with room to spare).
      const nodes = [{ id: '__start__', kind: 'start', label: 'Start', paused_before: false }];
      const edges = [];
      let prev = '__start__';
      for (let i = 0; i < 20; i += 1) {
        const id = `p${i}`;
        nodes.push({ id, kind: 'step', label: `Step ${i}`, decided_by: 'human', paused_before: true });
        edges.push({ source: prev, target: id, conditional: false, label: null });
        prev = id;
      }
      nodes.push({ id: '__end__', kind: 'end', label: 'End', paused_before: false });
      edges.push({ source: prev, target: '__end__', conditional: false, label: null });

      const { nodes: laidOut, height, minZoom } = toFlow({ ...fixture, nodes, edges });
      expect(height).toBe(1400); // capped, same as the plain-steps case above

      const contentBottom = Math.max(...laidOut.map((n) => n.position.y + n.height));
      expect(contentBottom).toBeGreaterThan(height); // the cap really did bite

      // A fixed 0.85 floor could not fit this content into the capped
      // canvas at all; the floor must have given way to something smaller.
      expect(minZoom).toBeLessThan(0.85);
      // ...but not so far it stops being a real floor.
      expect(minZoom).toBeGreaterThan(0);

      // At that zoom, the whole chain — in particular Start at the top and
      // End at the bottom — fits inside the canvas height.
      expect(contentBottom * minZoom).toBeLessThanOrEqual(height + 1);
      const start = laidOut.find((n) => n.id === '__start__');
      const end = laidOut.find((n) => n.id === '__end__');
      expect(start.position.y * minZoom).toBeGreaterThanOrEqual(0);
      expect((end.position.y + end.height) * minZoom).toBeLessThanOrEqual(height + 1);
    });

    it('keeps the default minZoom for a graph that already fits within the cap', () => {
      const { minZoom } = toFlow(fixture);
      expect(minZoom).toBe(0.85);
    });
  });
});
