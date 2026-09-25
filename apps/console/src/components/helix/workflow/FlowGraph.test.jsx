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

  // Read-only diagram: a node's own wrapper shouldn't be a second tab stop
  // next to its inner "Open <label>" button (nodesFocusable/edgesFocusable).
  it('exposes decided-by, pause and escalate info via aria-describedby (aria-label overrides the button’s own visible text for its accessible name)', () => {
    renderFlow();
    const resolveBtn = screen.getByRole('button', { name: 'Open Resolve books' });
    const descId = resolveBtn.getAttribute('aria-describedby');
    expect(descId).toBeTruthy();
    const desc = document.getElementById(descId);
    expect(desc).toHaveTextContent('Code');
    expect(desc).toHaveTextContent('can escalate');

    const reviewBtn = screen.getByRole('button', { name: 'Open Human sign-off' });
    const reviewDescId = reviewBtn.getAttribute('aria-describedby');
    expect(document.getElementById(reviewDescId)).toHaveTextContent('Pauses before');
  });

  it('exposes the Escalate node’s reason codes via aria-describedby too', () => {
    renderFlow();
    const escBtn = screen.getByRole('button', { name: 'Open Escalate' });
    const descId = escBtn.getAttribute('aria-describedby');
    expect(descId).toBeTruthy();
    const desc = document.getElementById(descId);
    expect(desc).toHaveTextContent('UNRESOLVED_BOOK');
    expect(desc).toHaveTextContent('DELTA_UNAVAILABLE');
  });

  it('gives each node exactly one tab stop — the inner button, not React Flow’s own node wrapper', () => {
    const { container } = renderFlow();
    // eslint-disable-next-line testing-library/no-node-access
    const wrappers = container.querySelectorAll('[data-testid^="rf__node-"]');
    expect(wrappers.length).toBeGreaterThan(0);
    for (const wrapper of wrappers) {
      expect(wrapper).not.toHaveAttribute('tabindex');
    }
  });

});
