import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import board from './__fixtures__/board.json';
import * as api from './data/helixApi';
import workflowFixture from './workflow/__fixtures__/workflow.json';
import HelixApp from './HelixApp';

// The fixture is a trimmed copy of a real /api/helix/board response.
vi.mock('./data/helixApi', () => ({
  fetchBoard: vi.fn(),
  fetchRec: vi.fn(),
  fetchTrace: vi.fn(),
  askSession: vi.fn(),
  decide: vi.fn(),
}));

vi.mock('./data/workflowApi', () => ({
  fetchWorkflow: vi.fn(async () => structuredClone(workflowFixture)),
  fetchVersions: vi.fn(async () => []),
  fetchVersion: vi.fn(async () => ({ ...workflowFixture.active, active_number: 3, diff: [] })),
  fetchRebased: vi.fn(),
  validateWorkflow: vi.fn(),
  saveDraft: vi.fn(),
  uploadYaml: vi.fn(),
  approveVersion: vi.fn(),
  rejectVersion: vi.fn(),
  downloadYaml: vi.fn(),
}));

const served = () => structuredClone(board);

async function renderLoaded(data = served()) {
  api.fetchBoard.mockResolvedValue(data);
  render(<HelixApp />);
  await screen.findByText('FOBO Controller');
  // R-1055 is mid-pipeline at "signoff", so the page settles in two steps,
  // each of which remounts elements a test would click or type into:
  // 1. RecDetail's mount effect retargets focus from the default "session"
  //    pane to "adjustments"; the session pane's wrapper is keyed on the
  //    focus target, so the composer remounts.
  // 2. One animation frame later AdjustmentsPanel flashes the first group
  //    with pending rows; that group is keyed on the flash, so its rows —
  //    and their Approve buttons — remount.
  // A click or keystroke before both land hits an element React is about
  // to discard, so every test starts from the settled page.
  await screen.findByRole('tab', { name: /Drafted adjustments/, selected: true });
  await waitFor(() => expect(document.querySelector('.hx-flash')).not.toBeNull());
  return data;
}

beforeEach(() => {
  vi.clearAllMocks();
  // jsdom has no scrolling; the panels scroll a row into view on focus.
  Element.prototype.scrollTo = vi.fn();
});

describe('HelixApp', () => {
  it('renders what the API served: caller, business date and adjustments', async () => {
    await renderLoaded();
    expect(screen.getByText('Praveen')).toBeInTheDocument();
    expect(screen.getByText('03 Aug 2026')).toBeInTheDocument();
    expect(screen.getAllByText('PRIME-MB-02').length).toBeGreaterThan(0);
    expect(screen.getAllByText('PRIME-MB-08').length).toBeGreaterThan(0);
  });

  it('offers a retry when the API cannot be reached', async () => {
    api.fetchBoard
      .mockRejectedValueOnce(new Error('GET /api/helix/board failed: 500'))
      .mockResolvedValueOnce(served());
    render(<HelixApp />);
    expect(await screen.findByText(/failed: 500/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Retry' }));
    expect(await screen.findByText('FOBO Controller')).toBeInTheDocument();
  });

  it('records an approval only after both confirmations, then shows the rec the API returns', async () => {
    const data = served();
    const after = structuredClone(data.recs[0]);
    after.adjustments[0].status = 'Approved';
    after.session = [
      ...after.session,
      {
        id: 'm1',
        role: 'system',
        tone: 'approved',
        time: '08:00',
        text: 'Praveen approved 1 adjustment (B-2), USD 1,880. Released to FAS for MOTIF posting.',
      },
    ];
    api.decide.mockResolvedValue({ rec: after, activity: data.activity });
    await renderLoaded(data);

    await userEvent.click(screen.getAllByRole('button', { name: 'Approve' })[0]);
    const dialog = screen.getByRole('dialog');
    const confirm = within(dialog).getAllByRole('button').at(-1);
    expect(confirm).toBeDisabled();
    for (const box of within(dialog).getAllByRole('checkbox')) {
      await userEvent.click(box);
    }
    expect(confirm).toBeEnabled();
    await userEvent.click(confirm);

    expect(api.decide).toHaveBeenCalledWith('R-1055', {
      ids: ['B-2'],
      decision: 'Approved',
      reason: '',
    });
    expect(await screen.findByText(/Released to FAS for MOTIF posting/)).toBeInTheDocument();
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('says so in the session when the API refuses a decision', async () => {
    api.decide.mockRejectedValue(new Error('no longer pending: B-2'));
    await renderLoaded();
    await userEvent.click(screen.getAllByRole('button', { name: 'Approve' })[0]);
    const dialog = screen.getByRole('dialog');
    for (const box of within(dialog).getAllByRole('checkbox')) {
      await userEvent.click(box);
    }
    await userEvent.click(within(dialog).getAllByRole('button').at(-1));
    expect(
      await screen.findByText(/was not recorded: no longer pending: B-2/),
    ).toBeInTheDocument();
  });

  it('asks the orchestrator, not the browser, and shows its answer', async () => {
    api.askSession.mockResolvedValue({
      user: { id: 'u9', role: 'user', time: '08:01', text: 'Explain B-8' },
      agent: {
        id: 'a9',
        role: 'agent',
        time: '08:01',
        answeredBy: 'router:adjustment',
        blocks: [{ type: 'p', text: 'Reference does not resolve in static data.' }],
        calls: [],
      },
    });
    await renderLoaded();
    const box = screen.getByPlaceholderText(/Ask about Prime/);
    await userEvent.type(box, 'Explain B-8{Enter}');
    expect(api.askSession).toHaveBeenCalledWith('R-1055', 'Explain B-8');
    expect(
      await screen.findByText('Reference does not resolve in static data.'),
    ).toBeInTheDocument();
  });

  it('opens the Workflow tab', async () => {
    await renderLoaded();
    await userEvent.click(screen.getByRole('button', { name: 'Workflow' }));
    expect(await screen.findByText('Workflow v3')).toBeInTheDocument();
  });

  it('offers the dev caller switch only when the API lists dev callers', async () => {
    const data = served();
    data.devCallers = [
      { id: 'praveen', roles: ['FO', 'PC'] },
      { id: 'asha', roles: ['PC'] },
    ];
    await renderLoaded(data);
    api.fetchBoard.mockClear();
    await userEvent.selectOptions(screen.getByLabelText('Act as'), 'asha');
    expect(window.localStorage.getItem('fobo.devCaller')).toBe('asha');
    expect(api.fetchBoard).toHaveBeenCalled();
    window.localStorage.removeItem('fobo.devCaller');
  });

  it('shows no dev caller switch without dev callers', async () => {
    await renderLoaded();
    expect(screen.queryByLabelText('Act as')).toBeNull();
  });
});
