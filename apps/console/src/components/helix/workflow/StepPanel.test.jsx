import { render, screen } from '@testing-library/react';
import { expect, it, vi } from 'vitest';
import graphFixture from './__fixtures__/graph.json';
import fixture from './__fixtures__/workflow.json';
import { StepPanel } from './StepPanel';

const step = (name) => fixture.steps.find((s) => s.name === name);
const renderPanel = (name, extra = {}) =>
  render(
    <StepPanel
      step={step(name)}
      config={fixture.active.config}
      schema={fixture.settings_schema}
      reasoner="none"
      onClose={vi.fn()}
      {...extra}
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

it('has no "How it decides" section without a graph', () => {
  renderPanel('gather');
  expect(screen.queryByText('How it decides')).toBeNull();
});

it('shows gather’s escalation codes with their conditions and where it is defined', () => {
  renderPanel('gather', { graph: graphFixture });
  expect(screen.getByText('How it decides')).toBeInTheDocument();
  const { escalates_when: escalatesWhen, defined_in: definedIn } = graphFixture.logic.gather;
  expect(escalatesWhen).toHaveLength(2);
  for (const { code, when } of escalatesWhen) {
    const row = screen.getByTestId(`escalates-${code}`);
    expect(row).toHaveTextContent(code);
    expect(row).toHaveTextContent(when);
  }
  expect(screen.getByText(definedIn)).toBeInTheDocument();
  expect(screen.getByText(graphFixture.router.rule)).toBeInTheDocument();
});

it('shows the decision tree for the Apply playbook step', () => {
  renderPanel('reason', { graph: graphFixture });
  expect(screen.getByText(/Named patterns, tried in order/)).toBeInTheDocument();
  expect(screen.getByTestId('verdict-row-A')).toBeInTheDocument();
});
