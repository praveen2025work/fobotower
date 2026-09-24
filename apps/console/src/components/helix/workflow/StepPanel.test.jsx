import { render, screen } from '@testing-library/react';
import { expect, it, vi } from 'vitest';
import fixture from './__fixtures__/workflow.json';
import { StepPanel } from './StepPanel';

const step = (name) => fixture.steps.find((s) => s.name === name);
const renderPanel = (name) =>
  render(
    <StepPanel
      step={step(name)}
      config={fixture.active.config}
      schema={fixture.settings_schema}
      reasoner="none"
      onClose={vi.fn()}
    />,
  );

it('shows a step’s settings with their meaning', () => {
  renderPanel('gather');
  expect(screen.getByText('priors lookback days')).toBeInTheDocument();
  expect(screen.getByText('180')).toBeInTheDocument();
  expect(screen.getByText(/How far back to look/)).toBeInTheDocument();
});

it('shows the session service settings with the playbook step', () => {
  renderPanel('reason');
  expect(screen.getByText('timeout seconds')).toBeInTheDocument();
});

it('says why a locked step cannot be removed', () => {
  renderPanel('review');
  expect(screen.getByText("Why it can't be removed")).toBeInTheDocument();
  expect(screen.getByText(/no decision is recorded without a person/)).toBeInTheDocument();
});
