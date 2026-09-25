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
  });
});
