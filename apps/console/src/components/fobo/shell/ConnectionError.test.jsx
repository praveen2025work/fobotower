import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import ConnectionError from './ConnectionError';

describe('ConnectionError', () => {
  it('shows the underlying failure rather than a generic message', () => {
    render(<ConnectionError message="Failed to fetch" onRetry={() => {}} />);
    expect(screen.getByText(/Failed to fetch/)).toBeInTheDocument();
  });

  it('names the port the console expects, so the cause is actionable', () => {
    render(<ConnectionError message="Failed to fetch" onRetry={() => {}} />);
    expect(screen.getByText(/:8100/)).toBeInTheDocument();
  });

  it('offers a retry, so a transient blip does not brick the page', async () => {
    const onRetry = vi.fn();
    render(<ConnectionError message="Failed to fetch" onRetry={onRetry} />);
    await userEvent.click(screen.getByRole('button', { name: /Retry/ }));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  it('can be retried more than once', async () => {
    const onRetry = vi.fn();
    render(<ConnectionError message="nope" onRetry={onRetry} />);
    const button = screen.getByRole('button', { name: /Retry/ });
    await userEvent.click(button);
    await userEvent.click(button);
    expect(onRetry).toHaveBeenCalledTimes(2);
  });
});
