import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import fixture from './__fixtures__/graph.json';
import { FlowGraph } from './FlowGraph';

const renderFlow = (props = {}) => {
  const onSelect = vi.fn();
  render(<FlowGraph graph={fixture} reasoner="none" onSelect={onSelect} {...props} />);
  return { onSelect };
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

  it('renders the legend', () => {
    renderFlow();
    expect(screen.getByText(/solid = next step/)).toBeInTheDocument();
    expect(screen.getByText(/red dashed = if escalated/)).toBeInTheDocument();
    expect(screen.getByText(/amber = waits for a controller/)).toBeInTheDocument();
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
