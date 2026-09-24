import { render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import * as api from '../data/helixApi';
import { WorkflowTraceDrawer } from './WorkflowTraceDrawer';

vi.mock('../data/helixApi', () => ({ fetchTrace: vi.fn() }));

const REC = { id: 'R-1055', name: 'CATS vs MOTIF — Prime' };

const TRACE = {
  state: 'open',
  trace: {
    thread_id: 'sess-r-1055',
    workflow_version: '1.0',
    checkpoints: 9,
    total_ms: 158,
    status: 'awaiting_signoff',
    parked_at: 'review',
    escalation_reason: null,
    steps: [
      {
        node: 'reason',
        label: 'Apply playbook',
        description: 'Settle by rule; route the rest to the reasoner',
        status: 'done',
        duration_ms: 51,
        produced: ['determinism', 'findings'],
        summary: '14 of 14 settled by playbook · 0 need judgement',
      },
      {
        node: 'review',
        label: 'Human sign-off',
        description: 'Controller approves or rejects',
        status: 'waiting',
        summary: 'awaiting controller sign-off',
      },
    ],
  },
};

beforeEach(() => vi.clearAllMocks());

describe('WorkflowTraceDrawer', () => {
  it('lists the graph steps from the checkpoints and where it is parked', async () => {
    api.fetchTrace.mockResolvedValue(TRACE);
    render(<WorkflowTraceDrawer rec={REC} onClose={() => {}} />);
    expect(
      await screen.findByText('14 of 14 settled by playbook · 0 need judgement'),
    ).toBeInTheDocument();
    expect(screen.getByText(/Paused before "review"/)).toBeInTheDocument();
    expect(screen.getByText('Done · 51 ms')).toBeInTheDocument();
    expect(screen.getByText('Waiting')).toBeInTheDocument();
    expect(screen.getByText('findings')).toBeInTheDocument();
    expect(api.fetchTrace).toHaveBeenCalledWith('R-1055');
  });

  it('says plainly when no investigation has run', async () => {
    api.fetchTrace.mockResolvedValue({ state: 'clear', trace: null });
    render(<WorkflowTraceDrawer rec={REC} onClose={() => {}} />);
    expect(
      await screen.findByText(/No investigation has run/),
    ).toBeInTheDocument();
  });

  it('shows the error when the trace cannot be read', async () => {
    api.fetchTrace.mockRejectedValue(new Error('GET failed: 503'));
    render(<WorkflowTraceDrawer rec={REC} onClose={() => {}} />);
    expect(await screen.findByText(/could not be loaded: GET failed: 503/)).toBeInTheDocument();
  });
});
