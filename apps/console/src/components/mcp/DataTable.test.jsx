import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { DataTable } from './DataTable';

const COLUMNS = [
  { key: 'tool', label: 'Tool' },
  { key: 'arguments', label: 'Arguments' },
];

describe('DataTable', () => {
  it('shows an object cell as JSON, not [object Object]', () => {
    render(
      <DataTable
        columns={COLUMNS}
        rows={[{ tool: 'fobo_break_detail', arguments: { break_id: 'COLL-7781' } }]}
      />,
    );
    expect(screen.getByText('{"break_id":"COLL-7781"}')).toBeInTheDocument();
    expect(screen.queryByText('[object Object]')).not.toBeInTheDocument();
  });

  it('shows a missing value as a dash', () => {
    render(<DataTable columns={COLUMNS} rows={[{ tool: 'x', arguments: null }]} />);
    expect(screen.getByText('—')).toBeInTheDocument();
  });
});
