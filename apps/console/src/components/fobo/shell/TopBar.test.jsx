import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import TopBar from './TopBar';

const STATS = {
  business_date: '2026-08-03',
  timezone: 'IST',
  next_run: '19:00',
};

describe('TopBar', () => {
  it('shows the product name and the horizontal-service subtitle', () => {
    render(<TopBar stats={STATS} activeTab="pipeline" onTabChange={() => {}} />);
    expect(screen.getByText('FOBO Control Tower')).toBeInTheDocument();
    expect(
      screen.getByText(/horizontal FOBO service across 280 P&Ls/),
    ).toBeInTheDocument();
  });

  it('formats the business date the way the mock does', () => {
    render(<TopBar stats={STATS} activeTab="pipeline" onTabChange={() => {}} />);
    expect(screen.getByText(/03 Aug 2026/)).toBeInTheDocument();
  });

  it('reads the next run from stats rather than hardcoding it', () => {
    render(
      <TopBar
        stats={{ ...STATS, next_run: '21:00' }}
        activeTab="pipeline"
        onTabChange={() => {}}
      />,
    );
    expect(screen.getByText('21:00 IST')).toBeInTheDocument();
  });

  it('marks the active tab with aria-current', () => {
    render(<TopBar stats={STATS} activeTab="analytics" onTabChange={() => {}} />);
    expect(screen.getByRole('button', { name: /Agent Analytics/ })).toHaveAttribute(
      'aria-current',
      'page',
    );
  });

  it('does not mark the inactive tab', () => {
    render(<TopBar stats={STATS} activeTab="analytics" onTabChange={() => {}} />);
    expect(screen.getByRole('button', { name: /Pipeline/ })).not.toHaveAttribute(
      'aria-current',
    );
  });

  it('calls onTabChange when a tab is clicked', async () => {
    const onTabChange = vi.fn();
    render(<TopBar stats={STATS} activeTab="pipeline" onTabChange={onTabChange} />);
    await userEvent.click(screen.getByRole('button', { name: /Agent Analytics/ }));
    expect(onTabChange).toHaveBeenCalledWith('analytics');
  });
});
