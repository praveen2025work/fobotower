import { render, screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import fixture from './__fixtures__/graph.json';
import { DecisionTree } from './DecisionTree';

describe('DecisionTree', () => {
  it('lists the named patterns, tried in order', () => {
    render(<DecisionTree decision={fixture.decision} reasoner="none" />);
    const items = screen.getAllByTestId('decision-pattern').map((li) => li.textContent);
    expect(items).toEqual(
      fixture.decision.patterns.map((p) => expect.stringContaining(p.code)),
    );
    expect(items[0]).toContain(fixture.decision.patterns[0].meaning);
  });

  it("shows a default verdict row's category name and FO/BO verdicts", () => {
    render(<DecisionTree decision={fixture.decision} reasoner="none" />);
    const row = screen.getByTestId('verdict-row-A');
    expect(within(row).getByText('Price break')).toBeInTheDocument();
    expect(within(row).getByText('DO_NOT_POST')).toBeInTheDocument();
    expect(within(row).getByText('POST')).toBeInTheDocument();
  });

  it('reads reasoner "none" as "a person"', () => {
    render(<DecisionTree decision={fixture.decision} reasoner="none" />);
    expect(screen.getByText(/a person — logged as Novel break/)).toBeInTheDocument();
  });

  it('names the reasoner in force when it is not "none"', () => {
    render(<DecisionTree decision={fixture.decision} reasoner="session_service" />);
    expect(screen.getByText(/session_service/)).toBeInTheDocument();
  });

  it('shows each pattern’s verdict where classify() sets a fixed one', () => {
    render(<DecisionTree decision={fixture.decision} reasoner="none" />);
    expect(screen.getByTestId('pattern-verdict-posting_failure')).toHaveTextContent(
      'CORRECT_AND_REPOST',
    );
    expect(screen.getByTestId('pattern-verdict-missing_price')).toHaveTextContent(
      'DO_NOT_POST',
    );
    expect(screen.getByTestId('pattern-verdict-side_double')).toHaveTextContent(
      'DO_NOT_POST',
    );
    expect(screen.getByTestId('pattern-verdict-reapplication')).toHaveTextContent('POST');
    expect(screen.getByTestId('pattern-verdict-single_cause')).toHaveTextContent(
      'from playbook default_verdicts',
    );
  });

  it('shows no verdict for missing_side — classify() does not set one', () => {
    render(<DecisionTree decision={fixture.decision} reasoner="none" />);
    expect(screen.queryByTestId('pattern-verdict-missing_side')).toBeNull();
  });

  it('marks a cause check that cannot settle a verdict (side UNKNOWN) with "→ reasoner"', () => {
    render(<DecisionTree decision={fixture.decision} reasoner="none" />);
    expect(screen.getByTestId('cause-check-C3')).toHaveTextContent('→ reasoner');
    expect(screen.getByTestId('cause-check-C4')).toHaveTextContent('→ reasoner');
  });

  it('does not mark a settling cause check with "→ reasoner"', () => {
    render(<DecisionTree decision={fixture.decision} reasoner="none" />);
    expect(screen.getByTestId('cause-check-C1')).not.toHaveTextContent('→ reasoner');
  });

  it('lists every way a break is unresolved and goes to the reasoner', () => {
    render(<DecisionTree decision={fixture.decision} reasoner="none" />);
    const items = screen.getAllByTestId('unresolved-when').map((li) => li.textContent);
    expect(items).toEqual(fixture.decision.unresolved_when);
  });

  it('lists the guards by id', () => {
    render(<DecisionTree decision={fixture.decision} reasoner="none" />);
    for (const g of fixture.decision.guards) {
      expect(screen.getByTestId(`guard-${g.id}`)).toHaveTextContent(g.id);
    }
  });

  it('shows where the decision logic is defined', () => {
    render(<DecisionTree decision={fixture.decision} reasoner="none" />);
    for (const path of fixture.decision.defined_in) {
      expect(screen.getByText(path)).toBeInTheDocument();
    }
  });
});
