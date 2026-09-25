import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import * as api from '../data/workflowApi';
import fixture from './__fixtures__/workflow.json';
import { WorkflowView } from './WorkflowView';

vi.mock('../data/workflowApi', () => ({
  fetchWorkflow: vi.fn(),
  fetchVersions: vi.fn(),
  fetchVersion: vi.fn(),
  fetchRebased: vi.fn(),
  validateWorkflow: vi.fn(),
  saveDraft: vi.fn(),
  uploadYaml: vi.fn(),
  approveVersion: vi.fn(),
  rejectVersion: vi.fn(),
  downloadYaml: vi.fn(),
}));

const history = [
  { number: 5, status: 'draft', note: 'drop rank', based_on: 3, drafted_by: 'asha' },
  { number: 4, status: 'draft', note: 'pause before reason', based_on: 3, drafted_by: 'praveen' },
  { number: 3, status: 'active', note: 'Lookback 180→90 days', based_on: 2, drafted_by: 'praveen' },
];

const overview = (over = {}) => ({ ...structuredClone(fixture), ...over });

beforeEach(() => {
  vi.clearAllMocks();
  api.fetchWorkflow.mockResolvedValue(overview());
  api.fetchVersions.mockResolvedValue(history);
  api.fetchVersion.mockImplementation(async (n) => ({
    ...history.find((v) => v.number === n),
    active_number: 3,
    diff: [],
    drafted_at: '2026-09-24T14:02:00+00:00',
  }));
  api.validateWorkflow.mockResolvedValue({ ok: true, errors: [] });
});

describe('WorkflowView', () => {
  it('shows the active version, the pending drafts and the graph', async () => {
    render(<WorkflowView callerKey="praveen" />);
    expect(await screen.findByText('Workflow v3')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '2 drafts awaiting approval' })).toBeInTheDocument();
    expect(screen.getAllByTestId('step-card')).toHaveLength(fixture.active.config.steps.length);
  });

  it('opens the first pending draft', async () => {
    render(<WorkflowView callerKey="praveen" />);
    expect(await screen.findByRole('region', { name: 'Version 5' })).toBeInTheDocument();
  });

  it('warns when the server overrides the approved reasoner', async () => {
    api.fetchWorkflow.mockResolvedValue(overview({ overrides: { reasoner: 'direct' } }));
    render(<WorkflowView callerKey="praveen" />);
    expect(await screen.findByText(/overridden to/)).toHaveTextContent('direct');
  });

  it('starts a draft from the active version', async () => {
    render(<WorkflowView callerKey="praveen" />);
    await userEvent.click(await screen.findByRole('button', { name: 'New draft' }));
    expect(screen.getByRole('region', { name: 'Draft editor' })).toHaveTextContent('based on v3');
  });

  it('does not offer drafting to a caller without Product Control', async () => {
    api.fetchWorkflow.mockResolvedValue(overview({ caller: { id: 'fo-user', roles: ['FO'] } }));
    render(<WorkflowView callerKey="fo-user" />);
    expect(await screen.findByRole('button', { name: 'New draft' })).toBeDisabled();
  });

  it('offers a retry when the workflow cannot be loaded', async () => {
    api.fetchWorkflow.mockRejectedValueOnce(new Error('GET /api/workflow failed: 500'));
    render(<WorkflowView callerKey="praveen" />);
    await userEvent.click(await screen.findByRole('button', { name: 'Retry' }));
    expect(await screen.findByText('Workflow v3')).toBeInTheDocument();
  });

  it('loads a redrafted config into an editor that is already open, even onto the same base version', async () => {
    // A stale draft (based on v2) next to the current active v3 — the same
    // base an already-open "New draft" (based on v3) editor carries, so a
    // remount can't be told apart by base version alone.
    api.fetchVersion.mockImplementation(async (n) => ({
      ...history.find((v) => v.number === n),
      based_on: 2,
      active_number: 3,
      diff: [],
      drafted_at: '2026-09-24T14:02:00+00:00',
    }));
    const rebased = {
      ...fixture.active.config,
      settings: {
        ...fixture.active.config.settings,
        gather: { ...fixture.active.config.settings.gather, priors_lookback_days: 45 },
      },
    };
    api.fetchRebased.mockResolvedValue({ config: rebased, based_on: 3, conflicts: [] });
    render(<WorkflowView callerKey="praveen" />);
    await userEvent.click(await screen.findByRole('button', { name: 'New draft' }));
    expect(screen.getByRole('region', { name: 'Draft editor' })).toHaveTextContent('based on v3');

    await userEvent.click(await screen.findByRole('button', { name: 'Redraft on v3' }));

    expect(await screen.findByLabelText('priors lookback days')).toHaveValue(45);
  });

  it('keeps unsaved edits and warns when the active version moves on while an editor stays open', async () => {
    render(<WorkflowView callerKey="praveen" />);
    await userEvent.click(await screen.findByRole('button', { name: 'New draft' }));
    await userEvent.type(screen.getByLabelText('Change note'), 'still drafting');

    // v5 (not drafted by praveen) is approved, moving the active version to 5
    // while the note above is still sitting in an editor based on v3.
    api.fetchWorkflow.mockResolvedValueOnce(overview({ active: { ...fixture.active, number: 5 } }));
    api.approveVersion.mockResolvedValue({ number: 5, status: 'active' });
    await userEvent.click(await screen.findByRole('button', { name: 'Approve' }));
    const dialog = screen.getByRole('dialog');
    for (const box of within(dialog).getAllByRole('checkbox')) await userEvent.click(box);
    await userEvent.click(within(dialog).getByRole('button', { name: 'Approve and activate' }));
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull());

    expect(screen.getByLabelText('Change note')).toHaveValue('still drafting');
    expect(await screen.findByText(/went live while you were editing/)).toBeInTheDocument();
  });
});
