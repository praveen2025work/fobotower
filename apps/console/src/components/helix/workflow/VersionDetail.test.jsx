import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import * as api from '../data/workflowApi';
import { VersionDetail } from './VersionDetail';

vi.mock('../data/workflowApi', () => ({
  fetchVersion: vi.fn(),
  fetchRebased: vi.fn(),
  approveVersion: vi.fn(),
  rejectVersion: vi.fn(),
  downloadYaml: vi.fn(),
}));

const PRAVEEN = { id: 'praveen', roles: ['FO', 'PC'] };
const ASHA = { id: 'asha', roles: ['PC'] };

const draft = (over = {}) => ({
  number: 4,
  status: 'draft',
  note: 'Lookback 180→90 days',
  based_on: 3,
  active_number: 3,
  drafted_by: 'praveen',
  drafted_at: '2026-09-24T14:02:00+00:00',
  decided_by: null,
  decided_at: null,
  reject_reason: null,
  diff: [
    { path: 'settings.gather.priors_lookback_days', kind: 'changed', before: 180, after: 90 },
    { path: 'steps.rank', kind: 'removed', before: 4, after: null },
    { path: 'pause_before.reason', kind: 'added', before: null, after: null },
  ],
  ...over,
});

const renderDetail = (caller = ASHA, version = draft()) => {
  api.fetchVersion.mockResolvedValue(version);
  const props = { onChanged: vi.fn(), onRedraft: vi.fn() };
  render(<VersionDetail number={version.number} caller={caller} {...props} />);
  return props;
};

beforeEach(() => vi.clearAllMocks());

describe('VersionDetail', () => {
  it('reads every change against the active version', async () => {
    renderDetail();
    expect(await screen.findByText('gather.priors_lookback_days: 180 → 90')).toBeInTheDocument();
    expect(screen.getByText('rank removed (was step 5)')).toBeInTheDocument();
    expect(screen.getByText('pause added before reason')).toBeInTheDocument();
  });

  it('will not let the drafter approve their own draft', async () => {
    renderDetail(PRAVEEN);
    expect(await screen.findByRole('button', { name: 'Approve' })).toBeDisabled();
    expect(screen.getByText('A second PC user must approve')).toBeInTheDocument();
  });

  it('approves only after both confirmations, with one key per confirmation', async () => {
    api.approveVersion.mockResolvedValue({ number: 4, status: 'active' });
    const { onChanged } = renderDetail(ASHA);
    await userEvent.click(await screen.findByRole('button', { name: 'Approve' }));
    const dialog = screen.getByRole('dialog');
    const confirm = within(dialog).getByRole('button', { name: 'Approve and activate' });
    expect(confirm).toBeDisabled();
    for (const box of within(dialog).getAllByRole('checkbox')) await userEvent.click(box);
    await userEvent.click(confirm);
    expect(api.approveVersion).toHaveBeenCalledWith(4, expect.any(String));
    expect(onChanged).toHaveBeenCalled();
  });

  it('keeps the dialog open with the server’s reason when approval fails', async () => {
    api.approveVersion.mockRejectedValue(new Error('v5 went live after this was drafted'));
    renderDetail(ASHA);
    await userEvent.click(await screen.findByRole('button', { name: 'Approve' }));
    const dialog = screen.getByRole('dialog');
    for (const box of within(dialog).getAllByRole('checkbox')) await userEvent.click(box);
    await userEvent.click(within(dialog).getByRole('button', { name: 'Approve and activate' }));
    expect(await within(dialog).findByText(/went live/)).toBeInTheDocument();
  });

  it('offers a redraft for a stale draft instead of approval', async () => {
    api.fetchRebased.mockResolvedValue({ config: { steps: [] }, based_on: 5, conflicts: ['steps'], errors: [] });
    const { onRedraft } = renderDetail(ASHA, draft({ active_number: 5 }));
    expect(await screen.findByText('v5 went live after this was drafted.')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Approve' })).toBeNull();
    await userEvent.click(screen.getByRole('button', { name: 'Redraft on v5' }));
    expect(onRedraft).toHaveBeenCalledWith({ config: { steps: [] }, basedOn: 5, conflicts: ['steps'] });
  });

  it('requires a reason to reject', async () => {
    api.rejectVersion.mockResolvedValue({ number: 4, status: 'rejected' });
    const { onChanged } = renderDetail(ASHA);
    await userEvent.click(await screen.findByRole('button', { name: 'Reject' }));
    const dialog = screen.getByRole('dialog');
    const confirm = within(dialog).getByRole('button', { name: 'Reject draft' });
    expect(confirm).toBeDisabled();
    await userEvent.type(within(dialog).getByLabelText('Reason'), 'too aggressive');
    await userEvent.click(confirm);
    expect(api.rejectVersion).toHaveBeenCalledWith(4, 'too aggressive');
    expect(onChanged).toHaveBeenCalled();
  });

  it('says so when a version is the active one', async () => {
    renderDetail(ASHA, draft({ number: 3, status: 'active', diff: [] }));
    expect(await screen.findByText('This is the active version.')).toBeInTheDocument();
  });

  it('drops a stale dialog when the reviewed number changes under it', async () => {
    const v6 = draft({ number: 6, active_number: 6, based_on: 6 });
    api.fetchVersion.mockResolvedValueOnce(draft()).mockResolvedValueOnce(v6);
    const props = { onChanged: vi.fn(), onRedraft: vi.fn() };
    const { rerender } = render(<VersionDetail number={4} caller={ASHA} {...props} />);
    await userEvent.click(await screen.findByRole('button', { name: 'Approve' }));
    expect(screen.getByRole('dialog')).toBeInTheDocument();
    rerender(<VersionDetail number={6} caller={ASHA} {...props} />);
    expect(screen.queryByRole('dialog')).toBeNull();
    expect(api.approveVersion).not.toHaveBeenCalled();
  });

  it('cannot be cancelled while the approval request is in flight', async () => {
    let resolveApprove;
    api.approveVersion.mockReturnValue(
      new Promise((resolve) => {
        resolveApprove = resolve;
      }),
    );
    const { onChanged } = renderDetail(ASHA);
    await userEvent.click(await screen.findByRole('button', { name: 'Approve' }));
    const dialog = screen.getByRole('dialog');
    for (const box of within(dialog).getAllByRole('checkbox')) await userEvent.click(box);
    await userEvent.click(within(dialog).getByRole('button', { name: 'Approve and activate' }));
    expect(within(dialog).getByRole('button', { name: 'Cancel' })).toBeDisabled();
    await userEvent.keyboard('{Escape}');
    expect(screen.getByRole('dialog')).toBeInTheDocument();
    resolveApprove({ number: 4, status: 'active' });
    await waitFor(() => expect(onChanged).toHaveBeenCalledTimes(1));
  });
});
