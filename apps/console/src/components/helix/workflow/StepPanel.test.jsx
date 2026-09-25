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

it('labels the definition path "Defined in" for a step that cannot escalate', () => {
  renderPanel('group', { graph: graphFixture });
  expect(screen.getByTestId('step-defined-in')).toHaveTextContent(
    `Defined in: ${graphFixture.logic.group.defined_in}`,
  );
});

it('does not prefix the definition path for a step that can escalate (context already says so)', () => {
  renderPanel('gather', { graph: graphFixture });
  expect(screen.getByTestId('step-defined-in')).toHaveTextContent(
    graphFixture.logic.gather.defined_in,
  );
  expect(screen.getByTestId('step-defined-in')).not.toHaveTextContent('Defined in:');
});

// --- Escalate: a pseudo-step with no entry in the step catalogue (see
// WorkflowView.jsx's `known[panel] || ESCALATE_STEP` fallback) -------------

const ESCALATE_STEP = {
  name: 'escalate',
  label: 'Escalate',
  description: 'Ends the run with a reason code',
  decided_by: 'code',
  removable: false,
  required_because: null,
  can_escalate: false,
  needs: [],
  produces: [],
  must_follow: [],
};

it('groups the Escalate panel’s reason codes by the step that raises them', () => {
  renderPanel('escalate', { graph: graphFixture, step: ESCALATE_STEP });
  for (const group of graphFixture.logic.escalate.raised_by) {
    for (const code of group.codes) {
      const row = screen.getByTestId(`escalate-reason-${code}`);
      expect(row).toHaveTextContent(code);
    }
  }
  // Grouped under their step's label, e.g. resolve's codes under "Resolve books".
  expect(screen.getByText('Resolve books')).toBeInTheDocument();
  expect(screen.getByText('Gather evidence')).toBeInTheDocument();
});

it('does not list a reason code no configured step raises as if it were reachable', () => {
  renderPanel('escalate', { graph: graphFixture, step: ESCALATE_STEP });
  for (const code of graphFixture.logic.escalate.other_known) {
    expect(screen.queryByTestId(`escalate-reason-${code}`)).toBeNull();
  }
});

it('separately, de-emphasised, lists codes accepted by escalate() but unreachable in this workflow', () => {
  renderPanel('escalate', { graph: graphFixture, step: ESCALATE_STEP });
  const note = screen.getByTestId('escalate-other-known');
  for (const code of graphFixture.logic.escalate.other_known) {
    expect(note).toHaveTextContent(code);
  }
  expect(note).toHaveTextContent('not raised by any step in this workflow');
});

it('shows where escalate() is defined', () => {
  renderPanel('escalate', { graph: graphFixture, step: ESCALATE_STEP });
  expect(screen.getByText(graphFixture.logic.escalate.defined_in)).toBeInTheDocument();
});

it('hides Needs, Produces and the settings message for the Escalate pseudo-step', () => {
  renderPanel('escalate', { graph: graphFixture, step: ESCALATE_STEP });
  expect(screen.queryByText('Needs')).toBeNull();
  expect(screen.queryByText('Produces')).toBeNull();
  expect(screen.queryByText('This step has no settings.')).toBeNull();
});
