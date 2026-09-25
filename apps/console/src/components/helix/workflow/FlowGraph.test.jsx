import { fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import fixture from './__fixtures__/graph.json';
import { FlowGraph } from './FlowGraph';
import { toFlow } from './graphLayout';

// jsdom reports every element as 0×0; React Flow refuses to lay nodes out in
// a zero-size container. Scoped to this file (not a global vitest.setup.js
// stub) so it can't mask a real zero-size regression in an unrelated test.
let rectSpy;
beforeEach(() => {
  rectSpy = vi.spyOn(Element.prototype, 'getBoundingClientRect').mockReturnValue({
    x: 0,
    y: 0,
    top: 0,
    left: 0,
    right: 1024,
    bottom: 640,
    width: 1024,
    height: 640,
    toJSON() {},
  });
});
afterEach(() => {
  rectSpy.mockRestore();
});

const renderFlow = (props = {}) => {
  const onSelect = vi.fn();
  const result = render(<FlowGraph graph={fixture} reasoner="none" onSelect={onSelect} {...props} />);
  return { onSelect, ...result };
};

describe('FlowGraph', () => {
  it('renders a node for every step', () => {
    renderFlow();
    for (const step of fixture.nodes.filter((n) => n.kind === 'step')) {
      expect(screen.getByRole('button', { name: `Open ${step.label}` })).toBeInTheDocument();
    }
  });

  it('renders the Escalate node', () => {
    renderFlow();
    expect(screen.getByRole('button', { name: 'Open Escalate' })).toBeInTheDocument();
  });

  it('lists the Escalate node’s reason codes grouped by source step', () => {
    renderFlow();
    const node = screen.getByRole('button', { name: 'Open Escalate' });
    expect(node).toHaveTextContent('Resolve books: UNRESOLVED_BOOK, AMBIGUOUS_BOOK');
    expect(node).toHaveTextContent('Gather evidence: DELTA_UNAVAILABLE, CHECKS_UNAVAILABLE');
  });

  it('renders the legend', () => {
    renderFlow();
    expect(screen.getByText(/solid = next step/)).toBeInTheDocument();
    expect(screen.getByText(/red dashed = if escalated/)).toBeInTheDocument();
    expect(screen.getByText(/amber = waits for a controller/)).toBeInTheDocument();
  });

  it('renders no MiniMap', () => {
    const { container } = renderFlow();
    expect(container.querySelector('.react-flow__minimap')).toBeNull();
  });

  it('sizes the canvas from the layout, not a fixed height', () => {
    const { container } = renderFlow();
    const { height } = toFlow(fixture);
    // eslint-disable-next-line testing-library/no-node-access
    const canvas = container.querySelector('.react-flow');
    expect(canvas.parentElement.style.height).toBe(`${height}px`);
  });

  // fireEvent.click (a plain "click", not userEvent's full mousedown→mouseup
  // sequence): React Flow's pane wires d3-zoom's drag-to-pan on mousedown,
  // and d3-zoom reads the synthetic event's `view`, which jsdom leaves null —
  // irrelevant here since these tests are about the click, not a drag.
  it('calls onSelect with the step id when a step node is clicked', () => {
    const { onSelect } = renderFlow();
    fireEvent.click(screen.getByRole('button', { name: 'Open Apply playbook' }));
    expect(onSelect).toHaveBeenCalledWith('reason');
  });

  it('calls onSelect with "escalate" when the Escalate node is clicked', () => {
    const { onSelect } = renderFlow();
    fireEvent.click(screen.getByRole('button', { name: 'Open Escalate' }));
    expect(onSelect).toHaveBeenCalledWith('escalate');
  });
});
