import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import fixture from './__fixtures__/workflow.json';
import { WorkflowGraph } from './WorkflowGraph';

const renderGraph = (props = {}) => {
  const handlers = { onSelect: vi.fn(), onChange: vi.fn() };
  render(
    <WorkflowGraph
      config={fixture.active.config}
      catalogue={fixture.steps}
      reasoner="none"
      {...handlers}
      {...props}
    />,
  );
  return handlers;
};

const card = (name) =>
  screen.getAllByTestId('step-card').find((c) => c.dataset.step === name);

describe('WorkflowGraph', () => {
  it('draws the configured steps in order', () => {
    renderGraph();
    expect(screen.getAllByTestId('step-card').map((c) => c.dataset.step)).toEqual(
      fixture.active.config.steps,
    );
  });

  it('tags each step with who decides it', () => {
    renderGraph();
    expect(within(card('reason')).getByText('Playbook')).toBeInTheDocument();
    expect(within(card('reason')).getByText('Reasoner: none')).toBeInTheDocument();
    expect(within(card('review')).getByText('Human')).toBeInTheDocument();
  });

  it('marks locked steps and says why', () => {
    renderGraph();
    expect(within(card('validate')).getByLabelText(/Cannot be removed/)).toBeInTheDocument();
    expect(within(card('rank')).queryByLabelText(/Cannot be removed/)).toBeNull();
  });

  it('shows where the run pauses and which steps can escalate', () => {
    renderGraph();
    expect(screen.getByLabelText('Pauses before review')).toBeInTheDocument();
    const escalate = screen.getByTestId('escalate');
    expect(within(escalate).getByText(/Resolve books/)).toBeInTheDocument();
    expect(within(escalate).getByText(/Gather evidence/)).toBeInTheDocument();
  });

  it('opens a step when its card is clicked', async () => {
    const { onSelect } = renderGraph();
    await userEvent.click(screen.getByRole('button', { name: 'Open Apply playbook' }));
    expect(onSelect).toHaveBeenCalledWith('reason');
  });

  it('in edit mode, toggles a pause, removes and moves steps', async () => {
    const { onChange } = renderGraph({ editing: true });
    await userEvent.click(screen.getByRole('button', { name: 'Pause before reason' }));
    expect(onChange.mock.lastCall[0].pause_before).toEqual(['review', 'reason']);
    await userEvent.click(screen.getByRole('button', { name: 'Remove rank' }));
    expect(onChange.mock.lastCall[0].steps).not.toContain('rank');
    await userEvent.click(screen.getByRole('button', { name: 'Move rank earlier' }));
    expect(onChange.mock.lastCall[0].steps.slice(3, 5)).toEqual(['rank', 'reason']);
  });

  it('shows a validation error on the step it names', () => {
    renderGraph({ errors: ["steps: 'draft' needs 'pattern_groups' before it runs"] });
    expect(within(card('draft')).getByRole('alert')).toHaveTextContent('pattern_groups');
  });

  it('attributes an error to its subject even when the message quotes another step', () => {
    renderGraph({
      errors: ["steps: 'validate' needs 'draft' before it runs — produced by draft"],
    });
    expect(within(card('validate')).getByRole('alert')).toBeInTheDocument();
    expect(within(card('draft')).queryByRole('alert')).toBeNull();
  });

  it('draws an unknown step instead of failing', () => {
    const config = { ...fixture.active.config, steps: [...fixture.active.config.steps, 'mystery'] };
    renderGraph({ config });
    expect(within(card('mystery')).getByText('Not a known step')).toBeInTheDocument();
  });
});
