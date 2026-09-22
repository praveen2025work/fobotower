import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import StatChipRow from './StatChipRow';

const STATS = {
  recs: 7,
  cleared: 2,
  awaiting: 1,
  blocked: 1,
  adj_pending: 14,
  auto_posted: 32,
  books_open: 56,
  books_not_open: 72,
  unlocked: 53,
  unlocked_total: 160,
};

describe('StatChipRow', () => {
  it('renders every chip from the mock', () => {
    render(<StatChipRow stats={STATS} />);
    for (const label of [
      'recs',
      'cleared',
      'awaiting',
      'blocked',
      'adj. pending',
      'auto-posted',
      'books open',
      'not open',
      'unlocked',
    ]) {
      expect(screen.getByText(label)).toBeInTheDocument();
    }
  });

  it('shows unlocked as a fraction', () => {
    render(<StatChipRow stats={STATS} />);
    expect(screen.getByText('53/160')).toBeInTheDocument();
  });

  it('reads values from props rather than hardcoding', () => {
    render(<StatChipRow stats={{ ...STATS, adj_pending: 99 }} />);
    expect(screen.getByText('99')).toBeInTheDocument();
    expect(screen.queryByText('14')).not.toBeInTheDocument();
  });
});
