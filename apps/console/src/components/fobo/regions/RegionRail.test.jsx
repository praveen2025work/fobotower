import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import RegionRail from './RegionRail';

const REGIONS = [
  {
    region: 'APAC',
    recs: [
      {
        rec_id: 'R-1050',
        name: 'CATS vs MOTIF — Rates',
        scheduled: '11:00',
        status: 'cleared',
        books_open: 22,
        books_total: 22,
        adj_pending: 0,
      },
      {
        rec_id: 'R-1055',
        name: 'Rec Factory — Cash Recon',
        scheduled: '11:00',
        status: 'awaiting',
        books_open: 9,
        books_total: 11,
        adj_pending: 14,
      },
    ],
  },
  {
    region: 'EMEA',
    recs: [
      {
        rec_id: 'R-2015',
        name: 'Rec Factory — Collateral',
        scheduled: '15:00',
        status: 'blocked',
        books_open: 1,
        books_total: 7,
        adj_pending: 0,
      },
    ],
  },
];

const noop = () => {};

describe('RegionRail', () => {
  it('groups recs under their region', () => {
    render(<RegionRail regions={REGIONS} selectedRecId={null} onSelectRec={noop} />);
    expect(screen.getByText('APAC')).toBeInTheDocument();
    expect(screen.getByText('EMEA')).toBeInTheDocument();
  });

  it('shows the schedule and open/total book count per rec', () => {
    render(<RegionRail regions={REGIONS} selectedRecId={null} onSelectRec={noop} />);
    expect(screen.getByText('11:00 IST · 9/11 open')).toBeInTheDocument();
  });

  it('badges a rec that has pending adjustments', () => {
    render(<RegionRail regions={REGIONS} selectedRecId={null} onSelectRec={noop} />);
    expect(screen.getByLabelText('14 adjustments pending')).toBeInTheDocument();
  });

  it('does not badge a rec with none pending', () => {
    render(<RegionRail regions={REGIONS} selectedRecId={null} onSelectRec={noop} />);
    expect(screen.queryByLabelText('0 adjustments pending')).not.toBeInTheDocument();
  });

  it('marks the selected rec', () => {
    render(
      <RegionRail regions={REGIONS} selectedRecId="R-1055" onSelectRec={noop} />,
    );
    expect(
      screen.getByRole('button', { name: /Rec Factory — Cash Recon/ }),
    ).toHaveAttribute('aria-pressed', 'true');
  });

  it('calls onSelectRec with the rec id', async () => {
    const onSelectRec = vi.fn();
    render(
      <RegionRail regions={REGIONS} selectedRecId={null} onSelectRec={onSelectRec} />,
    );
    await userEvent.click(screen.getByRole('button', { name: /Collateral/ }));
    expect(onSelectRec).toHaveBeenCalledWith('R-2015');
  });

  it('filters recs by the search box', async () => {
    render(<RegionRail regions={REGIONS} selectedRecId={null} onSelectRec={noop} />);
    await userEvent.type(screen.getByPlaceholderText('Search recs…'), 'Collateral');
    expect(screen.queryByText('CATS vs MOTIF — Rates')).not.toBeInTheDocument();
    expect(screen.getByText('Rec Factory — Collateral')).toBeInTheDocument();
  });

  it('hides a region whose recs all filter out', async () => {
    render(<RegionRail regions={REGIONS} selectedRecId={null} onSelectRec={noop} />);
    await userEvent.type(screen.getByPlaceholderText('Search recs…'), 'Collateral');
    expect(screen.queryByText('APAC')).not.toBeInTheDocument();
  });

  it('says so when nothing matches instead of rendering an empty rail', async () => {
    render(<RegionRail regions={REGIONS} selectedRecId={null} onSelectRec={noop} />);
    await userEvent.type(screen.getByPlaceholderText('Search recs…'), 'zzzz');
    expect(screen.getByText('No recs match.')).toBeInTheDocument();
  });
});
