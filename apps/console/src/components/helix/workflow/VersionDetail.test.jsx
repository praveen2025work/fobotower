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
  fetchVersionYaml: vi.fn(),
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

  it('opens the Approve dialog without throwing when crypto.randomUUID is unavailable', async () => {
    // Absent outside a secure context (plain HTTP on a non-localhost
    // origin) — an own, undefined property shadows the inherited method,
    // same as the browser leaves it in that context.
    const original = globalThis.crypto.randomUUID;
    Object.defineProperty(globalThis.crypto, 'randomUUID', { value: undefined, configurable: true });
    try {
      api.approveVersion.mockResolvedValue({ number: 4, status: 'active' });
      const { onChanged } = renderDetail(ASHA);
      await userEvent.click(await screen.findByRole('button', { name: 'Approve' }));
      const dialog = screen.getByRole('dialog');
      for (const box of within(dialog).getAllByRole('checkbox')) await userEvent.click(box);
      await userEvent.click(within(dialog).getByRole('button', { name: 'Approve and activate' }));
      expect(api.approveVersion).toHaveBeenCalledWith(4, expect.any(String));
      expect(api.approveVersion.mock.calls[0][1].length).toBeGreaterThan(0);
      expect(onChanged).toHaveBeenCalled();
    } finally {
      Object.defineProperty(globalThis.crypto, 'randomUUID', { value: original, configurable: true });
    }
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

  describe('YAML tab', () => {
    const V4_YAML = '# header v4\n#\nversion: 4\nname: fobo-investigation\n';
    const V3_YAML = '# header v3\n#\nversion: 3\nname: fobo-investigation\n';

    it('shows the Changes tab by default, without loading any YAML', async () => {
      renderDetail();
      expect(await screen.findByRole('tab', { name: 'Changes' })).toHaveAttribute('aria-selected', 'true');
      expect(screen.getByRole('tab', { name: 'YAML' })).toHaveAttribute('aria-selected', 'false');
      expect(screen.getByText('gather.priors_lookback_days: 180 → 90')).toBeInTheDocument();
      expect(api.fetchVersionYaml).not.toHaveBeenCalled();
    });

    it('loads the YAML lazily on first open, once', async () => {
      api.fetchVersionYaml.mockResolvedValue(V4_YAML);
      renderDetail();
      await userEvent.click(await screen.findByRole('tab', { name: 'YAML' }));
      expect(await screen.findByText('fobo-investigation')).toBeInTheDocument();
      expect(api.fetchVersionYaml).toHaveBeenCalledWith(4);
      expect(api.fetchVersionYaml).toHaveBeenCalledTimes(1);
      // Switching away and back does not reload it.
      await userEvent.click(screen.getByRole('tab', { name: 'Changes' }));
      await userEvent.click(screen.getByRole('tab', { name: 'YAML' }));
      expect(api.fetchVersionYaml).toHaveBeenCalledTimes(1);
    });

    it('offers Diff vs active vN for a draft, loading the active version’s YAML too', async () => {
      api.fetchVersionYaml.mockImplementation((n) => Promise.resolve(n === 4 ? V4_YAML : V3_YAML));
      renderDetail();
      await userEvent.click(await screen.findByRole('tab', { name: 'YAML' }));
      await screen.findByText('fobo-investigation');
      await userEvent.click(screen.getByRole('button', { name: 'Diff vs active v3' }));
      expect(await screen.findByText('version: 4')).toBeInTheDocument();
      expect(screen.getByText('version: 3')).toBeInTheDocument();
      expect(api.fetchVersionYaml).toHaveBeenCalledWith(3);
      expect(api.fetchVersionYaml).toHaveBeenCalledWith(4);
    });

    it('shows Retry when the YAML fails to load', async () => {
      api.fetchVersionYaml.mockRejectedValueOnce(new Error('boom')).mockResolvedValueOnce(V4_YAML);
      renderDetail();
      await userEvent.click(await screen.findByRole('tab', { name: 'YAML' }));
      expect(await screen.findByRole('alert')).toHaveTextContent('boom');
      await userEvent.click(screen.getByRole('button', { name: 'Retry' }));
      expect(await screen.findByText('fobo-investigation')).toBeInTheDocument();
      expect(api.fetchVersionYaml).toHaveBeenCalledTimes(2);
    });

    it('returns to the Changes tab when the reviewed number changes', async () => {
      api.fetchVersionYaml.mockResolvedValue(V4_YAML);
      const v6 = draft({ number: 6, active_number: 6, based_on: 6 });
      api.fetchVersion.mockResolvedValueOnce(draft()).mockResolvedValueOnce(v6);
      const props = { onChanged: vi.fn(), onRedraft: vi.fn() };
      const { rerender } = render(<VersionDetail number={4} caller={ASHA} {...props} />);
      await userEvent.click(await screen.findByRole('tab', { name: 'YAML' }));
      expect(await screen.findByText('fobo-investigation')).toBeInTheDocument();
      rerender(<VersionDetail number={6} caller={ASHA} {...props} />);
      expect(await screen.findByRole('tab', { name: 'Changes' })).toHaveAttribute('aria-selected', 'true');
      expect(screen.getByRole('tab', { name: 'YAML' })).toHaveAttribute('aria-selected', 'false');
    });
  });
});
