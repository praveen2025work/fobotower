import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { expect, it, vi } from 'vitest';
import { VersionList } from './VersionList';

const versions = [
  { number: 4, status: 'draft', note: 'drop rank', drafted_by: 'praveen' },
  { number: 3, status: 'active', note: 'Lookback 180→90 days', drafted_by: 'praveen' },
  { number: 2, status: 'rejected', note: 'too aggressive', drafted_by: 'asha' },
];

it('lists every version with its status, and selects one', async () => {
  const onSelect = vi.fn();
  render(<VersionList versions={versions} selected={3} onSelect={onSelect} />);
  expect(screen.getAllByRole('button').map((b) => b.textContent)).toEqual([
    expect.stringContaining('v4draft'),
    expect.stringContaining('v3active'),
    expect.stringContaining('v2rejected'),
  ]);
  expect(screen.getByRole('button', { current: true })).toHaveTextContent('v3');
  await userEvent.click(screen.getByRole('button', { name: /^v4/ }));
  expect(onSelect).toHaveBeenCalledWith(4);
});
