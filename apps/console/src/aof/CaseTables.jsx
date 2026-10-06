import { useState } from 'react';

import { Empty, Panel, formatValue } from './ui';

/** The case items, columns from the manifest; out-of-scope rows on request. */
export function ItemsTable({ label, columns, items }) {
  const [showAll, setShowAll] = useState(false);
  const shown = showAll ? items : items.filter((i) => i.in_scope);
  return (
    <Panel
      title={`${label}s (${shown.length} of ${items.length})`}
      aside={
        <label className="flex items-center gap-1 text-xs text-gray-600">
          <input type="checkbox" checked={showAll} onChange={(e) => setShowAll(e.target.checked)} />
          Show out of scope
        </label>
      }
    >
      {shown.length === 0 ? (
        <Empty>No {label.toLowerCase()}s in scope.</Empty>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="text-gray-500">
              <tr>
                {columns.map((col) => (
                  <th key={col} scope="col" className="px-2 py-1 font-medium">
                    {col.replaceAll('_', ' ')}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {shown.map((it) => (
                <tr key={it.item_id} className={it.in_scope ? '' : 'text-gray-400'}>
                  {columns.map((col) => (
                    <td key={col} className="px-2 py-1 tabular-nums">
                      {formatValue(it[col])}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Panel>
  );
}

/** Every connector call the run made: the grounding record. */
export function Evidence({ calls }) {
  return (
    <Panel title={`Evidence — connector calls (${calls.length})`}>
      {calls.length === 0 ? (
        <Empty>No connector calls.</Empty>
      ) : (
        <ul className="space-y-1 text-xs">
          {calls.map((c) => (
            <li key={c.call_id} className="flex flex-wrap gap-x-3">
              <span className="font-mono">{c.tool}</span>
              <span className="text-gray-500">by {c.requested_by}</span>
              <span className="text-gray-500">{JSON.stringify(c.arguments)}</span>
              {c.allowed ? (
                <span>
                  {c.error ? `error: ${c.error}` : `${c.row_count ?? '—'} rows`} · {c.latency_ms} ms
                </span>
              ) : (
                <span className="text-rose-700">refused: {c.denied_reason}</span>
              )}
            </li>
          ))}
        </ul>
      )}
    </Panel>
  );
}
