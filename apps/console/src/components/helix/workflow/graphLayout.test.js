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

  it('colours the resolve→escalate edge red and dashed, with the reason codes in its label', () => {
    const { edges } = toFlow(fixture);
    const edge = edges.find((e) => e.source === 'resolve' && e.target === 'escalate');
    expect(edge).toBeTruthy();
    expect(edge.style.stroke).toBe('var(--clr-red)');
    expect(edge.style.strokeDasharray).toBeTruthy();
    expect(edge.animated).toBe(false);
    expect(edge.label).toContain('if escalated');
    expect(edge.label).toContain('UNRESOLVED_BOOK');
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
});
