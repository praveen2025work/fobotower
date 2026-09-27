import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import graphFixture from './__fixtures__/graph.json';
import fixture from './__fixtures__/workflow.json';
import { ActiveWorkflowGraph } from './ActiveWorkflowGraph';

// A controllable stand-in for the real ResizeObserver: reports whatever
// width the test sets, synchronously, the moment the component observes
// its container — so no `waitFor` is needed to see the effect. React Flow
// (rendered in the "wide" case) runs its own ResizeObserver internally, on
// its node elements (each has a `data-id`); this fake only answers for our
// own container (a plain div with none), leaving React Flow's own
// measurement inert, same as every other test in this suite.
let mockWidth = 1024;
class FakeResizeObserver {
  constructor(callback) {
    this.callback = callback;
  }
  observe(element) {
    if (element && !element.hasAttribute('data-id')) {
      this.callback([{ target: element, contentRect: { width: mockWidth } }]);
    }
  }
  unobserve() {}
  disconnect() {}
}

// The wide case renders a real FlowGraph (React Flow); jsdom reports every
// element as 0×0, which React Flow needs a plausible size from. Scoped to
// this file, not a global vitest.setup.js stub.
let rectSpy;
beforeEach(() => {
  vi.stubGlobal('ResizeObserver', FakeResizeObserver);
  rectSpy = vi.spyOn(Element.prototype, 'getBoundingClientRect').mockReturnValue({
    x: 0,
    y: 0,
    top: 0,
    left: 0,
    right: 1024,
    bottom: 640,
    width: 1024,
    height: 640,
    toJSON() {},
  });
});
afterEach(() => {
  vi.unstubAllGlobals();
  rectSpy.mockRestore();
});

const renderAt = (width, extra = {}) => {
  mockWidth = width;
  const onSelect = vi.fn();
  render(
    <ActiveWorkflowGraph
      config={fixture.active.config}
      catalogue={fixture.steps}
      reasoner="none"
      graphState={{ state: 'ready', graph: graphFixture }}
      onRetryGraph={vi.fn()}
      onSelect={onSelect}
      {...extra}
    />,
  );
  return { onSelect };
};

describe('ActiveWorkflowGraph', () => {
  it('renders the React Flow diagram when the container is wide (lazy-loaded — shows a loading line first, then the diagram)', async () => {
    renderAt(900);
    // FlowGraph is loaded via next/dynamic (kept out of the initial bundle
    // for containers/visits that never need it), so it isn't there yet on
    // the very first render.
    expect(screen.getByText('Loading the diagram…')).toBeInTheDocument();
    expect(await screen.findByRole('button', { name: 'Open Apply playbook' })).toBeInTheDocument();
    expect(screen.queryByText(/Open on a wider screen/)).toBeNull();
  });

  it('renders the stacked card view with a note when the container is narrow', () => {
    renderAt(375);
    expect(screen.getByText('Open on a wider screen to see the diagram.')).toBeInTheDocument();
    expect(screen.getAllByTestId('step-card').map((c) => c.dataset.step)).toEqual(
      fixture.active.config.steps,
    );
  });

  it('exactly at the breakpoint counts as wide (the diagram, not the cards)', async () => {
    renderAt(640);
    expect(await screen.findByRole('button', { name: 'Open Apply playbook' })).toBeInTheDocument();
  });

  it('still opens the step panel by id when a card is tapped in the narrow view', async () => {
    const { onSelect } = renderAt(375);
    await userEvent.click(screen.getByRole('button', { name: 'Open Apply playbook' }));
    expect(onSelect).toHaveBeenCalledWith('reason');
  });

  it('shows a loading line for the diagram while the graph is still loading (wide only)', () => {
    renderAt(900, { graphState: { state: 'loading' } });
    expect(screen.getByText('Loading the diagram…')).toBeInTheDocument();
  });

  it('shows an error with retry for the diagram when the graph failed to load (wide)', async () => {
    const onRetryGraph = vi.fn();
    renderAt(900, { graphState: { state: 'error', error: 'boom' }, onRetryGraph });
    expect(screen.getByText('boom')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Retry' }));
    expect(onRetryGraph).toHaveBeenCalled();
  });

  it('shows an error with retry for the diagram when the graph failed to load (narrow too — the "How it decides" panels would be missing data)', async () => {
    const onRetryGraph = vi.fn();
    renderAt(375, { graphState: { state: 'error', error: 'boom' }, onRetryGraph });
    // The stacked card view still works without graph data...
    expect(screen.getAllByTestId('step-card').length).toBeGreaterThan(0);
    // ...but the failure to load it isn't silently dropped.
    expect(screen.getByText('boom')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Retry' }));
    expect(onRetryGraph).toHaveBeenCalled();
  });
});
