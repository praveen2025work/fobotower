import { render, screen, within } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import PipelineRail from './PipelineRail';

const STAGES = [
  { key: 'mbr', label: 'MBR / Rec Factory', sub: 'CATS ↔ MOTIF breaks' },
  {
    key: 'analysis',
    label: 'FOBO Agent Analysis',
    sub: 'Manual / Auto adjustments',
  },
  { key: 'signoff', label: 'Human Sign-off', sub: 'Reviewed & approved' },
  { key: 'post', label: 'Post to MOTIF', sub: 'via FAS' },
  { key: 'notify', label: 'Notify P&L Agent', sub: 'Book Unlocked' },
];

const COUNTS = { auto_posted: 3, awaiting_signoff: 9, not_open: 2 };

function renderRail(overrides = {}) {
  return render(
    <PipelineRail
      stages={STAGES}
      currentStage="signoff"
      counts={COUNTS}
      {...overrides}
    />,
  );
}

describe('PipelineRail', () => {
  it('renders every stage with its subtitle', () => {
    renderRail();
    expect(screen.getByText('MBR / Rec Factory')).toBeInTheDocument();
    expect(screen.getByText('via FAS')).toBeInTheDocument();
  });

  it('marks stages before the current one as complete', () => {
    renderRail();
    expect(screen.getByLabelText('MBR / Rec Factory: complete')).toBeInTheDocument();
    expect(
      screen.getByLabelText('FOBO Agent Analysis: complete'),
    ).toBeInTheDocument();
  });

  it('marks the current stage as active', () => {
    renderRail();
    expect(screen.getByLabelText('Human Sign-off: active')).toBeInTheDocument();
  });

  it('marks later stages as pending', () => {
    renderRail();
    expect(screen.getByLabelText('Post to MOTIF: pending')).toBeInTheDocument();
    expect(screen.getByLabelText('Notify P&L Agent: pending')).toBeInTheDocument();
  });

  it('shows the stacked progress legend with its counts', () => {
    renderRail();
    const legend = screen.getByRole('list', { name: 'Book status' });
    expect(within(legend).getByText('3')).toBeInTheDocument();
    expect(within(legend).getByText('auto-posted')).toBeInTheDocument();
    expect(within(legend).getByText('9')).toBeInTheDocument();
    expect(within(legend).getByText('awaiting sign-off')).toBeInTheDocument();
    expect(within(legend).getByText('2')).toBeInTheDocument();
    expect(within(legend).getByText('not open yet')).toBeInTheDocument();
  });

  it('renders a zero count rather than omitting the segment from the legend', () => {
    renderRail({ counts: { auto_posted: 0, awaiting_signoff: 14, not_open: 0 } });
    const legend = screen.getByRole('list', { name: 'Book status' });
    expect(within(legend).getAllByText('0')).toHaveLength(2);
  });

  it('survives a currentStage it does not recognise', () => {
    renderRail({ currentStage: 'nonsense' });
    expect(screen.getByLabelText('MBR / Rec Factory: pending')).toBeInTheDocument();
  });
});
