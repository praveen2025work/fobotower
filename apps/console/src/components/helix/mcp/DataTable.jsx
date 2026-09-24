import { mono } from '../lib/format';

export function DataTable({ columns, rows, max }) {
  const shown = max ? rows.slice(0, max) : rows;
  if (!rows.length)
    return (
      <div
        className="text-[11px] py-3 text-center"
        style={{
          color: 'var(--text-muted)',
        }}
      >
        No rows returned.
      </div>
    );
  return (
    <div
      className="overflow-x-auto rounded-lg"
      style={{
        border: '1px solid var(--border)',
      }}
    >
      <table className="w-full border-collapse text-[11px]">
        <thead>
          <tr
            style={{
              background: 'var(--bg-muted)',
            }}
          >
            {columns.map((c) => (
              <th
                key={c.key}
                className={`px-2 py-1.5 font-semibold whitespace-nowrap ${c.align === 'right' ? 'text-right' : 'text-left'}`}
                style={{
                  color: 'var(--text-muted)',
                  borderBottom: '1px solid var(--border)',
                }}
              >
                {c.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {shown.map((r, i) => (
            <tr
              key={i}
              style={{
                borderBottom:
                  i < shown.length - 1
                    ? '1px solid var(--border-subtle)'
                    : 'none',
              }}
            >
              {columns.map((c) => {
                const v = r[c.key];
                const bad =
                  v === 'Fail' ||
                  v === 'Not traced' ||
                  v === 'Missing' ||
                  v === 'No entry' ||
                  v === 'No';
                const good = v === 'Pass' || v === 'Traced';
                return (
                  <td
                    key={c.key}
                    className={`px-2 py-1.5 whitespace-nowrap tabular-nums ${c.align === 'right' ? 'text-right' : ''}`}
                    style={{
                      ...(c.mono ? mono : {}),
                      color: bad
                        ? 'var(--clr-red)'
                        : good
                          ? 'var(--clr-green)'
                          : 'var(--text-primary)',
                    }}
                  >
                    {v === undefined || v === null ? '—' : String(v)}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
      {max && rows.length > max && (
        <div
          className="text-[10px] px-2 py-1"
          style={{
            color: 'var(--text-muted)',
            background: 'var(--bg-muted)',
          }}
        >
          {rows.length - max}
          {' more rows in the inspector'}
        </div>
      )}
    </div>
  );
}
