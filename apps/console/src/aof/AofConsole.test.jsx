import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import * as api from './api';
import AofConsole from './AofConsole';

vi.mock('./api', () => ({
  currentUser: vi.fn(),
  setCurrentUser: vi.fn(),
  fetchDevUsers: vi.fn(),
  fetchCapabilities: vi.fn(),
  fetchCases: vi.fn(),
  openCase: vi.fn(),
  fetchCase: vi.fn(),
  decide: vi.fn(),
}));

const capability = {
  id: 'fin.variance-commentary',
  name: 'P&L variance commentary',
  description: 'Month-end commentary',
  version: 1,
  case_label: 'Lane',
  item_label: 'Variance line',
  case_key: ['entity', 'period'],
  steps: ['load', 'group', 'reason', 'draft', 'validate', 'review', 'record'],
};

const group = (decision = null) => ({
  group_id: '6100',
  label: 'account 6100',
  group_key: { account: '6100' },
  item_ids: ['L1'],
  priors: [],
  finding: { status: 'proposed', decided_by: 'llm:stub', comment: 'Salaries up 66,353.03.' },
  decision,
});

const caseDetail = (overrides = {}) => ({
  case_id: 'fin.variance-commentary.abc',
  subject: 'UK01 · 2026-09',
  status: 'awaiting_review',
  manifest_version: 1,
  opened_by: 'alice',
  trace_id: null,
  draft: { headline: '1 of 2 variance line(s) in scope' },
  labels: { case: 'Lane', item: 'Variance line' },
  columns: ['account', 'variance'],
  items: [
    { item_id: 'L1', in_scope: true, account: '6100', variance: 66353.03 },
    { item_id: 'L2', in_scope: false, account: '6200', variance: 10 },
  ],
  groups: [group()],
  tool_calls: [
    { call_id: 'c1', tool: 'gl.balances', requested_by: 'load', arguments: { entity: 'UK01' },
      allowed: true, row_count: 2, latency_ms: 12 },
    { call_id: 'c2', tool: 'ledger.postings', requested_by: 'llm', arguments: {},
      allowed: false, denied_reason: 'not allowed for capability' },
  ],
  can_decide: true,
  ...overrides,
});

beforeEach(() => {
  vi.clearAllMocks();
  api.currentUser.mockReturnValue('alice');
  api.fetchDevUsers.mockResolvedValue([{ user_id: 'alice', name: 'Alice' }, { user_id: 'bob', name: 'Bob' }]);
  api.fetchCapabilities.mockResolvedValue([capability]);
  api.fetchCases.mockResolvedValue([]);
});

describe('AofConsole', () => {
  it('lists the capabilities the user may use and builds the open form from the case key', async () => {
    render(<AofConsole />);
    expect(await screen.findByRole('heading', { name: 'P&L variance commentary' })).toBeInTheDocument();
    expect(screen.getByLabelText('entity')).toBeInTheDocument();
    expect(screen.getByLabelText('period')).toBeInTheDocument();
    expect(await screen.findByText(/No lanes yet/)).toBeInTheDocument();
  });

  it('says so when the user has no capabilities', async () => {
    api.fetchCapabilities.mockResolvedValue([]);
    render(<AofConsole />);
    expect(await screen.findByText(/No capabilities for this user/)).toBeInTheDocument();
  });

  it('opens a case and shows proposals, in-scope items and refused calls', async () => {
    api.openCase.mockResolvedValue(caseDetail());
    api.fetchCase.mockResolvedValue(caseDetail());
    render(<AofConsole />);
    await userEvent.type(await screen.findByLabelText('entity'), 'UK01');
    await userEvent.type(screen.getByLabelText('period'), '2026-09');
    await userEvent.click(screen.getByRole('button', { name: 'Open and run' }));

    expect(api.openCase).toHaveBeenCalledWith('fin.variance-commentary', { entity: 'UK01', period: '2026-09' });
    expect(await screen.findByText('Salaries up 66,353.03.')).toBeInTheDocument();
    expect(screen.getByText('Variance lines (1 of 2)')).toBeInTheDocument();
    expect(screen.getByText(/refused: not allowed for capability/)).toBeInTheDocument();
  });

  it('records a decision with an idempotency key and shows who approved', async () => {
    api.fetchCases.mockResolvedValue([{ case_id: 'fin.variance-commentary.abc', subject: 'UK01 · 2026-09', status: 'awaiting_review' }]);
    api.fetchCase.mockResolvedValue(caseDetail());
    api.decide.mockResolvedValue({
      case: caseDetail({ status: 'completed', can_decide: false,
        groups: [group({ action: 'approve', decided_by: 'alice', comment: 'agreed' })] }),
    });
    render(<AofConsole />);
    await userEvent.click(await screen.findByRole('button', { name: /UK01 · 2026-09/ }));
    const card = (await screen.findByText('Salaries up 66,353.03.')).closest('article');
    await userEvent.type(within(card).getByLabelText('Comment on account 6100'), 'agreed');
    await userEvent.click(within(card).getByRole('button', { name: 'Approve' }));

    await waitFor(() => expect(api.decide).toHaveBeenCalled());
    const [caseId, body] = api.decide.mock.calls[0];
    expect(caseId).toBe('fin.variance-commentary.abc');
    expect(body).toMatchObject({ groupId: '6100', action: 'approve', comment: 'agreed' });
    expect(body.idempotencyKey).toBeTruthy();
    expect(await screen.findByText('Approved by alice: agreed')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Approve' })).not.toBeInTheDocument();
  });

  it('shows the server problems when opening fails', async () => {
    const err = new Error('alice is not entitled to entity=US01');
    err.problems = [];
    api.openCase.mockRejectedValue(err);
    render(<AofConsole />);
    await userEvent.type(await screen.findByLabelText('entity'), 'US01');
    await userEvent.type(screen.getByLabelText('period'), '2026-09');
    await userEvent.click(screen.getByRole('button', { name: 'Open and run' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('not entitled to entity=US01');
  });
});
