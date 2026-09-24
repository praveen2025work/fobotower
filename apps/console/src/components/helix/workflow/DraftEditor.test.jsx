import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '@/lib/apiClient';
import * as api from '../data/workflowApi';
import fixture from './__fixtures__/workflow.json';
import { DraftEditor } from './DraftEditor';

vi.mock('../data/workflowApi', () => ({
  validateWorkflow: vi.fn(),
  saveDraft: vi.fn(),
}));

const renderEditor = (initial = {}) => {
  const props = { onSaved: vi.fn(), onCancel: vi.fn() };
  render(
    <DraftEditor
      initial={{ config: fixture.active.config, basedOn: 3, conflicts: [], ...initial }}
      catalogue={fixture.steps}
      schema={fixture.settings_schema}
      overrides={{}}
      debounceMs={0}
      {...props}
    />,
  );
  return props;
};

const lastValidated = () => api.validateWorkflow.mock.lastCall[0];
const saveButton = () => screen.getByRole('button', { name: 'Save draft' });

beforeEach(() => {
  vi.clearAllMocks();
  api.validateWorkflow.mockResolvedValue({ ok: true, errors: [] });
});

describe('DraftEditor', () => {
  it('validates the starting config and waits for a note before saving', async () => {
    renderEditor();
    await screen.findByText(/^Valid/);
    expect(saveButton()).toBeDisabled();
  });

  it('checks every edit with the server', async () => {
    renderEditor();
    await userEvent.click(screen.getByRole('button', { name: 'Remove rank' }));
    await waitFor(() => expect(lastValidated().steps).not.toContain('rank'));
  });

  it('sends a changed setting as a number', async () => {
    renderEditor();
    const input = screen.getByLabelText('priors lookback days');
    await userEvent.clear(input);
    await userEvent.type(input, '90');
    await waitFor(() => expect(lastValidated().settings.gather.priors_lookback_days).toBe(90));
  });

  it('lists the server’s problems, marks the step, and blocks saving', async () => {
    api.validateWorkflow.mockResolvedValue({
      ok: false,
      errors: ["steps: 'draft' needs 'pattern_groups' before it runs — produced by group"],
    });
    renderEditor();
    await userEvent.type(screen.getByLabelText('Change note'), 'why');
    const card = await waitFor(() =>
      screen.getAllByTestId('step-card').find((c) => c.dataset.step === 'draft'),
    );
    await waitFor(() => expect(within(card).getByRole('alert')).toBeInTheDocument());
    expect(saveButton()).toBeDisabled();
  });

  it('saves a valid draft with its note and base version', async () => {
    const version = { number: 4, status: 'draft' };
    api.saveDraft.mockResolvedValue(version);
    const { onSaved } = renderEditor();
    await screen.findByText(/^Valid/);
    await userEvent.type(screen.getByLabelText('Change note'), 'Lookback 180→90 days');
    await userEvent.click(saveButton());
    expect(api.saveDraft).toHaveBeenCalledWith({
      config: fixture.active.config,
      note: 'Lookback 180→90 days',
      basedOn: 3,
    });
    expect(onSaved).toHaveBeenCalledWith(version);
  });

  it('shows what the server refused when saving fails', async () => {
    api.saveDraft.mockRejectedValue(
      new ApiError('workflow is invalid', { status: 422, errors: ['first', 'second'] }),
    );
    renderEditor();
    await screen.findByText(/^Valid/);
    await userEvent.type(screen.getByLabelText('Change note'), 'why');
    await userEvent.click(saveButton());
    expect(await screen.findByText('second')).toBeInTheDocument();
  });

  it('never enables saving while the check cannot reach the server', async () => {
    api.validateWorkflow.mockRejectedValue(new Error('offline'));
    renderEditor();
    await userEvent.type(screen.getByLabelText('Change note'), 'why');
    expect(await screen.findByText(/Couldn't check/)).toBeInTheDocument();
    expect(saveButton()).toBeDisabled();
  });

  it('lists conflicts carried over from a redraft', () => {
    renderEditor({ conflicts: ['settings.gather.priors_lookback_days'] });
    expect(screen.getByText(/settings.gather.priors_lookback_days/)).toBeInTheDocument();
  });

  it('can put a removed step back', async () => {
    renderEditor();
    await userEvent.click(screen.getByRole('button', { name: 'Remove rank' }));
    await userEvent.click(screen.getByRole('button', { name: 'Add rank' }));
    await waitFor(() => expect(lastValidated().steps).toEqual(fixture.active.config.steps));
  });
});
